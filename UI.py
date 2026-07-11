import sys
import time
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QGroupBox, QFormLayout, QLabel, QLineEdit, QPushButton, 
                             QComboBox, QCheckBox, QDoubleSpinBox, QTabWidget, QGridLayout, 
                             QFrame, QPlainTextEdit, QSizePolicy)
from PyQt6.QtCore import Qt

# ==========================================
# 0. 预定义样式 (保持性能)
# ==========================================
STYLE_COORD = "font-weight: bold; font-size: 14px; color: #007BFF;"
STYLE_BTN_DIR = "font-size: 18px; font-family: Arial; padding: 0px;"
STYLE_IMG_BG = "background-color: #202020; border: 1px solid #555;"
STYLE_TEXT_GRAY = "color: #666; font-size: 20px;"
STYLE_VAL_RED = "color: red; font-weight: bold; background: #f0f0f0;"
STYLE_VAL_BLUE = "color: blue; font-weight: bold; background: #f0f0f0;"

# ==========================================
# 1. 增强版位移台控制
# ==========================================
class StageControlWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(8)

        # --- A. 实时坐标 ---
        pos_layout = QHBoxLayout()
        self.lbl_x = QLabel("X: 0.000 mm"); self.lbl_x.setStyleSheet(STYLE_COORD)
        self.lbl_y = QLabel("Y: 0.000 mm"); self.lbl_y.setStyleSheet(STYLE_COORD)
        self.btn_zero = QPushButton("归零"); self.btn_zero.setFixedSize(50, 25)
        
        pos_layout.addWidget(self.lbl_x); pos_layout.addSpacing(20)
        pos_layout.addWidget(self.lbl_y); pos_layout.addStretch()
        pos_layout.addWidget(self.btn_zero)
        layout.addLayout(pos_layout)

        # --- B. 运动控制 ---
        move_container = QHBoxLayout()
        
        # 摇杆
        joystick_frame = QFrame()
        j_layout = QGridLayout(joystick_frame); j_layout.setContentsMargins(0,0,0,0)
        self.btn_up = self.mk_btn("^"); self.btn_down = self.mk_btn("v")
        self.btn_left = self.mk_btn("<"); self.btn_right = self.mk_btn(">")
        j_layout.addWidget(self.btn_up, 0, 1); j_layout.addWidget(self.btn_left, 1, 0)
        j_layout.addWidget(self.btn_right, 1, 2); j_layout.addWidget(self.btn_down, 2, 1)
        move_container.addWidget(joystick_frame); move_container.addSpacing(15)

        # 参数
        p_layout = QFormLayout()
        self.step_spin = QDoubleSpinBox()
        self.step_spin.setRange(0.001, 100.0); self.step_spin.setValue(0.1)
        self.step_spin.setSingleStep(0.01); self.step_spin.setSuffix(" mm")
        self.step_spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.step_spin.setKeyboardTracking(False) # 防误触
        p_layout.addRow("点动步长:", self.step_spin)

        self.target_x = QLineEdit(); self.target_x.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.target_y = QLineEdit(); self.target_y.setAlignment(Qt.AlignmentFlag.AlignRight)
        p_layout.addRow("X:", self.target_x); p_layout.addRow("Y:", self.target_y)
        self.btn_go = QPushButton("移动到目标位置"); p_layout.addRow(self.btn_go)
        
        move_container.addLayout(p_layout); layout.addLayout(move_container)

        # --- C. 配置 ---
        c_layout = QHBoxLayout()
        self.check_swap = QCheckBox("交换XY")
        self.check_inv_x = QCheckBox("X反转"); self.check_inv_y = QCheckBox("Y反转")
        c_layout.addWidget(QLabel("配置:")); c_layout.addWidget(self.check_swap)
        c_layout.addWidget(self.check_inv_x); c_layout.addWidget(self.check_inv_y)
        c_layout.addStretch(); layout.addLayout(c_layout)

    def mk_btn(self, text):
        b = QPushButton(text); b.setFixedSize(40, 40); b.setStyleSheet(STYLE_BTN_DIR)
        return b

# ==========================================
# 2. 主界面 (ModernUI) - 完整修复版 (取消懒加载)
# ==========================================
class ModernUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("采集控制系统")
        self.resize(1280, 950)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        central = QWidget(); self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(5, 5, 5, 5); main_layout.setSpacing(5)

        # 左侧图像区
        self.image_area = QFrame(); self.image_area.setStyleSheet(STYLE_IMG_BG)
        self.image_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # 这里仅放一个占位，逻辑代码会替换它
        lbl_img = QLabel("Initializing Camera...", self.image_area)
        lbl_img.setStyleSheet(STYLE_TEXT_GRAY); lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_layout = QVBoxLayout(self.image_area)
        img_layout.addWidget(lbl_img)
        
        # 右侧面板
        self.right_panel = QWidget(); self.right_panel.setFixedWidth(400)
        r_layout = QVBoxLayout(self.right_panel)
        r_layout.setContentsMargins(5, 0, 5, 0); r_layout.setSpacing(8)

        # Tabs - 立即初始化所有 Tab，保证 main.py 能找到 self.btn_show_path 等变量
        self.tabs = QTabWidget()
        self.setup_hardware_tab() 
        self.setup_scan_tab() 
        self.tabs.addTab(self.tab_hardware, "硬件控制")
        self.tabs.addTab(self.tab_scan, "自动扫描")
        r_layout.addWidget(self.tabs); r_layout.addStretch() 

        # 底部面板 (光子数 / 按钮 / 日志)
        r_layout.addWidget(self.create_photon_panel())
        r_layout.addWidget(self.create_big_btns())
        r_layout.addWidget(self.create_log_panel())

        main_layout.addWidget(self.image_area); main_layout.addWidget(self.right_panel)  

    def setup_hardware_tab(self):
        self.tab_hardware = QWidget()
        layout = QVBoxLayout(self.tab_hardware)
        layout.setSpacing(10); layout.setContentsMargins(10, 10, 10, 10)

        # 1. 连接
        g_dev = QGroupBox("1. 设备连接"); l_dev = QGridLayout()
        l_dev.setContentsMargins(5, 10, 5, 10)
        l_dev.addWidget(QLabel("相机:"), 0, 0)
        self.combo_camera = self.mk_combo(["Hik", "IDS", "Galaxy", "QHY", "PCO"])
        l_dev.addWidget(self.combo_camera, 0, 1)
        
        # [修复] 显式赋值给 self
        self.btn_open_cam = QPushButton("打开")
        l_dev.addWidget(self.btn_open_cam, 0, 2)
        
        l_dev.addWidget(QLabel("位移台:"), 1, 0)
        self.combo_stage = self.mk_combo(["NewPort", "SmartAct", "Nators"])
        l_dev.addWidget(self.combo_stage, 1, 1)
        
        # [修复] 显式赋值给 self
        self.btn_connect_stage = QPushButton("连接")
        l_dev.addWidget(self.btn_connect_stage, 1, 2)
        g_dev.setLayout(l_dev); layout.addWidget(g_dev)

        # 2. 位移台
        g_stg = QGroupBox("2. 位移台控制"); l_stg = QVBoxLayout()
        self.stage_widget = StageControlWidget()
        l_stg.addWidget(self.stage_widget); g_stg.setLayout(l_stg)
        layout.addWidget(g_stg)

        # 3. 相机参数
        g_cam = QGroupBox("3. 相机参数"); l_cam = QGridLayout()
        l_cam.addWidget(QLabel("曝光(ms):"), 0, 0)
        self.exposure_spin = QDoubleSpinBox(); self.exposure_spin.setRange(0.001, 10000); self.exposure_spin.setValue(0.1)
        self.exposure_spin.setAlignment(Qt.AlignmentFlag.AlignRight); self.exposure_spin.setKeyboardTracking(False)
        l_cam.addWidget(self.exposure_spin, 0, 1)
        l_cam.addWidget(QLabel("波长(nm):"), 1, 0)
        self.wavelength_spin = QLineEdit("632.8"); self.wavelength_spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        l_cam.addWidget(self.wavelength_spin, 1, 1)
        l_cam.addWidget(QLabel("采样:"), 2, 0)
        self.combo_sampling = self.mk_combo(["1x1", "2x2", "4x4"])
        l_cam.addWidget(self.combo_sampling, 2, 1)
        g_cam.setLayout(l_cam); layout.addWidget(g_cam)

        # 4. ROI
        g_roi = QGroupBox("4. 采集区域与偏移"); l_roi = QGridLayout()
        h_sz = QHBoxLayout()
        self.roi_w = QLineEdit("1024"); self.roi_w.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.roi_h = QLineEdit("1024"); self.roi_h.setAlignment(Qt.AlignmentFlag.AlignRight)
        h_sz.addWidget(self.roi_w); h_sz.addWidget(QLabel("x")); h_sz.addWidget(self.roi_h)
        l_roi.addWidget(QLabel("Size W/H:"), 0, 0); l_roi.addLayout(h_sz, 0, 1)
        
        l_roi.addWidget(QLabel("Offset X/Y:"), 1, 0)
        h_off = QHBoxLayout()
        self.off_x = QLineEdit("0"); self.off_x.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.off_y = QLineEdit("0"); self.off_y.setAlignment(Qt.AlignmentFlag.AlignRight)
        h_off.addWidget(self.off_x); h_off.addWidget(self.off_y)
        l_roi.addLayout(h_off, 1, 1)

        self.btn_center = QPushButton("获取采集区域中心")
        l_roi.addWidget(self.btn_center, 2, 0, 1, 2)
        g_roi.setLayout(l_roi); layout.addWidget(g_roi)
        layout.addStretch()

    def setup_scan_tab(self):
        # [修复] 立即初始化，不使用 load_scan_tab_content 懒加载
        self.tab_scan = QWidget()
        layout = QVBoxLayout(self.tab_scan); layout.setSpacing(10)
        
        # 保存设置
        g_save = QGroupBox("保存设置"); l_save = QVBoxLayout(); l_save.setContentsMargins(10, 10, 10, 10)
        h_path = QHBoxLayout()
        self.save_dir_edit = QLineEdit("please change this to your own path"); h_path.addWidget(self.save_dir_edit)
        self.btn_browse = QPushButton("..."); self.btn_browse.setFixedWidth(40); h_path.addWidget(self.btn_browse)
        l_save.addLayout(h_path); g_save.setLayout(l_save); layout.addWidget(g_save)

        # 扫描参数
        g_scan = QGroupBox("自动扫描参数"); form = QFormLayout()
        self.combo_scan_mode = self.mk_combo(["矩形", "圆形", "螺旋"]); form.addRow("模式:", self.combo_scan_mode)
        h_rng = QHBoxLayout()
        self.scan_range_x = QLineEdit("0.2"); self.scan_range_x.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.scan_range_y = QLineEdit("0.2"); self.scan_range_y.setAlignment(Qt.AlignmentFlag.AlignRight)
        h_rng.addWidget(self.scan_range_x); h_rng.addWidget(self.scan_range_y); form.addRow("范围(mm):", h_rng)
        self.scan_step = QLineEdit("0.1"); self.scan_step.setAlignment(Qt.AlignmentFlag.AlignRight); form.addRow("步长(mm):", self.scan_step)
        
        # 显式赋值 self，给 main.py 调用
        self.scan_points = QLineEdit(); self.scan_points.setReadOnly(True); self.scan_points.setAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("预计点数:", self.scan_points)
        
        self.btn_show_path = QPushButton("显示路径"); form.addRow(self.btn_show_path)
        self.lbl_scan_preview = QLabel("Preview Area")
        self.lbl_scan_preview.setAlignment(Qt.AlignmentFlag.AlignCenter); self.lbl_scan_preview.setMinimumHeight(250)
        self.lbl_scan_preview.setStyleSheet("border: 1px dashed #aaa; background: #f9f9f9;")
        form.addRow(self.lbl_scan_preview); g_scan.setLayout(form); layout.addWidget(g_scan)
        layout.addStretch()

    def mk_combo(self, items):
        c = QComboBox(); c.addItems(items); c.setEditable(True)
        c.lineEdit().setReadOnly(True); c.lineEdit().setAlignment(Qt.AlignmentFlag.AlignCenter)
        for i in range(c.count()): c.setItemData(i, Qt.AlignmentFlag.AlignCenter, Qt.ItemDataRole.TextAlignmentRole)
        return c

    def create_photon_panel(self):
        g = QGroupBox("光子数监测"); f = QFormLayout(); f.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.line_cam_max = QLabel("-"); self.line_cam_max.setAlignment(Qt.AlignmentFlag.AlignRight)
        f.addRow("相机饱和:", self.line_cam_max)

        self.line_global_max = QLabel("0"); self.line_global_max.setStyleSheet(STYLE_VAL_RED)
        self.line_global_max.setAlignment(Qt.AlignmentFlag.AlignRight)
        f.addRow("全图Max:", self.line_global_max)

        self.line_mouse_val = QLabel("0"); self.line_mouse_val.setStyleSheet(STYLE_VAL_BLUE)
        self.line_mouse_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        f.addRow("鼠标Val:", self.line_mouse_val)
        g.setLayout(f); return g

    def create_big_btns(self):
        w = QWidget(); l = QGridLayout(w); l.setContentsMargins(0, 5, 0, 5)
        # 显式赋值
        self.btn_live = QPushButton("👁 启动"); self.btn_live.setStyleSheet("background: #27ae60; color: white; font-weight: bold; height: 45px;")
        self.btn_cap = QPushButton("🔴 采集"); self.btn_cap.setStyleSheet("background: #c0392b; color: white; font-weight: bold; height: 45px;")
        self.btn_save = QPushButton("💾 保存"); self.btn_save.setStyleSheet("background: #2980b9; color: white; font-weight: bold; height: 45px;")
        l.addWidget(self.btn_live, 0, 0); l.addWidget(self.btn_cap, 0, 1); l.addWidget(self.btn_save, 0, 2)
        
        aux = QHBoxLayout()
        self.chk_log = QCheckBox("Log")
        self.chk_mask = QCheckBox("Mask")
        aux.addWidget(self.chk_log); aux.addWidget(self.chk_mask)
        l.addLayout(aux, 1, 0, 1, 3)
        return w

    def create_log_panel(self):
        w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(0,0,0,0); l.setSpacing(0)
        l.addWidget(QLabel("系统日志:"))
        self.txt_log = QPlainTextEdit(); self.txt_log.setReadOnly(True); self.txt_log.setFixedHeight(100)
        self.txt_log.document().setMaximumBlockCount(1000)
        l.addWidget(self.txt_log); return w

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ModernUI()
    window.show()
    sys.exit(app.exec())