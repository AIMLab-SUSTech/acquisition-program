import time
import numpy as np
import queue # 引入队列
import os
from PIL import Image
import h5py
from PyQt6.QtCore import QThread, pyqtSignal

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
                # 注意：这里需要确保你的目录下有这些对应的硬件模块文件
                match(self.device_name):
                    case "IDS":
                        from camera import IDS; device_instance = IDS(); device_instance.start_acquisition(); device_instance.set_pixel_rate(7e7)
                    case "Ham":
                        from camera import Ham; device_instance = Ham(); device_instance.start_acquisition()
                    case "Lucid":
                        from lucid import LucidCamera; device_instance = LucidCamera(max_tries=1, wait_time=1); device_instance.start_acquisition()
                    case "PM":
                        from photometrics import PyVCAM; device_instance = PyVCAM(); device_instance.start_acquisition()
                    case "IDS_Peak":
                        from peak import IDSPeakCamera; device_instance = IDSPeakCamera(); device_instance.start_acquisition()
                    case "PI-mte3":
                        from pi_camera import PICamera; device_instance = PICamera(); device_instance.start_acquisition()
                    case "VSY":
                        from new_vsy_camera import NewVSYCamera; device_instance = NewVSYCamera()
                    case "Galaxy":
                        from camera import GalaxyCamera; device_instance = GalaxyCamera(); device_instance.start_acquisition()
                    case "QHY":
                        from QHY import QHYCamera; device_instance = QHYCamera(); device_instance.set_bit_depth(16); device_instance.start_acquisition()

            elif self.device_type == 'stage':
                match(self.device_name):
                    case "NewPort":
                        from motion_controller import xps; device_instance = xps(IP='192.168.0.254'); device_instance.init_groups(['Group3', 'Group4'])
                    case "Nators":
                        from motion_controller import nators; device_instance = nators(ip_address="192.168.0.254"); device_instance.open_system()
                    case "SmartAct":
                        from motion_controller import smartact; device_instance = smartact()

            if device_instance:
                self.finished_signal.emit(True, device_instance)
            else:
                self.finished_signal.emit(False, f"未找到驱动: {self.device_name}")

        except Exception as e:
            self.finished_signal.emit(False, str(e))

# =========================================================
#  后台扫描线程
# =========================================================
class ScanWorker(QThread):
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
        self.target_w, self.target_h, self.off_x, self.off_y = crop_params
        self.is_running = True

    def worker_crop(self, full_image):
        if full_image is None: return None
        h_full, w_full = full_image.shape
        target_w, target_h = self.target_w, self.target_h
        off_x, off_y = self.off_x, self.off_y

        if target_w >= w_full and target_h >= h_full: return full_image

        center_x = w_full // 2 + off_x
        center_y = h_full // 2 + off_y
        
        x1 = int(center_x - target_w // 2)
        y1 = int(center_y - target_h // 2)
        x2 = x1 + target_w
        y2 = y1 + target_h
        
        # 边界检查
        if x1 < 0: x1 = 0; x2 = target_w
        if y1 < 0: y1 = 0; y2 = target_h
        if x2 > w_full: x2 = w_full; x1 = w_full - target_w
        if y2 > h_full: y2 = h_full; y1 = h_full - target_h
            
        return full_image[max(0, y1):min(h_full, y2), max(0, x1):min(w_full, x2)]

    def run(self):
        total = len(self.scanner.x)
        if hasattr(self.camera, 'set_trigger_mode'):
            self.camera.set_trigger_mode('software')
            time.sleep(0.2)

        for i in range(total):
            if not self.is_running: break

            dx = self.scanner.x[i]
            dy = self.scanner.y[i]
            
            try:
                self.motion.move_by(dx, axis=0)
                self.motion.move_by(dy, axis=1)
                time.sleep(0.2)
            except Exception as e:
                self.log_signal.emit(f"移动错误: {e}", "error")
                break

            max_retries = 3
            raw_img = None
            for attempt in range(max_retries):
                time.sleep(self.exposure_s * 1.5)
                raw_img = self.camera.read_newest_image()
                if raw_img is not None and np.max(raw_img) > 0:
                    break
                else:
                    self.log_signal.emit(f"第 {i} 点重试...", "warning")
            
            if raw_img is not None:
                raw_img = self.worker_crop(raw_img)
            
            cur_x, cur_y = 0.0, 0.0
            try:
                if hasattr(self.motion, 'get_position'):
                    cur_x = self.motion.get_position(0)
                    cur_y = self.motion.get_position(1)
            except Exception as e:
                self.log_signal.emit(f"读取坐标错误: {e}", "error")
                break # 或 return

            if raw_img is not None:
                # 暗场扣除
                final_data = raw_img
                if self.dark_frame is not None:
                    img_int32 = raw_img.astype(np.int32)
                    dark_int32 = self.dark_frame.astype(np.int32)
                    subtracted = img_int32 - dark_int32
                    subtracted[subtracted < 0] = 0
                    final_data = subtracted.astype(np.uint16)
                elif raw_img.dtype != np.uint16:
                    final_data = raw_img.astype(np.uint16)
                
                self.update_signal.emit(final_data, cur_x, cur_y, i)
            else:
                self.log_signal.emit(f"第 {i} 点采集失败: 空图像", "warning")

        if hasattr(self.camera, 'set_trigger_mode'):
            self.camera.set_trigger_mode('continuous')
            time.sleep(0.1)
        self.finished_signal.emit()

    def stop(self):
        self.is_running = False

class FileSaverWorker(QThread):
    log_signal = pyqtSignal(str, str) # level, msg

    def __init__(self):
        super().__init__()
        self.queue = queue.Queue()
        self.is_running = True

    def save_tif(self, image_data, path):
        """外部调用的方法：添加保存TIF任务"""
        self.queue.put(("tif", image_data, path))

    def save_h5(self, h5_path, data_dict):
        """外部调用的方法：添加保存H5任务"""
        self.queue.put(("h5", h5_path, data_dict))

    def run(self):
        while self.is_running:
            try:
                # 从队列获取任务，超时1秒以便检查 is_running 标志
                task = self.queue.get(timeout=1)
            except queue.Empty:
                continue

            task_type = task[0]

            try:
                if task_type == "tif":
                    _, img_data, path = task
                    self._do_save_tif(img_data, path)
                
                elif task_type == "h5":
                    _, h5_path, data = task
                    self._do_save_h5(h5_path, data)
                
                # 标记任务完成
                self.queue.task_done()
                
            except Exception as e:
                self.log_signal.emit("error", f"后台保存失败: {e}")

    def _do_save_tif(self, img_data, path):
        # 确保目录存在
        folder = os.path.dirname(path)
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)

        if img_data.dtype != np.uint8 and img_data.dtype != np.uint16:
            save_data = img_data.astype(np.uint16)
        else:
            save_data = img_data
        
        Image.fromarray(save_data).save(path)
        # TIF保存太频繁，一般不发成功日志，除非你需要调试
        # self.log_signal.emit("info", f"已保存: {os.path.basename(path)}")

    def _do_save_h5(self, h5_path, data_dict):
        self.log_signal.emit("info", "正在后台写入 H5 文件，请稍候...")
        
        # 确保目录存在
        folder = os.path.dirname(h5_path)
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)

        with h5py.File(h5_path, 'w') as f: # 使用 'w' 覆盖或创建
            # 写入数据集
            if "data" in data_dict:
                f.create_dataset("data", data=data_dict["data"], compression="gzip")
            if "x" in data_dict:
                f.create_dataset("x", data=data_dict["x"], compression="gzip")
            if "y" in data_dict:
                f.create_dataset("y", data=data_dict["y"], compression="gzip")
            
            # 写入属性
            if "attrs" in data_dict:
                for k, v in data_dict["attrs"].items():
                    f.attrs[k] = v
        
        self.log_signal.emit("success", f"H5 文件写入完成: {os.path.basename(h5_path)}")

    def stop(self):
        self.is_running = False
        self.wait()