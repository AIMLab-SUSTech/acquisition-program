from enum import IntEnum
from ctypes import Structure
from ctypes import CFUNCTYPE
from ctypes import *

# 错误码
SC_OK = 0                      # 成功，无错误
SC_ERROR = -101                # 通用的错误
SC_INVALID_HANDLE = -102       # 错误或无效的句柄
SC_INVALID_PARAM = -103        # 错误的参数
SC_INVALID_FRAME_HANDLE = -104 # 错误或无效的帧句柄
SC_INVALID_FRAME = -105        # 无效的帧
SC_INVALID_RESOURCE = -106     # 相机/事件/流等资源无效
SC_INVALID_IP = -107           # IP网段不匹配
SC_NO_MEMORY = -108            # 内存不足
SC_INSUFFICIENT_MEMORY = -109  # 传入内存空间不足
SC_ERROR_PROPERTY_TYPE = -110  # 属性类型错误
SC_INVALID_ACCESS = -111       # 属性不可访问
SC_INVALID_RANGE = -112        # 属性值超出范围
SC_NOT_SUPPORT = -113          # 不支持的功能
SC_NOT_IMPLEMENTED = -114      # 功能未实现
SC_TIMEOUT = -115              # 超时
SC_BUSY = -116                 # 忙碌状态
SC_ACCESS_DENIED = -117        # 访问被拒绝
SC_INVALID_NODEMAP = -118      # nodemap非法或不存在

# 配置常量
SC_MAX_DEVICE_ENUM_NUM = 100   # 最大设备数
SC_MAX_STRING_LENTH = 256      # 字符串最大长度
SC_MAX_ERROR_LIST_NUM = 128    # 错误列表最大长度
SC_MAX_PATH_LENGTH = 1024      # 路径最大长度
SC_MAX_EVENT_LEN = 1024        # 事件最大长度


# 在SC_EPixelType枚举类前添加像素格式掩码常量
SC_PIX_MONO = 0x01000000
SC_PIX_RGB = 0x02000000
SC_PIX_COLOR = 0x02000000
SC_PIX_CUSTOM = 0x80000000
SC_PIX_COLOR_MASK = 0xFF000000

SC_PIX_OCCUPY1BIT = 0x00010000
SC_PIX_OCCUPY2BIT = 0x00020000
SC_PIX_OCCUPY4BIT = 0x00040000
SC_PIX_OCCUPY8BIT = 0x00080000
SC_PIX_OCCUPY12BIT = 0x000C0000
SC_PIX_OCCUPY16BIT = 0x00100000
SC_PIX_OCCUPY24BIT = 0x00180000
SC_PIX_OCCUPY32BIT = 0x00200000
SC_PIX_OCCUPY36BIT = 0x00240000
SC_PIX_OCCUPY48BIT = 0x00300000

SC_DEV_HANDLE = c_void_p  # 设备句柄类型

class SC_ECreateHandleMode(IntEnum):
    eModeByIndex = 0,    # 通过已枚举设备的索引(从0开始，比如 0, 1, 2...)  
    eModeByCameraKey = 1,    # 通过设备键"设备型号:序列号"                     
    eModeByDeviceUserID = 2, # 通过设备自定义名                                
    eModeByIPAddress = 3    # 通过设备IP地址

# define AGSDK constant and handle end
class SC_EInterfaceType(IntEnum):
    eInterfaceTypeCXP = 0x00000001,  # 网卡接口类型
    eInterfaceTypeUsb3 = 0x00000002,  # USB3.0接口类型
    eInterfaceTypeCustom = 0x0000004,
    eInterfaceTypeAll = 0x00000000,  # 忽略接口类型（CAMERALINK接口除外）
    eIInterfaceInvalidType = 0xFFFFFFFF  # 无效接口类型


class SCLogLevel(IntEnum):
    Trace = 0,
    Debug = 1,
    Info = 2,
    Warn = 3,
    Error = 4,
    Fatal = 5,


class SC_EFeatureAccessMode(IntEnum):
    eAccessUndefined = 0    # 未定义访问权限
    eAccessReadOnly = 1     # 只读
    eAccessWriteOnly = 2    # 只写
    eAccessReadWrite = 3    # 读写

# 枚举：图像格式
class SC_EPixelType(IntEnum):
    # Mono格式
    ePixelTypeUndefined = -1
    ePixelMono1p = SC_PIX_MONO | SC_PIX_OCCUPY1BIT | 0x0037
    ePixelMono2p = SC_PIX_MONO | SC_PIX_OCCUPY2BIT | 0x0038
    ePixelMono4p = SC_PIX_MONO | SC_PIX_OCCUPY4BIT | 0x0039
    ePixelMono8 = SC_PIX_MONO | SC_PIX_OCCUPY8BIT | 0x0001
    ePixelMono8S = SC_PIX_MONO | SC_PIX_OCCUPY8BIT | 0x0002
    ePixelMono10 = SC_PIX_MONO | SC_PIX_OCCUPY16BIT | 0x0003
    ePixelMono10Packed = SC_PIX_MONO | SC_PIX_OCCUPY12BIT | 0x0004
    ePixelMono12 = SC_PIX_MONO | SC_PIX_OCCUPY16BIT | 0x0005
    ePixelMono12Packed = SC_PIX_MONO | SC_PIX_OCCUPY12BIT | 0x0006
    ePixelMono14 = SC_PIX_MONO | SC_PIX_OCCUPY16BIT | 0x0025
    ePixelMono16 = SC_PIX_MONO | SC_PIX_OCCUPY16BIT | 0x0007

    # Bayer格式
    ePixelBayGR8 = SC_PIX_MONO | SC_PIX_OCCUPY8BIT | 0x0008
    ePixelBayRG8 = SC_PIX_MONO | SC_PIX_OCCUPY8BIT | 0x0009
    ePixelBayGB8 = SC_PIX_MONO | SC_PIX_OCCUPY8BIT | 0x000A
    ePixelBayBG8 = SC_PIX_MONO | SC_PIX_OCCUPY8BIT | 0x000B
    ePixelBayGR10 = SC_PIX_MONO | SC_PIX_OCCUPY16BIT | 0x000C
    ePixelBayRG10 = SC_PIX_MONO | SC_PIX_OCCUPY16BIT | 0x000D
    ePixelBayGB10 = SC_PIX_MONO | SC_PIX_OCCUPY16BIT | 0x000E
    ePixelBayBG10 = SC_PIX_MONO | SC_PIX_OCCUPY16BIT | 0x000F
    ePixelBayGR12 = SC_PIX_MONO | SC_PIX_OCCUPY16BIT | 0x0010
    ePixelBayRG12 = SC_PIX_MONO | SC_PIX_OCCUPY16BIT | 0x0011
    ePixelBayGB12 = SC_PIX_MONO | SC_PIX_OCCUPY16BIT | 0x0012
    ePixelBayBG12 = SC_PIX_MONO | SC_PIX_OCCUPY16BIT | 0x0013
    ePixelBayGR10Packed = SC_PIX_MONO | SC_PIX_OCCUPY12BIT | 0x0026
    ePixelBayRG10Packed = SC_PIX_MONO | SC_PIX_OCCUPY12BIT | 0x0027
    ePixelBayGB10Packed = SC_PIX_MONO | SC_PIX_OCCUPY12BIT | 0x0028
    ePixelBayBG10Packed = SC_PIX_MONO | SC_PIX_OCCUPY12BIT | 0x0029
    ePixelBayGR12Packed = SC_PIX_MONO | SC_PIX_OCCUPY12BIT | 0x002A
    ePixelBayRG12Packed = SC_PIX_MONO | SC_PIX_OCCUPY12BIT | 0x002B
    ePixelBayGB12Packed = SC_PIX_MONO | SC_PIX_OCCUPY12BIT | 0x002C
    ePixelBayBG12Packed = SC_PIX_MONO | SC_PIX_OCCUPY12BIT | 0x002D
    ePixelBayGR16 = SC_PIX_MONO | SC_PIX_OCCUPY16BIT | 0x002E
    ePixelBayRG16 = SC_PIX_MONO | SC_PIX_OCCUPY16BIT | 0x002F
    ePixelBayGB16 = SC_PIX_MONO | SC_PIX_OCCUPY16BIT | 0x0030
    ePixelBayBG16 = SC_PIX_MONO | SC_PIX_OCCUPY16BIT | 0x0031

    # RGB格式
    ePixelRGB8 = SC_PIX_RGB | SC_PIX_OCCUPY24BIT | 0x0014
    ePixelBGR8 = SC_PIX_RGB | SC_PIX_OCCUPY24BIT | 0x0015
    ePixelRGBA8 = SC_PIX_RGB | SC_PIX_OCCUPY32BIT | 0x0016
    ePixelBGRA8 = SC_PIX_RGB | SC_PIX_OCCUPY32BIT | 0x0017
    ePixelRGB10 = SC_PIX_RGB | SC_PIX_OCCUPY48BIT | 0x0018
    ePixelBGR10 = SC_PIX_RGB | SC_PIX_OCCUPY48BIT | 0x0019
    ePixelRGB12 = SC_PIX_RGB | SC_PIX_OCCUPY48BIT | 0x001A
    ePixelBGR12 = SC_PIX_RGB | SC_PIX_OCCUPY48BIT | 0x001B
    ePixelRGB16 = SC_PIX_RGB | SC_PIX_OCCUPY48BIT | 0x0033
    ePixelRGB10V1Packed = SC_PIX_RGB | SC_PIX_OCCUPY32BIT | 0x001C
    ePixelRGB10P32 = SC_PIX_RGB | SC_PIX_OCCUPY32BIT | 0x001D
    ePixelRGB12V1Packed = SC_PIX_RGB | SC_PIX_OCCUPY36BIT | 0x0034
    ePixelRGB565P = SC_PIX_RGB | SC_PIX_OCCUPY16BIT | 0x0035
    ePixelBGR565P = SC_PIX_RGB | SC_PIX_OCCUPY16BIT | 0x0036

    # YUV格式
    ePixelYUV411_8_UYYVYY = SC_PIX_COLOR | SC_PIX_OCCUPY12BIT | 0x001E
    ePixelYUV422_8_UYVY = SC_PIX_COLOR | SC_PIX_OCCUPY16BIT | 0x001F
    ePixelYUV422_8 = SC_PIX_COLOR | SC_PIX_OCCUPY16BIT | 0x0032
    ePixelYUV8_UYV = SC_PIX_COLOR | SC_PIX_OCCUPY24BIT | 0x0020
    ePixelYCbCr8CbYCr = SC_PIX_COLOR | SC_PIX_OCCUPY24BIT | 0x003A
    ePixelYCbCr422_8 = SC_PIX_COLOR | SC_PIX_OCCUPY16BIT | 0x003B
    ePixelYCbCr422_8_CbYCrY = SC_PIX_COLOR | SC_PIX_OCCUPY16BIT | 0x0043
    ePixelYCbCr411_8_CbYYCrYY = SC_PIX_COLOR | SC_PIX_OCCUPY12BIT | 0x003C
    ePixelYCbCr601_8_CbYCr = SC_PIX_COLOR | SC_PIX_OCCUPY24BIT | 0x003D
    ePixelYCbCr601_422_8 = SC_PIX_COLOR | SC_PIX_OCCUPY16BIT | 0x003E
    ePixelYCbCr601_422_8_CbYCrY = SC_PIX_COLOR | SC_PIX_OCCUPY16BIT | 0x0044
    ePixelYCbCr601_411_8_CbYYCrYY = SC_PIX_COLOR | SC_PIX_OCCUPY12BIT | 0x003F
    ePixelYCbCr709_8_CbYCr = SC_PIX_COLOR | SC_PIX_OCCUPY24BIT | 0x0040
    ePixelYCbCr709_422_8 = SC_PIX_COLOR | SC_PIX_OCCUPY16BIT | 0x0041
    ePixelYCbCr709_422_8_CbYCrY = SC_PIX_COLOR | SC_PIX_OCCUPY16BIT | 0x0045
    ePixelYCbCr709_411_8_CbYYCrYY = SC_PIX_COLOR | SC_PIX_OCCUPY12BIT | 0x0042

    # RGB Planar
    ePixelRGB8Planar = SC_PIX_COLOR | SC_PIX_OCCUPY24BIT | 0x0021
    ePixelRGB10Planar = SC_PIX_COLOR | SC_PIX_OCCUPY48BIT | 0x0022
    ePixelRGB12Planar = SC_PIX_COLOR | SC_PIX_OCCUPY48BIT | 0x0023
    ePixelRGB16Planar = SC_PIX_COLOR | SC_PIX_OCCUPY48BIT | 0x0024

    #mono格式，自定义格式
    ePixelMonoC = 0x012000FF,

# RecordFormatType
class SC_EVideoType(IntEnum):
    eTypeVideoFormatTIFF = 0,
    eTypeVideoFormatBMP = 1,        
    eTypeVideoFormatSCD = 2,        
    eTypeVideoFormatTIFFVideo = 3,  
    eTypeVideoFormatNotSupport = 255

class ExportNotify(IntEnum):
    eExportStart = 0,
    eExportProcessing = 1,
    eExportFinish = 2,
    eExportClose = 3

# event type
class SC_EVType(IntEnum):
    eOffLine = 0,
    eOnLine = 1

# 定义SDK中的结构体
class SC_String(Structure):
    _fields_ = [("str", c_char * 256)]

class SC_UsbInterfaceInfo(Structure):
    _fields_ = [
        ("description", c_char * 256),
        ("vendorID", c_char * 256),
        ("deviceID", c_char * 256),
        ("subsystemID", c_char * 256),
        ("revision", c_char * 256),
        ("speed", c_char * 256),
        ("chReserved", c_char * 4 * 256)
    ]

class SC_UsbDeviceInfo(Structure):
    _fields_ = [
        ("bLowSpeedSupported", c_bool),
        ("bFullSpeedSupported", c_bool),
        ("bHighSpeedSupported", c_bool),
        ("bSuperSpeedSupported", c_bool),
        ("bDriverInstalled", c_bool),
        ("boolReserved", c_bool * 3),
        ("nReserved", c_uint * 4),
        ("configurationValid", c_char * 256),
        ("genCPVersion", c_char * 256),
        ("u3vVersion", c_char * 256),
        ("deviceGUID", c_char * 256),
        ("familyName", c_char * 256),
        ("u3vSerialNumber", c_char * 256),
        ("speed", c_char * 256),
        ("maxPower", c_char * 256),
        ("usbProtocol", c_char * 256),
        ("chReserved", c_char * 3 * 256)
    ]


class SC_DeviceInfo(Structure):
    _fields_ = [
        ("cameraType", c_int),
        ("nCameraReserved", c_int * 5),
        ("cameraKey", c_char * 256),
        ("cameraName", c_char * 256),
        ("serialNumber", c_char * 256),
        ("vendorName", c_char * 256),
        ("modelName", c_char * 256),
        ("manufactureInfo", c_char * 256),
        ("deviceVersion", c_char * 256),
        ("chCameraReserved", c_char * 5 * 256),
        ("ctiPath", c_char * 1024),
        ("usbDeviceInfo", SC_UsbDeviceInfo),
        ("interfaceType", c_int),
        ("nInterfaceReserved", c_int * 5),
        ("interfaceName", c_char * 256),
        ("chInterfaceReserved", c_char * 5 * 256),
        ("usbInterfaceInfo", SC_UsbInterfaceInfo)
    ]



class SC_DeviceList(Structure):
    _fields_ = [
        ("devNum", c_uint),
        ("pDevInfo", POINTER(SC_DeviceInfo))
    ]


# 特征类型枚举（与C端定义完全一致）
class SC_EFeatureType(IntEnum):
    eFeatureInt = 0x10000000     # 整型
    eFeatureFloat = 0x20000000   # 浮点型
    eFeatureEnum = 0x30000000    # 枚举型
    eFeatureBool = 0x40000000    # 布尔型
    eFeatureString = 0x50000000  # 字符串型
    eFeatureCommand = 0x60000000 # 命令型
    eFeatureGroup = 0x70000000   # 分组节点
    eFeatureReg = 0x80000000     # 寄存器节点
    eFeatureUndefined = 0x90000000 # 未定义类型

# 在现有枚举定义后添加特征元数据
FEATURE_METADATA = [
    # 图像特征
    {"name": "SensorWidth", "type": SC_EFeatureType.eFeatureInt, "desc": "传感器宽度"},
    {"name": "SensorHeight", "type": SC_EFeatureType.eFeatureInt, "desc": "传感器高度"},
    {"name": "Width", "type": SC_EFeatureType.eFeatureInt, "desc": "图像宽度"},
    {"name": "Height", "type": SC_EFeatureType.eFeatureInt, "desc": "图像高度"},
    {"name": "OffsetX", "type": SC_EFeatureType.eFeatureInt, "desc": "图像 X 偏移"},
    {"name": "OffsetY", "type": SC_EFeatureType.eFeatureInt, "desc": "图像 Y 偏移"},
    
    # 采集控制
    {"name": "BinningMode", "type": SC_EFeatureType.eFeatureEnum, "desc": "合并模式"},
    {"name": "PixelFormat", "type": SC_EFeatureType.eFeatureEnum, "desc": "像素格式"},
    {"name": "ReadoutMode", "type": SC_EFeatureType.eFeatureEnum, "desc": "读出模式"},
    
    # 触发相关
    {"name": "TriggerInType", "type": SC_EFeatureType.eFeatureEnum, "desc": "触发输入信号"},
    {"name": "TriggerActivation", "type": SC_EFeatureType.eFeatureEnum, "desc": "触发输入信号属性"},
    {"name": "TriggerDelay", "type": SC_EFeatureType.eFeatureFloat, "desc": "触发输入触发延迟"},
    {"name": "TriggerOutSelector", "type": SC_EFeatureType.eFeatureEnum, "desc": "触发输出接口类型"},
    {"name": "TriggerOutType", "type": SC_EFeatureType.eFeatureEnum, "desc": "触发输出信号"},
    {"name": "TriggerOutActivation", "type": SC_EFeatureType.eFeatureEnum, "desc": "触发输出信号属性"},
    {"name": "TriggerOutDelay", "type": SC_EFeatureType.eFeatureFloat, "desc": "触发输出触发延迟"},
    {"name": "TriggerOutPulseWidth", "type": SC_EFeatureType.eFeatureFloat, "desc": "触发输出脉宽"},
    
    # 设备状态
    {"name": "DeviceTemperature", "type": SC_EFeatureType.eFeatureFloat, "desc": "设备温度"},
    {"name": "DeviceTemperatureTarget", "type": SC_EFeatureType.eFeatureInt, "desc": "设备目标温度"},
    {"name": "FanSwitch", "type": SC_EFeatureType.eFeatureBool, "desc": "风扇开关"},
    {"name": "FanMode", "type": SC_EFeatureType.eFeatureEnum, "desc": "风扇模式"}
]

# 定义SC_FrameInfo结构体
class SC_FrameInfo(Structure):
    _fields_ = [
        ('frameId', c_uint64),
        ('status', c_uint),
        ('width', c_uint),
        ('height', c_uint),
        ('size', c_uint),
        ('pixelFormat', c_int),
        ('timeStamp', c_uint64),
        ('exposureTime', c_uint64),
        ('paddingX', c_uint),
        ('paddingY', c_uint),
        ('usbSendCnt', c_uint),
        ('sendTimestampsec', c_uint),
        ('sendTimestampnas', c_uint),
        ('reserved', c_uint * 7)
    ]

# 定义SC_Frame结构体
class SC_Frame(Structure):
    _fields_ = [
        ('frameHandle', c_void_p),
        ('pData', POINTER(c_ubyte)),
        ('frameInfo', SC_FrameInfo),
        ('reserved', c_uint * 10)
    ]

class SC_EnumEntryInfo(Structure):
    _fields_ = [
    ('value', c_uint64),
    ('name', c_char * SC_MAX_STRING_LENTH)
]

class SC_EnumEntryList(Structure):
    _fields_ = [
    ('nEnumEntryBufferSize', c_uint),
    ('pEnumEntryInfo', POINTER(SC_EnumEntryInfo))
    ]

class SC_RecordParam(Structure):
    _fields_ = [
        ('startFrame', c_uint),
        ('count', c_uint),
        ('frameRate', c_float),
        ('quality', c_uint),
        ('recordFormat', c_uint),
        ('recordFilePath', c_char * SC_MAX_PATH_LENGTH),
        ('fileName', c_char * SC_MAX_PATH_LENGTH),
        ('reserved', c_uint * 5)
    ]

# connection event information
class SC_SConnectArg(Structure):
    _fields_ = [
        ('event', c_uint),
        ('serialNumber', c_char * SC_MAX_STRING_LENTH),
        ('reserved', c_uint * 10)
    ]

class SC_SParamUpdateArg(Structure):
    _fields_ = [
        ('isPoll', c_bool),
        ('reserve',c_uint * 10),
        ('nParamCnt', c_uint),
        ('pParamNameList', POINTER(SC_String))
    ]

# 与 SCDefines.h 中 SC_UpdateFeatureItem 一致
class SC_UpdateFeatureItem(Structure):
    _fields_ = [
        ('name', c_char * SC_MAX_STRING_LENTH),
    ]

# 与 SCDefines.h 中 SC_UpdateFeatureList 一致
class SC_UpdateFeatureList(Structure):
    _fields_ = [
        ('featureCount', c_uint64),
        ('pFeatures', POINTER(SC_UpdateFeatureItem)),
    ]

ExportNotifyCallBack = eval('CFUNCTYPE')(None, c_int, c_char, c_int, c_void_p)
FrameInfoCallBack = eval('CFUNCTYPE')(None, POINTER(SC_Frame), c_void_p)
ConnectCallBack = eval('CFUNCTYPE')(None, POINTER(SC_SConnectArg), c_void_p)
ParamUpdateCallBack = eval('CFUNCTYPE')(None, POINTER(SC_SParamUpdateArg), c_void_p)


