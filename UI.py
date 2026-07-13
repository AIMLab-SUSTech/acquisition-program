import sys
import time
import numpy as np
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QFrame, QLabel, QPushButton, QLineEdit, QComboBox,
    QRadioButton, QDialog, QScrollArea, QSpacerItem, QSizePolicy, 
    QDoubleSpinBox, QSpinBox, QGroupBox, QTabWidget, QPlainTextEdit
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QTextCursor

# 导入工业级超快渲染库 pyqtgraph
import pyqtgraph as pg

# 全局配置 pyqtgraph 使用符合行/列映射的图像坐标轴顺序
pg.setConfigOptions(imageAxisOrder='row-major')

# ==================== 工业原生样式常量定义 ====================
STYLE_IMG_BG = "background-color: #121212; border: 1px solid #3A3A3A; border-radius: 4px;"
STYLE_TEXT_GRAY = "color: #777777; font-size: 12px; font-weight: bold; font-family: 'Consolas', 'Microsoft YaHei';"


class ChartCard(QFrame):
    """工业图表容器组件：支持双击无缝弹窗放大，并全面采用动态占位替换机制"""
    def __init__(self, title, row, col, grid_layout, plot_type="line",placeholder_text="Waiting for Data..."):
        super().__init__()
        self.title = title
        self.row = row
        self.col = col
        self.grid_layout = grid_layout
        self.plot_type = plot_type
        self.is_popped_out = False
        
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Sunken)
        self.setLineWidth(2)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        
        # ================= 统一严格执行用户指定的纯黑占位格式 =================
        self.image_area = QFrame()
        self.image_area.setStyleSheet(STYLE_IMG_BG)
        self.image_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        self.lbl_img = QLabel(placeholder_text, self.image_area)
        self.lbl_img.setStyleSheet(STYLE_TEXT_GRAY)
        self.lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.img_layout = QVBoxLayout(self.image_area)
        self.img_layout.setContentsMargins(0, 0, 0, 0)
        self.img_layout.addWidget(self.lbl_img)
        
        self.main_layout.addWidget(self.image_area)
        
        # 实际的工业级渲染控件指针，初始全部置空（纯黑占位）
        self.plot_widget = None  

    def callback_update_image(self, data, colormap_name=None):
        """回调接口 1：专门用于更新图像/伪彩形貌数据流 (ImageView)"""
        if self.plot_widget is None:
            # 首次接收数据，安全销毁占位文本，装载硬件加速组件
            self.img_layout.removeWidget(self.lbl_img)
            self.lbl_img.deleteLater()
            
            self.plot_widget = pg.ImageView()
            self.plot_widget.ui.roiBtn.hide()    
            self.plot_widget.ui.menuBtn.hide()
            if colormap_name:
                self.plot_widget.setColorMap(pg.colormap.get(colormap_name))
                
            self.img_layout.addWidget(self.plot_widget)
            
        self.plot_widget.setImage(data)

    def callback_update_line(self, x, y, pen_color='#00FF00'):
        """回调接口 2：专门用于更新矢量曲线/分析图表数据 (PlotWidget)"""
        if self.plot_widget is None:
            # 首次接收数据，安全销毁占位文本，装载矢量控制组件
            self.img_layout.removeWidget(self.lbl_img)
            self.lbl_img.deleteLater()
            
            self.plot_widget = pg.PlotWidget()
            self.plot_widget.setTitle(self.title, color="w", size="10pt")
            self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
            
            self.img_layout.addWidget(self.plot_widget)
            
        self.plot_widget.plot(x, y, clear=True, pen=pg.mkPen(pen_color, width=1.5))

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self.is_popped_out:
                self.pop_out()
            else:
                self.dialog.close()

    def pop_out(self):
        self.is_popped_out = True
        self.grid_layout.removeWidget(self)
        
        self.dialog = QDialog(self.window())
        self.dialog.setWindowTitle(f"高级分析视图 - {self.title}")
        self.dialog.resize(950, 700)
        
        dialog_layout = QVBoxLayout(self.dialog)
        dialog_layout.setContentsMargins(6, 6, 6, 6)
        dialog_layout.addWidget(self)
        
        self.dialog.closeEvent = self.dialog_close_event
        self.dialog.show()

    def dialog_close_event(self, event):
        self.setParent(None)
        self.grid_layout.addWidget(self, self.row, self.col)
        self.is_popped_out = False
        event.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CMI高级光场智能采集与多维重构控制台")
        self.resize(1550, 900)
        
        self.log_terminal = None
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)
        
        # ==================== 左侧：2x2 统一占位工业绘图网格区 ====================
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        chart_grid_widget = QWidget()
        chart_grid = QGridLayout(chart_grid_widget)
        chart_grid.setContentsMargins(0, 0, 0, 0)
        chart_grid.setSpacing(8)
        
        # 4个视区全部使用各自名字的纯黑图进行状态占位
        self.card1 = ChartCard("相机实时采集画面", 0, 0, chart_grid,    
                               plot_type="image", placeholder_text="相机信号")
        
        self.card2 = ChartCard("波前重构结果", 0, 1, chart_grid,    
                               plot_type="line", placeholder_text="重构结果")
        
        self.card3 = ChartCard("3D 形貌", 1, 0, chart_grid,    
                               plot_type="profile", placeholder_text="3D 形貌")
        
        self.card4 = ChartCard("数据分析", 1, 1, chart_grid,    
                               plot_type="line", placeholder_text="数据分析结果")
        
        chart_grid.addWidget(self.card1, 0, 0)
        chart_grid.addWidget(self.card2, 0, 1)
        chart_grid.addWidget(self.card3, 1, 0)
        chart_grid.addWidget(self.card4, 1, 1)
        
        left_layout.addWidget(chart_grid_widget, stretch=1)
        main_layout.addWidget(left_panel, stretch=1)
        
        # ==================== 右侧：单栏式多标签控制面板区 ====================
        sidebar = QWidget()
        sidebar.setFixedWidth(360)  
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(8)
        
        self.tab_manager = QTabWidget()
        
        self.tab_camera = QWidget()
        self.col1_layout = QVBoxLayout(self.tab_camera)
        self.col1_layout.setContentsMargins(4, 8, 4, 4)
        self.col1_layout.setSpacing(8)
        self.build_column_1_acquisition()
        self.tab_manager.addTab(self.tab_camera, "相机采集与控制")
        
        self.tab_recon = QWidget()
        self.col2_layout = QVBoxLayout(self.tab_recon)
        self.col2_layout.setContentsMargins(4, 8, 4, 4)
        self.col2_layout.setSpacing(8)
        self.build_column_2_reconstruction()
        self.tab_manager.addTab(self.tab_recon, "重构参数配置")
        
        sidebar_layout.addWidget(self.tab_manager, stretch=0)
        
        self.build_results_section(sidebar_layout)
        self.build_log_section(sidebar_layout)
        
        main_layout.addWidget(sidebar)

    def build_column_1_acquisition(self):
        """构建 Tab 1：相机连接、控制与综合光路动态参数"""
        cam_box = QGroupBox("硬件与光路控制")
        cam_layout = QVBoxLayout(cam_box)
        
        # 1. 连接按钮行
        h_conn = QHBoxLayout()
        self.btn_conn = QPushButton("连接相机")
        h_conn.addWidget(self.btn_conn)
        cam_layout.addLayout(h_conn)

        grid_params = QGridLayout()
        grid_params.setSpacing(6)
        grid_params.setContentsMargins(2, 4, 2, 4)
        
        # 曝光时间
        grid_params.addWidget(QLabel("曝光时间 (ms):"), 0, 0, Qt.AlignmentFlag.AlignRight)
        self.exposure_spin = QDoubleSpinBox()
        self.exposure_spin.setRange(0.001, 2000.0)
        self.exposure_spin.setValue(12.5)
        self.exposure_spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        grid_params.addWidget(self.exposure_spin, 0, 1)

        # ROI 尺寸
        grid_params.addWidget(QLabel("ROI 裁剪窗口:"), 1, 0, Qt.AlignmentFlag.AlignRight)      
        h_size = QHBoxLayout()
        self.roi_w = QLineEdit("2048");self.roi_w.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.roi_h = QLineEdit("2048");self.roi_h.setAlignment(Qt.AlignmentFlag.AlignRight)
        h_size.addWidget(self.roi_w);h_size.addWidget(QLabel("x"));h_size.addWidget(self.roi_h)
        grid_params.addLayout(h_size, 1, 1)

        # 最大光子饱和阈值
        grid_params.addWidget(QLabel("最大光子饱和阈值:"), 2, 0, Qt.AlignmentFlag.AlignRight)
        self.line_global_max = QLabel("0")
        self.line_global_max.setAlignment(Qt.AlignmentFlag.AlignRight)
        grid_params.addWidget(self.line_global_max, 2, 1)    

        # 鼠标位置光子数
        grid_params.addWidget(QLabel("鼠标位置光子数:"), 3, 0, Qt.AlignmentFlag.AlignRight)
        self.line_global_mouse = QLabel("0")
        self.line_global_mouse.setAlignment(Qt.AlignmentFlag.AlignRight)
        grid_params.addWidget(self.line_global_mouse, 3, 1)    
        cam_layout.addLayout(grid_params)

        opt_layout = QHBoxLayout()
        opt_layout.addWidget(QLabel("光场形态:"))
        self.optical_mode_combo = QComboBox()
        self.optical_mode_combo.addItems(["汇聚光场", "平行光场"])
        opt_layout.addWidget(self.optical_mode_combo, stretch=1)
        cam_layout.addLayout(opt_layout)
        
        self.dynamic_widget = QWidget()
        self.dynamic_params_grid = QGridLayout(self.dynamic_widget)
        self.dynamic_params_grid.setContentsMargins(0, 0, 0, 0)
        self.dynamic_params_grid.setSpacing(6)
        cam_layout.addWidget(self.dynamic_widget)

        self.optical_mode_combo.currentIndexChanged.connect(lambda index: self.switch_dynamic_settings(index == 0))
        self.switch_dynamic_settings(True) 
        
        grid_ops = QGridLayout()
        self.chk_log = QPushButton("Log")
        self.chk_mask = QPushButton("Mask")
        grid_ops.addWidget(self.chk_log, 0, 0)
        grid_ops.addWidget(self.chk_mask, 0, 1)
        cam_layout.addLayout(grid_ops)
        
        self.btn_acquisition = QPushButton("采集")
        cam_layout.addWidget(self.btn_acquisition)
        self.col1_layout.addWidget(cam_box)
        self.col1_layout.addSpacerItem(QSpacerItem(0, 30, QSizePolicy.Minimum, QSizePolicy.Expanding))

    def build_column_2_reconstruction(self):
        """构建 Tab 2：专门负责固有重构算法解算参数与算法调度内核"""
        static_box = QGroupBox("参数")
        static_grid = QGridLayout(static_box)
        static_grid.setSpacing(6)

        static_grid.addWidget(QLabel("激光波长(nm):"), 0, 0, Qt.AlignRight)
        self.wavelength = QLineEdit("632.8");self.wavelength.setAlignment(Qt.AlignRight)
        static_grid.addWidget(self.wavelength, 0, 1)
        static_grid.addWidget(QLabel("迭代轮数:"), 1, 0, Qt.AlignRight)
        self.recon_iter_spin = QSpinBox()
        self.recon_iter_spin.setRange(1, 10000)
        self.recon_iter_spin.setValue(200)
        self.recon_iter_spin.setAlignment(Qt.AlignRight)
        static_grid.addWidget(self.recon_iter_spin, 1, 1)   
        
        static_grid.addWidget(QLabel("重构传播距离 (mm):"), 2, 0, Qt.AlignRight)
        self.recon_dist_spin = QDoubleSpinBox()
        self.recon_dist_spin.setRange(-2000.0, 2000.0)
        self.recon_dist_spin.setValue(84.32)
        self.recon_dist_spin.setAlignment(Qt.AlignRight)
        static_grid.addWidget(self.recon_dist_spin, 2, 1)
        self.col2_layout.addWidget(static_box)
        
        core_box = QGroupBox("重构")
        core_layout = QVBoxLayout(core_box)
        
        self.btn_ref = QPushButton("校准并保存基准场")
        self.btn_recon = QPushButton("启动波前重构")
        core_layout.addWidget(self.btn_ref)
        core_layout.addWidget(self.btn_recon)
        
        self.col2_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

    def build_results_section(self, parent_layout):
        res_box = QGroupBox("重构结果")
        res_layout = QVBoxLayout(res_box)
        
        h_data = QHBoxLayout()
        h_data.addWidget(QPushButton("导出当前数据"))
        h_data.addWidget(QPushButton("载入参数"))
        res_layout.addLayout(h_data)
        
        grid_res = QGridLayout()
        grid_res.setSpacing(6)
        grid_res.addWidget(QLabel("PV (nm):"), 0, 0, Qt.AlignRight)
        e1 = QLineEdit("0.142"); e1.setReadOnly(True); e1.setAlignment(Qt.AlignRight)
        grid_res.addWidget(e1, 0, 1)
        
        grid_res.addWidget(QLabel("RMS (nm):"), 1, 0, Qt.AlignRight)
        e2 = QLineEdit("0.024"); e2.setReadOnly(True); e2.setAlignment(Qt.AlignRight)
        grid_res.addWidget(e2, 1, 1)
        
        grid_res.addWidget(QLabel("偏移 X/Y:"), 2, 0, Qt.AlignRight)
        h_box_res = QHBoxLayout()
        ox = QLineEdit("0"); ox.setAlignment(Qt.AlignRight); ox.setReadOnly(True)
        oy = QLineEdit("0"); oy.setAlignment(Qt.AlignRight); oy.setReadOnly(True)
        h_box_res.addWidget(ox); h_box_res.addWidget(QLabel("/")); h_box_res.addWidget(oy)
        grid_res.addLayout(h_box_res, 2, 1)
        
        res_layout.addLayout(grid_res)
        parent_layout.addWidget(res_box)

    def build_log_section(self, parent_layout):
        log_box = QGroupBox("系统运行控制日志")
        log_layout = QVBoxLayout(log_box)
        log_layout.setContentsMargins(6, 6, 6, 6)
        
        self.log_terminal = QPlainTextEdit()
        self.log_terminal.setReadOnly(True)      
        log_layout.addWidget(self.log_terminal)
        log_box.setFixedHeight(180) 
        parent_layout.addWidget(log_box)

    def log(self, level, text):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        color_map = {
            "INFO": "#00FF00",    
            "WARN": "#FFCC00",    
            "SUCCESS": "#00FFFF"  
        }
        color = color_map.get(level, "#FFFFFF")
        
        if self.log_terminal is not None:
            log_line = f'<span style="color: #888888;">[{timestamp}]</span> <span style="color: {color}; font-weight: bold;">{level}</span>: {text}'
            self.log_terminal.appendHtml(log_line)
            self.log_terminal.moveCursor(QTextCursor.MoveOperation.End)
        else:
            print(f"[{timestamp}] [{level}] {text}")

    def switch_dynamic_settings(self, is_convergent):
        while self.dynamic_params_grid.count():
            item = self.dynamic_params_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub_item = item.layout().takeAt(0)
                    if sub_item.widget(): sub_item.widget().deleteLater()
                item.layout().deleteLater()
        
        if is_convergent:           
            self.dynamic_params_grid.addWidget(QLabel("数值孔径校准 F数:"), 3, 0, Qt.AlignRight)
            f_combo = QComboBox()
            f_combo.addItems(["F/10", "F/12", "F/16"])
            self.dynamic_params_grid.addWidget(f_combo, 3, 1)
        else:
            self.dynamic_params_grid.addWidget(QLabel("有效物理通光口径(mm):"), 1, 0, Qt.AlignRight)
            self.effective_aperture = QLabel("25.4")
            self.effective_aperture.setAlignment(Qt.AlignRight)
            self.dynamic_params_grid.addWidget(self.effective_aperture, 1, 1)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())