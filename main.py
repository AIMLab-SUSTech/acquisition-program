import sys
import os
import time
import io
import importlib
import threading
from pathlib import Path
import numpy as np
from PIL import Image
import traceback
import h5py
import shutil

# PyQt6 导入
from PyQt6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QVBoxLayout, QFileDialog, QMessageBox, QInputDialog
from PyQt6.QtGui import QImage, QPixmap, QPen, QColor
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QThread, QElapsedTimer

# 导入 UI 定义
from UI import ModernUI

# 不依赖启动程序时的当前工作目录。
PROJECT_ROOT = Path(__file__).resolve().parent
DRIVER_ROOT = PROJECT_ROOT / "hardware"
PE_LIBRARY_DIR = DRIVER_ROOT / "PE" / "extern" / "lib"
_DLL_DIRECTORY_HANDLES = []
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _register_dll_directory(directory):
    """把原生 DLL 及其依赖所在目录加入 Windows 搜索路径。"""
    directory = Path(directory).resolve()
    if not directory.is_dir():
        return

    directory_text = str(directory)
    path_items = os.environ.get("PATH", "").split(os.pathsep)
    if directory_text not in path_items:
        os.environ["PATH"] = directory_text + os.pathsep + os.environ.get("PATH", "")

    if os.name == "nt" and hasattr(os, "add_dll_directory"):
        try:
            # handle 必须保持存活，否则搜索路径会被立即移除。
            _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(directory_text))
        except OSError:
            pass


def _load_driver_module(vendor, module_name, extra_dll_dirs=()):
    """从 dll/<vendor> 加载驱动，并兼容驱动内部的同目录 import。"""
    driver_dir = (DRIVER_ROOT / vendor).resolve()
    module_file = driver_dir / f"{module_name}.py"
    if not module_file.is_file():
        raise ImportError(f"驱动文件不存在: {module_file}")

    driver_path = str(driver_dir)
    if driver_path not in sys.path:
        sys.path.insert(0, driver_path)

    _register_dll_directory(driver_dir)
    for dll_dir in extra_dll_dirs:
        _register_dll_directory(dll_dir)
    return importlib.import_module(module_name)

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
                        device_instance.set_pixel_rate(7e7)
                    case "PCO":
                        from camera import PCOCamera
                        device_instance = PCOCamera()   
                    case "Thorlabs":
                        module = _load_driver_module(
                            "Thorlabs", "thorlabs_camera"
                        )
                        device_instance = module.ThorlabsCamera()
                    case "QHY":
                        module = _load_driver_module("QHY", "QHY")
                        device_instance = module.QHYCamera()
                        device_instance.set_bit_depth(16) 
                    case "Hik":
                        module = _load_driver_module("Hik", "hik")
                        device_instance = module.HikrobotCamera()
                    case "SSZN":
                        module = _load_driver_module(
                            "SSZN", "SSZNCamera", extra_dll_dirs=(PE_LIBRARY_DIR,)
                        )
                        device_instance = module.SSZNCamera() 
                        if not device_instance.connect():
                            raise RuntimeError("SSZN 相机连接失败")
                    case "SC":
                        sc_sdk_home = os.getenv("Revealer_Scientific_Camera_SDK_HOME")
                        extra_dirs = ((Path(sc_sdk_home) / "bin",) if sc_sdk_home else ())
                        module = _load_driver_module(
                            "SC", "SCSDKCamera", extra_dll_dirs=extra_dirs
                        )
                        sc_index = module.find_camera_index()
                        if sc_index < 0:
                            raise RuntimeError("SC 相机连接失败：未发现可用相机（已跳过虚拟相机）")
                        device_instance = module.SCSDKCamera(sc_index)
                    case "Galaxy":
                        module = _load_driver_module("Galaxy", "GalaxyCamera")
                        device_instance = module.GalaxyCamera()
                        
            elif self.device_type == 'stage':
                match(self.device_name):
                    case "NewPort":
                        from motion_controller import xps
                        device_instance = xps(IP='192.168.254.254')
                        device_instance.init_groups(['Group1', 'Group2'])
                    case "newports":
                        module = _load_driver_module("NewPort", "conexcc_controller")
                        # todo port 
                        device_instance = module.ConexCCController()
                    case "Ami":
                        module = _load_driver_module("Ami", "Ami")
                        device_instance = module.PvcsvrController(
                            exe_path=str(DRIVER_ROOT / "Ami" / "pvcsvr.exe")
                        )
                        try:
                            device_instance.connect_and_enable()
                            device_instance.enable_channel(1, True)
                            device_instance.enable_channel(2, True)
                        except Exception as e:
                            raise RuntimeError(f"AMI 初始化失败: {e}") from e
                    case "Ami(双控制器)":
                        module = _load_driver_module("Ami", "dual_ami")
                        device_instance = module.DualAmiController(
                            exe_path=str(DRIVER_ROOT / "Ami" / "pvcsvr.exe"), x_axis=1
                        )
                        try:
                            device_instance.connect()
                            device_instance.enable_channels()
                        except Exception as e:
                            raise RuntimeError(f"双 AMI 初始化失败: {e}") from e

            if device_instance:
                self.finished_signal.emit(True, device_instance)
            else:
                self.finished_signal.emit(False, f"未找到驱动: {self.device_name}")

        except Exception as e:
            self.finished_signal.emit(False, str(e))


class LivePreviewWorker(QThread):
    """在后台读取相机，只保留最新帧，避免预览任务阻塞 GUI 事件循环。"""

    error_signal = pyqtSignal(str)
    exposure_applied = pyqtSignal(float)

    def __init__(self, camera, camera_lock, fps=30):
        super().__init__()
        self.camera = camera
        self.camera_lock = camera_lock
        self.frame_interval = 1.0 / max(1, fps)
        self._running = True
        self._latest_frame = None
        self._pending_exposure = None
        self._state_lock = threading.Lock()

    def run(self):
        while self._running:
            started = time.perf_counter()
            try:
                with self._state_lock:
                    exposure = self._pending_exposure
                    self._pending_exposure = None

                with self.camera_lock:
                    if exposure is not None:
                        self.camera.set_ex_time(exposure)
                        self.exposure_applied.emit(exposure * 1000.0)
                    if type(self.camera).__name__ == "NewVSYCamera":
                        self.camera.start_acquisition()
                    frame = self.camera.read_newest_image()

                if frame is not None:
                    with self._state_lock:
                        self._latest_frame = frame
            except Exception as exc:
                self.error_signal.emit(str(exc))
                break

            remaining = self.frame_interval - (time.perf_counter() - started)
            if remaining > 0:
                self.msleep(max(1, int(remaining * 1000)))

    def take_latest_frame(self):
        with self._state_lock:
            frame = self._latest_frame
            self._latest_frame = None
        return frame

    def request_exposure(self, exposure_seconds):
        with self._state_lock:
            self._pending_exposure = float(exposure_seconds)

    def stop(self):
        self._running = False

# =========================================================
#  新增：后台扫描线程 (解决 UI 卡顿和采集同步问题)
# =========================================================
class ScanWorker(QThread):
    # 定义信号：用来告诉主界面更新
    # update_signal 传递: (图像数据, 当前X, 当前Y, 当前索引)
    update_signal = pyqtSignal(object, float, float, int) 
    log_signal = pyqtSignal(str, str) # (消息内容, 颜色类型)
    finished_signal = pyqtSignal(bool, str)

    def __init__(
        self,
        camera,
        motion,
        scanner,
        exposure_time_ms,
        crop_params,
        dark_frame=None,
        axis_mapping=(False, False, False),
    ):
        super().__init__()
        self.camera = camera
        self.motion = motion
        self.scanner = scanner
        self.exposure_s = exposure_time_ms / 1000.0
        self.dark_frame = dark_frame
        self.bit_depth = 16
        self.is_swap, self.inv_x, self.inv_y = axis_mapping
        
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

    def _logical_to_physical_deltas(self, dx, dy):
        """把界面中的逻辑 XY 位移转换为物理轴 0/1 的位移。"""
        physical = [0.0, 0.0]
        x_axis = 1 if self.is_swap else 0
        y_axis = 0 if self.is_swap else 1
        physical[x_axis] = -dx if self.inv_x else dx
        physical[y_axis] = -dy if self.inv_y else dy
        return physical[0], physical[1]

    def _physical_to_logical_position(self, physical_x, physical_y):
        """把物理轴位置转换为与扫描路径一致的逻辑 XY 坐标。"""
        physical = (physical_x, physical_y)
        x_axis = 1 if self.is_swap else 0
        y_axis = 0 if self.is_swap else 1
        logical_x = physical[x_axis] * (-1 if self.inv_x else 1)
        logical_y = physical[y_axis] * (-1 if self.inv_y else 1)
        return logical_x, logical_y

    def wait_for_stage_target(
        self,
        target_x,
        target_y,
        dx,
        dy,
        timeout=10.0,
        allow_stopped=False,
    ):
        """轮询位置反馈，连续两次到位后立即返回实际坐标。"""
        if not hasattr(self.motion, 'get_position'):
            raise RuntimeError("位移台不支持位置反馈，无法确认移动完成")

        tolerance_x = min(0.005, max(0.0005, abs(dx) * 0.02))
        tolerance_y = min(0.005, max(0.0005, abs(dy) * 0.02))
        deadline = time.monotonic() + timeout
        consecutive_reached = 0
        cur_x = cur_y = 0.0

        while self.is_running or allow_stopped:
            cur_x = float(self.motion.get_position(0))
            cur_y = float(self.motion.get_position(1))
            reached = (
                abs(cur_x - target_x) <= tolerance_x
                and abs(cur_y - target_y) <= tolerance_y
            )

            if reached:
                consecutive_reached += 1
                if consecutive_reached >= 2:
                    return cur_x, cur_y
            else:
                consecutive_reached = 0

            if time.monotonic() >= deadline:
                raise TimeoutError(
                    "位移台到位超时: "
                    f"目标=({target_x:.6f}, {target_y:.6f}) mm, "
                    f"当前=({cur_x:.6f}, {cur_y:.6f}) mm"
                )

            time.sleep(0.01)

        raise RuntimeError("扫描已停止")

    def _return_stage_to_start(self, origin_x, origin_y):
        """根据实时位置回到扫描起点，而不是依赖计划路径的最终位移。"""
        cur_x = float(self.motion.get_position(0))
        cur_y = float(self.motion.get_position(1))
        dx = origin_x - cur_x
        dy = origin_y - cur_y

        for axis, target, delta in (
            (0, origin_x, dx),
            (1, origin_y, dy),
        ):
            if abs(delta) <= 0.0005:
                continue
            if hasattr(self.motion, 'move_to'):
                self.motion.move_to(target, axis=axis)
            else:
                self.motion.move_by(delta, axis=axis)

        return self.wait_for_stage_target(
            origin_x,
            origin_y,
            dx,
            dy,
            allow_stopped=True,
        )

    def run(self):
        total = len(self.scanner.x)
        use_software_trigger = getattr(
            self.camera, 'supports_software_trigger', False
        )
        origin = None
        success = False
        result_message = "扫描未完成"

        try:
            origin = (
                float(self.motion.get_position(0)),
                float(self.motion.get_position(1)),
            )

            if use_software_trigger:
                self.camera.set_trigger_mode('software')
                settle_time = getattr(self.camera, 'trigger_mode_settle_s', 0.0)
                if settle_time > 0:
                    time.sleep(settle_time)

            for i in range(total):
                if not self.is_running:
                    raise RuntimeError("扫描已停止")

                # 1. 按当前 XY 交换和方向配置移动位移台。
                logical_dx = self.scanner.x[i]
                logical_dy = self.scanner.y[i]
                dx, dy = self._logical_to_physical_deltas(
                    logical_dx, logical_dy
                )
                start_x = float(self.motion.get_position(0))
                start_y = float(self.motion.get_position(1))
                target_x = start_x + dx
                target_y = start_y + dy

                if dx != 0:
                    self.motion.move_by(dx, axis=0)
                if dy != 0:
                    self.motion.move_by(dy, axis=1)

                # 不再固定等待 0.2 s；到位后立即进入采集。
                cur_x, cur_y = self.wait_for_stage_target(
                    target_x, target_y, dx, dy
                )

                # Galaxy 等连续采集相机可能在位移期间积压旧帧。
                # 位移稳定后清空队列，下一次读取将阻塞等待新帧。
                if hasattr(self.camera, 'flush_image_queue'):
                    try:
                        if not self.camera.flush_image_queue():
                            self.log_signal.emit(
                                f"第 {i} 点清空相机缓冲队列失败",
                                "warning",
                            )
                    except Exception as e:
                        self.log_signal.emit(
                            f"第 {i} 点清空相机缓冲队列异常: {e}",
                            "warning",
                        )

                # 2. 每个点只采集一次；任一点读取失败即终止整次扫描。
                if use_software_trigger:
                    self.camera.trigger()

                # Galaxy 的 get_image 会阻塞等待新帧，无需再额外 sleep。
                # 其他非阻塞驱动仍按曝光时间等待。
                if not getattr(self.camera, 'read_waits_for_new_frame', False):
                    time.sleep(max(0.001, self.exposure_s * 1.1))
                raw_img = self.camera.read_newest_image()
                if raw_img is None:
                    raise RuntimeError(f"第 {i} 点未读取到图像，采集失败")
                if np.max(raw_img) <= 0:
                    raise RuntimeError(f"第 {i} 点读取到全黑图像，采集失败")

                raw_img = self.worker_crop(raw_img)
                if raw_img is None:
                    raise RuntimeError(f"第 {i} 点图像裁剪失败，采集失败")

                # 处理暗场 
                if self.dark_frame is not None:
                    if raw_img.shape != self.dark_frame.shape:
                        raise RuntimeError(
                            "暗场尺寸与当前图像不一致: "
                            f"图像={raw_img.shape}, 暗场={self.dark_frame.shape}"
                        )
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
                
                # 扫描线程是采集期间唯一的相机读取者。
                # 界面预览仅接收独立副本，不再从相机取帧。
                logical_x, logical_y = self._physical_to_logical_position(
                    cur_x, cur_y
                )
                self.update_signal.emit(
                    final_data.copy(), logical_x, logical_y, i
                )

            success = True
            result_message = f"采集完成，共 {total} 点"
        except Exception as e:
            result_message = str(e)
        finally:
            if origin is not None:
                try:
                    self._return_stage_to_start(*origin)
                except Exception as e:
                    success = False
                    result_message = (
                        f"{result_message}；回到扫描起点失败: {e}"
                    )
            self.finished_signal.emit(success, result_message)

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
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.curr_img_x = -1
        self.curr_img_y = -1
        self._image_size = None
        self._mouse_timer = QElapsedTimer()
        self._mouse_timer.start()

        self.v_line = None
        self.h_line = None
        self.circle = None

    def update_image(self, image_data, show_mask=False, bit_depth=16):
        # ===========================
        # 显示图像
        # ===========================
        self.np_img = image_data
        if image_data.dtype == np.uint16:
            display_data = image_data
        else:
            display_data = np.asarray(image_data, dtype=np.uint16)
        if bit_depth <= 12:
            display_data = np.left_shift(display_data, 16 - bit_depth)
        display_data = np.ascontiguousarray(display_data)

        h, w = display_data.shape
        qimg = QImage(display_data.data, w, h ,QImage.Format.Format_Grayscale16)
        pix = QPixmap.fromImage(qimg)
        size_changed = self._image_size != (w, h)
        self._image_size = (w, h)
        
        # 更新图片对象
        if self.pixmap_item is None:
            self.pixmap_item = self.scene.addPixmap(pix)
            self.pixmap_item.setZValue(0) # 图片永远在最底层
        else:
            self.pixmap_item.setPixmap(pix)

        # ===========================
        # Mask 绘制
        # ===========================
        if show_mask:
            cx, cy = w / 2 + 0.5 , h / 2 + 0.5
            radius = max(0, min(w, h) / 2 - 10)
            if self.v_line is None:
                self.v_line = self.scene.addLine(
                    0, 0, 0, 0, QPen(QColor("red"), 0, Qt.PenStyle.DashLine)
                )
                self.h_line = self.scene.addLine(
                    0, 0, 0, 0, QPen(QColor("blue"), 0, Qt.PenStyle.DashLine)
                )
                self.circle = self.scene.addEllipse(
                    0, 0, 0, 0, QPen(QColor("green"), 2, Qt.PenStyle.SolidLine)
                )
                for item in (self.v_line, self.h_line, self.circle):
                    item.setZValue(10)
            self.v_line.setLine(cx, 0, cx, h)
            self.h_line.setLine(0, cy, w, cy)
            self.circle.setRect(cx-radius, cy-radius, radius*2, radius*2)

        for item in (self.v_line, self.h_line, self.circle):
            if item is not None:
                item.setVisible(show_mask)

        if size_changed:
            self._fit_image()

    def _fit_image(self):
        if self.pixmap_item is not None and not self.pixmap_item.pixmap().isNull():
            self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_image()

    def mouseMoveEvent(self, event):
        if (self.np_img is not None and self.pixmap_item is not None
                and self._mouse_timer.elapsed() >= 33):
            self._mouse_timer.restart()
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
        self.pos_ref = True
        
        # 实时流定时器
        self.timer = QTimer()
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.update_frame) 
        self.camera_lock = threading.RLock()
        self.live_worker = None
        self.is_live = False
        self.scan_in_progress = False
        self._resume_live_after_scan = False
        self._is_saturated = None
        self._mouse_is_saturated = None
        self._log_lut = None
        self._log_lut_bit_depth = None
        self._stats_timer = QElapsedTimer()
        self._stats_timer.start()
        self._exposure_timer = QTimer(self)
        self._exposure_timer.setSingleShot(True)
        self._exposure_timer.setInterval(250)
        self._exposure_timer.timeout.connect(self._apply_exposure_time)
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.image_view.mouse_hover_signal.connect(self.on_mouse_moved)
        self.default_save_dir = "please change this to your own path"
        self.dark_frame = None
        self.cmi_dark = None
        self.save_dir = self.default_save_dir
        self.pixel_size = 3.45e-3
        self.bit_depth = 16

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
    # 改进的日志函数
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
        is_saturated = val >= self.saturation_value
        if is_saturated != self._mouse_is_saturated:
            self._mouse_is_saturated = is_saturated
            if is_saturated:
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
            # 1. 应用曝光
            self._apply_exposure_time()
            self.camera.start_acquisition()
            self.btn_open_cam.setText("已就绪")
            self.btn_open_cam.setStyleSheet("background-color: #4CAF50; color: white;")
            
            # --- 相机参数初始化逻辑 ---
            # 2. 获取位深
            try:
                if hasattr(self.camera, 'get_bit_depth'):
                    self.bit_depth = int(self.camera.get_bit_depth())
                elif hasattr(self.camera, 'bit_depth'):
                    self.bit_depth = int(self.camera.bit_depth)
                elif hasattr(self.camera, 'BitDepth'):
                    self.bit_depth = int(self.camera.BitDepth)
            except Exception as e:
                self.log_warning(f"获取位深失败，使用默认值 16: {e}")

            # 3. 计算饱和值
            self.saturation_value = (1 << self.bit_depth) - 1
            self.line_cam_max.setText(f"{self.saturation_value} ({self.bit_depth}-bit)")
            self.log_success(f"相机就绪 | 位深: {self.bit_depth} | 饱和阈值: {self.saturation_value}")
            
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
                # 这里更新显示的 Label，而不是 Target 输入框
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

        if target_w > w_full and target_h > h_full:
            self.log_info("ROI 大于图像尺寸，无需裁剪")
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
        # 扫描期间由 ScanWorker 独占相机，即使有未处理的定时器事件也不取帧。
        if self.scan_in_progress:
            return

        if self.camera and self.live_worker:
            try:
                # 取帧由后台线程完成，GUI 只消费最新帧。
                img = self.live_worker.take_latest_frame()
                if img is None: return
                cropped_img = self.crop_image(img)
                if cropped_img is None: return
                
                # ==========================================
                # 全局最大值监测与饱和报警
                # ==========================================
                # 数值和样式统计最高 10 Hz，预览仍保持 30 FPS。
                update_stats = self._stats_timer.elapsed() >= 100
                if update_stats:
                    self._stats_timer.restart()
                    max_val = np.max(cropped_img)
                    self.line_global_max.setText(f"{max_val}")
                    limit = getattr(self, 'saturation_value', 2**self.bit_depth - 1)
                    is_saturated = max_val >= limit
                    if is_saturated != self._is_saturated:
                        self._is_saturated = is_saturated
                        if is_saturated:
                            self.line_global_max.setStyleSheet("color: red; font-weight: bold; background: #ffeeee;")
                        else:
                            self.line_global_max.setStyleSheet("color: green; font-weight: bold; background: #f0f0f0;")

                # count = np.sum(np.array(cropped_img) >= limit)
                # self.line_saturation.setText(f"{count}")
                # self.line_saturation.setStyleSheet("color: red; font-weight: bold; background: #ffeeee;")

                # ==========================================
                # 处理 Log 显示和 Mask
                # ==========================================
                # 获取 Mask 勾选状态
                show_mask = self.chk_mask.isChecked()
                
                # 处理 Log 变换
                if self.chk_log.isChecked():
                    if self._log_lut is None or self._log_lut_bit_depth != self.bit_depth:
                        max_input = (1 << min(self.bit_depth, 16)) - 1
                        values = np.arange(max_input + 1, dtype=np.float32)
                        self._log_lut = (
                            np.sqrt(max_input) * np.sqrt(values)
                        ).clip(0, 65535).astype(np.uint16)
                        self._log_lut_bit_depth = self.bit_depth
                    lut_index = np.clip(cropped_img, 0, len(self._log_lut) - 1)
                    img_disp = self._log_lut[lut_index]
                    self.image_view.update_image(img_disp, show_mask, bit_depth=16)
                else:
                    # 正常线性显示
                    self.image_view.update_image(cropped_img, show_mask, bit_depth=self.bit_depth)

                # ==========================================
                # 鼠标悬停数值更新 (防止 ROI 变化导致越界)
                # ==========================================
                if update_stats:
                    h, w = cropped_img.shape
                    if 0 <= self.last_mouse_x < w and 0 <= self.last_mouse_y < h:
                        current_val = cropped_img[self.last_mouse_y, self.last_mouse_x]
                        self.update_pixel_display(current_val)
                    else:
                        self.last_mouse_x = w // 2
                        self.last_mouse_y = h // 2
            
            except Exception as e:
                self.log_error(f"更新图像时出错: {e}")

    def toggle_live(self):
        if self.scan_in_progress:
            self.log_warning("扫描采集期间不能单独启动实时预览")
            return

        if not self.camera:
            self.log_warning("请先连接并初始化相机！")
            return

        if self.is_live:
            if self._stop_live_preview():
                self.log_info("实时显示已停止")
        else:
            if self._start_live_preview():
                self.log_success("实时显示已启动（30 FPS）")

    def _start_live_preview(self):
        if not self.camera:
            return False
        if self.live_worker is not None:
            if self.live_worker.isRunning():
                self.log_warning("上一个取帧线程仍在停止中")
                return False
            self.live_worker.deleteLater()
            self.live_worker = None
        self.live_worker = LivePreviewWorker(self.camera, self.camera_lock, fps=30)
        self.live_worker.error_signal.connect(self._on_live_error)
        self.live_worker.exposure_applied.connect(self._on_exposure_applied)
        self.live_worker.start()
        self.timer.start()
        self.is_live = True
        self.btn_live.setText("⬛ 停止")
        self.btn_live.setStyleSheet(
            "background:#7f8c8d;color:white;font-weight:bold;min-height:40px;"
        )
        return True

    def _stop_live_preview(self, wait_ms=2000):
        self.timer.stop()
        self.is_live = False
        if self.live_worker is not None:
            self.live_worker.stop()
            self.live_worker.wait(wait_ms)
            if self.live_worker.isRunning():
                self.log_warning("相机取帧线程仍在停止中")
                return False
            self.live_worker.deleteLater()
            self.live_worker = None
        self.btn_live.setText("👁 启动")
        self.btn_live.setStyleSheet(
            "background:#27ae60;color:white;font-weight:bold;min-height:40px;"
        )
        return True

    def _on_live_error(self, message):
        self.log_error(f"实时取帧失败: {message}")
        self._stop_live_preview()

    def _on_exposure_applied(self, exposure_ms):
        self.log_info(f"曝光: {exposure_ms:g} ms")

    def _pause_live_preview_for_scan(self):
        """让扫描线程独占相机，记住扫描后是否需要恢复实时预览。"""
        self._resume_live_after_scan = self.is_live
        if self.live_worker is not None and not self._stop_live_preview(wait_ms=3000):
            return False
        self.scan_in_progress = True
        self.btn_live.setEnabled(False)
        self.btn_live.setText("扫描预览中...")
        self.btn_live.setStyleSheet(
            "background:#7f8c8d;color:white;font-weight:bold;min-height:40px;"
        )
        return True

    def _restore_live_preview_after_scan(self):
        """扫描结束后恢复按钮，并按扫描前的状态恢复实时预览。"""
        should_resume = self._resume_live_after_scan
        self._resume_live_after_scan = False
        self.scan_in_progress = False
        self.btn_live.setEnabled(True)

        if (
            self.camera
            and getattr(self.camera, 'supports_software_trigger', False)
        ):
            try:
                with self.camera_lock:
                    self.camera.set_trigger_mode('continuous')
            except Exception as e:
                self.log_warning(f"恢复相机连续采集模式失败: {e}")

        # 扫描期间修改的曝光值在此时统一下发。
        self._exposure_timer.stop()
        self._apply_exposure_time()

        if should_resume and self.camera:
            if self._start_live_preview():
                self.log_info("扫描结束，已恢复实时预览")
        else:
            self.is_live = False
            self.btn_live.setText("👁 启动")
            self.btn_live.setStyleSheet(
                "background:#27ae60;color:white;font-weight:bold;min-height:40px;"
            )

    def calculate_center(self): #todo
        if not self.camera:
            self.log_warning("相机未连接")
            return
                
        self.off_x.setText("0")
        self.off_y.setText("0")

        
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
            import matplotlib.pyplot as plt
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
            preview_size = self.lbl_scan_preview.contentsRect().size()
            if preview_size.width() > 0 and preview_size.height() > 0:
                pixmap = pixmap.scaled(
                    preview_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            self.lbl_scan_preview.setScaledContents(False)
            self.lbl_scan_preview.setPixmap(pixmap)

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
                return False
            else:
                confirm = QMessageBox.question(
                    self, 
                    "确认目录", 
                    f"是否进行覆写？(不覆写将追加到已存在文件)",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if confirm == QMessageBox.StandardButton.Yes:
                    self.log_info("确认进行覆写")
                    if os.path.exists(current_dir):
                        shutil.rmtree(current_dir)
                        self.log_info("已删除已存在文件")
                    return True
                else:
                    return True

        if os.path.exists(os.path.join(current_dir, "scandata.h5")):
            confirm = QMessageBox.question(
                    self, 
                    "确认目录", 
                    f"是否进行覆写？(不覆写将追加到已存在文件)",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
            if confirm == QMessageBox.StandardButton.Yes:
                self.log_info("确认进行覆写")
                if os.path.exists(current_dir):
                    shutil.rmtree(current_dir)
                    self.log_info("已删除已存在文件")
                return True
            else:
                return True

        # 3. 更新并确保目录存在
        self.save_dir = current_dir
        self.default_save_dir = self.save_dir
        if not os.path.exists(self.save_dir):
            try:
                os.makedirs(self.save_dir)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法创建目录:\n{e}")
                return False
        return True

    def start_scan(self):
        # 1. 检查目录
        if not self.confirm_directory():
            return

        if not self.camera:
            self.log_error("相机未初始化")
            return
        
        if not self.motion:
            self.log_error("电机未初始化")
            return

        self.btn_cap.setEnabled(False)  # 锁定按钮
        self.btn_cap.setText("采集中...")

        # 3. 停止旧线程（双重保险）
        if hasattr(self, 'worker') and self.worker is not None:
            if self.worker.isRunning():
                self.worker.stop()
                self.worker.wait(50) # 等待旧线程结束

        # 2. 路径检查
        self.preview_scan_path()
        if not getattr(self, 'scanner', None): 
            self.log_error("扫描器未初始化")
            return

        # 每次扫描前都让用户决定是否重新采集暗场。
        # 尚无暗场时必须采集；已有暗场时选“否”即复用当前暗场。
        dark_msg = QMessageBox(self)
        dark_msg.setWindowTitle("暗场检查")
        if self.dark_frame is None:
            dark_msg.setText("尚未采集暗场，是否现在采集？")
        else:
            dark_msg.setText("是否重新采集当前环境的暗场？\n选择“否”将使用已有暗场。")
        dark_msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        btn_no = dark_msg.button(QMessageBox.StandardButton.No)
        if self.dark_frame is None:
            btn_no.setEnabled(False)
            btn_no.setText("No (已禁用)")

        dark_result = dark_msg.exec()
        if dark_result == QMessageBox.StandardButton.Yes:
            with self.camera_lock:
                img_dark = self.camera.read_newest_image()
            if img_dark is None:
                self.log_error("暗场采集失败：无法获取图像")
                self.btn_cap.setEnabled(True)
                self.btn_cap.setText("采集")
                return
            img_dark = self.crop_image(img_dark)
            if img_dark is None:
                self.log_error("暗场采集失败：图像裁剪失败")
                self.btn_cap.setEnabled(True)
                self.btn_cap.setText("采集")
                return
            self.dark_frame = img_dark.astype(np.uint16)
            self.log_success("暗场采集完成")
            raw_data_dir = os.path.join(self.save_dir, "raw_data")
            if not os.path.exists(raw_data_dir):
                os.makedirs(raw_data_dir)
            path_dark = os.path.join(raw_data_dir, "dark.tif")
            try:
                if img_dark.dtype == np.uint16 or img_dark.dtype == np.uint8:
                    Image.fromarray(img_dark).save(path_dark)
                else:
                    Image.fromarray(img_dark.astype(np.uint16)).save(path_dark)
            except Exception as e:
                self.log_error(f"暗场保存失败: {e}")
        elif dark_result != QMessageBox.StandardButton.No or self.dark_frame is None:
            self.log_info("采集已取消")
            self.btn_cap.setEnabled(True)  # 释放按钮
            self.btn_cap.setText("采集")
            return
        
        if self.dark_frame is not None:
            confirm = QMessageBox.question(
                self, 
                "采集检查",        # <--- 这里是标题 (Title)
                "是否开始采集？",   # <--- 这里是内容 (Text)
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if confirm == QMessageBox.StandardButton.Yes:
                pass
            else:
                self.log_info("采集已取消")
                self.btn_cap.setEnabled(True)  # 释放按钮
                self.btn_cap.setText("采集")
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
        axis_mapping = (
            self.stage_widget.check_swap.isChecked(),
            self.stage_widget.check_inv_x.isChecked(),
            self.stage_widget.check_inv_y.isChecked(),
        )

        # === 【修改】 实例化 Worker 时传入参数 ===
        self.worker = ScanWorker(
            camera=self.camera,
            motion=self.motion,
            scanner=self.scanner,
            exposure_time_ms=exposure_val,
            crop_params=crop_params_tuple,  # <--- 传入这里
            dark_frame=self.dark_frame,
            axis_mapping=axis_mapping,
        )
        self.worker.update_signal.connect(self._update_scan_preview)
        self.worker.log_signal.connect(self._worker_log)
        self.worker.finished_signal.connect(self._scan_finished)

        if not self._pause_live_preview_for_scan():
            self.btn_cap.setEnabled(True)
            self.btn_cap.setText("🔴 采集")
            self.log_error("无法停止实时取帧，扫描未启动")
            return
        try:
            self.worker.start()
        except Exception as e:
            self._restore_live_preview_after_scan()
            self.btn_cap.setEnabled(True)
            self.btn_cap.setText("🔴 采集")
            self.log_error(f"启动扫描线程失败: {e}")

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
        """     
        # 更新界面图像显示
        show_mask = self.chk_mask.isChecked()
        self.image_view.update_image(
            img_data, show_mask=show_mask, bit_depth=self.bit_depth
        )

        frame_name = f"scan_{idx:03d}.tif"
        raw_data_dir = os.path.join(self.save_dir, "raw_data")
        if not os.path.exists(raw_data_dir):
            os.makedirs(raw_data_dir)
        path = os.path.join(raw_data_dir, frame_name)
        try:
            # 直接保存 raw
            if img_data.dtype != np.uint8 and img_data.dtype != np.uint16:
                save_data = img_data.astype(np.uint16)
            else:
                save_data = img_data
            Image.fromarray(save_data).save(path)
        except Exception as e:
            print(f"单帧保存失败: {e}")
        
        # 写入 H5
        self._write_scan_to_h5(img_data, cur_x, cur_y)

    def _scan_finished(self, success, message):
        if success:
            self.log_success(f"{message}，H5 文件写入完成！")
        else:
            self.log_error(message)

        # ScanWorker 已依据硬件实际位置回到本次扫描的起点。
        self.sync_hardware_position()
        self.pos_ref = True
        self.btn_cap.setEnabled(True)  # 锁定按钮
        self.btn_cap.setText("🔴 采集")
        self.btn_cap.setStyleSheet("background:#e74c3c;color:white;font-weight:bold;height: 45px;")
        self._restore_live_preview_after_scan()

    def _write_scan_to_h5(self, img_data, cur_x, cur_y, h5_path=None):
        """
        将当前扫描数据写入 H5 文件。(img_data, cur_x, cur_y, wl)
        """
        if not h5_path:
            h5_path = os.path.join(self.save_dir, self.current_scan_h5_name)
        try:
            os.makedirs(os.path.dirname(h5_path), exist_ok=True)
        except:
            self.log_error(f"创建目录失败: {h5_path}")
            return

        # --- 将 Data 写入 H5 ---
        frame = np.array(img_data, dtype=np.uint16)   # (H, W)
        if self.pos_ref == True:
            x_val = np.array([cur_x], dtype=np.float64)   # (1,)
            self.x_ref = x_val
            y_val = np.array([cur_y], dtype=np.float64)   # (1,)
            self.y_ref = y_val
            self.pos_ref = False

        x_val = np.array([cur_x], dtype=np.float64)
        x_val -= self.x_ref
        y_val = np.array([cur_y], dtype=np.float64)
        y_val -= self.y_ref

        try:  
            with h5py.File(h5_path, 'a') as f:
                if "data" not in f:    
                    H, W = frame.shape
                    f.create_dataset(
                        "data",
                        data=frame[np.newaxis],          # shape (1, H, W)
                        maxshape=(None, H, W),           # 第 0 轴无限扩展
                        compression="gzip",
                        chunks=(1, H, W),                # 按帧分块，追加高效
                    )
                    f.create_dataset(
                        "x",
                        data=x_val,                      # shape (1,)
                        maxshape=(None,),
                        compression="gzip",
                        chunks=(1,),
                    )
                    f.create_dataset(
                        "y",
                        data=y_val,
                        maxshape=(None,),
                        compression="gzip",
                        chunks=(1,),
                    )
                else:
                    n = f["data"].shape[0]               # 当前帧数

                    f["data"].resize(n + 1, axis=0)
                    f["data"][n] = frame

                    f["x"].resize(n + 1, axis=0)
                    f["x"][n] = x_val

                    f["y"].resize(n + 1, axis=0)
                    f["y"][n] = y_val

                f.attrs['wavelength'] = np.array([float(self.wavelength_spin.text())])
                # f.attrs['pixel_size'] = np.array([float(self.pixel_size.text())]) 有问题
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
                    rh = int(frame.shape[1]) if frame.ndim >= 2 else 0
                    rw = int(frame.shape[2]) if frame.ndim >= 3 else 0
                f.attrs['detector_size'] = np.array([rw, rh])
                f.attrs['exposure_time'] = np.array([float(self.exposure_spin.value())])
                f.attrs['scan_method'] = np.array([self.combo_scan_mode.currentText().encode('utf-8')])
                f.attrs['scan_range'] = np.array([float(self.scan_range_x.text()), float(self.scan_range_y.text())])
                f.attrs['scan_step'] = np.array([float(self.scan_step.text())]) 

        except Exception as e:
            self.log_error(f"H5 保存失败: {e}")
            traceback.print_exc()

    def set_exposure_time(self):
        """参数输入防抖：用户停止修改 250 ms 后再下发最终值。"""
        self._exposure_timer.start()

    def _apply_exposure_time(self):
        if not self.camera or self.scan_in_progress:
            return
        exposure_ms = self.exposure_spin.value()
        exposure_seconds = exposure_ms / 1000.0
        if self.live_worker is not None and self.live_worker.isRunning():
            self.live_worker.request_exposure(exposure_seconds)
            return
        try:
            with self.camera_lock:
                self.camera.set_ex_time(exposure_seconds)
            self._on_exposure_applied(exposure_ms)
        except Exception as exc:
            self.log_error(f"设置曝光失败: {exc}")

    def select_folder(self):
        path = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if path:
            self.save_dir_edit.setText(path)
            self.save_dir = path

    def on_manual_save(self):
        """响应'保存'按钮：保存当前视图为 tif 并写入 h5"""
        if not self.confirm_directory():
            return
        
        if not self.camera:
            self.log_error("相机未连接")
            return
        
        final_name = "scandata"
        if final_name.strip(): 
            msg = QMessageBox(None)
            msg.setWindowTitle("采集检查")
            msg.setText("是否需要采集暗场图")
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            btn_no = msg.button(QMessageBox.StandardButton.No)

            if self.cmi_dark is None:
                btn_no.setEnabled(False)
                btn_no.setText("No (已禁用)")
            result = msg.exec()

            if result == QMessageBox.StandardButton.Yes:
                with self.camera_lock:
                    self.cmi_dark = self.camera.read_newest_image()
                if self.cmi_dark is None:
                    self.log_error("暗场采集失败：无法获取图像")
                    return
                self.cmi_dark = self.crop_image(self.cmi_dark)
                if self.cmi_dark is None:
                    self.log_error("暗场采集失败：图像裁剪失败") 
                    return

                if not os.path.exists(self.save_dir):
                    os.makedirs(self.save_dir)
                try:
                    raw_data_dir = os.path.join(self.save_dir, "raw_data")
                    os.makedirs(raw_data_dir, exist_ok=True)
                    save_path = os.path.join(raw_data_dir, f"scandata_dark.tif")
                    if self.cmi_dark.dtype == np.uint16 or self.cmi_dark.dtype == np.uint8:
                        Image.fromarray(self.cmi_dark).save(save_path)
                    else:
                        Image.fromarray(self.cmi_dark.astype(np.uint16)).save(save_path)
                except Exception as e:
                    self.log_error(f"暗场保存失败: {e}")

                reply = QMessageBox.question(
                self, 
                "暗场采集完成", 
                "是否继续采集衍射图？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
                )
                
                if reply == QMessageBox.StandardButton.No:
                    self.log_info("采集已取消")
                    return
                     
            roi_img, cur_x, cur_y = self.save_current_frame(base_name=final_name)
            save_img = roi_img.astype(np.float32) - self.cmi_dark.astype(np.float32)
            save_img = np.clip(save_img, 0, 65535).astype(np.uint16)
            save_path = os.path.join(self.save_dir,final_name)

            if roi_img is not None:
                with h5py.File(save_path + ".h5", 'a') as f:
                    if "data" in f:
                        del f["data"]
                    f.create_dataset(
                        "data", 
                        data = save_img,        # 使用转换后的 numpy 数组
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
                        rh = int(roi_img.shape[1]) if roi_img.ndim >= 2 else 0
                        rw = int(roi_img.shape[2]) if roi_img.ndim >= 3 else 0
                    f.attrs['detector_size'] = np.array([rw, rh])
                    f.attrs['exposure_time'] = np.array([float(self.exposure_spin.value())])
                    # f.attrs['binning_number'] = np.array([int(self.combo_sampling.currentText().split()[0])])

                    # 4. 其他属性
                    # 注意：原代码 dp.shape[0] 如果 dp 是 list 会报错，必须用 len(dp) 或 dp_arr.shape[0]
                    # f.attrs['total_frames'] = dp_arr.shape[0] 
            else:
                self.log_error("无法获取图像数据，保存中止")
                return

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
            with self.camera_lock:
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
            
            raw_data_dir = os.path.join(self.save_dir, "raw_data")
            os.makedirs(raw_data_dir, exist_ok=True)
            path_tif = os.path.join(raw_data_dir, f"{base_name}.tif")

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

    def closeEvent(self, event):
        """退出前安全停止取帧/扫描线程，避免 QThread 运行中被销毁。"""
        self.timer.stop()
        self._exposure_timer.stop()

        if self.live_worker is not None and not self._stop_live_preview(wait_ms=1000):
            event.ignore()
            QTimer.singleShot(300, self.close)
            return

        worker = getattr(self, 'worker', None)
        if worker is not None and worker.isRunning():
            worker.stop()
            if not worker.wait(1000):
                event.ignore()
                QTimer.singleShot(300, self.close)
                return

        if self.camera is not None:
            try:
                with self.camera_lock:
                    if hasattr(self.camera, 'close'):
                        self.camera.close()
                    elif hasattr(self.camera, 'stop_acquisition'):
                        self.camera.stop_acquisition()
            except Exception as e:
                self.log_warning(f"关闭相机时出现异常: {e}")
            finally:
                self.camera = None

        super().closeEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LogicWindow()
    window.show()
    sys.exit(app.exec())

