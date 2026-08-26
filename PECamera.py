import ctypes
import numpy as np
from abc import ABC, abstractmethod

# 假设 Camera 基类已按原文件定义
class Camera(ABC):
    @abstractmethod
    def set_ex_time(self, ex_time): pass
    @abstractmethod
    def start_acquisition(self): pass
    @abstractmethod
    def read_newest_image(self): pass
    @abstractmethod
    def get_frame_period(self): pass

class PhotonEyeCamera(Camera):
    def __init__(self, dll_path="SLApi.dll", tl_type=0x30100003, if_idx=0, dev_idx=0):
        super().__init__()
        # 加载 C 动态链接库[cite: 1]
        self.slapi = ctypes.cdll.LoadLibrary(dll_path)
        
        # 初始化 SDK[cite: 1]
        self.slapi.SLIF_Init()
        
        self.hDevice = ctypes.c_void_p(None)
        # 打开指定传输层(TL)、接口索引和设备索引的相机[cite: 1]
        self.slapi.SLIF_OpenDevice(ctypes.c_uint(tl_type), ctypes.c_uint(if_idx), ctypes.c_uint(dev_idx), ctypes.byref(self.hDevice))

    def set_ex_time(self, ex_time):
        """设置曝光时间，将秒(S)转换为微秒(us)传递给C接口"""
        try:
            exposure_us = ctypes.c_double(ex_time * 1e6)
            # 通过 SLIF_SetFloat 设置 ExposureTime[cite: 1]
            self.slapi.SLIF_SetFloat(self.hDevice, b"ExposureTime", exposure_us)
        except Exception as e:
            print(f'PhotonEye曝光时间设置失败：{e}')

    def start_acquisition(self):
        """开始取流并切换至预览模式"""
        try:
            # 启动底层流传输[cite: 1]
            self.slapi.SLIF_StartCapture(self.hDevice)
            # 切换相机模式为 CAMERA_MODE_PREVIEW (值为 5)[cite: 1]
            # 参数类型常量 PARAM_VALUE_INT 对应 1[cite: 1]
            self.slapi.SLIF_SetInteger(self.hDevice, b"Mode", ctypes.c_longlong(5), 1)
        except Exception as e:
            print(f'PhotonEye开始采集失败：{e}')

    def read_newest_image(self):
        """读取单帧并转为 NumPy 数组"""
        # 对应 C 语言的 SL_REQIMAGES_PARAM 结构体[cite: 1]
        class SL_REQIMAGES_PARAM(ctypes.Structure):
            _fields_ = [("Width", ctypes.c_uint), ("Height", ctypes.c_uint), 
                        ("pixformat", ctypes.c_uint), ("datasize", ctypes.c_ulonglong),
                        ("frameid", ctypes.c_uint), ("AdcBitdepth", ctypes.c_uint),
                        ("RunMode", ctypes.c_uint), ("CacheSize", ctypes.c_uint),
                        ("BeforeTriggerFrameALLNum", ctypes.c_uint), ("AfterTriggerFrameALLNum", ctypes.c_uint),
                        ("BeforeTriggerFrameRecNum", ctypes.c_uint), ("AfterTriggerFrameRecNum", ctypes.c_uint),
                        ("LoopFlag", ctypes.c_uint)]

        data_ptr = ctypes.POINTER(ctypes.c_ubyte)()
        param = SL_REQIMAGES_PARAM()
        
        try:
            # 获取单帧，超时时间设为连续取流示例中的 500ms[cite: 1]
            ret = self.slapi.SLIF_AcquirePreviewFrameRef(self.hDevice, ctypes.byref(data_ptr), ctypes.byref(param), 500)
            
            # SLAPI_OK 的值为 0[cite: 1]
            if ret == 0 and param.datasize > 0:
                # 根据 C 指针地址和大小映射为 Numpy 数组，与 Basler/Galaxy 返回格式一致[cite: 1, 2]
                buffer_type = ctypes.c_ubyte * param.datasize
                buf = buffer_type.from_address(ctypes.addressof(data_ptr.contents))
                image = np.frombuffer(buf, dtype=np.uint8).reshape(param.Height, param.Width)
                return image
            return None
        except Exception as e:
            print(f'PhotonEye获取图像失败：{e}')
            return None

    def get_frame_period(self):
        """获取帧周期（S）"""
        try:
            fps = ctypes.c_longlong(0)
            # 通过 SLIF_GetInteger 读取 AcquisitionFrameRate 参数[cite: 1]
            self.slapi.SLIF_GetInteger(self.hDevice, b"AcquisitionFrameRate", ctypes.byref(fps), 1)
            return 1.0 / float(fps.value) if fps.value > 0 else 0.0
        except Exception as e:
            print(f'PhotonEye获取帧率失败：{e}')
            return 0.0

    def close(self):
        """停止取流并断开设备连接"""
        if self.hDevice:
            # 停止流传输[cite: 1]
            self.slapi.SLIF_StopCapture(self.hDevice)
            # 切换相机模式为 CAMERA_MODE_IDLE (值为 1)[cite: 1]
            self.slapi.SLIF_SetInteger(self.hDevice, b"Mode", ctypes.c_longlong(1), 1)
            # 关闭设备句柄并反初始化 SDK[cite: 1]
            self.slapi.SLIF_CloseDevice(self.hDevice)
            self.slapi.SLIF_UnInit()
            self.hDevice = None