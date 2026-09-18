from SCDefines import *
import sys
import os
import platform
from pathlib import Path
import ctypes

env_var_value = os.getenv('Revealer_Scientific_Camera_SDK_HOME')
if env_var_value == None:
    print("missing env Revealer_Scientific_Camera_SDK_HOME")
    sys.exit()
lib_file_name = str(env_var_value) + "/bin/scsdk.dll"

# current_dir = os.path.dirname(os.path.abspath(__file__))
# dll_dir = os.path.join(current_dir, 'dll', 'SCCamera')
# lib_file_name = os.path.join(dll_dir, 'scsdk.dll')

# load SDK library
if sys.platform == 'win32':
    print("Windows")
    bits, linkage = platform.architecture()
    if bits == '64bit':
        SCSDKDLL = cdll.LoadLibrary(lib_file_name)
else:
    print("Linux")
# _dll_directory_handle = None

# if sys.platform == 'win32':

#     print("Windows")
#     print("Python executable:")
#     print(sys.executable)

#     print("Python architecture:")
#     print(platform.architecture())

#     print("DLL directory:")
#     print(dll_dir)

#     print("scsdk.dll:")
#     print(lib_file_name)

#     print("scsdk exists:")
#     print(os.path.isfile(lib_file_name))

#     # 关键
#     if hasattr(os, "add_dll_directory"):
#         _dll_directory_handle = os.add_dll_directory(dll_dir)

#     SCSDKDLL = ctypes.CDLL(lib_file_name)

# else:
#     print("Linux")

class SCSDK():
    def __init__(self):
        print("PySCSDK init")
        super().__init__()
        self._handle = c_void_p()
        self.handle = pointer(self._handle)

    # C原型：int SC_CALL SC_Init(SCLogLevel level, const char *logPath=nullptr,  unsigned int fileSize = 10485760, unsigned int fileNum = 30);
    # initialize sdk
    @staticmethod
    def SC_Init(level, log_path, file_size = 10485760, file_num = 30):
        encoded_path = log_path.encode('utf-8') if log_path else None
        SCSDKDLL.SC_Init.argtypes = [
        c_int32,      # level
        c_char_p,     # log_path
        c_uint32,     # file_size
        c_uint32      # file_num
        ]
        SCSDKDLL.SC_Init.restype = c_int32

        return SCSDKDLL.SC_Init(level, encoded_path, file_size, file_num)
    
    # C原型：const char* SC_CALL SC_GetVersion(void);
    # get sdk version
    @staticmethod
    def SC_GetVersion():
        SCSDKDLL.SC_GetVersion.restype = c_char_p
        return SCSDKDLL.GetVersion()
    
    # C原型：int SC_CALL SC_Release(void);
    # release sdk
    @staticmethod
    def SC_Release():
        SCSDKDLL.SC_Release.restype = c_int
        return SCSDKDLL.SC_Release()

    # C原型：int SC_CALL SC_EnumDevices(OUT SC_DeviceList* pDeviceList, IN unsigned int interfaceType,  IN const char* ctiPath);
    # Enumerate Device
    @staticmethod
    def SC_EnumDevices(deviceList, interfaceType, ctiPath=None):
        SCSDKDLL.SC_EnumDevices.restype = c_int
        SCSDKDLL.SC_EnumDevices.argtype = (POINTER(SC_DeviceList), c_uint32, c_char_p)
        return SCSDKDLL.SC_EnumDevices(byref(deviceList), c_uint32(interfaceType), c_char_p(ctiPath))
    
    # C原型:int SC_CALL SC_CreateHandle(OUT SC_DEV_HANDLE* handle, IN SC_ECreateHandleMode mode, IN void* pIdentifier);
    # Create device handle by specifying identifiers
    def SC_CreateHandle(self, mode, pIdentifier):
        SCSDKDLL.SC_CreateHandle.argtype = (c_void_p, c_uint32, c_void_p)
        SCSDKDLL.SC_CreateHandle.restype = c_int
        return SCSDKDLL.SC_CreateHandle(byref(self.handle), c_uint32(mode), pIdentifier)
    
    # C原型:int SC_CALL SC_DestroyHandle(IN SC_HANDLE handle);
    # Destroy device handle
    def SC_DestroyHandle(self):
        SCSDKDLL.SC_DestroyHandle.argtype = c_void_p
        SCSDKDLL.SC_DestroyHandle.restype = c_int
        return SCSDKDLL.SC_DestroyHandle(self.handle)

    # C原型:int SC_CALL SC_GetDeviceInfo(IN SC_HANDLE handle, OUT SC_DeviceInfo *pDevInfo);
    # Get device information
    def SC_GetDeviceInfo(self, pDevInfo):
        SCSDKDLL.SC_GetDeviceInfo.argtype = (c_void_p, POINTER(SC_DeviceInfo))
        SCSDKDLL.SC_GetDeviceInfo.restype = c_int
        return SCSDKDLL.SC_GetDeviceInfo(self.handle, byref(pDevInfo))

    # C原型:int SC_CALL SC_Open(IN SC_HANDLE handle);
    # Open Device
    def SC_Open(self):
        SCSDKDLL.SC_Open.argtype = c_void_p
        SCSDKDLL.SC_Open.restype = c_int
        return SCSDKDLL.SC_Open(self.handle)

    # C原型:int SC_CALL SC_Close(IN SC_HANDLE handle);
    # Close Device
    def SC_Close(self):
        SCSDKDLL.SC_Open.argtype = c_void_p
        SCSDKDLL.SC_Open.restype = c_int
        return SCSDKDLL.SC_Close(self.handle)
    
    # C原型：int SC_CALL SC_SubscribeConnectArg(IN SC_DEV_HANDLE handle, IN SC_ConnectCallBack proc, IN void* pUser);
    # Register call back function of device connection status event.
    def SC_SubscribeConnectArg(self, proc, pUser):
        SCSDKDLL.SC_SubscribeConnectArg.argtype = (c_void_p, c_void_p, c_void_p)
        SCSDKDLL.SC_SubscribeConnectArg.restype = c_int
        return SCSDKDLL.SC_SubscribeConnectArg(None, proc, pUser)
    
    # C原型: int SC_CALL SC_SubscribeParamUpdateArg(IN SC_DEV_HANDLE handle, IN SC_ParamUpdateCallBack proc, IN void* pUser);
    # Register call back function of parameter update event.
    def SC_SubscribeParamUpdateArg(self, proc, pUser):
        SCSDKDLL.SC_SubscribeParamUpdateArg.argtype = (c_void_p, c_void_p, c_void_p)
        SCSDKDLL.SC_SubscribeParamUpdateArg.restype = c_int
        return SCSDKDLL.SC_SubscribeParamUpdateArg(self.handle, proc, pUser)

    # C原型: int SC_CALL SC_SubscribeParamUpdateFeature(IN SC_DEV_HANDLE handle, IN SC_ParamUpdateCallBack proc,
    #     IN SC_UpdateFeatureList *featureList, IN void* pUser);
    # Register call back function of parameter update event with feature_names.
    def SC_SubscribeParamUpdateFeature(self, proc, feature_names, pUser=None):
        if not feature_names:
            raise ValueError("feature_names must be a non-empty list of feature name strings")
        n = len(feature_names)
        items = (SC_UpdateFeatureItem * n)()
        for i in range(n):
            raw = feature_names[i].encode('utf-8') if isinstance(feature_names[i], str) else bytes(feature_names[i])
            if len(raw) >= SC_MAX_STRING_LENTH:
                raw = raw[: SC_MAX_STRING_LENTH - 1]
            items[i].name = raw
        feature_list = SC_UpdateFeatureList()
        feature_list.featureCount = n
        feature_list.pFeatures = cast(items, POINTER(SC_UpdateFeatureItem))
        # 订阅有效期内须保持数组有效（至再次调用本接口或关闭设备）
        self._param_update_feature_items = items
        self._param_update_feature_list = feature_list
        SCSDKDLL.SC_SubscribeParamUpdateFeature.argtypes = (c_void_p, c_void_p, POINTER(SC_UpdateFeatureList), c_void_p)
        SCSDKDLL.SC_SubscribeParamUpdateFeature.restype = c_int
        return SCSDKDLL.SC_SubscribeParamUpdateFeature(self.handle, proc, byref(feature_list), pUser)
      
    # C原型: int SC_CALL SC_SetBufferCount(IN SC_DEV_HANDLE handle, IN unsigned int nSize);
    # Set frame buffer count
    def SC_SetBufferCount(self, nSize):
        SCSDKDLL.SC_SetBufferCount.argtype = (c_void_p, c_uint32)
        SCSDKDLL.SC_SetBufferCount.restype = c_int
        return SCSDKDLL.SC_SetBufferCount(self.handle, c_uint32(nSize))

    # C原型: int SC_CALL SC_StartGrabbing(IN SC_DEV_HANDLE handle);
    # Start grabbing
    def SC_StartGrabbing(self):
        SCSDKDLL.SC_StartGrabbing.argtype = c_void_p
        SCSDKDLL.SC_StartGrabbing.restype = c_int
        return SCSDKDLL.SC_StartGrabbing(self.handle)
   
    # C原型: bool SC_CALL SC_IsGrabbing(IN SC_DEV_HANDLE handle);
    # Check whether device is grabbing or not
    def SC_IsGrabbing(self):
        SCSDKDLL.SC_IsGrabbing.argtype = c_void_p
        SCSDKDLL.SC_IsGrabbing.restype = c_bool
        return SCSDKDLL.SC_IsGrabbing(self.handle)

    # C原型: int SC_CALL SC_StopGrabbing(IN SC_DEV_HANDLE handle);
    # Stop grabbing
    def SC_StopGrabbing(self):
        SCSDKDLL.SC_StopGrabbing.argtype = c_void_p
        SCSDKDLL.SC_StopGrabbing.restype = c_int
        return SCSDKDLL.SC_StopGrabbing(self.handle)

    # C原型: int SC_CALL SC_AttachGrabbing(IN SC_DEV_HANDLE handle, IN SC_FrameCallBack proc, IN void* pUser);
    # Register frame data callback function
    def SC_AttachGrabbing(self, proc, pUser):
        SCSDKDLL.SC_AttachGrabbing.argtype = (c_void_p, c_void_p, c_void_p)
        SCSDKDLL.SC_AttachGrabbing.restype = c_int32
        return SCSDKDLL.SC_AttachGrabbing(self.handle, proc, pUser)

    # C原型: int SC_CALL SC_GetFrame(IN SC_DEV_HANDLE handle, OUT SC_Frame* pFrame, IN unsigned int timeoutMS);
    # Get a frame image
    def SC_GetFrame(self, pFrame, timeoutMS):
        SCSDKDLL.SC_GetFrame.argtype = (c_void_p, POINTER(SC_Frame), c_void_p)
        SCSDKDLL.SC_GetFrame.restype = c_int
        return SCSDKDLL.SC_GetFrame(self.handle, byref(pFrame), c_uint32(timeoutMS))

    # C原型: int SC_CALL SC_ReleaseFrame(IN SC_DEV_HANDLE handle, IN SC_Frame* pFrame);
    # Free image buffer
    def SC_ReleaseFrame(self, pFrame):
        SCSDKDLL.SC_ReleaseFrame.argtype = (c_void_p, POINTER(SC_Frame))
        SCSDKDLL.SC_ReleaseFrame.restype = c_int
        return SCSDKDLL.SC_ReleaseFrame(self.handle, byref(pFrame))
    
    # C原型:SC_API bool SC_CALL SC_FeatureIsAvailable(IN SC_HANDLE handle, IN const char* pFeatureName);
    # Check the property is available or not
    def SC_FeatureIsAvailable(self, pFeatureName):
        SCSDKDLL.SC_FeatureIsAvailable.argtype = (c_void_p, c_char_p)
        SCSDKDLL.SC_FeatureIsAvailable.restype = c_bool
        return SCSDKDLL.SC_FeatureIsAvailable(self.handle, pFeatureName.encode('utf-8'))

    # C原型:SC_API bool SC_CALL SC_FeatureIsReadable(IN SC_HANDLE handle, IN const char* pFeatureName);
    # Check the property is readable or not
    def SC_FeatureIsReadable(self, pFeatureName):
        SCSDKDLL.SC_FeatureIsReadable.argtype = (c_void_p, c_char_p)
        SCSDKDLL.SC_FeatureIsReadable.restype = c_bool
        return SCSDKDLL.SC_FeatureIsReadable(self.handle, pFeatureName.encode('utf-8'))

    # C原型:SC_API bool SC_CALL SC_FeatureIsWriteable(IN SC_HANDLE handle, IN const char* pFeatureName);
    # Check the property is writeable or not
    def SC_FeatureIsWriteable(self, pFeatureName):
        SCSDKDLL.SC_FeatureIsWriteable.argtype = (c_void_p, c_char_p)
        SCSDKDLL.SC_FeatureIsWriteable.restype = c_bool
        return SCSDKDLL.SC_FeatureIsWriteable(self.handle, pFeatureName.encode('utf-8'))

    # C原型:SC_API bool SC_CALL SC_FeatureIsStreamable(IN SC_HANDLE handle, IN const char* pFeatureName);
    # Check the property is streamable or not
    def SC_FeatureIsStreamable(self, pFeatureName):
        SCSDKDLL.SC_FeatureIsStreamable.argtype = (c_void_p, c_char_p)
        SCSDKDLL.SC_FeatureIsStreamable.restype = c_bool
        return SCSDKDLL.SC_FeatureIsStreamable(self.handle, pFeatureName.encode('utf-8'))

    # C原型:SC_API bool SC_CALL SC_GetFeatureType(IN SC_HANDLE handle, IN const char* pFeatureName, OUT SC_EFeatureType* pPropertyType);
    # get property type
    def SC_GetFeatureType(self, pFeatureName, pPropertyType):
        SCSDKDLL.SC_GetFeatureType.argtype = (c_void_p, c_char_p, POINTER(c_int32))
        SCSDKDLL.SC_GetFeatureType.restype = c_bool
        return SCSDKDLL.SC_GetFeatureType(self.handle, pFeatureName.encode('utf-8'), byref(pPropertyType))

    # C原型:SC_API int SC_CALL SC_GetIntFeatureValue(IN SC_HANDLE handle, IN const char* pFeatureName, OUT int64_t* pIntValue);
    # Get integer property value
    def SC_GetIntFeatureValue(self, pFeatureName, pIntValue):
        SCSDKDLL.SC_GetIntFeatureValue.argtype = (c_void_p, c_char_p, POINTER(c_int64))
        SCSDKDLL.SC_GetIntFeatureValue.restype = c_int
        return SCSDKDLL.SC_GetIntFeatureValue(self.handle, pFeatureName.encode('utf-8'), byref(pIntValue))

    # C原型:SC_API int SC_CALL SC_GetIntFeatureMin(IN SC_HANDLE handle, IN const char* pFeatureName, OUT int64_t* pIntValue);
    # Get the integer property settable minimum value
    def SC_GetIntFeatureMin(self, pFeatureName, pIntValue):
        SCSDKDLL.SC_GetIntFeatureMin.argtype = (c_void_p, c_char_p, POINTER(c_int64))
        SCSDKDLL.SC_GetIntFeatureMin.restype = c_int
        return SCSDKDLL.SC_GetIntFeatureMin(self.handle, pFeatureName.encode('utf-8'), byref(pIntValue))

    # C原型:SC_API int SC_CALL SC_GetIntFeatureMax(IN SC_HANDLE handle, IN const char* pFeatureName, OUT int64_t* pIntValue);
    # Get the integer property settable maximum value
    def SC_GetIntFeatureMax(self, pFeatureName, pIntValue):
        SCSDKDLL.SC_GetIntFeatureMax.argtype = (c_void_p, c_char_p, POINTER(c_int64))
        SCSDKDLL.SC_GetIntFeatureMax.restype = c_int
        return SCSDKDLL.SC_GetIntFeatureMax(self.handle, pFeatureName.encode('utf-8'), byref(pIntValue))

    # C原型:SC_API int SC_CALL SC_GetIntFeatureInc(IN SC_HANDLE handle, IN const char* pFeatureName, OUT int64_t* pIntValue);
    # Get integer property increment
    def SC_GetIntFeatureInc(self, pFeatureName, pIntValue):
        SCSDKDLL.SC_GetIntFeatureInc.argtype = (c_void_p, c_char_p, POINTER(c_int64))
        SCSDKDLL.SC_GetIntFeatureInc.restype = c_int
        return SCSDKDLL.SC_GetIntFeatureInc(self.handle, pFeatureName.encode('utf-8'), byref(pIntValue))
    
    # C原型:SC_API int SC_CALL SC_GetFloatFeatureInc(IN SC_HANDLE handle, IN const char* pFeatureName, OUT double* pIntValue);
    # Get float property increment
    def SC_GetFloatFeatureInc(self, pFeatureName, pDoubleValue):
        SCSDKDLL.SC_GetFloatFeatureInc.argtype = (c_void_p, c_char_p, POINTER(c_double))
        SCSDKDLL.SC_GetFloatFeatureInc.restype = c_int
        return SCSDKDLL.SC_GetFloatFeatureInc(self.handle, pFeatureName.encode('utf-8'), byref(pDoubleValue))

    # C原型:SC_API int SC_CALL SC_SetIntFeatureValue(IN SC_HANDLE handle, IN const char* pFeatureName, IN int64_t intValue);
    # Set integer property value
    def SC_SetIntFeatureValue(self, pFeatureName, pIntValue):
        SCSDKDLL.SC_SetIntFeatureValue.argtype = (c_void_p, c_char_p, c_int64)
        SCSDKDLL.SC_SetIntFeatureValue.restype = c_int
        return SCSDKDLL.SC_SetIntFeatureValue(self.handle, pFeatureName.encode('utf-8'), c_int64(pIntValue))

    # C原型:SC_API int SC_CALL SC_GetFloatFeatureValue(IN SC_HANDLE handle, IN const char* pFeatureName, OUT double* pDoubleValue);
    # Get float property value
    def SC_GetFloatFeatureValue(self, pFeatureName, pDoubleValue):
        SCSDKDLL.SC_GetFloatFeatureValue.argtype = (c_void_p, c_char_p, POINTER(c_double))
        SCSDKDLL.SC_GetFloatFeatureValue.restype = c_int
        return SCSDKDLL.SC_GetFloatFeatureValue(self.handle, pFeatureName.encode('utf-8'), byref(pDoubleValue))

    # C原型:SC_API int SC_CALL SC_GetFloatFeatureMin(IN SC_HANDLE handle, IN const char* pFeatureName, OUT double* pDoubleValue);
    # Get the float property settable minimum value
    def SC_GetFloatFeatureMin(self, pFeatureName, pDoubleValue):
        SCSDKDLL.SC_GetFloatFeatureMin.argtype = (c_void_p, c_char_p, POINTER(c_double))
        SCSDKDLL.SC_GetFloatFeatureMin.restype = c_int
        return SCSDKDLL.SC_GetFloatFeatureMin(self.handle, pFeatureName.encode('utf-8'), byref(pDoubleValue))

    # C原型:SC_API int SC_CALL SC_GetFloatFeatureMax(IN SC_HANDLE handle, IN const char* pFeatureName, OUT double* pDoubleValue);
    # Get the float property settable maximum value
    def SC_GetFloatFeatureMax(self, pFeatureName, pDoubleValue):
        SCSDKDLL.SC_GetFloatFeatureMax.argtype = (c_void_p, c_char_p, POINTER(c_double))
        SCSDKDLL.SC_GetFloatFeatureMax.restype = c_int
        return SCSDKDLL.SC_GetFloatFeatureMax(self.handle, pFeatureName.encode('utf-8'), byref(pDoubleValue))

    # C原型:SC_API int SC_CALL SC_SetFloatFeatureValue(IN SC_HANDLE handle, IN const char* pFeatureName, IN double doubleValue);
    # Set float property value
    def SC_SetFloatFeatureValue(self, pFeatureName, doubleValue):
        SCSDKDLL.SC_SetFloatFeatureValue.argtype = (c_void_p, c_char_p, c_double)
        SCSDKDLL.SC_SetFloatFeatureValue.restype = c_int
        return SCSDKDLL.SC_SetFloatFeatureValue(self.handle, pFeatureName.encode('utf-8'), c_double(doubleValue))

    # C原型:SC_API int SC_CALL SC_GetBoolFeatureValue(IN SC_HANDLE handle, IN const char* pFeatureName, OUT bool* pBoolValue);
    # Get boolean property value
    def SC_GetBoolFeatureValue(self, pFeatureName, pBoolValue):
        SCSDKDLL.SC_GetBoolFeatureValue.argtype = (c_void_p, c_char_p, c_void_p)
        SCSDKDLL.SC_GetBoolFeatureValue.restype = c_int
        return SCSDKDLL.SC_GetBoolFeatureValue(self.handle, pFeatureName.encode('utf-8'), byref(pBoolValue))

    # C原型:SC_API int SC_CALL SC_SetBoolFeatureValue(IN SC_HANDLE handle, IN const char* pFeatureName, IN bool boolValue);
    # Set boolean property value
    def SC_SetBoolFeatureValue(self, pFeatureName, boolValue):
        SCSDKDLL.SC_SetBoolFeatureValue.argtype = (c_void_p, c_char_p, c_bool)
        SCSDKDLL.SC_SetBoolFeatureValue.restype = c_int
        return SCSDKDLL.SC_SetBoolFeatureValue(self.handle, pFeatureName.encode('utf-8'), c_bool(boolValue))

    # C原型:SC_API int SC_CALL SC_GetEnumFeatureValue(IN SC_HANDLE handle, IN const char* pFeatureName, OUT uint64_t* pEnumValue);
    # Get enumeration property value
    def SC_GetEnumFeatureValue(self, pFeatureName, pEnumValue):
        SCSDKDLL.SC_GetEnumFeatureValue.argtype = (c_void_p, c_char_p, POINTER(c_uint64))
        SCSDKDLL.SC_GetEnumFeatureValue.restype = c_int
        return SCSDKDLL.SC_GetEnumFeatureValue(self.handle, pFeatureName.encode('utf-8'), byref(pEnumValue))

    # C原型:SC_API int SC_CALL SC_SetEnumFeatureValue(IN SC_HANDLE handle, IN const char* pFeatureName, IN uint64_t enumValue);
    # Set enumeration property value
    def SC_SetEnumFeatureValue(self, pFeatureName, enumValue):
        SCSDKDLL.SC_SetEnumFeatureValue.argtype = (c_void_p, c_char_p, c_uint64)
        SCSDKDLL.SC_SetEnumFeatureValue.restype = c_int
        return SCSDKDLL.SC_SetEnumFeatureValue(self.handle, pFeatureName.encode('utf-8'), c_uint64(enumValue))

    # C原型:SC_API int SC_CALL SC_GetEnumFeatureSymbol(IN SC_HANDLE handle, IN const char* pFeatureName, OUT SC_String* pEnumSymbol);
    # Get enumeration property symbol value
    def SC_GetEnumFeatureSymbol(self, pFeatureName, pEnumSymbol):
        SCSDKDLL.SC_GetEnumFeatureSymbol.argtype = (c_void_p, c_char_p, POINTER(SC_String))
        SCSDKDLL.SC_GetEnumFeatureSymbol.restype = c_int
        return SCSDKDLL.SC_GetEnumFeatureSymbol(self.handle, pFeatureName.encode('utf-8'), byref(pEnumSymbol))

    # C原型:SC_API int SC_CALL SC_SetEnumFeatureSymbol(IN SC_HANDLE handle, IN const char* pFeatureName, IN const char* pEnumSymbol);
    # Set enumeration property symbol value
    def SC_SetEnumFeatureSymbol(self, pFeatureName, pEnumSymbol):
        SCSDKDLL.SC_SetEnumFeatureSymbol.argtype = (c_void_p, c_char_p, c_char_p)
        SCSDKDLL.SC_SetEnumFeatureSymbol.restype = c_int
        return SCSDKDLL.SC_SetEnumFeatureSymbol(self.handle, pFeatureName.encode('utf-8'), pEnumSymbol.encode('utf-8'))

    # C原型:SC_API int SC_CALL SC_GetEnumFeatureEntryNum(IN SC_HANDLE handle, IN const char* pFeatureName, OUT unsigned int* pEntryNum);
    # Get the number of enumeration property settable enumeration
    def SC_GetEnumFeatureEntryNum(self, pFeatureName, pEntryNum):
        SCSDKDLL.SC_GetEnumFeatureEntryNum.argtype = (c_void_p, c_char_p, POINTER(c_uint32))
        SCSDKDLL.SC_GetEnumFeatureEntryNum.restype = c_int
        return SCSDKDLL.SC_GetEnumFeatureEntryNum(self.handle, pFeatureName.encode('utf-8'), byref(pEntryNum))

    # C原型:SC_API int SC_CALL SC_GetEnumFeatureEntrys(IN SC_HANDLE handle, IN const char* pFeatureName, IN_OUT SC_EnumEntryList* pEnumEntryList);
    # Get settable enumeration value list of enumeration property
    def SC_GetEnumFeatureEntrys(self, pFeatureName, pEnumEntryList):
        SCSDKDLL.SC_GetEnumFeatureEntrys.argtype = (c_void_p, c_char_p, c_void_p)
        SCSDKDLL.SC_GetEnumFeatureEntrys.restype = c_int
        return SCSDKDLL.SC_GetEnumFeatureEntrys(self.handle, pFeatureName.encode('utf-8'), byref(pEnumEntryList))

    # C原型:SC_API int SC_CALL SC_GetStringFeatureValue(IN SC_HANDLE handle, IN const char* pFeatureName, OUT SC_String* pStringValue);
    # Get string property value
    def SC_GetStringFeatureValue(self, pFeatureName, pStringValue):
        SCSDKDLL.SC_GetStringFeatureValue.argtype = (c_void_p, c_char_p, POINTER(SC_String))
        SCSDKDLL.SC_GetStringFeatureValue.restype = c_int
        return SCSDKDLL.SC_GetStringFeatureValue(self.handle, pFeatureName.encode('utf-8'), byref(pStringValue))

    # C原型:SC_API int SC_CALL SC_SetStringFeatureValue(IN SC_HANDLE handle, IN const char* pFeatureName, IN const char* pStringValue);
    # Set string property value
    def SC_SetStringFeatureValue(self, pFeatureName, pStringValue):
        SCSDKDLL.SC_SetStringFeatureValue.argtype = (c_void_p, c_char_p, c_char_p)
        SCSDKDLL.SC_SetStringFeatureValue.restype = c_int
        return SCSDKDLL.SC_SetStringFeatureValue(self.handle, pFeatureName.encode('utf-8'), pStringValue.encode('utf-8'))
    
    # C原型:SC_API int SC_CALL SC_ExecuteCommandFeature(IN SC_HANDLE handle, IN const char* pFeatureName);
    # Execute command property
    def SC_ExecuteCommandFeature(self, pFeatureName):
        SCSDKDLL.SC_ExecuteCommandFeature.argtype = (c_void_p, c_char_p)
        SCSDKDLL.SC_ExecuteCommandFeature.restype = c_int
        return SCSDKDLL.SC_ExecuteCommandFeature(self.handle, pFeatureName.encode('utf-8'))
    
    # C原型:int SC_CALL SC_DownLoadGenICamXML(IN SC_DEV_HANDLE handle, IN const char* pFullFileName);
    # Download device description XML file, and save the files to specified path.
    def SC_DownLoadGenICamXML(self, pFullFileName):
        SCSDKDLL.SC_DownLoadGenICamXML.argtype = (c_void_p, c_char_p)
        SCSDKDLL.SC_DownLoadGenICamXML.restype = c_int
        return SCSDKDLL.SC_DownLoadGenICamXML(self.handle, pFullFileName.encode('utf-8'))
    
    # C原型: SC_API int SC_CALL SC_OpenRecord(IN SC_DEV_HANDLE handle, IN SC_RecordParam* pstRecordParam);
    # Open record
    def SC_OpenRecord(self, pRecordParam):
        SCSDKDLL.SC_OpenRecord.argtypes = (c_void_p, POINTER(SC_RecordParam))
        SCSDKDLL.SC_OpenRecord.restype = c_int
        return SCSDKDLL.SC_OpenRecord(self.handle, byref(pRecordParam))
    
    # C原型：SC_API int SC_CALL SC_CloseRecord(IN SC_DEV_HANDLE handle);
    # Close record
    def SC_CloseRecord(self):
        SCSDKDLL.SC_CloseRecord.argtypes = (c_void_p)
        SCSDKDLL.SC_CloseRecord.restype = c_int
        return SCSDKDLL.SC_CloseRecord(self.handle)
    
    # C原型: int SC_CALL SC_SubscribeExportNotify(IN SC_DEV_HANDLE handle, IN ExportEventCB proc, IN void* pUser);
    # subscribe export notify callback function
    def SC_SubscribeExportNotify(self, proc, pUser):
        SCSDKDLL.SC_SubscribeExportNotify.argtype = (c_void_p, c_void_p, c_void_p)
        SCSDKDLL.SC_SubscribeExportNotify.restype = c_int
        return SCSDKDLL.SC_SubscribeExportNotify(self.handle, proc, pUser)
    
    # C原型: int SC_CALL SC_SetExportCacheSize(IN SC_DEV_HANDLE handle, IN uint64_t cacheSizeInByte);
    # set the cache size used for recording
    def SC_SetExportCacheSize(self, cacheSizeInByte):
        SCSDKDLL.SC_SetExportCacheSize.argtype = (c_void_p, c_uint64)
        SCSDKDLL.SC_SetExportCacheSize.restype = c_int
        return SCSDKDLL.SC_SetExportCacheSize(self.handle, cacheSizeInByte)

    # C原型：SC_API int SC_CALL SC_SetROI(IN SC_DEV_HANDLE handle, IN int64_t width, IN int64_t height, IN int64_t offsetX, IN int64_t offsetY);
    # set roi
    def SC_SetROI(self, width, height, offsetX, offsetY):
        SCSDKDLL.SC_SetROI.argtypes = (c_void_p, c_int64, c_int64, c_int64, c_int64)
        SCSDKDLL.SC_SetROI.restype = c_int
        return SCSDKDLL.SC_SetROI(self.handle, width, height, offsetX, offsetY)
                                