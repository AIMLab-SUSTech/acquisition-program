import sys
import os
import time
import io
import traceback
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')  # 使用非GUI后端
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
        
        # --- 外部配置参数 (由 event1.py 注入) ---
        self.config_pixel_size = 3.45e-3  # 默认值 (mm)
        self.config_xps_groups = ['Group1', 'Group2']  # 默认值

        # --- 1. UI 初始化：替换图像控件 ---
        old_layout = self.image_area.layout()
        if old_layout:
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget(): 
                    item.widget().deleteLater()
        else:
            old_layout = QVBoxLayout(self.image_area)
            
        self.image_view = InteractiveImageView()
        old_layout.addWidget(self.image_view)

        # --- 2. 内部状态变量 ---
        self.camera = None
        self.motion = None
        self.is_live = False
        self.dark_frame = None
        self.save_dir = os.path.join(os.getcwd(), "Data")  # 默认路径
        if not os.path.exists(self.save_dir): 
            os.makedirs(self.save_dir)
        self.save_dir_edit.setText(self.save_dir)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_live_frame) 
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.bit_depth = 16
        self.saturation_value = 65535
        
        # 扫描相关
        self.scanner = None

        # --- 3. 信号绑定 ---
        self.image_view.mouse_hover_signal.connect(self.on_mouse_moved)
        self.btn_open_cam.clicked.connect(self.start_init_camera)
        self.btn_connect_stage.clicked.connect(self.start_init_motion)
        self.btn_live.clicked.connect(self.toggle_live)
        self.btn_cap.clicked.connect(self.start_scan)
        self.btn_save.clicked.connect(self.on_manual_save)
        self.btn_browse.clicked.connect(self.select_folder)
        self.btn_show_path.clicked.connect(self.preview_scan_path)
        
        # 位移台控制
        self.stage_widget.btn_go.clicked.connect(self.move_stage_absolute)
        self.stage_widget.btn_zero.clicked.connect(self.zero_stage)
        self.stage_widget.btn_up.clicked.connect(lambda: self.jog_stage('Y', 1))
        self.stage_widget.btn_down.clicked.connect(lambda: self.jog_stage('Y', -1))
        self.stage_widget.btn_left.clicked.connect(lambda: self.jog_stage('X', -1))
        self.stage_widget.btn_right.clicked.connect(lambda: self.jog_stage('X', 1))
        
        # 曝光时间
        self.exposure_spin.valueChanged.connect(self.set_exposure_time)
        
        # 启动位置更新定时器
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self.update_stage_position)
        self.position_timer.start(500)  # 每500ms更新一次位置

    # --- 对外接口 (供 event1.py 调用) ---
    def set_pixel_size(self, size_um):
        """设置像素尺寸 (单位: um)"""
        self.config_pixel_size = float(size_um) * 1e-3  # 转换为 mm
        self.log_info(f"系统配置: 像素尺寸设为 {size_um} um")

    def set_xps_groups(self, groups_list):
        """设置 XPS 轴组"""
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
        self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())

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
            if hasattr(self.camera, 'start_acquisition'):
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
            self.btn_connect_stage.setStyleSheet("background-color: #4CAF50; color: white;")
            self.log_success("位移台连接成功")
            self.sync_hardware_position()
        else:
            self.log_error(f"位移台错误: {result}")

    # --- 位移台控制 ---
    def jog_stage(self, axis_name, direction):
        """点动控制"""
        if not self.motion:
            self.log_error("位移台未连接")
            return
        
        try:
            step = self.stage_widget.step_spin.value()
            
            # 检查轴交换
            if self.stage_widget.check_swap.isChecked():
                axis_name = 'Y' if axis_name == 'X' else 'X'
            
            # 检查轴反转
            if axis_name == 'X' and self.stage_widget.check_inv_x.isChecked():
                direction = -direction
            elif axis_name == 'Y' and self.stage_widget.check_inv_y.isChecked():
                direction = -direction
            
            # 确定轴索引
            axis_idx = 0 if axis_name == 'X' else 1
            
            # 移动
            distance = step * direction
            if hasattr(self.motion, 'move_by'):
                self.motion.move_by(distance, axis=axis_idx)
                self.log_info(f"{axis_name} 轴移动 {distance:.3f} mm")
            else:
                self.log_error("位移台不支持相对移动")
                
        except Exception as e:
            self.log_error(f"移动失败: {e}")

    def move_stage_absolute(self):
        """绝对位置移动"""
        if not self.motion:
            self.log_error("位移台未连接")
            return
        
        try:
            target_x = float(self.stage_widget.target_x.text())
            target_y = float(self.stage_widget.target_y.text())
            
            if hasattr(self.motion, 'move_to'):
                self.motion.move_to(target_x, axis=0)
                self.motion.move_to(target_y, axis=1)
                self.log_success(f"移动到 ({target_x:.3f}, {target_y:.3f})")
            else:
                self.log_error("位移台不支持绝对移动")
                
        except ValueError:
            self.log_error("请输入有效的数值")
        except Exception as e:
            self.log_error(f"移动失败: {e}")

    def zero_stage(self):
        """归零"""
        if not self.motion:
            self.log_error("位移台未连接")
            return
        
        try:
            if hasattr(self.motion, 'move_to'):
                self.motion.move_to(0, axis=0)
                self.motion.move_to(0, axis=1)
                self.log_success("已归零")
            else:
                self.log_error("位移台不支持归零")
        except Exception as e:
            self.log_error(f"归零失败: {e}")

    def update_stage_position(self):
        """更新位移台位置显示"""
        if not self.motion:
            return
        
        try:
            if hasattr(self.motion, 'get_position'):
                x = self.motion.get_position(0)
                y = self.motion.get_position(1)
                self.stage_widget.lbl_x.setText(f"X: {x:.3f} mm")
                self.stage_widget.lbl_y.setText(f"Y: {y:.3f} mm")
        except:
            pass

    def sync_hardware_position(self):
        """同步硬件位置到输入框"""
        if not self.motion:
            return
        
        try:
            if hasattr(self.motion, 'get_position'):
                x = self.motion.get_position(0)
                y = self.motion.get_position(1)
                self.stage_widget.target_x.setText(f"{x:.3f}")
                self.stage_widget.target_y.setText(f"{y:.3f}")
        except:
            pass

    # --- 扫描逻辑 ---
    def start_scan(self):
        if not self.camera or not self.motion:
            self.log_error("设备未就绪")
            return

        self.preview_scan_path()  # 确保 Scanner 对象更新
        if not self.scanner:
            self.log_error("请先生成扫描路径")
            return

        # 准备元数据 (供 ScanWorker 写入 H5)
        try:
            rw = int(self.roi_w.text())
            rh = int(self.roi_h.text())
            ox = int(self.off_x.text())
            oy = int(self.off_y.text())
        except: 
            rw, rh, ox, oy = 1024, 1024, 0, 0
        
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
        self.btn_cap.setEnabled(False)
        self.btn_cap.setText("Scanning...")
        
        # 停止实时流
        if self.is_live: 
            self.toggle_live()
        if hasattr(self.camera, 'stop_acquisition'): 
            self.camera.stop_acquisition()

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
        """扫描更新回调"""
        self.image_view.update_image(img_data, self.chk_mask.isChecked())
        # 更新全局最大值
        if img_data is not None:
            max_val = np.max(img_data)
            self.line_global_max.setText(f"{max_val}")

    def on_worker_log(self, msg, level):
        """工作线程日志回调"""
        if level == 'error': 
            self.log_error(msg)
        elif level == 'warning': 
            self.log_info(f"⚠️ {msg}")
        elif level == 'success': 
            self.log_success(msg)
        else: 
            self.log_info(msg)

    def on_scan_finished(self):
        """扫描完成回调"""
        self.log_success("扫描流程结束")
        self.btn_cap.setEnabled(True)
        self.btn_cap.setText("🔴 采集")
        
        # 回原点
        try:
            if self.scanner and hasattr(self.scanner, 'final_pos'):
                fx, fy = self.scanner.final_pos
                if hasattr(self.motion, 'move_by'):
                    self.motion.move_by(-fx, axis=0)
                    self.motion.move_by(-fy, axis=1)
                    self.log_info("已返回起点")
        except Exception as e:
            self.log_error(f"返回起点失败: {e}")
        
        # 恢复实时预览
        if hasattr(self.camera, 'start_acquisition'):
            self.camera.start_acquisition()
        self.toggle_live()

    # --- 其他辅助函数 ---
    def set_exposure_time(self):
        """设置曝光时间"""
        if self.camera and hasattr(self.camera, 'set_ex_time'):
            self.camera.set_ex_time(self.exposure_spin.value() / 1000.0)

    def toggle_live(self):
        """切换实时预览"""
        if not self.camera: 
            self.log_error("相机未连接")
            return
        
        if self.is_live:
            self.timer.stop()
            self.is_live = False
            self.btn_live.setText("👁 启动")
            self.btn_live.setStyleSheet("background:#27ae60;color:white; border-radius:5px; font-weight:bold;")
        else:
            self.timer.start(50)
            self.is_live = True
            self.btn_live.setText("⬛ 停止")
            self.btn_live.setStyleSheet("background:#7f8c8d;color:white; border-radius:5px; font-weight:bold;")

    def update_live_frame(self):
        """更新实时图像"""
        if not self.camera or not hasattr(self.camera, 'read_newest_image'):
            return
        
        try:
            img = self.camera.read_newest_image()
            if img is not None:
                self.image_view.update_image(img, self.chk_mask.isChecked())
                # 更新最大值
                max_val = np.max(img)
                self.line_global_max.setText(f"{max_val}")
                # 更新饱和值显示
                self.line_cam_max.setText(f"{self.saturation_value}")
        except Exception as e:
            pass

    def on_mouse_moved(self, x, y, val):
        """鼠标移动回调"""
        self.line_mouse_val.setText(f"{val}")

    def select_folder(self):
        """选择保存文件夹"""
        path = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if path:
            self.save_dir_edit.setText(path)
            self.save_dir = path
            self.log_info(f"保存路径: {path}")

    def on_manual_save(self):
        """手动保存当前图像"""
        if not self.camera:
            self.log_error("相机未连接")
            return
        
        try:
            img = self.camera.read_newest_image()
            if img is not None:
                filename = f"snap_{time.strftime('%Y%m%d_%H%M%S')}.tif"
                path = os.path.join(self.save_dir, filename)
                Image.fromarray(img).save(path)
                self.log_success(f"截图已保存: {filename}")
            else:
                self.log_error("无法获取图像")
        except Exception as e:
            self.log_error(f"保存失败: {e}")

    def preview_scan_path(self):
        """预览扫描路径"""
        try:
            from Scanner import Scanner
            
            # 读取UI参数
            mode_map = {"矩形": "rectangle", "圆形": "round", "螺旋": "fermat"}
            mode = mode_map.get(self.combo_scan_mode.currentText(), "round")
            
            step = float(self.scan_step.text())
            range_x = float(self.scan_range_x.text())
            range_y = float(self.scan_range_y.text())
            
            # 生成扫描器
            self.scanner = Scanner(
                step=step, 
                scan_range_x=range_x, 
                scan_range_y=range_y, 
                mode=mode
            )
            
            # 更新点数
            self.scan_points.setText(str(len(self.scanner.x)))
            
            # 绘制路径预览
            self.draw_scan_preview()
            
            self.log_success(f"扫描路径已生成: {len(self.scanner.x)} 点")
            
        except Exception as e:
            self.log_error(f"路径生成失败: {e}")
            import traceback
            traceback.print_exc()

    def draw_scan_preview(self):
        """绘制扫描路径预览图"""
        if not self.scanner:
            return
        
        try:
            # 创建图形
            fig, ax = plt.subplots(figsize=(4, 4))
            
            x = np.array(self.scanner.abs_x)
            y = np.array(self.scanner.abs_y)
            
            # 绘制路径
            ax.plot(x, y, 'b-', linewidth=0.5, alpha=0.5)
            ax.scatter(x, y, c=range(len(x)), cmap='viridis', s=10)
            
            # 标记起点和终点
            ax.plot(x[0], y[0], 'go', markersize=10, label='Start')
            ax.plot(x[-1], y[-1], 'r*', markersize=10, label='End')
            
            ax.set_aspect('equal')
            ax.grid(True, alpha=0.3)
            ax.legend()
            ax.set_xlabel('X (mm)')
            ax.set_ylabel('Y (mm)')
            ax.set_title(f'{self.scanner.mode} - {len(x)} points')
            
            # 保存为图像
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=80, bbox_inches='tight')
            buf.seek(0)
            plt.close(fig)
            
            # 显示在 QLabel
            qimg = QImage()
            qimg.loadFromData(buf.read())
            pixmap = QPixmap.fromImage(qimg)
            self.lbl_scan_preview.setPixmap(pixmap.scaled(
                self.lbl_scan_preview.width(),
                self.lbl_scan_preview.height(),
                aspectRatioMode=1  # KeepAspectRatio
            ))
            
        except Exception as e:
            self.log_error(f"绘图失败: {e}")