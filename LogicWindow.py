import sys
import os
import time
import io
import traceback
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt

# PyQt6 导入
from PyQt6.QtWidgets import QVBoxLayout, QFileDialog, QMessageBox, QInputDialog
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import QTimer

# 模块导入
from UI import ModernUI
from ScanWorker import ScanWorker
from DeviceLoader import DeviceLoader
from InteractiveImageView import InteractiveImageView

class LogicWindow(ModernUI):
    def __init__(self):
        super().__init__()
        sys.excepthook = self.handle_exception
        
        # --- 外部配置参数 (由 main.py 注入) ---
        self.config_pixel_size = 3.45e-3 # 默认值
        self.config_xps_groups = ['Group1', 'Group2'] # 默认值

        # --- 1. UI 初始化：替换图像控件 ---
        old_layout = self.image_area.layout()
        if old_layout:
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget(): item.widget().deleteLater()
        else:
            old_layout = QVBoxLayout(self.image_area)
            
        self.image_view = InteractiveImageView()
        old_layout.addWidget(self.image_view)

        # --- 2. 内部状态变量 ---
        self.camera = None
        self.motion = None
        self.is_live = False
        self.dark_frame = None
        self.save_dir = os.path.join(os.getcwd(), "Data") # 默认路径
        if not os.path.exists(self.save_dir): os.makedirs(self.save_dir)
        self.save_dir_edit.setText(self.save_dir)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_live_frame) 
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.bit_depth = 16
        self.saturation_value = 65535

        # --- 3. 信号绑定 ---
        self.image_view.mouse_hover_signal.connect(self.on_mouse_moved)
        self.btn_open_cam.clicked.connect(self.start_init_camera)
        self.btn_connect_stage.clicked.connect(self.start_init_motion)
        self.btn_live.clicked.connect(self.toggle_live)
        self.btn_cap.clicked.connect(self.start_scan)
        self.btn_save.clicked.connect(self.on_manual_save)
        self.btn_browse.clicked.connect(self.select_folder)
        self.btn_show_path.clicked.connect(self.preview_scan_path)
        
        # 简单控制
        self.stage_widget.btn_go.clicked.connect(self.move_stage_absolute)
        self.stage_widget.btn_zero.clicked.connect(self.zero_stage)
        self.exposure_spin.valueChanged.connect(self.set_exposure_time)

    # --- 对外接口 (供 main.py 调用) ---
    def set_pixel_size(self, size_um):
        self.config_pixel_size = float(size_um)
        self.log_info(f"系统配置: 像素尺寸设为 {self.config_pixel_size} um")

    def set_xps_groups(self, groups_list):
        self.config_xps_groups = groups_list
        self.log_info(f"系统配置: XPS 轴组设为 {self.config_xps_groups}")

    # --- 异常与日志 ---
    def handle_exception(self, exc_type, exc_value, exc_traceback):
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        print(error_msg, file=sys.stderr)
        self.log_error(f"系统错误: {exc_value}")

    def log_info(self, msg):
        self.txt_log.append(f"<span style='color:#2196F3;'><b>[{time.strftime('%H:%M:%S')}]</b> ℹ️ {msg}</span>")
        self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())
    
    def log_error(self, msg):
        self.txt_log.append(f"<span style='color:#F44336;'><b>[{time.strftime('%H:%M:%S')}]</b> ❌ {msg}</span>")
        self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())

    def log_success(self, msg):
        self.txt_log.append(f"<span style='color:#4CAF50;'><b>[{time.strftime('%H:%M:%S')}]</b> ✅ {msg}</span>")

    # --- 硬件加载 ---
    def start_init_camera(self):
        cam_name = self.combo_camera.currentText()
        self.log_info(f"初始化相机: {cam_name}...")
        self.btn_open_cam.setEnabled(False)
        self.loader_cam = DeviceLoader('camera', cam_name)
        self.loader_cam.finished_signal.connect(self.on_camera_loaded)
        self.loader_cam.start()

    def on_camera_loaded(self, success, result):
        self.btn_open_cam.setEnabled(True)
        if success:
            self.camera = result
            self.camera.start_acquisition()
            self.btn_open_cam.setText("就绪")
            self.btn_open_cam.setStyleSheet("background-color: #4CAF50; color: white;")
            self.set_exposure_time()
            self.log_success("相机连接成功")
        else:
            self.log_error(f"相机错误: {result}")

    def start_init_motion(self):
        stage_name = self.combo_stage.currentText()
        self.log_info(f"连接位移台: {stage_name}...")
        self.btn_connect_stage.setEnabled(False)
        
        # 组装配置传给 DeviceLoader
        configs = {'xps_groups': self.config_xps_groups}
        
        self.loader_stage = DeviceLoader('stage', stage_name, extra_configs=configs)
        self.loader_stage.finished_signal.connect(self.on_motion_loaded)
        self.loader_stage.start()

    def on_motion_loaded(self, success, result):
        self.btn_connect_stage.setEnabled(True)
        if success:
            self.motion = result
            self.btn_connect_stage.setText("已连接")
            self.log_success("位移台连接成功")
            self.sync_hardware_position()
        else:
            self.log_error(f"位移台错误: {result}")

    # --- 扫描逻辑 ---
    def start_scan(self):
        if not self.camera or not self.motion:
            self.log_error("设备未就绪")
            return

        self.preview_scan_path() # 确保 Scanner 对象更新
        if not getattr(self, 'scanner', None): return

        # 准备元数据 (供 ScanWorker 写入 H5)
        try:
            rw = int(self.roi_w.text())
            rh = int(self.roi_h.text())
            ox = int(self.off_x.text())
            oy = int(self.off_y.text())
        except: rw, rh, ox, oy = 1024, 1024, 0, 0
        
        metadata = {
            'wavelength': float(self.wavelength_spin.text()),
            'pixel_size': self.config_pixel_size,
            'offset_x': ox,
            'offset_y': oy,
            'exposure_time': self.exposure_spin.value(),
            'detector_size': np.array([rw, rh])
        }
        
        h5_path = os.path.join(self.save_dir, "scandata.h5")

        # 启动线程
        self.btn_cap.setEnabled(False); self.btn_cap.setText("Scanning...")
        
        # 停止实时流
        if self.is_live: self.toggle_live()
        if hasattr(self.camera, 'stop_acquisition'): self.camera.stop_acquisition()

        self.worker = ScanWorker(
            camera=self.camera,
            motion=self.motion,
            scanner=self.scanner,
            exposure_time_ms=self.exposure_spin.value(),
            crop_params=(rw, rh, ox, oy),
            dark_frame=self.dark_frame,
            save_path=h5_path,
            metadata=metadata
        )
        self.worker.update_signal.connect(self.on_scan_update)
        self.worker.log_signal.connect(self.on_worker_log)
        self.worker.finished_signal.connect(self.on_scan_finished)
        self.worker.start()

    def on_scan_update(self, img_data, x, y, idx):
        self.image_view.update_image(img_data, self.chk_mask.isChecked())

    def on_worker_log(self, msg, level):
        if level == 'error': self.log_error(msg)
        elif level == 'warning': self.log_info(f"⚠️ {msg}") # 用info显示warning避免太红
        elif level == 'success': self.log_success(msg)
        else: self.log_info(msg)

    def on_scan_finished(self):
        self.log_success("扫描流程结束")
        self.btn_cap.setEnabled(True); self.btn_cap.setText("开始采集")
        # 回原点
        try:
            fx, fy = self.scanner.final_pos
            self.motion.move_by(-fx, 0); self.motion.move_by(-fy, 1)
        except: pass
        self.toggle_live() # 恢复实时

    # --- 其他辅助函数 (精简版) ---
    def set_exposure_time(self):
        if self.camera: self.camera.set_ex_time(self.exposure_spin.value()/1000.0)

    def toggle_live(self):
        if not self.camera: return
        if self.is_live:
            self.timer.stop()
            self.is_live = False
            self.btn_live.setText("👁 启动")
            self.btn_live.setStyleSheet("background:#27ae60;color:white;")
        else:
            self.timer.start(50)
            self.is_live = True
            self.btn_live.setText("⬛ 停止")
            self.btn_live.setStyleSheet("background:#7f8c8d;color:white;")

    def update_live_frame(self):
        if not self.camera: return
        img = self.camera.read_newest_image()
        if img is not None:
            # 简单裁剪显示，不保存
            try:
                w, h = int(self.roi_w.text()), int(self.roi_h.text())
                ox, oy = int(self.off_x.text()), int(self.off_y.text())
                # ... (此处省略详细裁剪计算代码，与 ScanWorker 类似) ...
                # 为简洁起见，这里直接显示全图或需复用 crop_image 逻辑
                self.image_view.update_image(img, self.chk_mask.isChecked())
            except: 
                self.image_view.update_image(img, self.chk_mask.isChecked())

    def on_mouse_moved(self, x, y, val):
        self.line_mouse_val.setText(f"{val}")

    def select_folder(self):
        path = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if path:
            self.save_dir_edit.setText(path)
            self.save_dir = path

    def on_manual_save(self):
        if not self.camera: return
        img = self.camera.read_newest_image()
        if img is not None:
            path = os.path.join(self.save_dir, f"snap_{time.time():.0f}.tif")
            Image.fromarray(img).save(path)
            self.log_success(f"截图已保存: {path}")

    def preview_scan_path(self):
        # ... (保留原有的路径生成和绘图逻辑) ...
        try:
            from Scanner import Scanner
            mode = "round" # 简化，实际需读取 UI
            self.scanner = Scanner(step=0.1, scan_range_x=1, scan_range_y=1, mode=mode)
            self.scan_points.setText(str(len(self.scanner.x)))
            # 绘图逻辑省略，与原代码一致
        except Exception as e: self.log_error(f"路径生成失败: {e}")

    def move_stage_absolute(self):
        # ... (保留原有的移动逻辑) ...
        pass
    
    def zero_stage(self):
        # ... (保留原有的归零逻辑) ...
        pass
    
    def sync_hardware_position(self):
        # ... (保留原有的同步逻辑) ...
        pass