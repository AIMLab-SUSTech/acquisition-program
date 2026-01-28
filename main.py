from re import S
import sys
import os
import time
import io
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import traceback
import h5py

# PyQt6 导入
from PyQt6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QVBoxLayout, QFileDialog, QMessageBox, QInputDialog
from PyQt6.QtGui import QImage, QPixmap, QPen, QColor
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QThread

# 导入 UI 定义
from UI import ModernUI

# =========================================================
#  硬件加载线程
# =========================================================
class DeviceLoader(QThread):
    finished_signal = pyqtSignal(bool, object)

    def __init__(self, device_type, device_name):
        super().__init__()
        self.device_type = device_type 
        self.device_name = device_name

    def run(self):
        try:
            device_instance = None
            if self.device_type == 'camera':
                match(self.device_name):
                    case "IDS":
                        from camera import IDS
                        device_instance = IDS()
                        device_instance.start_acquisition()
                        device_instance.set_pixel_rate(7e7)
                    case "Ham":
                        from camera import Ham
                        device_instance = Ham()
                        device_instance.start_acquisition()
                    case "Lucid":
                        from lucid import LucidCamera
                        device_instance = LucidCamera(max_tries=1, wait_time=1)
                        device_instance.start_acquisition()
                    case "PM":
                        from photometrics import PyVCAM
                        device_instance = PyVCAM() 
                        device_instance.start_acquisition()
                    case "IDS_Peak":
                        from peak import IDSPeakCamera
                        device_instance = IDSPeakCamera()
                        device_instance.start_acquisition()
                    case "PI-mte3":
                        from pi_camera import PICamera                        
                        device_instance = PICamera()
                        device_instance.start_acquisition()
                    case "VSY":
                        from new_vsy_camera import NewVSYCamera                     
                        device_instance = NewVSYCamera()
                    case "Galaxy":
                        from camera import GalaxyCamera                        
                        device_instance = GalaxyCamera()
                        device_instance.start_acquisition()
                    case "QHY":
                        from QHY import QHYCamera
                        device_instance = QHYCamera()
                        device_instance.set_bit_depth(16)
                        device_instance.start_acquisition()
                        

            elif self.device_type == 'stage':
                match(self.device_name):
                    case "NewPort":
                        from motion_controller import xps
                        device_instance = xps(IP='192.168.0.254')
                        device_instance.init_groups(['Group3', 'Group4'])
                    case "Nators":
                        from motion_controller import nators
                        device_instance = nators(ip_address="192.168.0.254")
                        device_instance.open_system()
                    case "SmartAct":
                        from motion_controller import smartact
                        device_instance = smartact()

            if device_instance:
                self.finished_signal.emit(True, device_instance)
            else:
                self.finished_signal.emit(False, f"未找到驱动: {self.device_name}")

        except Exception as e:
            self.finished_signal.emit(False, str(e))

# =========================================================
#  新增：后台扫描线程 (解决 UI 卡顿和采集同步问题)
# =========================================================
class ScanWorker(QThread):
    # 定义信号：用来告诉主界面更新
    # update_signal 传递: (图像数据, 当前X, 当前Y, 当前索引)
    update_signal = pyqtSignal(object, float, float, int) 
    log_signal = pyqtSignal(str, str) # (消息内容, 颜色类型)
    finished_signal = pyqtSignal()

    def __init__(self, camera, motion, scanner, exposure_time_ms, crop_params, dark_frame=None):
        super().__init__()
        self.camera = camera
        self.motion = motion
        self.scanner = scanner
        self.exposure_s = exposure_time_ms / 1000.0
        self.dark_frame = dark_frame
        
        # 解包裁剪参数 (width, height, off_x, off_y)
        self.target_w, self.target_h, self.off_x, self.off_y = crop_params
        
        self.is_running = True

    # 2. 新增一个不依赖 UI 的纯计算裁剪函数
    def worker_crop(self, full_image):
        if full_image is None: return None
        h_full, w_full = full_image.shape
        
        # 使用初始化时传进来的 int 变量，而不是读取 UI
        target_w = self.target_w
        target_h = self.target_h
        off_x = self.off_x
        off_y = self.off_y

        if target_w >= w_full and target_h >= h_full:
            return full_image

        center_x = w_full // 2 + off_x
        center_y = h_full // 2 + off_y
        
        x1 = int(center_x - target_w // 2)
        y1 = int(center_y - target_h // 2)
        x2 = x1 + target_w
        y2 = y1 + target_h
        
        # 边界检查
        if x1 < 0: 
            x1 = 0; x2 = target_w
        if y1 < 0:
            y1 = 0; y2 = target_h
        if x2 > w_full:
            x2 = w_full; x1 = w_full - target_w
        if y2 > h_full:
            y2 = h_full; y1 = h_full - target_h
            
        x1 = max(0, x1); y1 = max(0, y1)
        x2 = min(w_full, x2); y2 = min(h_full, y2)
        
        return full_image[y1:y2, x1:x2]

    def run(self):
        total = len(self.scanner.x)
        if hasattr(self.camera, 'set_trigger_mode'):
            # 停止实时流，准备精确采集
            self.camera.set_trigger_mode('software')
            # 给一点时间让相机反应
            time.sleep(0.2)  # 增加延迟时间

        for i in range(total):
            if not self.is_running: break

            # 1. 移动位移台
            dx = self.scanner.x[i]
            dy = self.scanner.y[i]
            
            # --- 移动逻辑 ---
            try:
                # 简单粗暴：直接调用 motion 的相对移动
                self.motion.move_by(dx, axis=0) # 假设 0 是 X
                self.motion.move_by(dy, axis=1) # 假设 1 是 Y
                # 给位移台足够的时间稳定
                time.sleep(0.2)  # 增加延迟时间
            except Exception as e:
                self.log_signal.emit(f"移动错误: {e}", "error")
                break

            # 2. 读取图像 - 多次尝试确保获取到有效图像
            max_retries = 3
            raw_img = None
            for attempt in range(max_retries):
                # 给相机足够的时间采集
                time.sleep(self.exposure_s * 1.5)  # 增加采集时间
                raw_img = self.camera.read_newest_image()
                if raw_img is not None:
                    # 检查图像是否为全黑
                    if np.max(raw_img) > 0:
                        break
                    else:
                        self.log_signal.emit(f"第 {i} 点第 {attempt+1} 次采集到全黑图像，重试...", "warning")
                else:
                    self.log_signal.emit(f"第 {i} 点第 {attempt+1} 次采集失败，重试...", "warning")
            
            if raw_img is not None:
                raw_img = self.worker_crop(raw_img)
            
            # 获取当前绝对坐标 (用于保存)
            # 如果驱动读坐标慢，可以用理论坐标代替，这里尝试读硬件
            cur_x = 0.0
            cur_y = 0.0
            try:
                if hasattr(self.motion, 'get_position'):
                    cur_x = self.motion.get_position(0)
                    cur_y = self.motion.get_position(1)
            except:
                self.log_signal.emit(f"读取坐标错误: {e}", "error")
                return

            if raw_img is not None:
                # 处理暗场 (如果在线程里做耗时计算，UI会更流畅)
                if self.dark_frame is not None:
                    # 先转换为uint16，然后再转换为int32进行减法，避免溢出
                    img_uint16 = raw_img.astype(np.uint16)
                    dark_uint16 = self.dark_frame.astype(np.uint16)
                    # 转换为int32进行减法，避免uint16溢出
                    img_int32 = img_uint16.astype(np.int32)
                    dark_int32 = dark_uint16.astype(np.int32)
                    subtracted = img_int32 - dark_int32
                    # 将负值设为0
                    subtracted[subtracted < 0] = 0
                    # 转换回uint16
                    final_data = subtracted.astype(np.uint16)
                else:
                    # 确保数据类型为uint16
                    if raw_img.dtype != np.uint16:
                        final_data = raw_img.astype(np.uint16)
                    else:
                        final_data = raw_img
                
                # 发送信号给主界面保存和显示
                self.update_signal.emit(final_data, cur_x, cur_y, i)
            else:
                self.log_signal.emit(f"第 {i} 点采集失败: 空图像", "warning")

        if hasattr(self.camera, 'set_trigger_mode'):
            # 停止实时流，准备精确采集
            self.camera.set_trigger_mode('continuous')
            # 给一点时间让相机反应
            time.sleep(0.1)
        # 循环结束
        self.finished_signal.emit()

    def stop(self):
        self.is_running = False

# =========================================================
#  自定义图像显示控件
# =========================================================
class InteractiveImageView(QGraphicsView):
    mouse_hover_signal = pyqtSignal(int, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pixmap_item = None
        self.np_img = None 
        self.setMouseTracking(True) 
        self.setStyleSheet("background: #000; border: 0px;")
        
        self.curr_img_x = -1
        self.curr_img_y = -1

        self.v_line = None
        self.h_line = None

    def update_image(self, image_data, show_mask=False):
        # ===========================
        # 1. 显示底图 (保持不变) 可能有问题
        # ===========================
        self.np_img = image_data
        if image_data.dtype == np.uint16:
            display_data = image_data.astype(np.uint16)
        else:
            display_data = image_data.astype(np.uint16) << 4

        h, w = display_data.shape
        qimg = QImage(display_data.data, w, h ,QImage.Format.Format_Grayscale16) #  w, h, 2*w,
        pix = QPixmap.fromImage(qimg)
        
        # 更新图片对象
        if self.pixmap_item is None:
            self.pixmap_item = self.scene.addPixmap(pix)
            self.pixmap_item.setZValue(0) # 图片永远在最底层
        else:
            self.pixmap_item.setPixmap(pix)

        # ===========================
        # 2. 核心修复：Mask 绘制逻辑
        # ===========================
        
        # --- 第一步：清理战场 ---
        if getattr(self, 'v_line', None): 
            self.scene.removeItem(self.v_line)
            self.v_line = None
            
        if getattr(self, 'h_line', None): 
            self.scene.removeItem(self.h_line)
            self.h_line = None
            
        if getattr(self, 'circle', None): 
            self.scene.removeItem(self.circle)
            self.circle = None

        # --- 第二步：如果勾选了显示，则重新绘制 ---
        if show_mask:
            cx, cy = w / 2, h / 2
            r = min(w, h) / 2 - 10  # 半径设为图像的 1/4

            # 定义笔 (颜色, 粗细, 样式)
            pen_v = QPen(QColor("red"), 2, Qt.PenStyle.DashLine)
            pen_h = QPen(QColor("blue"), 2, Qt.PenStyle.DashLine)
            pen_c = QPen(QColor("green"), 2, Qt.PenStyle.SolidLine)

            # 重新添加到场景中
            self.v_line = self.scene.addLine(cx, 0, cx, h, pen_v)
            self.h_line = self.scene.addLine(0, cy, w, cy, pen_h)
            self.circle = self.scene.addEllipse(cx-r, cy-r, r*2, r*2, pen_c)

            # 设为顶层，确保不被图片遮挡
            self.v_line.setZValue(10)
            self.h_line.setZValue(10)
            self.circle.setZValue(10)

        # 自动适应视图大小
        self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def mouseMoveEvent(self, event):
        if self.np_img is not None and self.pixmap_item is not None:
            scene_pos = self.mapToScene(event.pos())
            item_pos = self.pixmap_item.mapFromScene(scene_pos)
            x, y = int(item_pos.x()), int(item_pos.y())

            h, w = self.np_img.shape
            if 0 <= x < w and 0 <= y < h:
                val = self.np_img[y, x]
                self.mouse_hover_signal.emit(x, y, val)
            else:
                self.mouse_hover_signal.emit(-1, -1, 0)
        super().mouseMoveEvent(event)

# =========================================================
#  主逻辑窗口
# =========================================================
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
        self.is_init = False
        self.dp = []
        self.pos_x = []
        self.pos_y = [] 
        
        # 实时流定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame) 
        self.is_live = False
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.image_view.mouse_hover_signal.connect(self.on_mouse_moved)
        self.default_save_dir = "please change this to your own path"
        self.dark_frame = None
        self.save_dir = self.default_save_dir
        self.pixel_size = 3.45e-3

        # --- 3. 信号绑定 ---
        self.btn_open_cam.clicked.connect(self.start_init_camera)
        self.btn_connect_stage.clicked.connect(self.start_init_motion)
        
        self.btn_live.clicked.connect(self.toggle_live)
        self.btn_cap.clicked.connect(self.start_scan)
        self.btn_save.clicked.connect(self.on_manual_save)
        self.btn_browse.clicked.connect(self.select_folder)
        self.btn_show_path.clicked.connect(self.preview_scan_path)

        # 位移台控制
        self.stage_widget.btn_up.clicked.connect(lambda: self.move_stage_manual('Y', 1))
        self.stage_widget.btn_down.clicked.connect(lambda: self.move_stage_manual('Y', -1))
        self.stage_widget.btn_left.clicked.connect(lambda: self.move_stage_manual('X', -1))
        self.stage_widget.btn_right.clicked.connect(lambda: self.move_stage_manual('X', 1))
        self.stage_widget.btn_go.clicked.connect(self.move_stage_absolute)
        self.stage_widget.btn_zero.clicked.connect(self.zero_stage)

        # 辅助功能
        self.btn_center.clicked.connect(self.calculate_center)
        self.exposure_spin.valueChanged.connect(self.set_exposure_time)

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        """全局异常捕获"""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        print(error_msg, file=sys.stderr)
        
        header = f"⛔ 【系统崩溃/错误】 {exc_type.__name__}: {exc_value}"
        self.log_error(header + "\n" + error_msg)

    # =====================================================
    # 【新增】改进的日志函数
    # =====================================================
    def log_info(self, msg):
        """信息日志 - 蓝色"""
        timestamp = time.strftime("%H:%M:%S")
        html = f"<span style='color:#2196F3;'><b>[{timestamp}]</b> ℹ️ {msg}</span>"
        self.txt_log.appendHtml(html)
        self._scroll_to_bottom()
    
    def log_success(self, msg):
        """成功日志 - 绿色"""
        timestamp = time.strftime("%H:%M:%S")
        html = f"<span style='color:#4CAF50;'><b>[{timestamp}]</b> ✅ {msg}</span>"
        self.txt_log.appendHtml(html)   
        self._scroll_to_bottom()
    
    def log_warning(self, msg):
        """警告日志 - 橙色"""
        timestamp = time.strftime("%H:%M:%S")
        html = f"<span style='color:#FF9800;'><b>[{timestamp}]</b> ⚠️ {msg}</span>"
        self.txt_log.appendHtml(html)
        self._scroll_to_bottom()
    
    def log_error(self, msg):
        """错误日志 - 红色"""
        timestamp = time.strftime("%H:%M:%S")
        html = f"<span style='color:#F44336;'><b>[{timestamp}]</b> ❌ {msg}</span>"
        self.txt_log.appendHtml(html)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        """自动滚动到底部"""
        scrollbar = self.txt_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def on_mouse_moved(self, x, y, val):
        if x >= 0 and y >= 0:
            self.last_mouse_x = x
            self.last_mouse_y = y
            self.update_pixel_display(val)

    def update_pixel_display(self, val):
        if val is None: return 
        
        self.line_mouse_val.setText(f"{val}")
        
        if val >= self.saturation_value:
            self.line_mouse_val.setStyleSheet("color: red; font-weight: bold; background: #ffeeee;")
        else:
            self.line_mouse_val.setStyleSheet("color: blue; font-weight: bold; background: #f0f0f0;")

    # --- 异步加载设备 ---
    def start_init_camera(self):
        """步骤1: 仅仅负责启动线程"""
        cam_name = self.combo_camera.currentText()
        self.log_info(f"正在初始化相机: {cam_name}...")
        self.btn_open_cam.setEnabled(False) # 禁用按钮防止重复点击
        
        # 创建并启动线程
        self.loader_thread_cam = DeviceLoader('camera', cam_name)
        # 【关键】将线程结束的信号，连接到下面的回调函数
        self.loader_thread_cam.finished_signal.connect(self.on_camera_loaded)
        self.loader_thread_cam.start()

    def on_camera_loaded(self, success, result):
        """步骤2: 线程跑完后自动运行这里，处理结果"""
        self.btn_open_cam.setEnabled(True) # 恢复按钮
        
        if success:
            self.camera = result
            self.btn_open_cam.setText("已就绪")
            self.btn_open_cam.setStyleSheet("background-color: #4CAF50; color: white;")
            
            # --- 相机参数初始化逻辑 ---
            # 1. 应用曝光
            self.set_exposure_time()

            # 2. 获取位深
            bit_depth = 16 
            try:
                if hasattr(self.camera, 'get_bit_depth'):
                    bit_depth = int(self.camera.get_bit_depth())
                elif hasattr(self.camera, 'bit_depth'):
                    bit_depth = int(self.camera.bit_depth)
                elif hasattr(self.camera, 'BitDepth'):
                    bit_depth = int(self.camera.BitDepth)
            except Exception as e:
                self.log_warning(f"获取位深失败，使用默认值 16: {e}")

            # 3. 计算饱和值
            self.saturation_value = (1 << bit_depth) - 1
            
            self.line_cam_max.setText(f"{self.saturation_value} ({bit_depth}-bit)")
            self.log_success(f"相机就绪 | 位深: {bit_depth} | 饱和阈值: {self.saturation_value}")
            
        else:
            self.log_error(f"相机初始化失败: {result}")

    def start_init_motion(self):
        stage_name = self.combo_stage.currentText()
        self.log_info(f"正在连接位移台: {stage_name}...")
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

    def sync_hardware_position(self):
        """标准逻辑：读取硬件当前的绝对位置更新到软件"""
        if not self.motion: return
        
        hw_x, hw_y = 0.0, 0.0
        success = False

        try:     
            # 1. 尝试通用接口 get_position(axis)
            if hasattr(self.motion, 'get_position'):
                hw_x = float(self.motion.get_position(0))
                hw_y = float(self.motion.get_position(1))
                success = True
            
            # 2. 针对特定控制器的特殊处理 (XPS, SmartAct)
            elif hasattr(self.motion, 'xps') and hasattr(self.motion, 'groups'):
                if len(self.motion.groups) >= 2:
                    g0 = self.motion.groups[0]
                    g1 = self.motion.groups[1]
                    hw_x = self.motion.xps.get_stage_position(f'{g0}.Pos')
                    hw_y = self.motion.xps.get_stage_position(f'{g1}.Pos')
                    success = True
                
            if success:
                # [关键] 这里更新显示的 Label，而不是 Target 输入框
                # 显示给用户看的是 lbl_x / lbl_y
                self.stage_widget.lbl_x.setText(f"X: {hw_x:.3f} mm")
                self.stage_widget.lbl_y.setText(f"Y: {hw_y:.3f} mm")
                
                self.stage_widget.target_x.blockSignals(True)
                self.stage_widget.target_y.blockSignals(True)
                
                # 安全地修改文本，此时绝对不会触发 move_stage_absolute
                self.stage_widget.target_x.setText(f"{hw_x:.3f}")
                self.stage_widget.target_y.setText(f"{hw_y:.3f}")
                
                # 修改完后，必须恢复信号，否则用户手动输入回车也没反应了
                self.stage_widget.target_x.blockSignals(False)
                self.stage_widget.target_y.blockSignals(False)
            else:
                self.log_warning("无法同步硬件位置")

        except Exception as e:
            self.stage_widget.target_x.blockSignals(False)
            self.stage_widget.target_y.blockSignals(False)
            self.log_error(f"同步位置异常: {e}")


    # --- 图像处理核心逻辑 ---
    def crop_image(self, full_image):
        if full_image is None: return None
        h_full, w_full = full_image.shape
        
        try:
            target_w = int(self.roi_w.text()) # 假设这是 QLineEdit，如果是 SpinBox 用 .value()
            target_h = int(self.roi_h.text())
        except:
            target_w = 1024
            target_h = 1024

        if target_w >= w_full and target_h >= h_full:
            self.log_info("ROI 大于等于图像尺寸，无需裁剪")
            return full_image

        try:
            off_x = int(self.off_x.text())
            off_y = int(self.off_y.text())
        except:
            off_x = 0
            off_y = 0
        
        center_x = w_full // 2 + off_x
        center_y = h_full // 2 + off_y
        
        x1 = int(center_x - target_w // 2)
        y1 = int(center_y - target_h // 2)
        x2 = x1 + target_w
        y2 = y1 + target_h
        
        if x1 < 0: 
            x1 = 0
            x2 = target_w
        if y1 < 0:
            y1 = 0
            y2 = target_h
        if x2 > w_full:
            x2 = w_full
            x1 = w_full - target_w
        if y2 > h_full:
            y2 = h_full
            y1 = h_full - target_h
            
        # 最后的安全检查
        x1 = max(0, x1); y1 = max(0, y1)
        x2 = min(w_full, x2); y2 = min(h_full, y2)
        
        return full_image[y1:y2, x1:x2]

    def update_frame(self):
        if self.camera:
            try:
                if type(self.camera).__name__ == "NewVSYCamera":
                    self.camera.start_acquisition()

                # 1. 获取并裁剪图像
                img = self.camera.read_newest_image()
                if img is None: return
                cropped_img = self.crop_image(img)
                
                # ==========================================
                # 【恢复】 2. 全局最大值监测与饱和报警
                # ==========================================
                max_val = np.max(cropped_img)
                self.line_global_max.setText(f"{max_val}")
                
                # 检查是否过曝
                limit = getattr(self, 'saturation_value', 65535)
                
                if max_val >= limit:
                    self.line_global_max.setStyleSheet("color: red; font-weight: bold; background: #ffeeee;")
                else:
                    self.line_global_max.setStyleSheet("color: green; font-weight: bold; background: #f0f0f0;")

                # ==========================================
                # 【恢复】 3. 处理 Log 显示和 Mask
                # ==========================================
                # 获取 Mask 勾选状态
                show_mask = self.chk_mask.isChecked()
                
                # 处理 Log 变换
                if self.chk_log.isChecked():
                    # log(1+x) 变换，拉伸暗部细节
                    img_disp = np.log1p(cropped_img.astype(np.uint16))
                    # 归一化回原来的位深范围，以便显示
                    img_disp = (img_disp / img_disp.max() * limit).astype(np.uint16)
                    self.image_view.update_image(img_disp, show_mask)
                else:
                    # 正常线性显示
                    self.image_view.update_image(cropped_img, show_mask)

                # ==========================================
                # 【保留】 4. 鼠标悬停数值更新 (防止 ROI 变化导致越界)
                # ==========================================
                h, w = cropped_img.shape
                if 0 <= self.last_mouse_x < w and 0 <= self.last_mouse_y < h:
                    # 从【原始数据】中取出值 (即使在 Log 模式下，也显示原始光子数)
                    current_val = cropped_img[self.last_mouse_y, self.last_mouse_x]
                    self.update_pixel_display(current_val)
                else:
                    # 越界重置
                    self.last_mouse_x = w // 2
                    self.last_mouse_y = h // 2
            
            except Exception as e:
                self.log_error(f"更新图像时出错: {e}")

    def toggle_live(self):
        if not self.camera:
            self.log_warning("请先连接并初始化相机！")
            return

        if self.is_live:
            # === 如果当前是启动状态，则停止 ===
            self.timer.stop()  # 停止定时器
            self.is_live = False
            
            # 更新按钮样式
            self.btn_live.setText("👁 启动")
            self.btn_live.setStyleSheet("background:#27ae60;color:white;font-weight:bold;")
            self.log_info("实时显示已停止")
            
        else:
            # 根据您相机的曝光时间，这个值可以调整，比如 30 或 100
            exposure_ms = self.exposure_spin.value()
            refresh_interval = max(30, int(exposure_ms)) 
            
            self.timer.start(refresh_interval)
            self.is_live = True
            
            # 更新按钮样式
            self.btn_live.setText("⬛ 停止")
            self.btn_live.setStyleSheet("background:#7f8c8d;color:white;font-weight:bold;")
            self.log_success("实时显示已启动")

    def calculate_center(self): #todo
        if not self.camera:
            self.log_warning("相机未连接")
            return

        H, W = cropped_img.shape
        
    # --- 位移台逻辑 ---
    def update_stage_display(self):
        self.stage_widget.lbl_x.setText(f"X: {self.stage_widget.target_x.text()} mm")
        self.stage_widget.lbl_y.setText(f"Y: {self.stage_widget.target_y.text()} mm")

    def move_stage_manual(self, axis_name, direction):
        if not self.motion:
            self.log_warning("位移台未连接")
            return
        stage_step = self.stage_widget.step_spin.value()
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
            
        dist = stage_step * direction
        try:
            # 1. 执行相对移动
            self.motion.move_by(dist, axis=target_axis)
            self.sync_hardware_position()
            
        except Exception as e:
            self.log_error(f"移动失败: {e}")

    def move_stage_absolute(self):
        if not self.motion: return
        try:
            target_x = float(self.stage_widget.target_x.text())
            target_y = float(self.stage_widget.target_y.text())
        except ValueError:
            self.log_error("坐标输入格式错误，请输入数字")
            return
        
        self.log_success(f"移动至绝对位置: ({target_x}, {target_y})...")
        
        try:
            # 方案 A: 优先使用绝对移动接口 (更准)
            if hasattr(self.motion, 'move_to'):
                # 处理轴交换
                is_swap = self.stage_widget.check_swap.isChecked()
                
                # 简单逻辑：如果不交换，0是X；如果交换，1是X
                ax_x = 1 if is_swap else 0
                ax_y = 0 if is_swap else 1
                
                self.motion.move_to(target_x, axis=ax_x)
                self.motion.move_to(target_y, axis=ax_y)
            
            else:
                # 方案 B: 如果只有 move_by，则需要先读取当前位置算差值
                current_x_str = self.stage_widget.lbl_x.text().split(':')[-1].replace('mm','').strip()
                current_y_str = self.stage_widget.lbl_y.text().split(':')[-1].replace('mm','').strip()
                
                cur_x = float(current_x_str) if current_x_str else 0.0
                cur_y = float(current_y_str) if current_y_str else 0.0
                
                dx = target_x - cur_x
                dy = target_y - cur_y
                
                if abs(dx) > 1e-6: self._move_logical_delta(dx, 0)
                if abs(dy) > 1e-6: self._move_logical_delta(dy, 1)

            # 无论哪种方式，移动完最后都要同步显示
            self.sync_hardware_position()
            self.log_success(f"移动完成")
                
        except Exception as e:
            self.log_error(f"绝对移动失败: {e}")

    def _move_logical_delta(self, delta, logical_axis_idx): 
        """
        执行相对移动，并在移动后直接读取硬件位置更新界面。
        """
        # 1. 获取轴映射设置
        is_swap = self.stage_widget.check_swap.isChecked()
        inv_x = self.stage_widget.check_inv_x.isChecked()
        inv_y = self.stage_widget.check_inv_y.isChecked()
        
        phys_axis = 0
        phys_dist = delta
        
        # 2. 计算物理轴和方向
        if logical_axis_idx == 0: # 逻辑 X 轴
            phys_axis = 1 if is_swap else 0
            if inv_x: phys_dist *= -1
        else: # 逻辑 Y 轴
            phys_axis = 0 if is_swap else 1
            if inv_y: phys_dist *= -1
            
        # 3. 执行物理移动
        if self.motion:
            try:
                # 发送移动指令
                self.motion.move_by(phys_dist, axis=phys_axis)
                
                # 可选：如果电机响应慢，可以加一点微小的延时，确保读回来的是移动后的值
                # time.sleep(0.05) 
                
                self.sync_hardware_position()
                
            except Exception as e:
                self.log_error(f"相对移动失败: {e}")

    def zero_stage(self):
        if not self.motion:
            self.log_warning("位移台未连接")
            return

        try:
            # 尝试调用硬件的绝对移动接口
            # 假设驱动通过 move_to(position, axis) 实现
            # Axis 0 = X, Axis 1 = Y
            self.motion.move_to(self.zero_stage_x, axis=0)
            self.motion.move_to(self.zero_stage_y, axis=1)
            
            # 移动完成后，同步硬件位置显示
            self.sync_hardware_position()
            self.log_success("回零完成")
            
        except AttributeError:
            # 如果驱动没有 move_to，尝试其他常见命名
            self.log_warning("驱动未提供标准 move_to 接口，尝试 set_position 0...")
            try:
                # 某些驱动可能是 set_position
                if hasattr(self.motion, 'move_absolute'):
                    self.motion.move_absolute(0, axis=0)
                    self.motion.move_absolute(0, axis=1)
                    self.sync_hardware_position()
            except Exception as e:
                self.log_error(f"回零失败: {e}")

    def preview_scan_path(self):
        try:
            from Scanner import Scanner
            mode_map = {
                "矩形": "rectangle", 
                "圆形": "round", 
                "螺旋": "fermat"
            }
            # 获取当前选中的模式文本，并映射到英文key
            ui_mode_text = self.combo_scan_mode.currentText()
            mode = mode_map.get(ui_mode_text, "round") # 默认 fallback 到 round
            
            # 2. 获取圈数
            try:
                scan_range_x = float(self.scan_range_x.text())
                scan_range_y = float(self.scan_range_y.text())
            except ValueError: scan_range_x = scan_range_y = 1

            try:
                scan_step = float(self.scan_step.text())
            except ValueError: scan_step = 0.1
            
            # 4. 生成 Scanner 对象
            self.scanner = Scanner(step=scan_step, scan_range_x=scan_range_x, scan_range_y=scan_range_y, mode=mode)
            
            # 5. 更新 UI 上的采集点数显示
            total_points = len(self.scanner.x)
            self.scan_points.setText(str(total_points))
            self.log_success(f"生成扫描路径: {ui_mode_text}, 总点数: {total_points}")

            # 6. 绘制预览
            plt.style.use('default')
            fig, ax = plt.subplots(figsize=(4, 3), dpi=100)
            x_pts = np.array(self.scanner.abs_x)
            y_pts = np.array(self.scanner.abs_y)
            
            # 绘制路径连线
            ax.plot(x_pts, y_pts, 'b.-', markersize=2, linewidth=0.5, alpha=0.6)
            
            ax.set_aspect('equal')
            ax.grid(True, linestyle=':', alpha=0.5)
            plt.tight_layout()

            buf = io.BytesIO()
            fig.savefig(buf, format='png')
            plt.close(fig)
            buf.seek(0)
            
            qimg = QImage.fromData(buf.getvalue())
            pixmap = QPixmap.fromImage(qimg)
            self.lbl_scan_preview.setPixmap(pixmap)
            self.lbl_scan_preview.setScaledContents(True)

        except Exception as e:
            self.log_error(f"生成路径失败: {e}")
            traceback.print_exc()

    def confirm_directory(self):
        """
        弹出确认框，询问用户目录是否正确。
        返回: True (用户点Yes), False (用户点No)
        """
        current_dir = self.save_dir_edit.text().strip()
        
        # 1. 检查是否为空
        if not current_dir:
            QMessageBox.warning(self, "路径错误", "保存目录不能为空!")
            return False
        
        # 2. 检查是否还是默认值
        if current_dir == self.default_save_dir:
            reply = QMessageBox.warning(
                self, 
                "⚠️ 目录未更改", 
                "请修改保存目录!",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # 假设 Yes 意味着 "我要去改"，则返回 False 阻止采集
                return False
            else:
                # No 意味着取消操作
                return False
        
        # 3. 更新并确保目录存在
        self.save_dir = current_dir
        if not os.path.exists(self.save_dir):
            try:
                os.makedirs(self.save_dir)
                self.log_success(f"已创建目录: {self.save_dir}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法创建目录:\n{e}")
                return False
        
        return True

    def start_scan(self):
        # 1. 检查目录
        if not self.confirm_directory():
            return

        # 2. 路径检查
        self.preview_scan_path()
        if not getattr(self, 'scanner', None): 
            self.log_error("扫描器未初始化")
            return

        if self.dark_frame is None:
            confirm = QMessageBox.question(
                self, 
                "暗场检查",                 # <--- 这里是标题 (Title)
                "是否采集当前环境的暗场？",   # <--- 这里是内容 (Text)
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if confirm == QMessageBox.StandardButton.Yes:
                img_dark = self.camera.read_newest_image()
                if img_dark is None:
                    self.log_error("暗场采集失败：无法获取图像")
                    return
                img_dark = self.crop_image(img_dark)
                if img_dark is None:
                    self.log_error("暗场采集失败：图像裁剪失败")
                    return
                self.dark_frame = img_dark.astype(np.uint16)
                self.log_success("暗场采集完成")
                path_dark = os.path.join(self.save_dir, f"dark.tif")
                try:
                    if img_dark.dtype == np.uint16 or img_dark.dtype == np.uint8:
                        Image.fromarray(img_dark).save(path_dark)
                    else:
                        Image.fromarray(img_dark.astype(np.uint16)).save(path_dark)
                except Exception as e:
                    self.log_error(f"暗场保存失败: {e}")
            else:
                self.log_info("采集已取消")
                return
        
        if self.dark_frame is not None:
            confirm = QMessageBox.question(
                self, 
                "采集检查",                 # <--- 这里是标题 (Title)
                "是否开始采集？",   # <--- 这里是内容 (Text)
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if confirm == QMessageBox.StandardButton.Yes:
                pass
            else:
                self.log_info("采集已取消")
                return

        # 4. 设置文件名
        self.current_scan_h5_name = f"scandata.h5"
        self.log_info(f"开始采集 {len(self.scanner.x)} 点... 数据将暂存内存")

        exposure_val = self.exposure_spin.value()

        try:
            w = int(self.roi_w.text())
            h = int(self.roi_h.text())
        except:
            w, h = 1024, 1024
        
        try:
            ox = int(self.off_x.text())
            oy = int(self.off_y.text())
        except:
            ox, oy = 0, 0
            
        crop_params_tuple = (w, h, ox, oy) # 打包成元组

        self.dp = []
        self.pos_x = []
        self.pos_y = []

        # === 【修改】 实例化 Worker 时传入参数 ===
        self.worker = ScanWorker(
            camera=self.camera,
            motion=self.motion,
            scanner=self.scanner,
            exposure_time_ms=exposure_val,
            crop_params=crop_params_tuple,  # <--- 传入这里
            dark_frame=self.dark_frame
        )
        self.worker.update_signal.connect(self._update_scan_preview)
        self.worker.log_signal.connect(self._worker_log)
        self.worker.finished_signal.connect(self._scan_finished)

        if self.is_live:
            self.timer.stop()
            self.is_live = False
            self.btn_live.setText("🟢 启动")
            self.btn_live.setStyleSheet("background:#27ae60;color:white;font-weight:bold;")
            self.was_live_before_scan = True
            self.log_info("为保证采集稳定,已暂停实时显示")
            
            # 【关键】让相机停止连续采集
            if hasattr(self.camera, 'stop_acquisition'):
                self.camera.stop_acquisition()
            time.sleep(0.3)  # 给更长时间让buffer清空

        self.worker.start()

    def _worker_log(self, msg, level):
        """
        处理子线程发来的日志信号
        ScanWorker.log_signal -> (msg, level)
        """
        if level == "error":
            self.log_error(msg)
        elif level == "warning":
            self.log_warning(msg)
        elif level == "success":
            self.log_success(msg)
        else:
            self.log_info(msg)

    def _update_scan_preview(self, img_data, cur_x, cur_y, idx):
        """
        处理子线程发来的图像更新信号
        ScanWorker.update_signal -> (img_data, cur_x, cur_y, idx)
        此函数替代了原本未使用的 on_scan_step_received
        """
        # 1. 将数据存入内存列表 (这是最关键的一步，否则最后保存为空)
        self.dp.append(img_data)
        self.pos_x.append(cur_x)
        self.pos_y.append(cur_y)
        
        # 2. 更新界面图像显示
        # 检查是否需要显示 Mask (十字准星)
        show_mask = self.chk_mask.isChecked()
        self.image_view.update_image(img_data, show_mask=show_mask)

        frame_name = f"scan_{idx:03d}.tif"
        path = os.path.join(self.save_dir, frame_name)
        try:
            # 直接保存 raw
            if img_data.dtype != np.uint8 and img_data.dtype != np.uint16:
                save_data = img_data.astype(np.uint16)
            else:
                save_data = img_data
            Image.fromarray(save_data).save(path)
        except Exception as e:
            print(f"单帧保存失败: {e}")

    def _scan_finished(self):
        self.log_info("扫描线程结束，正在写入 H5...")
        
        self.dark_frame = None

        # 写入 H5
        self._write_scan_to_h5(self.dp, self.pos_x, self.pos_y)
        self.log_success("H5 文件写入完成！")
        
        # 回到原点
        final_x = self.scanner.final_pos[0]
        final_y = self.scanner.final_pos[1]
        self._move_logical_delta(-final_x, 0)
        self._move_logical_delta(-final_y, 1)

        if getattr(self, 'was_live_before_scan', False):
            self.log_info("自动恢复实时显示...")
            self.toggle_live() # 直接调用 toggle 函数重新启动

    def _write_scan_to_h5(self,dp, pos_x, pos_y, h5_path=None):
        """
        将当前扫描数据写入 H5 文件。(dp, pos_x, pos_y, wl)
        """
        if not h5_path:
            h5_path = os.path.join(self.save_dir, "raw_data", self.current_scan_h5_name)
        try:
            os.makedirs(os.path.dirname(h5_path), exist_ok=True)
        except:
            pass
        
        try:  
                # --- 将 Data 写入 H5 ---
            dp_arr = np.array(dp)       
            pos_x = np.array(pos_x)
            pos_y = np.array(pos_y)

            with h5py.File(h5_path, 'a') as f:    
                if "data" in f:
                    del f["data"]
                if "x" in f:
                    del f["x"]
                if "y" in f:
                    del f["y"]

                # 1. 写入图像数据
                f.create_dataset(
                    "data", 
                    data=dp_arr,        # 使用转换后的 numpy 数组
                    compression="gzip"  # 只有 numpy 数组才能支持压缩
                )             
                f.create_dataset(
                    "x", 
                    data=pos_x,        # 使用转换后的 numpy 数组
                    compression="gzip"  # 只有 numpy 数组才能支持压缩
                )
                f.create_dataset(
                    "y", 
                    data=pos_y,        # 使用转换后的 numpy 数组
                    compression="gzip"  # 只有 numpy 数组才能支持压缩
                )
                f.attrs['wavelength'] = np.array([float(self.wavelength_spin.text())])
                f.attrs['pixel_size'] = np.array([float(self.pixel_size)])
                try:
                    ox = int(self.off_x.text())
                    oy = int(self.off_y.text())
                except:
                    try:
                        ox = int(self.off_x.value())
                        oy = int(self.off_y.value())
                    except:
                        ox, oy = 0, 0
                f.attrs['offset_x'] = np.array([float(ox)])
                f.attrs['offset_y'] = np.array([float(oy)])
                try:
                    rw = int(self.roi_w.text())
                    rh = int(self.roi_h.text())
                except:
                    rh = int(dp_arr.shape[1]) if dp_arr.ndim >= 2 else 0
                    rw = int(dp_arr.shape[2]) if dp_arr.ndim >= 3 else 0
                f.attrs['detector_size'] = np.array([rw, rh])
                f.attrs['exposure_time'] = np.array([float(self.exposure_spin.value())])
                
                # 4. 其他属性
                # 注意：原代码 dp.shape[0] 如果 dp 是 list 会报错，必须用 len(dp) 或 dp_arr.shape[0]
                f.attrs['total_frames'] = dp_arr.shape[0] 
                f.attrs['timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')

        except Exception as e:
            self.log_error(f"H5 保存失败: {e}")
            traceback.print_exc()

    def set_exposure_time(self):
        if self.camera:
            val = self.exposure_spin.value()
            self.camera.set_ex_time(val / 1000.0)
            self.log_info(f"曝光: {val} ms")

    def select_folder(self):
        path = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if path:
            self.save_dir_edit.setText(path)
            self.save_dir = path

    def on_manual_save(self):
        """响应'保存'按钮：保存当前视图为 tif"""
        if not self.confirm_directory():
            return
        
        default_name = f"image_{time.strftime('%H%M%S')}"
        filename, ok = QInputDialog.getText(
            self, "保存当前视图", "请输入文件名:", text=default_name
        )
        
        if ok and filename.strip():
            final_name = filename.strip()
            
            # 1. 调用通用函数保存 TIF，并获取数据 (save_current_frame只负责保存TIF和返回数据)
            img_data = self.save_current_frame(base_name=final_name)
            
            if img_data is None:
                self.log_error("无法获取图像数据，保存中止")
                return
        else:
            self.log_info("保存已取消")

    def save_current_frame(self, base_name=None):
        """
        功能：
        1. 获取并裁剪图像
        2. 保存为 TIF (可视化用)
        3. 返回 (image_data, cur_x, cur_y) 供 Dataclass 或 H5 写入使用
        """
        if not self.camera: 
            return None

        try:
            # 1. 获取并裁剪图像
            full_img = self.camera.read_newest_image()
            if full_img is None: 
                return None
            
            roi_img = self.crop_image(full_img)
            if roi_img is None: 
                return None
            
            # 获取当前坐标
            try:
                cur_x = float(self.stage_widget.target_x.text())
                cur_y = float(self.stage_widget.target_y.text())
            except:
                cur_x, cur_y = 0.0, 0.0

            # 2. 准备路径并保存 TIF
            if not base_name:
                base_name = f"capture_{int(time.time())}"
            # 确保没有后缀
            base_name = os.path.splitext(base_name)[0]

            if not os.path.exists(self.save_dir): 
                os.makedirs(self.save_dir)
            
            path_tif = os.path.join(self.save_dir, f"{base_name}.tif")

            try:
                Image.fromarray(roi_img).save(path_tif)
                self.log_info(f"图片已保存: {base_name}.tif")
            except Exception as e:
                self.log_warning(f"TIF保存失败: {e}")   

            # 3. 返回原始数据
            return roi_img, cur_x, cur_y

        except Exception as e:
            self.log_error(f"保存帧异常: {e}")
            traceback.print_exc()
            return None, 0, 0

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LogicWindow()
    window.show()
    sys.exit(app.exec())

