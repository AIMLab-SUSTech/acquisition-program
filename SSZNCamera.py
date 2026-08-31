import ctypes
import numpy as np
import pfnc

from camera import Camera
from SLStreamLink import (
    SLStreamLink,
    RTNCODE,
    INTERFACE,
    PARAM_VALUE_TYPE,
    SL_RECORD_MEDIA,
    SL_REQIMAGES_PARAM,
    SL_INTERFACE_INFO_LIST,
    SL_INTERFACE_INFO,
    SL_DEVICE_INFO_LIST,
    SL_DEVICE_INFO,
    SLEnumItem,
    SL_EVENT_CALLBACK,
    SlDefineParam,
)


# 相机运行模式 SlParamMode (与 PE 示例 main.c 一致)
CAMERA_MODE_IDLE = 1      # 空闲 / 停止
CAMERA_MODE_READY = 2     # 就绪 (录制前)
CAMERA_MODE_RECORD = 3    # 录制中
CAMERA_MODE_PREVIEW = 5   # 预览 / 采集

# SensorMode 枚举值 (相机 GenICam SensorMode)
SENSOR_MODE_HDRB = 0      # RGB 模式
SENSOR_MODE_HSRH = 3
SENSOR_MODE_HSRL = 4
SENSOR_MODE_HDSS = 5      # 单光子模式 (Single Shot / SPAD)
SENSOR_MODE_GSHG = 8
SENSOR_MODE_GSLG = 9
SENSOR_MODE_GDRB = 10


class SSZNCamera(Camera):

    def __init__(self):
        super().__init__()

        # ==============================
        # SLStreamLink
        # ==============================
        self.sl = SLStreamLink()

        # 设备状态
        self.m_deviceHandle = None
        self.m_connect = False
        self.m_stream_active = False

        # 事件回调必须保存引用
        self._event_callback = None

        # 图像参数
        self.width = 0
        self.height = 0
        self.exposureTime = 0.0
        self.acquisitionFPS = 0.0

        # 当前接口 / 设备
        self.tlayer_type = None
        self.interface_id = None
        self.device_id = None

        # 初始化 SDK
        ret = self.sl.init()

        if ret != RTNCODE.OK:
            print(f"SSZN: 初始化 SLStreamLink 失败: {ret}")
            try:
                print(self.sl.get_last_error_info())
            except Exception:
                pass
            return

        print("SSZN: SLStreamLink 初始化成功")

    # ==========================================================
    # 1. 获取支持的传输层类型
    # ==========================================================
    def get_support_tlayer_types(self):
        """
        对应 Demo 中的 GetSupportTLayerType()

        返回:
            [(tlayer_type, name), ...]
        """

        nTLayerTypeList = (ctypes.c_uint * 64)()
        piTLayerTypeNum = ctypes.c_int(64)

        ret = self.sl.dll.SLIF_GetSupportTLayerTypeList(
            nTLayerTypeList,
            ctypes.byref(piTLayerTypeNum)
        )

        if ret != RTNCODE.OK:
            print(f"SSZN: 获取传输层类型失败: {ret}")
            return []

        result = []

        for i in range(piTLayerTypeNum.value):

            tlayer_type = nTLayerTypeList[i]

            # 查询初始化结果
            pBuffer = ctypes.create_string_buffer(
                256
            )
            piSize = ctypes.c_int(256)

            ret_init = self.sl.dll.SLIF_GetTLayerTypeInitResult(
                tlayer_type,
                pBuffer,
                ctypes.byref(piSize)
            )

            # 与 Demo 保持一致
            if piSize.value != 256:
                continue

            # 查询名称
            tl_name_size = ctypes.c_int(128)
            tl_name = ctypes.create_string_buffer(128)

            ret_name = self.sl.dll.SLIF_GetTLayerTypeName(
                tlayer_type,
                tl_name,
                ctypes.byref(tl_name_size)
            )

            if ret_name == RTNCODE.OK:
                name = tl_name.value.decode(
                    "latin-1",
                    errors="ignore"
                )

                result.append(
                    (tlayer_type, name)
                )

                print(
                    f"SSZN: 支持传输层 "
                    f"{name}, type={tlayer_type}"
                )

        return result

    # ==========================================================
    # 2. 搜索接口
    # ==========================================================
    def search_interfaces(self, tlayer_type):
        """
        对应 Demo 中的 SearchInterface()

        返回:
            interface 数量
        """

        interface_list = SL_INTERFACE_INFO_LIST()

        ret = self.sl.dll.SLIF_DetectInterfaces(
            ctypes.c_uint(tlayer_type),
            ctypes.byref(interface_list),
            None,
            0
        )

        if ret != RTNCODE.OK:
            print(
                f"SSZN: 检测接口失败: {ret}"
            )
            return []

        interfaces = []

        print(
            f"SSZN: 检测到 {interface_list.nInterfaceNum} 个接口"
        )

        for i in range(interface_list.nInterfaceNum):

            if_info_ptr = ctypes.cast(
                interface_list.pInterfaceInfos[i],
                ctypes.POINTER(SL_INTERFACE_INFO)
            )

            display_name = (
                if_info_ptr.contents.chDisplayName
            )

            name = bytes(display_name).decode(
                "latin1",
                errors="ignore"
            ).rstrip("\x00")

            interfaces.append({
                "id": i,
                "name": name
            })

            print(
                f"  Interface[{i}] = {name}"
            )

        return interfaces

    # ==========================================================
    # 3. 搜索设备
    # ==========================================================
    def search_devices(self, tlayer_type):
        """
        对应 Demo 中的 SearchDevice()

        返回:
            [
                {
                    "id": 列表序号,
                    "interface_index": nInterFaceIndex (OpenDevice 用),
                    "device_index": nDeviceIndex (OpenDevice 用),
                    "name": display name,
                    "device_id": ...
                }
            ]
        """

        dev_list = SL_DEVICE_INFO_LIST()

        ret = self.sl.dll.SLIF_DetectDevices(
            ctypes.c_uint(tlayer_type),
            ctypes.byref(dev_list),
            None,
            0
        )

        if ret != RTNCODE.OK:
            print(
                f"SSZN: 检测设备失败: {ret} "
                f"({self.sl.get_last_error_info()})"
            )
            return []

        devices = []

        print(
            f"SSZN: 检测到 {dev_list.nDeviceNum} 个设备"
        )

        for i in range(dev_list.nDeviceNum):

            dev_info_ptr = ctypes.cast(
                dev_list.pDeviceInfo[i],
                ctypes.POINTER(SL_DEVICE_INFO)
            )

            dev_info = dev_info_ptr.contents

            display_name = ctypes.string_at(
                dev_info.chDeviceDisplayName
            ).decode(
                "latin1",
                errors="ignore"
            )

            device_id = ctypes.string_at(
                dev_info.chDeviceID
            ).decode(
                "latin1",
                errors="ignore"
            )

            interface_index = dev_info.nInterFaceIndex
            device_index = dev_info.nDeviceIndex

            devices.append({
                "id": i,
                "interface_index": interface_index,
                "device_index": device_index,
                "name": display_name,
                "device_id": device_id
            })

            print(
                f"  Device[{i}] \"{display_name}\""
                f"  ifIdx={interface_index}"
                f"  devIdx={device_index}"
                f"  devID={device_id}"
            )

        return devices

    # ==========================================================
    # 4. 连接相机
    # ==========================================================
    def connect(
        self,
        tlayer_type=None,
        interface_id=None,
        device_id=None,
        device_index=0,
        sensor_mode="HDSS"
    ):
        """
        连接相机 (流程与 PE 示例 PhotonEyeSDK_c/main.c 一致):

          1. 切换连接协议 (默认 OCT U3V: SL_USB_INTERFACE_OCT,
             OCT 下搜不到设备时自动切换其它传输层协议)
          2. 搜索采集卡   SLIF_DetectInterfaces
          3. 搜索设备连接 SLIF_DetectDevices
          4. 打开设备     SLIF_OpenDevice(tl, ifIdx, devIdx, &h)
          5. 注册事件回调 SLIF_RegisterEventCallBack (掉线检测)

        参数:
            tlayer_type:
                传输层协议。None = 默认 OCT (0x30100003)。

            interface_id / device_id:
                直接指定 OpenDevice 的 ifIdx / devIdx
                (与 PE 菜单 "连接设备" 输入一致)。
                为 None 时从搜索结果中取 device_index 号设备,
                使用其上报的 nInterFaceIndex / nDeviceIndex。

            device_index:
                设备列表序号 (默认 0 = 第一台相机)。

            sensor_mode:
                连接成功后直接切换的传感器模式。
                可传符号名 (默认 "HDSS" 单光子模式)
                或数值 (如 SENSOR_MODE_HDSS=5)。
                None = 不切换, 保持相机当前模式。

        返回:
            bool: 是否连接成功
        """

        # 已连接
        if self.m_connect:
            print("SSZN: 设备已经连接")
            return True

        # ------------------------------------------------------
        # 1. 切换连接协议 (默认 OCT U3V)
        # ------------------------------------------------------
        if tlayer_type is None:
            tlayer_type = INTERFACE.SL_USB_INTERFACE_OCT

            print(
                f"SSZN: 使用 OCT 连接协议 "
                f"(TL=0x{tlayer_type:08X})"
            )

        self.tlayer_type = tlayer_type

        # ------------------------------------------------------
        # 2. 搜索采集卡 (接口)
        #    USB OCT 直连相机没有独立采集卡, 搜不到不报错,
        #    ifIdx 以设备上报的 nInterFaceIndex 为准。
        # ------------------------------------------------------
        self.search_interfaces(tlayer_type)

        # ------------------------------------------------------
        # 3. 搜索设备连接
        #    OCT 下搜不到设备时, 自动切换其它协议重试
        # ------------------------------------------------------
        devices = self.search_devices(tlayer_type)

        if len(devices) == 0 and \
                tlayer_type == INTERFACE.SL_USB_INTERFACE_OCT:

            for tl, name in self.get_support_tlayer_types():

                if tl == tlayer_type:
                    continue

                print(
                    f"SSZN: OCT 下未找到设备, "
                    f"切换协议 {name} (0x{tl:08X}) 重试 ..."
                )

                tlayer_type = tl
                self.tlayer_type = tl

                devices = self.search_devices(tl)

                if len(devices) > 0:
                    break

        if len(devices) == 0:
            print(
                f"SSZN: 没有检测到相机 "
                f"(TL=0x{tlayer_type:08X})"
            )
            return False

        # ------------------------------------------------------
        # 确定 ifIdx / devIdx
        # ------------------------------------------------------
        if interface_id is None or device_id is None:

            if device_index < 0 or device_index >= len(devices):
                print(
                    f"SSZN: device_index 无效: {device_index}"
                )
                return False

            dev = devices[device_index]

            interface_id = dev["interface_index"]
            device_id = dev["device_index"]

        self.interface_id = interface_id
        self.device_id = device_id

        # ------------------------------------------------------
        # 4. 打开设备
        # ------------------------------------------------------
        self.m_deviceHandle = ctypes.c_void_p()

        ret = self.sl.dll.SLIF_OpenDevice(
            ctypes.c_uint(tlayer_type),
            ctypes.c_uint(interface_id),
            ctypes.c_uint(device_id),
            ctypes.byref(self.m_deviceHandle)
        )

        if ret != RTNCODE.OK:

            print(
                f"SSZN: 打开设备失败: {ret} "
                f"({self.sl.get_last_error_info()})"
            )

            self.m_deviceHandle = None

            return False

        # ------------------------------------------------------
        # 5. 注册事件回调 (检测相机掉线)
        # ------------------------------------------------------
        self._event_callback = SL_EVENT_CALLBACK(
            self._shs_event_callback
        )

        ret = self.sl.dll.SLIF_RegisterEventCallBack(
            self.m_deviceHandle,
            self._event_callback,
            None
        )

        if ret != RTNCODE.OK:

            print(
                f"SSZN: 注册事件回调失败: {ret}"
            )

            self.sl.dll.SLIF_CloseDevice(
                self.m_deviceHandle
            )

            self.m_deviceHandle = None

            return False

        # ------------------------------------------------------
        # 连接成功
        # ------------------------------------------------------
        self.m_connect = True

        print(
            f"SSZN: 相机连接成功 "
            f"(TL=0x{tlayer_type:08X}, "
            f"ifIdx={interface_id}, devIdx={device_id})"
        )

        # 获取相机参数
        self._refresh_parameters()

        # 直接切换传感器模式 (默认 HDSS 单光子模式)
        if sensor_mode is not None:
            self.set_sensor_mode(sensor_mode)

        return True

    # ==========================================================
    # 5. 事件回调
    # ==========================================================
    def _shs_event_callback(
        self,
        nMsgType,
        pUser
    ):

        print(
            f"SSZN Event: {nMsgType}"
        )

        # 与 Demo 保持一致
        if nMsgType == 0x10000001:

            print(
                "SSZN: 相机掉线！"
            )

            self.m_connect = False

    # ==========================================================
    # 6. 刷新相机参数
    # ==========================================================
    def _refresh_parameters(self):

        if not self.m_deviceHandle:
            return

        # Width
        width = ctypes.c_longlong(0)

        ret = self.sl.dll.SLIF_GetInteger(
            self.m_deviceHandle,
            b"Width",
            ctypes.byref(width),
            PARAM_VALUE_TYPE.PARAM_VALUE_INT
        )

        if ret == RTNCODE.OK:
            self.width = width.value

        # Height
        height = ctypes.c_longlong(0)

        ret = self.sl.dll.SLIF_GetInteger(
            self.m_deviceHandle,
            b"Height",
            ctypes.byref(height),
            PARAM_VALUE_TYPE.PARAM_VALUE_INT
        )

        if ret == RTNCODE.OK:
            self.height = height.value

        # Exposure
        exposure = ctypes.c_double(0)

        ret = self.sl.dll.SLIF_GetFloat(
            self.m_deviceHandle,
            b"ExposureTime",
            ctypes.byref(exposure)
        )

        if ret == RTNCODE.OK:
            self.exposureTime = exposure.value

        # FPS
        fps = ctypes.c_double(0)

        ret = self.sl.dll.SLIF_GetFloat(
            self.m_deviceHandle,
            b"AcquisitionFrameRate",
            ctypes.byref(fps)
        )

        if ret == RTNCODE.OK:
            self.acquisitionFPS = fps.value

        print(
            f"SSZN 参数:"
            f" {self.width} x {self.height},"
            f" exposure={self.exposureTime} us,"
            f" FPS={self.acquisitionFPS}"
        )

    # ==========================================================
    # 7. 查询 SensorMode 可选项
    # ==========================================================
    def get_sensor_mode_items(self):
        """
        查询 SensorMode 枚举项 (对应 PE 示例 do_refresh_params)。

        返回:
            [(value, symbolic), ...]
            例如 [(0, "HDRB"), (5, "HDSS"), ...]
        """

        if not self.m_deviceHandle:
            return []

        ecount = ctypes.c_longlong(0)

        ret = self.sl.dll.SLIF_GetEnumItems(
            self.m_deviceHandle,
            b"SensorMode",
            None,
            ctypes.byref(ecount)
        )

        if ret != RTNCODE.OK or ecount.value <= 0:
            return []

        items = (SLEnumItem * ecount.value)()

        ret = self.sl.dll.SLIF_GetEnumItems(
            self.m_deviceHandle,
            b"SensorMode",
            items,
            ctypes.byref(ecount)
        )

        if ret != RTNCODE.OK:
            return []

        result = []

        for i in range(ecount.value):

            symbolic = items[i].strSymbolic.decode(
                "latin1",
                errors="ignore"
            ).rstrip("\x00")

            result.append(
                (int(items[i].nValue), symbolic)
            )

        return result

    # ==========================================================
    # 8. 设置 SensorMode
    # ==========================================================
    def set_sensor_mode(self, mode=SENSOR_MODE_HDSS):
        """
        设置传感器模式 SensorMode。

        参数:
            mode:
                符号名 (如 "HDSS" 单光子模式) 或
                数值 (如 SENSOR_MODE_HDSS=5)。

        说明:
            HDSS = 单光子模式 (SPAD Single Shot)

        返回:
            bool: 是否设置成功
        """

        if not self.m_deviceHandle:
            return False

        # 符号名 → 枚举值
        if isinstance(mode, str):

            items = self.get_sensor_mode_items()

            target = None

            for value, symbolic in items:

                if symbolic.upper() == mode.upper():
                    target = value
                    break

            if target is None:

                print(
                    f"SSZN: SensorMode 枚举中找不到 "
                    f"\"{mode}\""
                )

                return False

            mode = target

        ret = self.sl.dll.SLIF_SetInteger(
            self.m_deviceHandle,
            b"SensorMode",
            ctypes.c_longlong(int(mode)),
            PARAM_VALUE_TYPE.PARAM_VALUE_ENUM
        )

        if ret == RTNCODE.OK:

            print(
                f"SSZN: SensorMode = {mode}"
                f"{' (HDSS 单光子模式)' if int(mode) == SENSOR_MODE_HDSS else ''}"
            )

            # 模式切换后刷新参数
            self._refresh_parameters()

            return True

        print(
            f"SSZN: 设置 SensorMode 失败: {ret} "
            f"({self.sl.get_last_error_info()})"
        )

        return False

    # ==========================================================
    # 9. 设置曝光时间
    # ==========================================================
    def set_ex_time(self, ex_time):
        """
        ex_time:
            秒

        SSZN SDK:
            ExposureTime 单位为 us
        """

        if not self.m_deviceHandle:
            return False

        exposure_us = float(ex_time) * 1e6

        ret = self.sl.dll.SLIF_SetFloat(
            self.m_deviceHandle,
            b"ExposureTime",
            ctypes.c_double(exposure_us)
        )

        if ret != RTNCODE.OK:

            print(
                f"SSZN: 设置曝光时间失败: {ret}"
            )

            return False

        self.exposureTime = exposure_us

        print(
            f"SSZN: 曝光时间 = "
            f"{exposure_us} us"
        )

        return True

    # ==========================================================
    # 10. 设置帧率
    # ==========================================================
    def set_fps(self, fps):

        if not self.m_deviceHandle:
            return False

        ret = self.sl.dll.SLIF_SetFloat(
            self.m_deviceHandle,
            b"AcquisitionFrameRate",
            ctypes.c_double(float(fps))
        )

        if ret != RTNCODE.OK:

            print(
                f"SSZN: 设置帧率失败: {ret}"
            )

            return False

        self.acquisitionFPS = float(fps)

        return True

    # ==========================================================
    # 11. 切换相机运行模式 (CCD 模式 / 采集模式)
    # ==========================================================
    def set_run_mode(self, mode):
        """
        切换 SlParamMode (与 PE 示例一致):

            CAMERA_MODE_IDLE    = 1  空闲 / 停止
            CAMERA_MODE_READY   = 2  就绪 (录制前)
            CAMERA_MODE_RECORD  = 3  录制中
            CAMERA_MODE_PREVIEW = 5  预览 / 采集

        返回:
            RTNCODE.OK / RTNCODE.NG
        """

        if not self.m_deviceHandle:
            return RTNCODE.NG

        ret = self.sl.dll.SLIF_SetInteger(
            self.m_deviceHandle,
            SlDefineParam.MODE,
            ctypes.c_longlong(int(mode)),
            PARAM_VALUE_TYPE.PARAM_VALUE_INT
        )

        if ret == RTNCODE.OK:
            print(
                f"SSZN: SlParamMode 切换为 {mode}"
            )

        return ret

    # ==========================================================
    # 12. 开始采集
    # ==========================================================
    def start_acquisition(self):
        """
        开始取流 (与 PE 示例 do_start_capture 一致):
          1. SLIF_StartCapture
          2. SlParamMode = PREVIEW (5)
        """

        if not self.m_deviceHandle:
            print(
                "SSZN: 没有设备句柄"
            )
            return False

        if not self.m_connect:
            print(
                "SSZN: 设备未连接"
            )
            return False

        if self.m_stream_active:
            print(
                "SSZN: 取流已在运行中"
            )
            return True

        # ------------------------------------------------------
        # 第一步：StartCapture
        # ------------------------------------------------------
        ret = self.sl.dll.SLIF_StartCapture(
            self.m_deviceHandle
        )

        if ret != RTNCODE.OK:

            print(
                f"SSZN: StartCapture 失败: {ret} "
                f"({self.sl.get_last_error_info()})"
            )

            return False

        self.m_stream_active = True

        # ------------------------------------------------------
        # 第二步：切换到采集 (预览) 模式 PREVIEW (5)
        # ------------------------------------------------------
        ret = self.set_run_mode(
            CAMERA_MODE_PREVIEW
        )

        if ret != RTNCODE.OK:

            print(
                f"SSZN: 切换采集模式失败: {ret}"
            )

            self.sl.dll.SLIF_StopCapture(
                self.m_deviceHandle
            )

            self.m_stream_active = False

            return False

        print(
            "SSZN: 开始采集成功 (预览模式)"
        )

        return True

    # ==========================================================
    # 13. 停止采集
    # ==========================================================
    def stop_acquisition(self):
        """
        停止取流 (与 PE 示例 do_stop_capture 一致):
          1. SLIF_StopCapture
          2. SlParamMode = IDLE (1)
        """

        if not self.m_deviceHandle:
            return True

        if not self.m_stream_active:
            print(
                "SSZN: 取流未启动"
            )
            return True

        ret = self.sl.dll.SLIF_StopCapture(
            self.m_deviceHandle
        )

        if ret != RTNCODE.OK:

            print(
                f"SSZN: 停止采集失败: {ret}"
            )

            return False

        self.m_stream_active = False

        # 切回空闲 (停止) 模式
        self.set_run_mode(CAMERA_MODE_IDLE)

        print(
            "SSZN: 停止采集成功"
        )

        return True

    # ==========================================================
    # 14. 开始录制
    # ==========================================================
    def start_record(
        self,
        media=SL_RECORD_MEDIA.RecordMedia_MRAW,
        cache_frames=100,
        save_path="",
        max_disk_frames=0
    ):
        """
        开始录制 (与 PE 示例 do_start_record 一致):

          1. SlParamRecMedia   = media   (ENUM)
          2. SlParamCacheFrames = cache_frames (INT)
          3. 非 Memory 媒介:
             SlParamRecordDiskPath   = save_path
             SlParamRecordDiskRecframes = max_disk_frames
          4. 模式切换: PREVIEW(5) → READY(2) → RECORD(3)

        参数:
            media:
                SL_RECORD_MEDIA 枚举
                (0=Memory, 0x1002=MRAW, 0x2001=BMP, 0x2002=PNG ...)

            cache_frames:
                缓存帧数

            save_path:
                磁盘录制保存路径 (非 Memory 必填)

            max_disk_frames:
                磁盘录制帧数, <=0 时取 cache_frames

        返回:
            bool: 是否成功
        """

        if not self.m_deviceHandle:
            print(
                "SSZN: 没有设备句柄"
            )
            return False

        if not self.m_connect:
            print(
                "SSZN: 设备未连接"
            )
            return False

        dll = self.sl.dll
        h = self.m_deviceHandle

        # Step 1: 录制媒介
        ret = dll.SLIF_SetInteger(
            h,
            SlDefineParam.REC_MEDIA,
            ctypes.c_longlong(int(media)),
            PARAM_VALUE_TYPE.PARAM_VALUE_ENUM
        )

        print(
            f"SSZN: SetRecMedia({int(media)}) ret={ret}"
        )

        # Step 2: 缓存帧数
        ret = dll.SLIF_SetInteger(
            h,
            SlDefineParam.CACHE_FRAMES,
            ctypes.c_longlong(int(cache_frames)),
            PARAM_VALUE_TYPE.PARAM_VALUE_INT
        )

        print(
            f"SSZN: SetCacheFrames({cache_frames}) ret={ret}"
        )

        # Step 3: 磁盘录制
        if int(media) != SL_RECORD_MEDIA.RecordMedia_Memory:

            if not save_path:
                print(
                    "SSZN: 磁盘录制必须指定 save_path"
                )
                return False

            path = str(save_path)

            if not path.endswith(("\\", "/")):
                path += "\\"

            ret = dll.SLIF_SetString(
                h,
                SlDefineParam.RECORD_DISK_PATH,
                path.encode("ascii", errors="ignore")
            )

            print(
                f"SSZN: SetDiskPath(\"{path}\") ret={ret}"
            )

            if max_disk_frames <= 0:
                max_disk_frames = cache_frames

            ret = dll.SLIF_SetInteger(
                h,
                SlDefineParam.RECORD_DISK_RECFRAMES,
                ctypes.c_longlong(int(max_disk_frames)),
                PARAM_VALUE_TYPE.PARAM_VALUE_INT
            )

            print(
                f"SSZN: SetDiskRecFrames({max_disk_frames}) ret={ret}"
            )

        # Step 4: 模式切换 PREVIEW → READY → RECORD
        self.set_run_mode(CAMERA_MODE_PREVIEW)
        self.set_run_mode(CAMERA_MODE_READY)

        ret = self.set_run_mode(CAMERA_MODE_RECORD)

        if ret == RTNCODE.OK:
            print(
                f"SSZN: 开始录制成功 "
                f"(media=0x{int(media):04X}, "
                f"cacheFrames={cache_frames})"
            )
            return True

        print(
            f"SSZN: 开始录制失败: {ret} "
            f"({self.sl.get_last_error_info()})"
        )

        return False

    # ==========================================================
    # 15. 停止录制
    # ==========================================================
    def stop_record(self):
        """
        停止录制 (与 PE 示例 do_stop_record 一致):
          SlParamMode 切回 PREVIEW (5)
        """

        if not self.m_deviceHandle:
            print(
                "SSZN: 没有设备句柄"
            )
            return False

        if not self.m_connect:
            print(
                "SSZN: 设备未连接"
            )
            return False

        ret = self.set_run_mode(CAMERA_MODE_PREVIEW)

        if ret == RTNCODE.OK:
            print(
                "SSZN: 录制已停止"
            )
            return True

        print(
            f"SSZN: 停止录制失败: {ret} "
            f"({self.sl.get_last_error_info()})"
        )

        return False

    # ==========================================================
    # 16. 获取最新图像
    # ==========================================================
    def read_newest_image(self):

        if not self.m_deviceHandle:
            return None

        if not self.m_connect:
            return None

        param = SL_REQIMAGES_PARAM()

        raw_data_ptr = ctypes.c_void_p()

        ret = self.sl.dll.SLIF_AcquirePreviewFrameRef(
            self.m_deviceHandle,
            ctypes.byref(raw_data_ptr),
            ctypes.byref(param),
            2500
        )

        if ret != RTNCODE.OK:

            return None

        width = int(param.Width)
        height = int(param.Height)

        raw_data = ctypes.cast(
            raw_data_ptr,
            ctypes.POINTER(ctypes.c_ubyte)
        )

        # ======================================================
        # Mono8
        # ======================================================
        if param.pixformat == pfnc.PFNC_Mono8:

            buffer = ctypes.string_at(
                raw_data,
                width * height
            )

            image = np.frombuffer(
                buffer,
                dtype=np.uint8
            ).reshape(
                height,
                width
            )

            return image.copy()

        # ======================================================
        # Mono12
        # ======================================================
        elif param.pixformat == pfnc.PFNC_Mono12:

            image = self._mono12_to_numpy(
                raw_data,
                param.datasize,
                width,
                height
            )

            return image

        # ======================================================
        # Mono12p
        # ======================================================
        elif param.pixformat == pfnc.PFNC_Mono12p:

            image = self._mono12p_to_numpy(
                raw_data,
                param.datasize,
                width,
                height
            )

            return image

        # ======================================================
        # Mono14 / Mono16
        # ======================================================
        elif param.pixformat in (
            pfnc.PFNC_Mono14,
            pfnc.PFNC_Mono16
        ):

            buffer = ctypes.string_at(
                raw_data,
                width * height * 2
            )

            image = np.frombuffer(
                buffer,
                dtype=np.uint16
            ).reshape(
                height,
                width
            )

            return image.copy()

        # ======================================================
        # RGB8
        # ======================================================
        elif param.pixformat == pfnc.PFNC_RGB8:

            buffer = ctypes.string_at(
                raw_data,
                width * height * 3
            )

            image = np.frombuffer(
                buffer,
                dtype=np.uint8
            ).reshape(
                height,
                width,
                3
            )

            return image.copy()

        else:

            print(
                f"SSZN: 未知像素格式: "
                f"{param.pixformat}"
            )

            return None

    # ==========================================================
    # 17. Mono12 解码
    # ==========================================================
    def _mono12_to_numpy(
        self,
        raw_data,
        recvImageBytes,
        width,
        height
    ):

        validBytes = (
            recvImageBytes // 3
        ) * 3

        if validBytes <= 0:
            return None

        data = np.ctypeslib.as_array(
            raw_data,
            shape=(validBytes,)
        )

        data = data.reshape(
            (-1, 3)
        )

        b0 = data[:, 0].astype(
            np.uint16
        )

        b1 = data[:, 1].astype(
            np.uint16
        )

        b2 = data[:, 2].astype(
            np.uint16
        )

        p0 = (
            b0 |
            ((b1 & 0x0F) << 8)
        )

        p1 = (
            ((b1 & 0xF0) >> 4) |
            (b2 << 4)
        )

        # 转成 16bit 左对齐
        p0 = p0 << 4
        p1 = p1 << 4

        image = np.empty(
            validBytes // 3 * 2,
            dtype=np.uint16
        )

        image[0::2] = p0
        image[1::2] = p1

        return image[:width * height].reshape(
            height,
            width
        )

    # ==========================================================
    # 18. Mono12p 解码
    # ==========================================================
    def _mono12p_to_numpy(
        self,
        raw_data,
        recvImageBytes,
        width,
        height
    ):

        validBytes = (
            recvImageBytes // 3
        ) * 3

        if validBytes <= 0:
            return None

        data = np.ctypeslib.as_array(
            raw_data,
            shape=(validBytes,)
        )

        data = data.reshape(
            (-1, 3)
        )

        b0 = data[:, 0].astype(
            np.uint16
        )

        b1 = data[:, 1].astype(
            np.uint16
        )

        b2 = data[:, 2].astype(
            np.uint16
        )

        # Mono12p:
        # pixel0 = b0 + b1低4bit
        # pixel1 = b2 + b1高4bit
        p0 = (
            b0 |
            ((b1 & 0x0F) << 8)
        )

        p1 = (
            b2 |
            ((b1 & 0xF0) << 4)
        )

        image = np.empty(
            validBytes // 3 * 2,
            dtype=np.uint16
        )

        image[0::2] = p0
        image[1::2] = p1

        image = image[:width * height]

        return image.reshape(
            height,
            width
        )

    # ==========================================================
    # 19. 获取帧周期
    # ==========================================================
    def get_frame_period(self):

        if not self.m_deviceHandle:
            return 0.0

        fps = ctypes.c_double(0.0)

        ret = self.sl.dll.SLIF_GetFloat(
            self.m_deviceHandle,
            b"AcquisitionFrameRate",
            ctypes.byref(fps)
        )

        if ret == RTNCODE.OK and fps.value > 0:

            return 1.0 / fps.value

        return 0.0

    # ==========================================================
    # 20. 关闭相机
    # ==========================================================
    def close(self):
        """
        断开设备 (与 PE 示例 do_disconnect 一致):
          先停止取流 (SlParamMode → IDLE), 再关闭设备句柄。
        """

        # 停止采集
        if self.m_connect:

            try:
                self.stop_acquisition()
            except Exception:
                pass

        # 关闭设备
        if self.m_deviceHandle:

            try:
                self.sl.dll.SLIF_CloseDevice(
                    self.m_deviceHandle
                )
            except Exception:
                pass

        self.m_deviceHandle = None
        self.m_connect = False
        self.m_stream_active = False

        # 释放 SLStreamLink
        try:
            self.sl.uninit()
        except Exception:
            pass

        print(
            "SSZN: 相机已关闭"
        )