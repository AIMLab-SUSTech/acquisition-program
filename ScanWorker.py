import time
import os
import numpy as np
import h5py
from PyQt6.QtCore import QThread, pyqtSignal

class ScanWorker(QThread):
    """
    负责执行扫描任务，并将数据在线程内部保存为 H5 文件。
    """
    # 信号：(图像数据, 当前X, 当前Y, 当前索引) - 仅用于UI显示，不用于主线程保存
    update_signal = pyqtSignal(object, float, float, int) 
    log_signal = pyqtSignal(str, str) # (消息内容, 颜色类型: info/success/warning/error)
    finished_signal = pyqtSignal()

    def __init__(self, camera, motion, scanner, exposure_time_ms, crop_params, dark_frame, 
                 save_path, metadata):
        """
        save_path: 完整的 .h5 文件路径
        metadata: 包含 wavelength, pixel_size, timestamps 等信息的字典
        """
        super().__init__()
        self.camera = camera
        self.motion = motion
        self.scanner = scanner
        self.exposure_s = exposure_time_ms / 1000.0
        self.dark_frame = dark_frame
        
        # H5 相关参数
        self.save_path = save_path
        self.metadata = metadata
        
        # 解包裁剪参数 (width, height, off_x, off_y)
        self.target_w, self.target_h, self.off_x, self.off_y = crop_params
        
        # 内部数据缓存
        self.data_buffer = []
        self.pos_x_buffer = []
        self.pos_y_buffer = []

        self.is_running = True

    def worker_crop(self, full_image):
        """纯计算裁剪，不依赖 UI"""
        if full_image is None: return None
        h_full, w_full = full_image.shape
        
        target_w, target_h = self.target_w, self.target_h
        off_x, off_y = self.off_x, self.off_y

        if target_w >= w_full and target_h >= h_full:
            return full_image

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
            
        x1 = max(0, x1); y1 = max(0, y1)
        x2 = min(w_full, x2); y2 = min(h_full, y2)
        
        return full_image[y1:y2, x1:x2]

    def save_h5_internal(self):
        """在子线程中执行 H5 保存操作"""
        if not self.data_buffer:
            self.log_signal.emit("没有数据可保存", "warning")
            return

        try:
            self.log_signal.emit("正在后台写入 H5 文件...", "info")
            
            # 确保目录存在
            os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
            
            dp_arr = np.array(self.data_buffer, dtype=np.uint16)
            px_arr = np.array(self.pos_x_buffer)
            py_arr = np.array(self.pos_y_buffer)
            
            with h5py.File(self.save_path, 'a') as f: # 使用 'a' 可覆写
                # 写入主要数据集
                f.create_dataset("data", data=dp_arr, compression="gzip")
                f.create_dataset("x", data=px_arr, compression="gzip")
                f.create_dataset("y", data=py_arr, compression="gzip")
                
                # 写入元数据 (Attributes)
                if self.metadata:
                    for key, val in self.metadata.items():
                        try:
                            f.attrs[key] = val
                        except Exception as e:
                            print(f"Skipping attr {key}: {e}")
                
                # 自动计算的属性
                f.attrs['total_frames'] = dp_arr.shape[0]
                f.attrs['timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')

            self.log_signal.emit(f"H5 保存成功: {os.path.basename(self.save_path)}", "success")

        except Exception as e:
            self.log_signal.emit(f"H5 保存失败: {e}", "error")
            import traceback
            traceback.print_exc()

    def run(self):
        total = len(self.scanner.x)
        if hasattr(self.camera, 'set_trigger_mode'):
            self.camera.set_trigger_mode('software')
            time.sleep(0.2)

        for i in range(total):
            if not self.is_running: break

            # 1. 移动
            dx = self.scanner.x[i]
            dy = self.scanner.y[i]
            try:
                self.motion.move_by(dx, axis=0) 
                self.motion.move_by(dy, axis=1)
                time.sleep(0.15) 
            except Exception as e:
                self.log_signal.emit(f"移动错误: {e}", "error")
                break

            # 2. 采集
            max_retries = 3
            raw_img = None
            for attempt in range(max_retries):
                time.sleep(self.exposure_s * 1.1 + 0.02)
                raw_img = self.camera.read_newest_image()
                if raw_img is not None and np.max(raw_img) > 0:
                    break
            
            if raw_img is not None:
                raw_img = self.worker_crop(raw_img)
            
            # 3. 获取坐标
            cur_x, cur_y = 0.0, 0.0
            try:
                if hasattr(self.motion, 'get_position'):
                    cur_x = self.motion.get_position(0)
                    cur_y = self.motion.get_position(1)
            except: pass

            if raw_img is not None:
                # 暗场处理
                final_data = raw_img
                if self.dark_frame is not None:
                    img_int32 = raw_img.astype(np.int32)
                    dark_int32 = self.dark_frame.astype(np.int32)
                    sub = img_int32 - dark_int32
                    sub[sub < 0] = 0
                    final_data = sub.astype(np.uint16)
                elif raw_img.dtype != np.uint16:
                    final_data = raw_img.astype(np.uint16)
                
                # --- 保存到内存列表 ---
                self.data_buffer.append(final_data)
                self.pos_x_buffer.append(cur_x)
                self.pos_y_buffer.append(cur_y)

                # --- 发送信号给 UI 显示 ---
                self.update_signal.emit(final_data, cur_x, cur_y, i)
            else:
                self.log_signal.emit(f"第 {i} 点采集失败", "warning")

        if hasattr(self.camera, 'set_trigger_mode'):
            self.camera.set_trigger_mode('continuous')
        
        # 扫描结束后，直接在当前线程保存 H5
        if self.is_running:
            self.save_h5_internal()

        self.finished_signal.emit()

    def stop(self):
        self.is_running = False