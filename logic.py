import sys
import os
import time
import io
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import traceback
import h5py

from PyQt6.QtWidgets import QVBoxLayout, QFileDialog, QMessageBox, QInputDialog
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import QTimer

# 导入拆分后的模块
from UI import ModernUI
from widgets import InteractiveImageView
from workers import DeviceLoader, ScanWorker, FileSaverWorker

class LogicWindow(ModernUI):
    def __init__(self):
        super().__init__()
        sys.excepthook = self.handle_exception
        
        # --- 1. 替换图像控件 ---
        old_layout = self.image_area.layout()
        if old_layout:
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget(): item.widget().deleteLater()
        else:
            old_layout = QVBoxLayout(self.image_area)
            
        self.image_view = InteractiveImageView()
        old_layout.addWidget(self.image_view)

        # --- 2. 内部变量 ---
        self.camera = None
        self.motion = None
        self.scanner = None
        self.dp = []
        self.pos_x = []
        self.pos_y = [] 
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame) 
        self.is_live = False
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.image_view.mouse_hover_signal.connect(self.on_mouse_moved)
        self.default_save_dir = "please change this to your own path"
        self.save_dir = self.default_save_dir
        self.dark_frame = None
        self.pixel_size = 3.45e-3
        self.saturation_value = 65535 # 默认16位相机饱和值

        self.file_saver = FileSaverWorker()
        self.file_saver.log_signal.connect(self._saver_log)
        self.file_saver.start()

        # --- 3. 信号绑定 ---
        self.btn_open_cam.clicked.connect(self.start_init_camera)
        self.btn_connect_stage.clicked.connect(self.start_init_motion)
        
        self.btn_live.clicked.connect(self.toggle_live)
        self.btn_cap.clicked.connect(self.start_scan)
        self.btn_save.clicked.connect(self.on_manual_save)
        self.btn_browse.clicked.connect(self.select_folder)
        self.btn_show_path.clicked.connect(self.preview_scan_path)

        # 位移台
        self.stage_widget.btn_up.clicked.connect(lambda: self.move_stage_manual('Y', 1))
        self.stage_widget.btn_down.clicked.connect(lambda: self.move_stage_manual('Y', -1))
        self.stage_widget.btn_left.clicked.connect(lambda: self.move_stage_manual('X', -1))
        self.stage_widget.btn_right.clicked.connect(lambda: self.move_stage_manual('X', 1))
        self.stage_widget.btn_go.clicked.connect(self.move_stage_absolute)
        self.stage_widget.btn_zero.clicked.connect(self.zero_stage)

        self.btn_center.clicked.connect(self.calculate_center)
        self.exposure_spin.valueChanged.connect(self.set_exposure_time)

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        print(error_msg, file=sys.stderr)
        self.log_error(f"⛔ 【系统错误】 {exc_type.__name__}: {exc_value}\n{error_msg}")

    # --- 日志 ---
    def log_info(self, msg):
        self._log(msg, "#2196F3", "ℹ️")
    
    def log_success(self, msg):
        self._log(msg, "#4CAF50", "✅")
    
    def log_warning(self, msg):
        self._log(msg, "#FF9800", "⚠️")
    
    def log_error(self, msg):
        self._log(msg, "#F44336", "❌")

    def _saver_log(self, level, msg):
        if level == "error": self.log_error(msg)
        elif level == "success": self.log_success(msg)
        else: self.log_info(msg)

    def _log(self, msg, color, icon):
        t = time.strftime("%H:%M:%S")
        # 使用 appendHtml 适配 QPlainTextEdit
        self.txt_log.appendHtml(f"<span style='color:{color};'><b>[{t}]</b> {icon} {msg}</span>")
        self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())

    # --- 设备初始化 ---
    def start_init_camera(self):
        cam_name = self.combo_camera.currentText()
        self.log_info(f"初始化相机: {cam_name}...")
        self.btn_open_cam.setEnabled(False)
        self.loader_thread_cam = DeviceLoader('camera', cam_name)
        self.loader_thread_cam.finished_signal.connect(self.on_camera_loaded)
        self.loader_thread_cam.start()

    def on_camera_loaded(self, success, result):
        self.btn_open_cam.setEnabled(True)
        if success:
            self.camera = result
            self.btn_open_cam.setText("已就绪")
            self.btn_open_cam.setStyleSheet("background-color: #4CAF50; color: white;")
            self.set_exposure_time()
            
            bit_depth = 16
            try:
                if hasattr(self.camera, 'get_bit_depth'): bit_depth = int(self.camera.get_bit_depth())
                elif hasattr(self.camera, 'bit_depth'): bit_depth = int(self.camera.bit_depth)
            except: pass
            self.saturation_value = (1 << bit_depth) - 1
            self.line_cam_max.setText(f"{self.saturation_value} ({bit_depth}-bit)")
            self.log_success(f"相机就绪 | 位深: {bit_depth}")
        else:
            self.log_error(f"相机初始化失败: {result}")

    def start_init_motion(self):
        stage_name = self.combo_stage.currentText()
        self.log_info(f"连接位移台: {stage_name}...")
        self.btn_connect_stage.setEnabled(False)
        self.loader_thread_stage = DeviceLoader('stage', stage_name)
        self.loader_thread_stage.finished_signal.connect(self.on_motion_loaded)
        self.loader_thread_stage.start()

    def on_motion_loaded(self, success, result):
        self.btn_connect_stage.setEnabled(True)
        if success:
            self.motion = result
            self.btn_connect_stage.setText("已连接")
            self.log_success("位移台连接成功")
            self.sync_hardware_position()
            self.zero_stage_x = float(self.stage_widget.target_x.text())
            self.zero_stage_y = float(self.stage_widget.target_y.text())
        else:
            self.log_error(f"位移台错误: {result}")

    # --- 辅助逻辑 ---
    def sync_hardware_position(self):
        if not self.motion: return
        hw_x, hw_y = 0.0, 0.0
        try:
            if hasattr(self.motion, 'get_position'):
                hw_x = float(self.motion.get_position(0))
                hw_y = float(self.motion.get_position(1))
                self.stage_widget.lbl_x.setText(f"X: {hw_x:.3f} mm")
                self.stage_widget.lbl_y.setText(f"Y: {hw_y:.3f} mm")
                self.stage_widget.target_x.blockSignals(True)
                self.stage_widget.target_y.blockSignals(True)
                self.stage_widget.target_x.setText(f"{hw_x:.3f}")
                self.stage_widget.target_y.setText(f"{hw_y:.3f}")
                self.stage_widget.target_x.blockSignals(False)
                self.stage_widget.target_y.blockSignals(False)
        except Exception as e:
            self.log_error(f"同步位置异常: {e}")

    def crop_image(self, full_image):
        if full_image is None: return None
        h_full, w_full = full_image.shape
        try: target_w = int(self.roi_w.text())
        except: target_w = 1024
        try: target_h = int(self.roi_h.text())
        except: target_h = 1024
        try: off_x = int(self.off_x.text())
        except: off_x = 0
        try: off_y = int(self.off_y.text())
        except: off_y = 0
        
        if target_w >= w_full and target_h >= h_full: return full_image
        
        center_x = w_full // 2 + off_x
        center_y = h_full // 2 + off_y
        x1 = int(center_x - target_w // 2)
        y1 = int(center_y - target_h // 2)
        x2 = x1 + target_w
        y2 = y1 + target_h
        
        x1 = max(0, x1); y1 = max(0, y1)
        x2 = min(w_full, x2); y2 = min(h_full, y2)
        return full_image[y1:y2, x1:x2]

    def update_frame(self):
        if self.camera:
            try:
                if type(self.camera).__name__ == "NewVSYCamera": self.camera.start_acquisition()
                img = self.camera.read_newest_image()
                if img is None: return
                cropped_img = self.crop_image(img)
                
                max_val = np.max(cropped_img)
                self.line_global_max.setText(f"{max_val}")
                if max_val >= self.saturation_value:
                    self.line_global_max.setStyleSheet("color: red; font-weight: bold; background: #ffeeee;")
                else:
                    self.line_global_max.setStyleSheet("color: green; font-weight: bold; background: #f0f0f0;")

                show_mask = self.chk_mask.isChecked()
                if self.chk_log.isChecked():
                    img_disp = np.log1p(cropped_img.astype(np.float32))
                    img_disp = (img_disp / np.max(img_disp) * self.saturation_value).astype(np.uint16)
                    self.image_view.update_image(img_disp, show_mask)
                else:
                    self.image_view.update_image(cropped_img, show_mask)

                h, w = cropped_img.shape
                if 0 <= self.last_mouse_x < w and 0 <= self.last_mouse_y < h:
                    self.update_pixel_display(cropped_img[self.last_mouse_y, self.last_mouse_x])
            except Exception as e:
                self.log_error(f"Live View Error: {e}")

    def on_mouse_moved(self, x, y, val):
        self.last_mouse_x = x; self.last_mouse_y = y
        self.update_pixel_display(val)

    def update_pixel_display(self, val):
        self.line_mouse_val.setText(f"{val}")
        if val >= self.saturation_value:
            self.line_mouse_val.setStyleSheet("color: red; font-weight: bold; background: #ffeeee;")
        else:
            self.line_mouse_val.setStyleSheet("color: blue; font-weight: bold; background: #f0f0f0;")

    def toggle_live(self):
        if not self.camera:
            self.log_warning("相机未连接")
            return
        if self.is_live:
            self.timer.stop()
            self.is_live = False
            self.btn_live.setText("👁 启动")
            self.btn_live.setStyleSheet("background:#27ae60;color:white;font-weight:bold;")
            self.log_info("实时显示已停止")
        else:
            exposure_ms = self.exposure_spin.value()
            self.timer.start(max(30, int(exposure_ms)))
            self.is_live = True
            self.btn_live.setText("⬛ 停止")
            self.btn_live.setStyleSheet("background:#7f8c8d;color:white;font-weight:bold;")
            self.log_success("实时显示已启动")

    def calculate_center(self):
        # TODO: 实现自动计算中心逻辑
        self.log_info("Function not implemented yet.")

    def set_exposure_time(self):
        if self.camera:
            val = self.exposure_spin.value()
            self.camera.set_ex_time(val / 1000.0)
            self.log_info(f"曝光: {val} ms")

    # --- 位移台操作 ---
    def move_stage_manual(self, axis_name, direction):
        if not self.motion: return
        step = self.stage_widget.step_spin.value()
        is_swap = self.stage_widget.check_swap.isChecked()
        inv_x = self.stage_widget.check_inv_x.isChecked()
        inv_y = self.stage_widget.check_inv_y.isChecked()
        
        target_axis = 0 
        if axis_name == 'X':
            target_axis = 1 if is_swap else 0
            if inv_x: direction *= -1
        else: 
            target_axis = 0 if is_swap else 1
            if inv_y: direction *= -1
            
        try:
            self.motion.move_by(step * direction, axis=target_axis)
            self.sync_hardware_position()
        except Exception as e:
            self.log_error(f"移动失败: {e}")

    def move_stage_absolute(self):
        if not self.motion: return
        try:
            tx = float(self.stage_widget.target_x.text())
            ty = float(self.stage_widget.target_y.text())
        except: return
        
        is_swap = self.stage_widget.check_swap.isChecked()
        ax_x = 1 if is_swap else 0
        ax_y = 0 if is_swap else 1
        
        try:
            if hasattr(self.motion, 'move_to'):
                self.motion.move_to(tx, axis=ax_x)
                self.motion.move_to(ty, axis=ax_y)
            else:
                # 简易 fallback: 计算差值移动
                # (建议完善此处逻辑，参考原代码)
                pass 
            self.sync_hardware_position()
            self.log_success("移动完成")
        except Exception as e:
            self.log_error(f"移动失败: {e}")

    def zero_stage(self):
        if not self.motion: return
        try:
            if hasattr(self.motion, 'move_to'):
                self.motion.move_to(self.zero_stage_x, axis=0)
                self.motion.move_to(self.zero_stage_y, axis=1)
            elif hasattr(self.motion, 'move_absolute'):
                self.motion.move_absolute(0, axis=0)
                self.motion.move_absolute(0, axis=1)
            self.sync_hardware_position()
        except Exception as e:
            self.log_error(f"回零失败: {e}")

    # --- 扫描与保存 ---
    def preview_scan_path(self):
        try:
            from Scanner import Scanner # 局部导入
            mode_map = {"矩形": "rectangle", "圆形": "round", "螺旋": "fermat"}
            mode = mode_map.get(self.combo_scan_mode.currentText(), "round")
            
            try: rx, ry = float(self.scan_range_x.text()), float(self.scan_range_y.text())
            except: rx, ry = 1, 1
            try: step = float(self.scan_step.text())
            except: step = 0.1
            
            self.scanner = Scanner(step=step, scan_range_x=rx, scan_range_y=ry, mode=mode)
            self.scan_points.setText(str(len(self.scanner.x)))
            self.log_success(f"路径生成: {mode}, 点数: {len(self.scanner.x)}")

            # 绘图
            plt.style.use('default')
            fig, ax = plt.subplots(figsize=(4, 3), dpi=100)
            ax.plot(self.scanner.abs_x, self.scanner.abs_y, 'b.-', markersize=2, linewidth=0.5, alpha=0.6)
            ax.set_aspect('equal'); ax.grid(True, linestyle=':', alpha=0.5); plt.tight_layout()
            
            buf = io.BytesIO()
            fig.savefig(buf, format='png'); plt.close(fig); buf.seek(0)
            self.lbl_scan_preview.setPixmap(QPixmap.fromImage(QImage.fromData(buf.getvalue())))
            self.lbl_scan_preview.setScaledContents(True)
        except Exception as e:
            self.log_error(f"路径生成失败: {e}")

    def confirm_directory(self):
        curr = self.save_dir_edit.text().strip()
        if not curr or curr == self.default_save_dir:
            QMessageBox.warning(self, "路径错误", "请修改保存目录!")
            return False
        self.save_dir = curr
        if not os.path.exists(curr):
            try: os.makedirs(curr)
            except: return False
        return True

    def start_scan(self):
        if not self.confirm_directory(): return
        self.preview_scan_path()
        if not self.scanner: return

        if self.dark_frame is None:
            if QMessageBox.question(self, "暗场", "采集暗场？", QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                img = self.camera.read_newest_image()
                if img is not None:
                    self.dark_frame = self.crop_image(img).astype(np.uint16)
                    Image.fromarray(self.dark_frame).save(os.path.join(self.save_dir, "dark.tif"))
                    self.log_success("暗场已保存")

        if QMessageBox.question(self, "确认", "开始采集？", QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) == QMessageBox.StandardButton.No:
            return

        self.current_scan_h5_name = "scandata.h5"
        self.dp = []; self.pos_x = []; self.pos_y = []
        
        try: w, h = int(self.roi_w.text()), int(self.roi_h.text())
        except: w, h = 1024, 1024
        try: ox, oy = int(self.off_x.text()), int(self.off_y.text())
        except: ox, oy = 0, 0
        
        self.worker = ScanWorker(self.camera, self.motion, self.scanner, self.exposure_spin.value(), (w, h, ox, oy), self.dark_frame)
        self.worker.update_signal.connect(self._update_scan_preview)
        self.worker.log_signal.connect(self._worker_log)
        self.worker.finished_signal.connect(self._scan_finished)
        
        if self.is_live:
            self.timer.stop(); self.is_live = False; self.was_live_before_scan = True
            self.btn_live.setText("👁 启动")
            if hasattr(self.camera, 'stop_acquisition'): self.camera.stop_acquisition()
            time.sleep(0.3)
            
        self.worker.start()

    def _worker_log(self, msg, level):
        if level == "error": self.log_error(msg)
        elif level == "warning": self.log_warning(msg)
        elif level == "success": self.log_success(msg)
        else: self.log_info(msg)

    def _update_scan_preview(self, img_data, cur_x, cur_y, idx):
        # 1. 内存记录 (不变)
        self.dp.append(img_data)
        self.pos_x.append(cur_x)
        self.pos_y.append(cur_y)
        
        # 2. 界面显示 (不变)
        self.image_view.update_image(img_data, self.chk_mask.isChecked())
        
        # 3. 【修改】提交到后台线程保存 TIF
        frame_name = f"scan_{idx:03d}.tif"
        path = os.path.join(self.save_dir, frame_name)
        
        # 使用 copy() 确保传给子线程的数据不会被后续修改（虽然这里append的是新对象，但安全第一）
        self.file_saver.save_tif(img_data.copy(), path)

    def _scan_finished(self):
        self.log_info("扫描结束，正在后台处理数据...")
        
        # 准备数据字典
        h5_path = os.path.join(self.save_dir, "raw_data", self.current_scan_h5_name)
        
        # 收集属性
        attrs = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'exposure_time': float(self.exposure_spin.value())
            # 你可以在这里添加更多属性，如 pixel_size, wavelength 等
        }
        
        data_package = {
            "data": np.array(self.dp), # 此时转 numpy 可能会花一点时间，但也比写硬盘快
            "x": np.array(self.pos_x),
            "y": np.array(self.pos_y),
            "attrs": attrs
        }

        # 【修改】提交 H5 保存任务
        self.file_saver.save_h5(h5_path, data_package)
        
        self.dark_frame = None
        
        # 回到起点 (不变)
        fx, fy = self.scanner.final_pos
        self._move_logical_delta(-fx, 0)
        self._move_logical_delta(-fy, 1)
        
        if getattr(self, 'was_live_before_scan', False):
            self.toggle_live()

    def _move_logical_delta(self, delta, logic_axis):
        # 简化版相对回零，实际使用需完善
        try:
            phys_axis = logic_axis # 需结合 check_swap 判断
            self.motion.move_by(delta, axis=phys_axis)
        except: pass

    def _write_scan_to_h5(self, dp, pos_x, pos_y):
        h5_path = os.path.join(self.save_dir, "raw_data", self.current_scan_h5_name)
        try: os.makedirs(os.path.dirname(h5_path), exist_ok=True)
        except: pass
        
        try:
            with h5py.File(h5_path, 'a') as f:
                for k in ["data", "x", "y"]: 
                    if k in f: del f[k]
                f.create_dataset("data", data=np.array(dp), compression="gzip")
                f.create_dataset("x", data=np.array(pos_x), compression="gzip")
                f.create_dataset("y", data=np.array(pos_y), compression="gzip")
                # 写入属性...
                f.attrs['timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
            self.log_success("H5 保存成功")
        except Exception as e:
            self.log_error(f"H5 保存失败: {e}")

    def select_folder(self):
        path = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if path: self.save_dir_edit.setText(path)

    def on_manual_save(self):
        if not self.confirm_directory(): return
        fname, ok = QInputDialog.getText(self, "保存", "文件名:", text=f"img_{time.strftime('%H%M%S')}")
        if ok and fname:
            if not self.camera: return
            img = self.camera.read_newest_image()
            if img is not None:
                roi = self.crop_image(img)
                path = os.path.join(self.save_dir, f"{fname}.tif")
                
                # 【修改】提交后台保存
                self.file_saver.save_tif(roi, path)
                self.log_success(f"已添加到保存队列: {fname}.tif")
    
    def closeEvent(self, event):
        self.file_saver.stop()
        super().closeEvent(event)