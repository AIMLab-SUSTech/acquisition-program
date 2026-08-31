import ctypes
from ctypes import (
    c_uint, c_ulong, c_ulonglong, c_int, c_double,
    c_char_p, c_void_p, byref, create_string_buffer,
    CFUNCTYPE,
    c_long,
    c_longlong,
    c_byte
)
import enum
import sys

# 定义字符集
if sys.platform == "win32":
    _DEFAULT_CHARSET = ctypes.c_char
else:
    _DEFAULT_CHARSET = ctypes.c_char


# 枚举定义
class RTNCODE(enum.IntEnum):
    OK = 0
    WARNING = 1
    NG = -1


class INTERFACE(enum.IntEnum):
    SL_CXP_INTERFACE_UNKNOW = 0x00000000
    SL_CXP_INTERFACE_FLEXIO = 0x10100001
    SL_GEV_INTERFACE_SSZN = 0x20000002
    SL_USB_INTERFACE_OCT = 0x30100003


class PARAM_VALUE_TYPE(enum.IntEnum):
    PARAM_VALUE_INT = 0
    PARAM_VALUE_BOOL = 1
    PARAM_VALUE_ENUM = 2
    PARAM_VALUE_STRING = 3
    PARAM_VALUE_FLOAT = 4


class SL_RECORD_MEDIA(enum.IntEnum):
    RecordMedia_Memory = 0
    RecordMedia_RAWW = 0x1001
    RecordMedia_MRAW = 0x1002
    RecordMedia_BMP = 0x2001
    RecordMedia_PNG = 0x2002
    RecordMedia_TIFF = 0x2003
    RecordMedia_AVI = 0x3001
    RecordMedia_MP4 = 0x3002


# 常量定义
class SlDefineParam:
    # 参数名称常量
    BAND_WIDTH = b"SlParamBandWidth"
    CAP_FPS = b"SlParamCameraCapFps"
    MODE = b"SlParamMode"
    REC_MEDIA = b"SlParamRecMedia"
    TRIG_MODE = b"SlParamTrigMode"
    RECORD_SUPPORT = b"SlParamRecordSupport"
    FRAME_SIZE = b"SlParamCameraFrameSize"
    DISPLAY_NAME = b"SlParamCameraDisplayName"
    INTERFACE_DISPLAY_NAME = b"SlParamInterfaceDisplayName"
    CACHE_FRAMES = b"SlParamCacheFrames"
    MAXCACHE_FRAMES = b"SlParamMaxcacheFrames"
    MEMORYLOAD = b"SlParamMemoryload"
    TRIG_MANUAL_BEFOR_FRAME = b"SlParamTrigManualBeforFrame"
    TRIG_MANUAL_AFTER_FRAME = b"SlParamTrigManualAfterFrame"
    RECORD_DISK_PATH = b"SlParamRecordDiskPath"
    RECORD_DISK_FILENAME = b"SlParamRecordDiskFilename"
    # 新版 SDK: SLPARAM_RECORD_DISK_PATHNAME 已删除, 由 FILEMARK/FOLDERNAME 一组替代
    # RECORD_DISK_PATHNAME = b"SlParamRecordDiskPathname"
    RECORD_DISK_FILEMARK = b"SlParamRecordDiskFilemark"
    RECORD_DISK_FILEINFO_MARK_LIST = b"SlParamRecordDiskFileinfoMarkList"
    RECORD_DISK_FOLDERNAME = b"SlParamRecordDiskFoldername"
    RECORD_DISK_FOLDERMARK = b"SlParamRecordDiskFoldermark"
    RECORD_DISKDIR_MODE = b"SlParamRecordDiskdirMode"
    RECORD_DISK_FILEPARAM = b"SlParamRecordDiskFileparam"
    RECORD_DISK_RECFRAMES = b"SlParamRecordDiskRecframes"
    RECORD_DISK_ENDMODE = b"SlParamRecordDiskEndmode"
    MAXRECORD_DISK_FRAMES = b"SlParamMaxrecordDiskFrames"
    RECORD_DISK_USED = b"SlParamRecordDiskUsed"
    RECORD_DISK_TOTAL = b"SlParamRecordDiskTotal"
    ALREADY_RECORD_FRAMES = b"SlParamAlreadyRecordFrames"
    ALREADY_RECORD_MEMORY_INFO = b"SlParamAlreadyRecordMemoryInfo"
    ALREADY_RECORD_AFTER_FRAMES = b"SlParamAlreadyRecordAfterFrames"
    ALREADY_RECORD_BEFOR_FRAMES = b"SlParamAlreadyRecordBeforFrames"
    ONLINE_STATE = b"SlParamCameraOnlineState"
    LOOP_RECORD_ENABLE = b"SlParamLoopRecordEnable"
    MANUL_MEM2DISK_MODE = b"SlParamManaulMem2diskMode"
    MANUL_MEM2DISK_ENABLE = b"SlParamManaulMem2diskEnable"
    MANUL_MEM2DISK_STOP = b"SlParamManaulMem2diskStop"
    MANUL_MEM2DISK_PROGRESS = b"SlParamManaulMem2diskProgress"

    # 数值常量
    INFO_MAX_BUFFER_SIZE = 256
    SL_MAX_INTERFACE_NUM = 64
    SL_MAX_DEVICE_NUM = 256


# 结构体定义
class SL_GENTL_CXP_DEVICE_INFO(ctypes.Structure):
    _fields_ = [
        ("chVendorName", ctypes.c_byte * 256),
        ("chModelName", ctypes.c_byte * 256),
        ("chManufacturerInfo", ctypes.c_byte * 256),
        ("chDeviceVersion", ctypes.c_byte * 256),
        ("chSerialNumber", ctypes.c_byte * 256),
        ("chUserDefinedName", ctypes.c_byte * 256),
        ("nReserved", ctypes.c_uint * 256)
    ]


class SL_OCT_USB3_DEVICE_INFO(ctypes.Structure):
    _fields_ = [
        ("chVendorName", ctypes.c_byte * 256),
        ("chModelName", ctypes.c_byte * 256),
        ("chFamilyName", ctypes.c_byte * 256),
        ("chDeviceVersion", ctypes.c_byte * 256),
        ("chManufacturerName", ctypes.c_byte * 256),
        ("chSerialNumber", ctypes.c_byte * 256),
        ("chUserDefinedName", ctypes.c_byte * 256),
        ("nReserved", ctypes.c_uint * 2)
    ]


class SL_SSZN_GEV_DEVICE_INFO(ctypes.Structure):
    _fields_ = [
        ("chDeviceIpAddr", ctypes.c_byte * 256),
        ("chDeviceMacAddr", ctypes.c_byte * 256),
        ("chDeviceUserName", ctypes.c_byte * 256),
        ("chModelName", ctypes.c_byte * 256),
        ("chDeviceVersion", ctypes.c_byte * 256),
        ("nReserved", ctypes.c_uint * 2)
    ]


# 联合体定义
class SpecialInfoUnion(ctypes.Union):
    _fields_ = [
        ("stGenTLCXPInfo", SL_GENTL_CXP_DEVICE_INFO),
        ("stOctUsb3VInfo", SL_OCT_USB3_DEVICE_INFO),
        ("stCustGevInfo", SL_SSZN_GEV_DEVICE_INFO)
    ]


class SL_DEVICE_INFO(ctypes.Structure):
    _fields_ = [
        ("nInterFaceIndex", ctypes.c_uint),
        ("nDeviceIndex", ctypes.c_uint),
        ("nTLayerType", ctypes.c_uint),
        ("chInterfaceID", ctypes.c_byte * SlDefineParam.INFO_MAX_BUFFER_SIZE),
        ("chDeviceID", ctypes.c_byte * SlDefineParam.INFO_MAX_BUFFER_SIZE),
        ("chDeviceDisplayName", ctypes.c_byte * SlDefineParam.INFO_MAX_BUFFER_SIZE),
        ("nReserved", ctypes.c_uint * 3),
        ("SpecialInfo", SpecialInfoUnion)
    ]


class SL_DEVICE_INFO_LIST(ctypes.Structure):
    _fields_ = [
        ("nDeviceNum", ctypes.c_uint),
        ("pDeviceInfo", ctypes.POINTER(ctypes.c_void_p) * SlDefineParam.SL_MAX_DEVICE_NUM)
    ]


class SL_INTERFACE_INFO(ctypes.Structure):
    _fields_ = [
        ("chInterfaceID", ctypes.c_byte * SlDefineParam.INFO_MAX_BUFFER_SIZE),
        ("chDisplayName", ctypes.c_byte * SlDefineParam.INFO_MAX_BUFFER_SIZE),
        ("chSerialNumber", ctypes.c_byte * SlDefineParam.INFO_MAX_BUFFER_SIZE),
        ("chModelName", ctypes.c_byte * SlDefineParam.INFO_MAX_BUFFER_SIZE),
        ("chManufacturer", ctypes.c_byte * SlDefineParam.INFO_MAX_BUFFER_SIZE),
        ("chDeviceVersion", ctypes.c_byte * SlDefineParam.INFO_MAX_BUFFER_SIZE),
        ("chUserDefinedName", ctypes.c_byte * SlDefineParam.INFO_MAX_BUFFER_SIZE),
        ("nReserved", ctypes.c_uint * 64)
    ]


class SL_INTERFACE_INFO_LIST(ctypes.Structure):
    _fields_ = [
        ("nInterfaceNum", ctypes.c_uint),
        ("pInterfaceInfos", ctypes.POINTER(ctypes.c_void_p) * SlDefineParam.SL_MAX_INTERFACE_NUM)
    ]


class SLEnumItem(ctypes.Structure):
    _fields_ = [
        ("nValue", ctypes.c_longlong),
        ("strSymbolic", ctypes.c_char* 128)
    ]


class SL_REQIMAGES_PARAM(ctypes.Structure):
    _fields_ = [
        ("datasize", ctypes.c_ulonglong),
        ("Width", ctypes.c_uint),
        ("Height", ctypes.c_uint),
        ("pixformat", ctypes.c_uint),
        ("frameid", ctypes.c_uint),
        ("BeforeTriggerFrameALLNum", ctypes.c_uint),
        ("AfterTriggerFrameALLNum", ctypes.c_uint),
        ("BeforeTriggerFrameRecNum", ctypes.c_uint),
        ("AfterTriggerFrameRecNum", ctypes.c_uint),
        ("RunMode", ctypes.c_uint),
        ("CacheSize", ctypes.c_uint),
        ("LoopFlag", ctypes.c_uint),
        ("Frametime", ctypes.c_ulonglong),
        ("AdcBitdepth", ctypes.c_uint),
        ("Reserve", ctypes.c_byte * SlDefineParam.INFO_MAX_BUFFER_SIZE)
    ]


# 回调函数类型定义
SL_EVENT_CALLBACK = CFUNCTYPE(None, c_uint, c_void_p)
# 新版 SDK 破坏性变更: void(*)(unsigned char* data, const SL_REQIMAGES_PARAM*, void*),
# 回调首参新增图像数据指针 (旧版为 void(*)(const SL_REQIMAGES_PARAM*, void*))
SL_STREAM_CALLBACK = CFUNCTYPE(None, ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(SL_REQIMAGES_PARAM), c_void_p)


# 核心封装类
class SLStreamLink:
    def __init__(self, dll_name="SLStreamLink.dll"):
        import os
        import sys
        import ctypes

    # ==============================================
    # 【绝对关键】获取 当前 py 文件所在的目录（永远正确）
    # ==============================================
        current_folder = os.path.dirname(os.path.abspath(__file__))
        dll_full_path = os.path.join(current_folder, "dll", "PE", "extern", "lib", dll_name)

        print("="*50)
        print("当前脚本目录：", current_folder)
        print("DLL 完整路径：", dll_full_path)
        print("DLL 是否存在：", os.path.exists(dll_full_path))
        print("="*50)
    # ==============================================
    # 强制切换工作目录到项目根目录
    # ==============================================
        lib_dir = r"C:\Users\JKHKOJKLJ\Documents\GitHub\acquisition-program\dll\PE\extern\lib"
        os.chdir(lib_dir)

    # ==============================================
    # 把当前目录加入 DLL 搜索路径
    # ==============================================
        os.environ['PATH'] = current_folder + os.pathsep + os.environ['PATH']
        if sys.version_info >= (3, 8):
            os.add_dll_directory(current_folder)

    # ==============================================
    # 用 绝对路径 加载 DLL（100%找到）
    # ==============================================
        dll_full_path = os.path.join(current_folder, "dll", "PE", "extern", "lib", dll_name)
        self.dll = ctypes.CDLL(dll_full_path)

        self._setup_functions()
        self.dev_handles = []

    def _setup_functions(self):
        """设置DLL函数的参数和返回值类型"""
        # 基础函数
        self.dll.SLIF_Init.argtypes = []
        self.dll.SLIF_Init.restype = c_int

        self.dll.SLIF_UnInit.argtypes = []
        self.dll.SLIF_UnInit.restype = c_int

        self.dll.SLIF_GetLastErrorInfo.argtypes = [ctypes.c_char_p, ctypes.POINTER(c_int)]
        self.dll.SLIF_GetLastErrorInfo.restype = c_int

        # 获取支持的图层类型列表
        self.dll.SLIF_GetSupportTLayerTypeList.argtypes = [ctypes.POINTER(c_uint), ctypes.POINTER(c_int)]
        self.dll.SLIF_GetSupportTLayerTypeList.restype = c_int

        # 获取图层类型名称
        self.dll.SLIF_GetTLayerTypeName.argtypes = [c_uint, ctypes.c_char_p, ctypes.POINTER(c_int)]
        self.dll.SLIF_GetTLayerTypeName.restype = c_int

        # 获取图层类型初始化结果
        self.dll.SLIF_GetTLayerTypeInitResult.argtypes = [c_uint, ctypes.c_char_p, ctypes.POINTER(c_int)]
        self.dll.SLIF_GetTLayerTypeInitResult.restype = c_int

        # 检测接口
        self.dll.SLIF_DetectInterfaces.argtypes = [c_uint, ctypes.POINTER(SL_INTERFACE_INFO_LIST), c_void_p, c_int]
        self.dll.SLIF_DetectInterfaces.restype = c_int

        # 检测设备
        self.dll.SLIF_DetectDevices.argtypes = [c_uint, ctypes.POINTER(SL_DEVICE_INFO_LIST), c_void_p, c_int]
        self.dll.SLIF_DetectDevices.restype = c_int

        # 打开设备
        self.dll.SLIF_OpenDevice.argtypes = [c_uint, c_uint, c_uint, ctypes.POINTER(c_void_p)]
        self.dll.SLIF_OpenDevice.restype = c_int

        # 关闭设备
        self.dll.SLIF_CloseDevice.argtypes = [c_void_p]
        self.dll.SLIF_CloseDevice.restype = c_int

        # 注册事件回调
        self.dll.SLIF_RegisterEventCallBack.argtypes = [c_void_p, SL_EVENT_CALLBACK, c_void_p]
        self.dll.SLIF_RegisterEventCallBack.restype = c_int

        # 注册流回调
        #self.dll.SLIF_RegisterStreamCallBack.argtypes = [c_void_p, SL_STREAM_CALLBACK, c_void_p]
        #self.dll.SLIF_RegisterStreamCallBack.restype = c_int

        # 开始采集
        self.dll.SLIF_StartCapture.argtypes = [c_void_p]
        self.dll.SLIF_StartCapture.restype = c_int

        # 停止采集
        self.dll.SLIF_StopCapture.argtypes = [c_void_p]
        self.dll.SLIF_StopCapture.restype = c_int

        # 获取预览帧
        self.dll.SLIF_AcquirePreviewFrameRef.argtypes = [c_void_p, ctypes.POINTER(c_void_p),
                                                         ctypes.POINTER(SL_REQIMAGES_PARAM), c_uint]
        self.dll.SLIF_AcquirePreviewFrameRef.restype = c_int

        # 读取GenICam XML到内存
        self.dll.SLIF_ReadGenICamXmlToMemory.argtypes = [c_void_p, ctypes.c_char_p, ctypes.POINTER(c_ulonglong)]
        self.dll.SLIF_ReadGenICamXmlToMemory.restype = c_int

        # 读取GenICam XML到文件
        self.dll.SLIF_ReadGenICamXmlToFile.argtypes = [c_void_p, c_char_p]
        self.dll.SLIF_ReadGenICamXmlToFile.restype = c_int

        # 设置字符串参数
        self.dll.SLIF_SetString.argtypes = [c_void_p, c_char_p, c_char_p]
        self.dll.SLIF_SetString.restype = c_int

        # 获取字符串参数
        self.dll.SLIF_GetString.argtypes = [c_void_p, c_char_p, ctypes.c_char_p, ctypes.POINTER(c_ulonglong)]
        self.dll.SLIF_GetString.restype = c_int

        # 设置命令
        self.dll.SLIF_SetCommand.argtypes = [c_void_p, c_char_p]
        self.dll.SLIF_SetCommand.restype = c_int

        # 设置整数参数
        self.dll.SLIF_SetInteger.argtypes = [c_void_p, c_char_p, ctypes.c_longlong, c_int]
        self.dll.SLIF_SetInteger.restype = c_int

        # 获取整数参数
        self.dll.SLIF_GetInteger.argtypes = [c_void_p, c_char_p, ctypes.POINTER(c_longlong), c_int]
        self.dll.SLIF_GetInteger.restype = c_int

        # 获取枚举项
        self.dll.SLIF_GetEnumItems.argtypes = [c_void_p, c_char_p, ctypes.POINTER(SLEnumItem), ctypes.POINTER(c_longlong)]
        self.dll.SLIF_GetEnumItems.restype = c_int

        # 设置浮点参数
        self.dll.SLIF_SetFloat.argtypes = [c_void_p, c_char_p, c_double]
        self.dll.SLIF_SetFloat.restype = c_int

        # 获取浮点参数
        self.dll.SLIF_GetFloat.argtypes = [c_void_p, c_char_p, ctypes.POINTER(c_double)]
        self.dll.SLIF_GetFloat.restype = c_int

    @staticmethod
    def byte_array_to_string(data):
        """将字节数组转换为字符串（处理C风格的NULL终止）"""
        try:
            null_idx = data.index(0)
            return bytes(data[:null_idx]).decode('ascii')
        except ValueError:
            return bytes(data).decode('ascii', errors='ignore')

    # 封装常用方法
    def init(self):
        """初始化库"""
        return self.dll.SLIF_Init()

    def uninit(self):
        """反初始化库，关闭所有打开的设备"""
        # 关闭所有打开的设备
        for handle in self.dev_handles:
            self.dll.SLIF_CloseDevice(handle)
        self.dev_handles.clear()
        return self.dll.SLIF_UnInit()

    def get_last_error_info(self):
        """获取最后错误信息"""
        buf_size = 1024
        buf = create_string_buffer(buf_size)
        size = c_int(buf_size)
        ret = self.dll.SLIF_GetLastErrorInfo(buf, byref(size))
        if ret == RTNCODE.OK:
            return buf.value.decode('utf-8', errors='ignore')
        return ""

    def detect_interfaces(self, tlayer_type):
        """检测指定类型的接口

        Args:
            tlayer_type: 图层类型（INTERFACE枚举值）

        Returns:
            tuple: (返回码, 接口列表)
        """
        interface_list = SL_INTERFACE_INFO_LIST()
        interface_list.nInterfaceNum = 0

        ret = self.dll.SLIF_DetectInterfaces(tlayer_type, byref(interface_list), None, 0)
        if ret != RTNCODE.OK:
            return ret, []

        interfaces = []
        for i in range(interface_list.nInterfaceNum):
            if interface_list.pInterfaceInfos[i]:
                interface_info = ctypes.cast(interface_list.pInterfaceInfos[i],
                                             ctypes.POINTER(SL_INTERFACE_INFO)).contents
                interfaces.append({
                    "interface_id": self.byte_array_to_string(interface_info.chInterfaceID),
                    "display_name": self.byte_array_to_string(interface_info.chDisplayName),
                    "serial_number": self.byte_array_to_string(interface_info.chSerialNumber),
                    "model_name": self.byte_array_to_string(interface_info.chModelName),
                    "manufacturer": self.byte_array_to_string(interface_info.chManufacturer),
                    "device_version": self.byte_array_to_string(interface_info.chDeviceVersion),
                    "user_defined_name": self.byte_array_to_string(interface_info.chUserDefinedName)
                })
        return ret, interfaces

    def detect_devices(self, tlayer_type):
        """检测指定类型的设备

        Args:
            tlayer_type: 图层类型（INTERFACE枚举值）

        Returns:
            tuple: (返回码, 设备列表)
        """
        device_list = SL_DEVICE_INFO_LIST()
        device_list.nDeviceNum = 0

        ret = self.dll.SLIF_DetectDevices(tlayer_type, byref(device_list), None, 0)
        if ret != RTNCODE.OK:
            return ret, []

        devices = []
        for i in range(device_list.nDeviceNum):
            if device_list.pDeviceInfo[i]:
                device_info = ctypes.cast(device_list.pDeviceInfo[i], ctypes.POINTER(SL_DEVICE_INFO)).contents
                devices.append({
                    "interface_index": device_info.nInterFaceIndex,
                    "device_index": device_info.nDeviceIndex,
                    "tlayer_type": device_info.nTLayerType,
                    "interface_id": self.byte_array_to_string(device_info.chInterfaceID),
                    "device_id": self.byte_array_to_string(device_info.chDeviceID),
                    "display_name": self.byte_array_to_string(device_info.chDeviceDisplayName)
                })
        return ret, devices

    def open_device(self, tlayer_type, interface_id, device_id):
        """打开设备

        Args:
            tlayer_type: 图层类型
            interface_id: 接口ID
            device_id: 设备ID

        Returns:
            tuple: (返回码, 设备句柄)
        """
        dev_handle = c_void_p()
        ret = self.dll.SLIF_OpenDevice(tlayer_type, interface_id, device_id, byref(dev_handle))
        if ret == RTNCODE.OK:
            self.dev_handles.append(dev_handle)
        return ret, dev_handle

    def close_device(self, dev_handle):
        """关闭设备

        Args:
            dev_handle: 设备句柄

        Returns:
            int: 返回码
        """
        if dev_handle in self.dev_handles:
            self.dev_handles.remove(dev_handle)
        return self.dll.SLIF_CloseDevice(dev_handle)

    def start_capture(self, dev_handle):
        """开始采集

        Args:
            dev_handle: 设备句柄

        Returns:
            int: 返回码
        """
        return self.dll.SLIF_StartCapture(dev_handle)

    def stop_capture(self, dev_handle):
        """停止采集

        Args:
            dev_handle: 设备句柄

        Returns:
            int: 返回码
        """
        return self.dll.SLIF_StopCapture(dev_handle)

    def set_string_param(self, dev_handle, feature, value):
        """设置字符串参数

        Args:
            dev_handle: 设备句柄
            feature: 参数名（bytes类型）
            value: 参数值（bytes类型）

        Returns:
            int: 返回码
        """
        return self.dll.SLIF_SetString(dev_handle, feature, value)

    def get_string_param(self, dev_handle, feature, buf_size=SlDefineParam.INFO_MAX_BUFFER_SIZE):
        """获取字符串参数

        Args:
            dev_handle: 设备句柄
            feature: 参数名（bytes类型）
            buf_size: 接收缓冲区大小（字节），默认 256；如 MARK_LIST 需传 2048

        Returns:
            tuple: (返回码, 参数值)
        """
        buf = create_string_buffer(buf_size)
        size = c_ulonglong(buf_size)

        ret = self.dll.SLIF_GetString(dev_handle, feature, buf, byref(size))
        if ret == RTNCODE.OK:
            return ret, self.byte_array_to_string(buf.raw)
        return ret, ""

    def set_integer_param(self, dev_handle, feature, value, val_type=PARAM_VALUE_TYPE.PARAM_VALUE_INT):
        """设置整数参数

        Args:
            dev_handle: 设备句柄
            feature: 参数名（bytes类型）
            value: 参数值
            val_type: 参数类型（PARAM_VALUE_TYPE枚举）

        Returns:
            int: 返回码
        """
        return self.dll.SLIF_SetInteger(dev_handle, feature, value, val_type)

    def get_integer_param(self, dev_handle, feature, val_type=PARAM_VALUE_TYPE.PARAM_VALUE_INT):
        """获取整数参数

        Args:
            dev_handle: 设备句柄
            feature: 参数名（bytes类型）
            val_type: 参数类型（PARAM_VALUE_TYPE枚举）

        Returns:
            tuple: (返回码, 参数值)
        """
        value = c_longlong()
        ret = self.dll.SLIF_GetInteger(dev_handle, feature, byref(value), val_type)
        if ret == RTNCODE.OK:
            return ret, value.value
        return ret, 0

    def set_float_param(self, dev_handle, feature, value):
        """设置浮点参数

        Args:
            dev_handle: 设备句柄
            feature: 参数名（bytes类型）
            value: 参数值

        Returns:
            int: 返回码
        """
        return self.dll.SLIF_SetFloat(dev_handle, feature, value)

    def get_float_param(self, dev_handle, feature):
        """获取浮点参数

        Args:
            dev_handle: 设备句柄
            feature: 参数名（bytes类型）

        Returns:
            tuple: (返回码, 参数值)
        """
        value = c_double()
        ret = self.dll.SLIF_GetFloat(dev_handle, feature, byref(value))
        if ret == RTNCODE.OK:
            return ret, value.value
        return ret, 0.0

    def register_event_callback(self, dev_handle, callback, user_data=None):
        """注册事件回调

        Args:
            dev_handle: 设备句柄
            callback: 回调函数 (def callback(msg_type: int, user_data: int))
            user_data: 用户数据

        Returns:
            int: 返回码
        """
        c_callback = SL_EVENT_CALLBACK(callback)
        return self.dll.SLIF_RegisterEventCallBack(dev_handle, c_callback, user_data)

    #def register_stream_callback(self, dev_handle, callback, user_data=None):
        """注册流回调

        Args:
            dev_handle: 设备句柄
            callback: 回调函数 (新版 SDK: def callback(data, param: SL_REQIMAGES_PARAM, user_data: int))
            user_data: 用户数据

        Returns:
            int: 返回码
        """
        c_callback = SL_STREAM_CALLBACK(callback)
        return self.dll.SLIF_RegisterStreamCallBack(dev_handle, c_callback, user_data)

    def __del__(self):
        """析构函数，确保反初始化"""
        try:
            self.uninit()
        except:
            pass


# 使用示例
if __name__ == "__main__":
    # 创建SLStreamLink实例
    sl = SLStreamLink()

    # 初始化库
    ret = sl.init()
    if ret != RTNCODE.OK:
        print(f"初始化失败: {sl.get_last_error_info()}")
        sys.exit(1)

    try:
        # 检测CXP接口设备
        ret, interfaces = sl.detect_interfaces(INTERFACE.SL_CXP_INTERFACE_FLEXIO)
        if ret == RTNCODE.OK:
            print(f"检测到 {len(interfaces)} 个接口:")
            for idx, iface in enumerate(interfaces):
                print(f"接口 {idx}: {iface}")

        # 检测设备
        ret, devices = sl.detect_devices(INTERFACE.SL_CXP_INTERFACE_FLEXIO)
        if ret == RTNCODE.OK:
            print(f"\n检测到 {len(devices)} 个设备:")
            for idx, dev in enumerate(devices):
                print(f"设备 {idx}: {dev}")

                # 打开第一个设备
                if idx == 0:
                    ret, dev_handle = sl.open_device(
                        INTERFACE.SL_CXP_INTERFACE_FLEXIO,
                        dev['interface_index'],
                        dev['device_index']
                    )
                    if ret == RTNCODE.OK:
                        print(f"\n成功打开设备: {dev['display_name']}")

                        # 获取相机名称
                        ret, display_name = sl.get_string_param(dev_handle, SlDefineParam.DISPLAY_NAME)
                        if ret == RTNCODE.OK:
                            print(f"相机名称: {display_name}")

                        # 开始采集
                        ret = sl.start_capture(dev_handle)
                        if ret == RTNCODE.OK:
                            print("开始采集成功")

                            # 模拟采集5秒
                            import time

                            time.sleep(5)

                            # 停止采集
                            sl.stop_capture(dev_handle)
                            print("停止采集成功")

                        # 关闭设备
                        sl.close_device(dev_handle)

    finally:
        # 反初始化
        sl.uninit()
        print("\n库已反初始化")