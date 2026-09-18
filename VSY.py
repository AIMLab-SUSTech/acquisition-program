from abc import ABC
import sys
import ctypes
from ctypes import *
import numpy as np
from abc import ABC, abstractmethod


from camera import Camera


# 此处省略您提供的所有常量定义和结构体定义...




VSY_MAX_DEVICE_NUM = 20
VSY_MAX_IPV4_ADDR_LEN = 16
VSY_MAX_STRING_LEN = 256
VSY_MAX_XML_ENUM_NUM = 32
VSY_MAX_XML_DISC_STRLEN = 512
VSY_MAX_XML_NODE_STRLEN = 54
VSY_MAX_XML_NODE_NUM = 128

VSY_GVSP_PIX_MONO = 0x01000000

# 图像相关码
VSY_BUFFER_STATUS_SUCCESS = 0x00000001
VSY_BUFFER_STATUS_TIMEOUT = 0x00000002
VSY_BUFFER_STATUS_FAILED = 0x00000003


# 枚举值定义
class VSY_XML_Interface(ctypes.c_int):
    T_Undefined = -1
    T_Integer = 0
    T_Boolean = 1
    T_Command = 2
    T_Float = 3
    T_String = 4
    T_Register = 5
    T_Category = 6
    T_Enumeration = 7
    T_EnumEntry = 8
    T_Port = 9


class VSY_XML_AccessMode(ctypes.c_int):
    AM_Undefined = -1
    AM_RO = 1
    AM_WO = 2
    AM_RW = 3
    AM_NI = 4
    AM_NA = 5


class VSY_XML_Visibility(ctypes.c_int):
    V_Undefined = -1
    V_Invisible = 1
    V_Guru = 2
    V_Expert = 3
    V_Beginner = 4


class VSY_XML_Representation(ctypes.c_int):
    R_Undefined = -1
    R_Linear = 1
    R_Logarithmic = 2
    R_Boolean = 3
    R_PureNumber = 4
    R_HexNumber = 5
    R_IPV4Address = 6
    R_MacAddress = 7


class VsyGvspPixelType(ctypes.c_int):
    # Undefined pixel type
    PixelType_Gvsp_Undefined = 0xFFFFFFFF,

    # Mono buffer format defines
    PixelType_Gvsp_Mono8 = (VSY_GVSP_PIX_MONO | (8 << 16) | 0x0001)
    PixelType_Gvsp_Mono8_Signed = (VSY_GVSP_PIX_MONO | (8 << 16) | 0x0002)
    PixelType_Gvsp_Mono10 = (VSY_GVSP_PIX_MONO | (16 << 16) | 0x0003)
    PixelType_Gvsp_Mono10_Packed = (VSY_GVSP_PIX_MONO | (12 << 16) | 0x0004)
    PixelType_Gvsp_Mono12 = (VSY_GVSP_PIX_MONO | (16 << 16) | 0x0005)
    PixelType_Gvsp_Mono12_Packed = (VSY_GVSP_PIX_MONO | (12 << 16) | 0x0006)
    PixelType_Gvsp_Mono14 = (VSY_GVSP_PIX_MONO | (16 << 16) | 0x0025)
    PixelType_Gvsp_Mono16 = (VSY_GVSP_PIX_MONO | (16 << 16) | 0x0007)


# 定义设备信息结构体
class VSY_CC_DEVICE_INFO(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("nDeviceType", ctypes.c_ushort),
                ("ip_addr", ctypes.c_char * VSY_MAX_IPV4_ADDR_LEN)]


# 定义设备信息列表结构体
class VSY_CC_DEVICE_INFO_LIST(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("nDeviceNum", ctypes.c_uint),
                ("stDeviceInfo", VSY_CC_DEVICE_INFO * VSY_MAX_DEVICE_NUM)]


# 枚举值信息结构体
class VSY_CC_STRING_VALUE(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("chCurValue", ctypes.c_char * VSY_MAX_STRING_LEN)]


class VSY_CC_ENUM_VALUE(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("nCurValue", ctypes.c_uint),
                ("chCurValue", ctypes.c_char * VSY_MAX_STRING_LEN),
                ("nSupportedNum", ctypes.c_uint),
                ("nSupportedValue", ctypes.c_uint * VSY_MAX_XML_ENUM_NUM),
                ("stSupportedValue", VSY_CC_STRING_VALUE * VSY_MAX_XML_ENUM_NUM)]


# 节点信息结构体
class VSY_XML_NODE_FEATURE(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("enType", VSY_XML_Interface),
                ("enVisibility", VSY_XML_Visibility),
                ("enAccessMode", VSY_XML_AccessMode),
                ("strDescription", ctypes.c_char * VSY_MAX_XML_DISC_STRLEN),
                ("strName", ctypes.c_char * VSY_MAX_XML_NODE_STRLEN)]


class VSY_XML_NODE_FEATURE_LIST(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("nNodeNum", ctypes.c_uint),
                ("stNodes", VSY_XML_NODE_FEATURE * VSY_MAX_XML_NODE_NUM)]


class VSY_FRAME_OUT_INFO_EX(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("nWidth", ctypes.c_ushort),
                ("nHeight", ctypes.c_ushort),
                ("nFrameLen", ctypes.c_uint),
                ("nFrameID", ctypes.c_uint),
                ("enPixelType", VsyGvspPixelType)]


class VSyCamera(Camera):
    def __init__(self):
        super().__init__()
        self.pDevObject = None
        self.width = 0
        self.height = 0
        self.bits = 8
        self.frame_rate = 30.0
        self._initialize_camera()


    def _initialize_camera(self):
        """初始化相机连接"""
        # 加载动态库（路径需要根据实际环境调整）
        self.VsyGevLib = cdll.LoadLibrary("C:/Users/JKHKOJKLJ/Documents/GitHub/acquisition-program/dll/vsy/VsyCameraControl.dll")
        self.VsyGevLib.VSY_GigECam_SetFeature.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_double, ctypes.c_ushort]

        # 搜索设备
        devicelist = VSY_CC_DEVICE_INFO_LIST()
        ret = self.VsyGevLib.VSY_GigECam_EnumDevices(byref(devicelist))
        if ret != 0 or devicelist.nDeviceNum < 1:
            raise RuntimeError("No cameras found")

        # 创建设备对象
        self.pDevObject = c_void_p()
        ret = self.VsyGevLib.VSY_GigECam_CreateObject(byref(self.pDevObject), byref(devicelist.stDeviceInfo[0]))
        if ret != 0:
            raise RuntimeError("Camera object creation failed")

        # self.set_pixel_format(VsyGvspPixelType.PixelType_Gvsp_Mono12_Packed)

        # 打开设备
        if self.VsyGevLib.VSY_GigECam_OpenDevice(self.pDevObject) != 0:
            self._cleanup()
            raise RuntimeError("Device connection failed")

        # 获取基础参数
        self._get_sensor_params()
        self._setup_initial_settings()

    def _get_sensor_params(self):
        """获取传感器参数"""
        # 获取宽高
        w, h = c_double(), c_double()
        self._check_error(
            self.VsyGevLib.VSY_GigECam_GetFeature(self.pDevObject, b"Width", byref(w), VSY_XML_Interface.T_Integer),
            "Get width failed"
        )
        self._check_error(
            self.VsyGevLib.VSY_GigECam_GetFeature(self.pDevObject, b"Height", byref(h), VSY_XML_Interface.T_Integer),
            "Get height failed"
        )
        self.width, self.height = int(w.value), int(h.value)

        # 获取像素格式
        stEnumValue = VSY_CC_ENUM_VALUE()
        self._check_error(
            self.VsyGevLib.VSY_GigECam_GetFeatureEnum(self.pDevObject, b"PixelFormat", byref(stEnumValue)),
            "Get pixel format failed"
        )
        self.bits = (stEnumValue.nCurValue >> 16) & 0xff

    def _setup_initial_settings(self):
        """初始化相机设置"""
        # 设置内触发模式
        self._check_error(
            self.VsyGevLib.VSY_GigECam_SetFeature(self.pDevObject, b"TriggerMode", 0, VSY_XML_Interface.T_Enumeration),
            "Set trigger mode failed"
        )

    def set_pixel_format(self, pixel_type):
        """
        设置像素格式
        :param pixel_type: 使用 VsyGvspPixelType 中的枚举值，如 PixelType_Gvsp_Mono12_Packed
        """
        # 验证是否支持该格式
        stEnum = VSY_CC_ENUM_VALUE()
        ret = self.VsyGevLib.VSY_GigECam_GetFeatureEnum(
            self.pDevObject,
            b"PixelFormat",
            byref(stEnum)
        )
        if ret != 0:
            raise RuntimeError("Failed to get supported pixel formats")

        # 检查目标格式是否在支持列表中
        supported_values = list(stEnum.nSupportedValue)[:stEnum.nSupportedNum]

        if pixel_type not in supported_values:
            raise ValueError(f"Unsupported pixel format: 0x{pixel_type:X}")

        # 设置像素格式
        ret = self.VsyGevLib.VSY_GigECam_SetFeature(
            self.pDevObject,
            b"PixelFormat",
            pixel_type,
            VSY_XML_Interface.T_Enumeration
        )
        self._check_error(ret, "Set pixel format failed")

        # 更新当前位深参数
        self.bits = (pixel_type >> 16) & 0xff

    def set_ex_time(self, ex_time):
        """设置曝光时间（单位：秒）"""
        # 转换为毫秒（假设SDK使用毫秒为单位）
        ex_ms = ex_time * 1000
        ret = self.VsyGevLib.VSY_GigECam_SetFeature(
            self.pDevObject,
            b"ExposureTime",
            c_double(ex_ms),
            VSY_XML_Interface.T_Float
        )
        self._check_error(ret, "Set exposure time failed")

    def start_acquisition(self):
        """开始采集"""
        ret = self.VsyGevLib.VSY_GigECam_StartAcquisition(self.pDevObject)
        self._check_error(ret, "Start acquisition failed")

    def read_newest_image(self):
        """读取最新图像帧"""
        # 计算缓冲区大小
        imgsize = self.width * self.height * (2 if self.bits > 8 else 1)

        # 获取图像帧
        img_buffer = (c_ubyte * imgsize)()
        frame_info = VSY_FRAME_OUT_INFO_EX()

        ret = self.VsyGevLib.VSY_GigECam_GetOneFrameTimeoutEx(
            self.pDevObject,
            cast(img_buffer, POINTER(c_ubyte)),
            imgsize,
            byref(frame_info),
            1000  # 超时时间1秒
        )

        if ret != VSY_BUFFER_STATUS_SUCCESS:
            return ret

        # 转换为numpy数组
        dtype = np.uint16
        img_np = np.frombuffer(img_buffer, dtype=dtype).reshape((self.height, self.width))

        return img_np

    def get_frame_period(self):
        """获取帧周期（秒）"""
        fps = c_double()
        self._check_error(
            self.VsyGevLib.VSY_GigECam_GetFeature(self.pDevObject, b"AcquisitionFrameRate", byref(fps),
                                                  VSY_XML_Interface.T_Float),
            "Get frame rate failed"
        )
        return 1.0 / fps.value

    def _check_error(self, ret, msg):
        """错误检查"""
        if ret != 0:
            self._cleanup()
            raise RuntimeError(f"{msg} (error code: {ret})")

    def _cleanup(self):
        """资源清理"""
        if self.pDevObject:
            self.VsyGevLib.VSY_GigECam_StopAcquisition(self.pDevObject)
            self.VsyGevLib.VSY_GigECam_CloseDevice(self.pDevObject)
            self.VsyGevLib.VSY_GigECam_DestroyObject(self.pDevObject)
            self.pDevObject = None

    def __del__(self):
        self._cleanup()


# 使用示例
if __name__ == "__main__":
    cam = VSyCamera()
    cam.set_pixel_format(VsyGvspPixelType.PixelType_Gvsp_Mono16)
    # 设置参数
    cam.set_ex_time(0.1) # S
    MONO12_PACKED = 0x010C0006  # 对应PixelType_Gvsp_Mono12_Packed


    # 开始采集
    cam.start_acquisition()


    img = cam.read_newest_image()

    print(np.min(img), np.mean(img), np.max(img))
    
    cam.set_ex_time(0.01)

    img = cam.read_newest_image()

    print(np.min(img), np.mean(img), np.max(img))

    # 获取帧率信息
    print(f"Frame period: {cam.get_frame_period():.3f}s")