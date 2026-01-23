
import numpy as np
import ctypes
from ctypes import *
from enum import Enum
import os
import time

class CONTROL_ID(Enum):
    CONTROL_BRIGHTNESS = 0
    CONTROL_CONTRAST = 1
    CONTROL_WBR = 2
    CONTROL_WBB = 3
    CONTROL_WBG = 4
    CONTROL_GAMMA = 5
    CONTROL_GAIN = 6
    CONTROL_OFFSET = 7
    CONTROL_EXPOSURE = 8
    CONTROL_SPEED = 9
    CONTROL_TRANSFERBIT = 10
    CONTROL_CHANNELS = 11
    CONTROL_USBTRAFFIC = 12
    CONTROL_CURTEMP = 14
    CONTROL_CURPWM = 15
    CONTROL_MANULPWM = 16
    CONTROL_CFWPORT = 17
    CONTROL_COOLER = 18
    CONTROL_ST4PORT = 19
    CAM_COLOR = 20
    CAM_BIN1X1MODE = 21
    CAM_BIN2X2MODE = 22
    CAM_BIN3X3MODE = 23
    CAM_BIN4X4MODE = 24
    CAM_8BITS = 34
    CAM_16BITS = 35
    CAM_GPS = 36
    CONTROL_AMPV = 41
    CONTROL_CFWSLOTSNUM = 44
    CAM_SINGLEFRAMEMODE = 57
    CAM_LIVEVIDEOMODE = 58
    CAM_IS_COLOR = 59

class QHYCamera:
    def __init__(self, dll_path=None):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        dll_dir = os.path.join(current_dir, 'dll', 'QHY')
        dll_file_path = os.path.join(dll_dir, 'qhyccd.dll')
            
        try:
            self.qhyccddll = cdll.LoadLibrary(dll_file_path)
        except OSError:
            raise FileNotFoundError(f"Cannot load QHY DLL from {dll_file_path}")

        self._setup_dll_functions()
        
        self.camhandle = 0
        self._is_live_mode = False
        self._current_bit_depth = 16
        self._exposure_us = 20000.0  # 默认20ms
        
        self.image_width = 0
        self.image_height = 0
        self.image_channels = 1
        self.is_color = False
        
        self.imgdata_buffer = None
        self.buffer_size = 0
        
        self._initialize_camera()
        
    def _setup_dll_functions(self):
        """设置DLL函数参数类型"""
        self.qhyccddll.GetQHYCCDId.argtypes = [ctypes.c_uint32, ctypes.c_char_p]
        self.qhyccddll.OpenQHYCCD.argtypes = [ctypes.c_char_p]
        self.qhyccddll.OpenQHYCCD.restype = ctypes.c_void_p
        self.qhyccddll.CloseQHYCCD.argtypes = [ctypes.c_void_p]
        self.qhyccddll.SetQHYCCDReadMode.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self.qhyccddll.SetQHYCCDStreamMode.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self.qhyccddll.InitQHYCCD.argtypes = [ctypes.c_void_p]
        self.qhyccddll.GetQHYCCDChipInfo.argtypes = [ctypes.c_void_p,
                                                    ctypes.POINTER(ctypes.c_double), 
                                                    ctypes.POINTER(ctypes.c_double),
                                                    ctypes.POINTER(ctypes.c_uint32), 
                                                    ctypes.POINTER(ctypes.c_uint32),
                                                    ctypes.POINTER(ctypes.c_double), 
                                                    ctypes.POINTER(ctypes.c_double),
                                                    ctypes.POINTER(ctypes.c_uint32)]
        self.qhyccddll.GetQHYCCDParam.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self.qhyccddll.GetQHYCCDParam.restype = ctypes.c_double
        self.qhyccddll.SetQHYCCDParam.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_double]
        self.qhyccddll.SetQHYCCDDebayerOnOff.argtypes = [ctypes.c_void_p, ctypes.c_bool]
        self.qhyccddll.SetQHYCCDBinMode.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32]
        self.qhyccddll.SetQHYCCDResolution.argtypes = [ctypes.c_void_p, ctypes.c_uint32, 
                                                      ctypes.c_uint32, ctypes.c_uint32, 
                                                      ctypes.c_uint32]
        self.qhyccddll.IsQHYCCDControlAvailable.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self.qhyccddll.BeginQHYCCDLive.argtypes = [ctypes.c_void_p]
        self.qhyccddll.GetQHYCCDLiveFrame.argtypes = [ctypes.c_void_p,
                                                     ctypes.POINTER(ctypes.c_uint32), 
                                                     ctypes.POINTER(ctypes.c_uint32),
                                                     ctypes.POINTER(ctypes.c_uint32), 
                                                     ctypes.POINTER(ctypes.c_uint32),
                                                     ctypes.POINTER(ctypes.c_uint8)]
        self.qhyccddll.StopQHYCCDLive.argtypes = [ctypes.c_void_p]
        self.qhyccddll.InitQHYCCDResource.restype = ctypes.c_int
        self.qhyccddll.ScanQHYCCD.restype = ctypes.c_int
        self.qhyccddll.ReleaseQHYCCDResource.restype = ctypes.c_int

    def _initialize_camera(self):
        """初始化相机 - 按照官方Demo的正确顺序"""
        try:
            # 1. 初始化SDK资源
            ret = self.qhyccddll.InitQHYCCDResource()
            print(f"InitQHYCCDResource ret = {ret}")
            
            # 2. 扫描相机
            num = self.qhyccddll.ScanQHYCCD()
            print(f"ScanQHYCCD num = {num}")
            if num <= 0:
                raise Exception("No QHY camera found")
            
            # 3. 获取相机ID并打开
            id_buffer = ctypes.create_string_buffer(40)
            ret = self.qhyccddll.GetQHYCCDId(0, id_buffer)
            result_id = id_buffer.value.decode("utf-8")
            print(f"Camera ID: {result_id}")
            
            self.camhandle = self.qhyccddll.OpenQHYCCD(id_buffer)
            print(f"OpenQHYCCD camhandle = {hex(self.camhandle)}")
            if self.camhandle == 0:
                raise Exception("Failed to open camera")
            
            # 4. 设置读出模式
            ret = self.qhyccddll.SetQHYCCDReadMode(self.camhandle, 0)
            print(f"SetQHYCCDReadMode ret = {ret}")
            
            # 5. 【关键】设置Stream Mode为Live模式 (必须在InitQHYCCD之前)
            ret = self.qhyccddll.SetQHYCCDStreamMode(self.camhandle, 1)
            print(f"SetQHYCCDStreamMode ret = {ret}")
            
            # 6. 初始化相机
            ret = self.qhyccddll.InitQHYCCD(self.camhandle)
            print(f"InitQHYCCD ret = {ret}")
            
            # 7. 获取芯片信息
            chipW, chipH, imageW, imageH, pixelW, pixelH, imageB = \
                ctypes.c_double(), ctypes.c_double(), ctypes.c_uint32(), \
                ctypes.c_uint32(), ctypes.c_double(), ctypes.c_double(), ctypes.c_uint32()
            
            ret = self.qhyccddll.GetQHYCCDChipInfo(
                self.camhandle, byref(chipW), byref(chipH), 
                byref(imageW), byref(imageH), byref(pixelW),
                byref(pixelH), byref(imageB)
            )
            
            self.image_width = imageW.value
            self.image_height = imageH.value
            self.max_bit_depth = imageB.value
            
            print(f"Image: {self.image_width}x{self.image_height}, {self.max_bit_depth} bits")
            
            # 8. 【关键】检查是否是彩色相机并设置Debayer
            ret = self.qhyccddll.IsQHYCCDControlAvailable(self.camhandle, 
                                                         CONTROL_ID.CAM_IS_COLOR.value)
            if ret == 0:  # QHYCCD_SUCCESS
                self.is_color = True
                print("This is a color camera")
                # Live模式建议开启Debayer获取RGB图像
                ret = self.qhyccddll.SetQHYCCDDebayerOnOff(self.camhandle, True)
                print(f"SetQHYCCDDebayerOnOff(True) ret = {ret}")
                self.image_channels = 3
            else:
                self.is_color = False
                print("This is a mono camera")
                ret = self.qhyccddll.SetQHYCCDDebayerOnOff(self.camhandle, False)
                print(f"SetQHYCCDDebayerOnOff(False) ret = {ret}")
                self.image_channels = 1
            
            # 9. 设置其他参数
            self._set_default_parameters()
            
            # 10. 分配buffer
            self._allocate_buffer()
            
            print(">>> QHY Camera initialized successfully")
            
        except Exception as e:
            print(f"初始化相机失败: {e}")
            if self.camhandle != 0:
                self.qhyccddll.CloseQHYCCD(self.camhandle)
            raise
    
    def _allocate_buffer(self):
        """根据当前分辨率和位深预分配buffer"""
        # 为安全起见,按最大可能分配
        self.buffer_size = self.image_width * self.image_height * 4
        self.imgdata_buffer = (ctypes.c_uint8 * self.buffer_size)()
        print(f"Allocated buffer: {self.buffer_size} bytes")

    def _set_default_parameters(self):
        """设置默认参数"""
        # BIN模式
        ret = self.qhyccddll.SetQHYCCDBinMode(self.camhandle, 1, 1)
        print(f"SetQHYCCDBinMode ret = {ret}")
        
        # 分辨率
        ret = self.qhyccddll.SetQHYCCDResolution(self.camhandle, 0, 0, 
                                                self.image_width, self.image_height)
        print(f"SetQHYCCDResolution ret = {ret}")
        
        # 【关键修改】曝光时间必须在位深度之前设置
        self._exposure_us = 100000.0  # 100ms，先设置一个适中的值
        ret = self.qhyccddll.SetQHYCCDParam(self.camhandle, 
                                           CONTROL_ID.CONTROL_EXPOSURE.value, 
                                           self._exposure_us)
        print(f"SetQHYCCDParam EXPOSURE={self._exposure_us} us, ret = {ret}")
        
        # Gain
        ret = self.qhyccddll.SetQHYCCDParam(self.camhandle, 
                                           CONTROL_ID.CONTROL_GAIN.value, 50.0)
        print(f"SetQHYCCDParam GAIN ret = {ret}")
        
        # Offset
        ret = self.qhyccddll.SetQHYCCDParam(self.camhandle, 
                                           CONTROL_ID.CONTROL_OFFSET.value, 80.0)
        print(f"SetQHYCCDParam OFFSET ret = {ret}")
        
        # USB Traffic (参考官方Demo设置为0，表示最大速度)
        ret = self.qhyccddll.SetQHYCCDParam(self.camhandle, 
                                           CONTROL_ID.CONTROL_USBTRAFFIC.value, 0.0)
        print(f"SetQHYCCDParam USBTRAFFIC ret = {ret}")
        
        # 位深度 (官方Live Demo用的是8-bit)
        ret = self.qhyccddll.SetQHYCCDParam(self.camhandle, 
                                           CONTROL_ID.CONTROL_TRANSFERBIT.value, 8.0)
        print(f"SetQHYCCDParam TRANSFERBIT=8 ret = {ret}")
        self._current_bit_depth = 8

    def set_ex_time(self, ex_time):
        """设置曝光时间 (秒)"""
        try:
            self._exposure_us = ex_time * 1e6
            ret = self.qhyccddll.SetQHYCCDParam(self.camhandle, 
                                               CONTROL_ID.CONTROL_EXPOSURE.value, 
                                               self._exposure_us)
            print(f"Set exposure: {self._exposure_us} us, ret = {ret}")
        except Exception as e:
            print(f'设置曝光时间失败: {e}')

    def set_bit_depth(self, bit_depth):
        """设置位深度"""
        try:
            if bit_depth >= 16:
                ret = self.qhyccddll.SetQHYCCDParam(self.camhandle, 
                                                   CONTROL_ID.CONTROL_TRANSFERBIT.value, 16.0)
                self._current_bit_depth = 16
            else:
                ret = self.qhyccddll.SetQHYCCDParam(self.camhandle, 
                                                   CONTROL_ID.CONTROL_TRANSFERBIT.value, 8.0)
                self._current_bit_depth = 8
            print(f"Set bit depth: {self._current_bit_depth}, ret = {ret}")
        except Exception as e:
            print(f'设置位深度失败: {e}')

    def start_acquisition(self):
        """开始实时采集"""
        if self._is_live_mode:
            print("Already in live mode")
            return 
            
        try:
            # 注意:StreamMode已经在初始化时设置为1了,这里直接开始Live
            ret = self.qhyccddll.BeginQHYCCDLive(self.camhandle)
            print(f"BeginQHYCCDLive ret = {ret}")
            
            if ret == 0:
                self._is_live_mode = True
                print(">>> QHY Live mode started")
            else:
                print(f">>> BeginQHYCCDLive failed with ret = {ret}")
        except Exception as e:
            print(f'开始实时采集失败: {e}')

    def stop_acquisition(self):
        """停止实时采集"""
        try:
            if self._is_live_mode:
                ret = self.qhyccddll.StopQHYCCDLive(self.camhandle)
                print(f"StopQHYCCDLive ret = {ret}")
                self._is_live_mode = False
        except Exception as e:
            print(f'停止实时采集失败: {e}')

    def read_newest_image(self):
        """读取最新的图像"""
        if not self._is_live_mode:
            self.start_acquisition()
            # 【关键】等待第一帧准备好（曝光时间 + buffer时间）
            wait_time = max(0.1, self._exposure_us / 1e6 + 0.05)
            print(f"Waiting {wait_time:.2f}s for first frame...")
            time.sleep(wait_time)
            
        w = ctypes.c_uint32()
        h = ctypes.c_uint32()
        b = ctypes.c_uint32()
        c = ctypes.c_uint32()
        
        # 【关键修改】循环尝试获取，最多重试5次
        max_retries = 5
        for attempt in range(max_retries):
            ret = self.qhyccddll.GetQHYCCDLiveFrame(self.camhandle, byref(w), byref(h), 
                                                   byref(b), byref(c), self.imgdata_buffer)
            
            if ret == 0:
                # 成功获取数据
                # if attempt > 0:
                #     print(f"Got frame after {attempt + 1} attempts")
                
                if b.value == 16:
                    raw_data = np.frombuffer(self.imgdata_buffer, dtype=np.uint16, 
                                            count=w.value * h.value * c.value).copy()
                elif b.value == 8:
                    raw_data = np.frombuffer(self.imgdata_buffer, dtype=np.uint8, 
                                            count=w.value * h.value * c.value).copy()
                else:
                    print(f"Unknown bit depth: {b.value}")
                    return None
                
                if c.value == 1:
                    return raw_data.reshape((h.value, w.value))
                elif c.value == 3:
                    return raw_data.reshape((h.value, w.value, c.value))
                else:
                    print(f"Unknown channel count: {c.value}")
                    return None
            else:
                # 失败，短暂等待后重试
                # if attempt == 0:
                #     # 第一次失败时打印详细信息
                #     print(f"GetQHYCCDLiveFrame ret = {ret} (attempt {attempt + 1})")
                time.sleep(0.02)  # 等待20ms
        
        # 所有尝试都失败
        return None

    def get_bit_depth(self):
        return self._current_bit_depth

    def close(self):
        """关闭相机"""
        try:
            if hasattr(self, '_is_live_mode') and self._is_live_mode:
                self.stop_acquisition()
            
            if hasattr(self, 'camhandle') and self.camhandle != 0:
                if self.qhyccddll:
                    self.qhyccddll.CloseQHYCCD(self.camhandle)
                    self.qhyccddll.ReleaseQHYCCDResource()
                self.camhandle = 0
                print("QHY camera closed")
        except Exception as e:
            print(f"Error closing QHY camera: {e}")

    def __del__(self):
        self.close()


# ===== 测试代码 =====
if __name__ == "__main__":
    import cv2

    try:
        print("="*50)
        print("初始化相机...")
        print("="*50)
        cam = QHYCamera()
        
        # 设置参数
        cam.set_ex_time(0.02)  # 20ms曝光
        
        # 开始采集
        cam.start_acquisition()
        
        print("\n开始预览。按 'q' 退出, 按 's' 保存截图。\n")
        
        window_name = "QHY Live Preview"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 1024, 768)
        
        last_time = time.time()
        frames = 0
        empty_count = 0
        
        # 【关键】给相机充足的预热时间
        print("等待相机预热...")
        time.sleep(0.5)

        while True:
            img = cam.read_newest_image()
            
            if img is not None:
                empty_count = 0  # 重置空帧计数
                
                # 16位转8位显示
                if img.dtype == np.uint16:
                    display_img = cv2.normalize(img, None, 0, 255, 
                                               cv2.NORM_MINMAX).astype(np.uint8)
                else:
                    display_img = img
                
                cv2.imshow(window_name, display_img)
                
                # 帧率统计
                frames += 1
                if frames % 20 == 0:
                    curr_time = time.time()
                    fps = 20 / (curr_time - last_time)
                    print(f"FPS: {fps:.1f} | Shape: {img.shape} | dtype: {img.dtype}")
                    last_time = curr_time

                key = cv2.waitKey(1) & 0xFF
                
                if key == ord('q'):
                    break
                elif key == ord('s'):
                    filename = f"QHY_Capture_{int(time.time())}.png"
                    cv2.imwrite(filename, img)
                    print(f"已保存: {filename}")
            else:
                # 连续空帧检测
                empty_count += 1
                if empty_count % 50 == 0:
                    print(f"警告: 已连续{empty_count}次未获取到图像")
                
                # 短暂休息,避免CPU占满
                time.sleep(0.01)
                
                # 仍然检测按键
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"错误: {e}")
    finally:
        if 'cam' in locals():
            cam.close()
        cv2.destroyAllWindows()