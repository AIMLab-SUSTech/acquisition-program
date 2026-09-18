from abc import ABC
import sys
import ctypes
from ctypes import *
import numpy as np
from camera import Camera


# 常量定义
VSY_DEVICE_GIGE	= 0x00000001    # GigE
VSY_DEVICE_GBE = 0x00000002      # GbE
VSY_DEVICE_UVC = 0x00000004      # UVC
VSY_DEVICE_U3V = 0x00000008		# USB3.0

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

VSY_TIMESTAMP_PIXELS_COUNT = 8


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
    _fields_ = [('nDeviceType', ctypes.c_ushort),
                ('ip_addr', ctypes.c_char * VSY_MAX_IPV4_ADDR_LEN),
                ('chModelName', ctypes.c_char * VSY_MAX_STRING_LEN),
                ('chSerialNumber', ctypes.c_char * VSY_MAX_STRING_LEN)]


# 定义设备信息列表结构体
class VSY_CC_DEVICE_INFO_LIST(ctypes.Structure):
    _pack_ = 1
    _fields_ = [('nDeviceNum', ctypes.c_uint),
               ('stDeviceInfo', VSY_CC_DEVICE_INFO * VSY_MAX_DEVICE_NUM)]


# 枚举值信息结构体
class VSY_CC_STRING_VALUE(ctypes.Structure):
    _pack_ = 1
    _fields_ = [('chCurValue', ctypes.c_char * VSY_MAX_STRING_LEN)]


class VSY_CC_ENUM_VALUE(ctypes.Structure):
    _pack_ = 1
    _fields_ = [('nCurValue', ctypes.c_uint),
               ('chCurValue', ctypes.c_char * VSY_MAX_STRING_LEN),
               ('nSupportedNum', ctypes.c_uint),
               ('nSupportedValue', ctypes.c_uint * VSY_MAX_XML_ENUM_NUM),
               ('stSupportedValue', VSY_CC_STRING_VALUE * VSY_MAX_XML_ENUM_NUM)]


# 节点信息结构体
class VSY_XML_NODE_FEATURE(ctypes.Structure):
    _pack_ = 1
    _fields_ = [('enType', VSY_XML_Interface),
               ('enVisibility', VSY_XML_Visibility),
               ('enAccessMode', VSY_XML_AccessMode),
               ('strDescription', ctypes.c_char * VSY_MAX_XML_DISC_STRLEN),
               ('strName', ctypes.c_char * VSY_MAX_XML_NODE_STRLEN)]


class VSY_XML_NODE_FEATURE_LIST(ctypes.Structure):
    _pack_ = 1
    _fields_ = [('nNodeNum', ctypes.c_uint),
               ('stNodes', VSY_XML_NODE_FEATURE * VSY_MAX_XML_NODE_NUM)]

class VSY_FRAME_OUT_INFO_EX(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        # 图像基础参数
        ('nWidth', ctypes.c_ushort),  # unsigned short → 图像宽度
        ('nHeight', ctypes.c_ushort),  # unsigned short → 图像高度
        ('nFrameLen', ctypes.c_uint),  # unsigned int → 帧数据总长度（字节）
        ('nFrameID', ctypes.c_uint),  # unsigned int → 帧序号（唯一标识）
        ('enPixelType', VsyGvspPixelType),  # enum → 像素格式（本质是 c_int 兼容）

        # 像素属性参数
        ('pixelBits', ctypes.c_int),  # int → 像素有效位数（如 8/10/12）
        ('pixelSize', ctypes.c_double),  # double → 像素物理尺寸（μm，<0 表示未配置）
        ('isPixelSigned', ctypes.c_int),  # int → 是否有符号（0=无符号，1=有符号）

        # 统计信息
        ('statisEnabled', ctypes.c_int),  # int → 统计功能使能（1=启用，0=禁用）
        ('sum', ctypes.c_double),  # double → 像素灰度总和
        ('squareSum', ctypes.c_double),  # double → 像素灰度平方和
        ('count', ctypes.c_double),  # double → 参与统计的像素数
        ('mean', ctypes.c_double),  # double → 平均灰度值
        ('variance', ctypes.c_double),  # double → 方差
        ('sigma', ctypes.c_double),  # double → 标准差
        ('rms', ctypes.c_double),  # double → 均方根
        ('min', ctypes.c_double),  # double → 最小灰度值
        ('max', ctypes.c_double),  # double → 最大灰度值

        # 时间戳相关参数
        ('timestampType', ctypes.c_int),  # int → 时间戳类型（0=无，1=0-6字节，2=16-22字节）
        ('timestampUtcSeconds', ctypes.c_longlong),  # long long → UTC 时间（秒）
        ('timestampUtcUs', ctypes.c_longlong),  # long long → UTC 时间（微秒）
        ('keepTimestampInImage', ctypes.c_int),  # int → 图像是否保留时间戳（0=不保留，1=保留）

        # 时间戳像素数组（长度由 VSY_TIMESTAMP_PIXELS_COUNT 定义）
        ('timestampPixels', ctypes.c_int * VSY_TIMESTAMP_PIXELS_COUNT)
    ]


class NewVSyCamera(Camera):
    def __init__(self):
        super().__init__()
        self.pDevObject = None
        self.width = 0
        self.height = 0
        self.bits = 8
        self.frame_rate = 30.0
        self.VsyCamCtrlLib = None
        self._initialize_camera()

    def _initialize_camera(self):
        """初始化相机连接"""
        # 加载动态库
        self.VsyCamCtrlLib = ctypes.CDLL("./dll/vsy/VsyCameraControl.dll")

        # 搜索设备
        devicelist = VSY_CC_DEVICE_INFO_LIST()
        ret = self.VsyCamCtrlLib.VSY_CC_EnumDevices(VSY_DEVICE_GIGE | VSY_DEVICE_GBE, ctypes.byref(devicelist))
        if ret != 0:
            raise RuntimeError(f"VSY_CC_EnumDevices failed with error code {ret}")

        if devicelist.nDeviceNum < 1:
            raise RuntimeError("No cameras found")

        # 打印搜索到的设备 IP
        print(f"Found {devicelist.nDeviceNum} devices:")
        for i in range(devicelist.nDeviceNum):
            ip_addr = devicelist.stDeviceInfo[i].ip_addr.decode('utf-8').rstrip('\x00')
            print(f"Device {i + 1}: ip:{ip_addr}, type:{devicelist.stDeviceInfo[i].nDeviceType}")

        # 创建设备对象
        self.pDevObject = ctypes.c_void_p()
        ret = self.VsyCamCtrlLib.VSY_CC_CreateObject(ctypes.byref(self.pDevObject), ctypes.byref(devicelist.stDeviceInfo[0]))
        if ret != 0:
            raise RuntimeError(f"VSY_CC_CreateObject failed with error code {ret}")

        # 打开设备
        ret = self.VsyCamCtrlLib.VSY_CC_OpenDevice(self.pDevObject)
        if ret != 0:
            self._cleanup()
            raise RuntimeError(f"VSY_CC_OpenDevice failed with error code {ret}")

        # 设置函数参数类型
        self.VsyCamCtrlLib.VSY_CC_SetFeature.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_double, ctypes.c_ushort]
        self.VsyCamCtrlLib.VSY_CC_SetFeature.restype = c_int
        self.VsyCamCtrlLib.VSY_CC_GetFeature.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_double), ctypes.c_ushort]
        self.VsyCamCtrlLib.VSY_CC_GetFeature.restype = c_int
        self.VsyCamCtrlLib.VSY_CC_GetFeatureEnum.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(VSY_CC_ENUM_VALUE)]
        self.VsyCamCtrlLib.VSY_CC_GetFeatureEnum.restype = ctypes.c_int

        # 获取基础参数
        self._get_sensor_params()
        self._setup_initial_settings()

    def _get_sensor_params(self):
        """获取传感器参数"""
        # 获取宽高
        w, h = c_double(), c_double()
        self._check_error(
            self.VsyCamCtrlLib.VSY_CC_GetFeature(self.pDevObject, b"Width", byref(w), VSY_XML_Interface.T_Integer),
            "Get width failed"
        )
        self._check_error(
            self.VsyCamCtrlLib.VSY_CC_GetFeature(self.pDevObject, b"Height", byref(h), VSY_XML_Interface.T_Integer),
            "Get height failed"
        )
        self.width, self.height = int(w.value), int(h.value)

        # 默认使用16位像素格式
        self.bits = 12

    def _setup_initial_settings(self):
        """初始化相机设置"""
        # 设置触发模式 0-内触发
        self._check_error(
            self.VsyCamCtrlLib.VSY_CC_SetFeature(self.pDevObject, b"TriggerMode", 0, VSY_XML_Interface.T_Enumeration),
            "Set trigger mode failed"
        )

        # 设置曝光时间为20.0毫秒
        self._check_error(
            self.VsyCamCtrlLib.VSY_CC_SetFeature(self.pDevObject, b"ExposureTime", 20.0, VSY_XML_Interface.T_Float),
            "Set exposure time failed"
        )

        # 设置帧频为2.0 fps
        self.frame_rate = 5.0
        self._check_error(
            self.VsyCamCtrlLib.VSY_CC_SetFeature(self.pDevObject, b"AcquisitionFrameRate", self.frame_rate, VSY_XML_Interface.T_Float),
            "Set frame rate failed"
        )

    def set_pixel_format(self, pixel_type):
        """
        设置像素格式
        :param pixel_type: 使用 VsyGvspPixelType 中的枚举值
        """
        # 验证是否支持该格式
        stEnum = VSY_CC_ENUM_VALUE()
        ret = self.VsyCamCtrlLib.VSY_CC_GetFeatureEnum(
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
        ret = self.VsyCamCtrlLib.VSY_CC_SetFeature(
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
        # 转换为毫秒
        ex_ms = ex_time * 1000.0
        ret = self.VsyCamCtrlLib.VSY_CC_SetFeature(
            self.pDevObject,
            b"ExposureTime",
            ex_ms,
            VSY_XML_Interface.T_Float
        )
        self._check_error(ret, "Set exposure time failed")

    def start_acquisition(self):
        """开始采集"""
        ret = self.VsyCamCtrlLib.VSY_CC_StartAcquisition(self.pDevObject)
        self._check_error(ret, "Start acquisition failed")

    def read_newest_image(self):
        """读取最新图像帧"""
        # 计算缓冲区大小
        imgsize = self.width * self.height * (2 if self.bits > 8 else 1)

        # 设置函数参数类型
        self.VsyCamCtrlLib.VSY_CC_GetOneFrameTimeoutEx.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte),
                                                                   ctypes.c_uint, ctypes.POINTER(VSY_FRAME_OUT_INFO_EX),
                                                                  ctypes.c_uint]
        self.VsyCamCtrlLib.VSY_CC_GetOneFrameTimeoutEx.restype = ctypes.c_int

        # 分配用于存储图像数据的缓冲区
        img_buffer = (ctypes.c_ubyte * imgsize)()
        frameinfo = VSY_FRAME_OUT_INFO_EX()

        ret = self.VsyCamCtrlLib.VSY_CC_GetOneFrameTimeoutEx(self.pDevObject, ctypes.cast(img_buffer, ctypes.POINTER(ctypes.c_ubyte)),
                                                              imgsize, ctypes.byref(frameinfo), 1000)

        if ret != VSY_BUFFER_STATUS_SUCCESS:
            return ret

        # 转换为numpy数组
        img_np = np.ctypeslib.as_array(img_buffer)

        # 根据像素位数调整图像格式
        if frameinfo.pixelBits == 8:
            # 8位灰度图像
            img_np = img_np.reshape((frameinfo.nHeight, frameinfo.nWidth))
        else:
            # 16位灰度图像
            img_np = img_np.view(np.uint16).reshape((frameinfo.nHeight, frameinfo.nWidth))

        return img_np

    def get_frame_period(self):
        """获取帧周期（秒）"""
        fps = c_double()
        self._check_error(
            self.VsyCamCtrlLib.VSY_CC_GetFeature(self.pDevObject, b"AcquisitionFrameRate", byref(fps), VSY_XML_Interface.T_Float),
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
            self.VsyCamCtrlLib.VSY_CC_StopAcquisition(self.pDevObject)
            self.VsyCamCtrlLib.VSY_CC_CloseDevice(self.pDevObject)
            self.VsyCamCtrlLib.VSY_CC_DestroyObject(self.pDevObject)
            self.pDevObject = None

    def __del__(self):
        self._cleanup()


# 使用示例
if __name__ == "__main__":
    import matplotlib.pyplot as plt
    from time import sleep
    try:
        # 初始化相机
        cam = NewVSyCamera()
        
        # 开始采集
        cam.start_acquisition()
        
        # 获取一帧图像
        for i in range(100):
            img_np = cam.read_newest_image()
        # sleep(10)
            print(img_np.shape)
        img_np = cam.read_newest_image()
        # print(f"Frame ID: {frameinfo.nFrameID}, Width: {frameinfo.nWidth}, Height: {frameinfo.nHeight}")
        # print(f"Pixel bits: {frameinfo.pixelBits}, Mean: {frameinfo.mean:.2f}, Max: {frameinfo.max:.2f}")
        
        # 显示图像
        # if frameinfo.pixelBits == 8:
        #     plt.imshow(img_np, cmap='gray', vmin=0, vmax=255)
        # else:
        #     plt.imshow(img_np, cmap='gray', vmin=0, vmax=4095)
        
        # plt.title(f"Frame ID: {frameinfo.nFrameID}")
        # plt.axis('off')
        # plt.show(block=True)
        print(img_np)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()