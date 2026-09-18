# -*- coding: utf-8 -*-
import os
import sys
import time
from ctypes import *

import numpy as np

# 导入基类
from camera import Camera

# SCSDK Python 绑定与当前文件位于同一目录。
_SDK_DIR = os.path.dirname(os.path.abspath(__file__))
if _SDK_DIR not in sys.path:
    sys.path.insert(0, _SDK_DIR)

# python/SCSDK/scsdk.py 依赖环境变量 Revealer_Scientific_Camera_SDK_HOME
if os.getenv('Revealer_Scientific_Camera_SDK_HOME') is None:
    raise RuntimeError(
        "缺少环境变量 Revealer_Scientific_Camera_SDK_HOME，"
        "请指向 Revealer Scientific Camera SDK 安装目录后再运行"
    )

from scsdk import SCSDK
from SCDefines import (
    SC_OK,
    SC_ECreateHandleMode,
    SC_EInterfaceType,
    SC_EFeatureType,
    SC_EVideoType,
    SC_DeviceList,
    SC_Frame,
    SC_String,
    SC_EnumEntryList,
    SC_EnumEntryInfo,
    SC_RecordParam,
    SCLogLevel,
    FrameInfoCallBack,
)


def _enum_devices(interface_type=SC_EInterfaceType.eInterfaceTypeAll.value):
    """枚举相机设备，返回设备信息列表"""
    device_list = SC_DeviceList()
    device_list.devNum = 0
    device_list.pDevInfo = None

    cti_path = ''
    cti_path = cti_path.encode('utf-8') if cti_path else None
    n_ret = SCSDK.SC_EnumDevices(device_list, interface_type, cti_path)
    if n_ret != SC_OK or device_list.devNum == 0:
        return []

    devices = []
    for i in range(device_list.devNum):
        info = device_list.pDevInfo[i]
        devices.append({
            'vendor': info.vendorName.decode('utf-8'),
            'model': info.modelName.decode('utf-8'),
            'serial': info.serialNumber.decode('utf-8'),
            'name': info.cameraName.decode('utf-8'),
            'cti': info.ctiPath.decode('utf-8'),
        })
    return devices


def _frame_to_numpy(frame):
    """将 SC_Frame 底层内存转换为 numpy 数组（调用前必须持有 frame）"""
    frame_info = frame.frameInfo
    width = frame_info.width
    height = frame_info.height
    size = frame_info.size
    p_data = frame.pData

    if not p_data or width == 0 or height == 0:
        return None

    total_pixels = width * height
    bytes_per_pix = size // total_pixels if total_pixels > 0 else 2

    if bytes_per_pix == 1:
        img_data = np.ctypeslib.as_array(
            cast(p_data, POINTER(c_uint8 * size)).contents
        ).copy()
    else:
        pixel_count = size // 2
        img_data = np.ctypeslib.as_array(
            cast(p_data, POINTER(c_uint16 * pixel_count)).contents
        ).copy()
    return img_data.reshape((height, width))


_sdk_initialized = False
_enum_cache = {}


def _sdk_init(log_path: str = 'RevealerLog'):
    """初始化 SDK（同一进程内仅生效一次，重复调用无副作用）"""
    global _sdk_initialized
    if _sdk_initialized:
        return
    SCSDK.SC_Init(SCLogLevel.Info.value, log_path, 10485760, 5)
    _sdk_initialized = True


def _list_devices(interface_type: int = SC_EInterfaceType.eInterfaceTypeAll.value):
    """
    枚举相机（同一进程内按接口类型缓存）
    SDK 每重复调用一次 SC_EnumDevices 会多挂一个 GenTL 系统，
    退出时每个多余系统都会报 "program is already running"，故仅枚举一次
    """
    if interface_type not in _enum_cache:
        _sdk_init()
        _enum_cache[interface_type] = _enum_devices(interface_type)
    return _enum_cache[interface_type]


def find_camera_index(prefer_real: bool = True) -> int:
    """
    返回建议的相机索引
    prefer_real 为 True 时跳过虚拟/模拟相机 (vendor/model 含 SIMULATION)，
    找不到真实相机时返回 -1（而不是回退到虚拟相机）
    """
    devices = _list_devices()
    if len(devices) == 0:
        return -1
    if prefer_real:
        for i, d in enumerate(devices):
            if 'SIMULATION' not in (d['vendor'] + d['model']).upper():
                return i
        return -1
    return 0


class SCSDKCamera(Camera):
    """
    Revealer SCSDK 科学相机封装类
    基于 python 文件夹内的 SCSDK 绑定打包，继承自 Camera 基类
    """

    def __init__(self, camera_index: int = 0,
                 interface_type: int = SC_EInterfaceType.eInterfaceTypeAll.value,
                 log_path: str = 'RevealerLog',
                 buffer_count: int = 10,
                 bit_depth: int = 16):
        super().__init__()
        self.camera_index = camera_index
        self.sdk = None
        self.is_open = False
        self.is_grabbing = False
        self._frame_callback_ref = None
        self._current_bit_depth = None

        # 1. 初始化 SDK（同一进程内仅生效一次）
        self.sdk = SCSDK()
        _sdk_init(log_path)

        # 2. 枚举设备（进程内缓存，避免重复枚举）
        devices = _list_devices(interface_type)
        if len(devices) == 0:
            raise RuntimeError("未发现 Revealer SCSDK 相机，请检查连接")
        for i, d in enumerate(devices):
            print(f"[{i}] {d['vendor']} {d['model']} SN:{d['serial']}")

        if camera_index >= len(devices):
            raise ValueError(
                f"相机索引越界: 发现 {len(devices)} 台相机，请求索引为 {camera_index}"
            )

        # 3. 创建设备句柄
        n_ret = self.sdk.SC_CreateHandle(
            SC_ECreateHandleMode.eModeByIndex,
            byref(c_void_p(camera_index))
        )
        if n_ret != SC_OK:
            raise RuntimeError(f"创建相机句柄失败，错误码: {n_ret}")

        # 4. 打开设备
        n_ret = self.sdk.SC_Open()
        if n_ret != SC_OK:
            raise RuntimeError(f"打开相机失败，错误码: {n_ret}")
        self.is_open = True

        # 设置内部帧缓存大小
        self.sdk.SC_SetBufferCount(buffer_count)

        # 相机固件默认 12bit，默认切换为 16bit 模式
        self.set_bit_depth(bit_depth)

        self.get_bit_depth()
        print(f"SCSDK 相机已初始化 (Index: {camera_index}, 位深: {self.get_bit_depth()}bit)")

    # ========================== 核心抽象方法实现 ==========================

    def set_ex_time(self, ex_time: float):
        """
        设置曝光时间
        :param ex_time: 曝光时间，单位：秒 (S)
        """
        if not self.is_open:
            return
        try:
            exposure_us = float(ex_time * 1e6)

            min_val = c_double(0)
            max_val = c_double(0)
            self.sdk.SC_GetFloatFeatureMin("ExposureTime", min_val)
            self.sdk.SC_GetFloatFeatureMax("ExposureTime", max_val)

            if max_val.value > 0:
                target_us = max(min_val.value, min(exposure_us, max_val.value))
            else:
                target_us = exposure_us

            n_ret = self.sdk.SC_SetFloatFeatureValue("ExposureTime", target_us)
            if n_ret != SC_OK:
                print(f"SCSDK 设置曝光时间失败，错误码: {n_ret}")
        except Exception as e:
            print(f"SCSDK 设置曝光异常: {e}")

    def get_ex_time(self) -> float:
        """获取当前曝光时间，单位：秒 (S)"""
        if not self.is_open:
            return 0.0
        try:
            value = c_double(0)
            n_ret = self.sdk.SC_GetFloatFeatureValue("ExposureTime", value)
            if n_ret == SC_OK:
                return value.value / 1e6
            return 0.0
        except Exception:
            return 0.0

    def start_acquisition(self):
        """开始图像流采集"""
        if not self.is_open or self.is_grabbing:
            return
        try:
            n_ret = self.sdk.SC_StartGrabbing()
            if n_ret == SC_OK:
                self.is_grabbing = True
                print("SCSDK 相机开始采集流...")
            else:
                print(f"SCSDK 开始采集失败，错误码: {n_ret}")
        except Exception as e:
            print(f"SCSDK 启动采集异常: {e}")

    def stop_acquisition(self):
        """停止图像流采集"""
        if self.is_open and self.is_grabbing:
            try:
                self.sdk.SC_StopGrabbing()
            except Exception:
                pass
            self.is_grabbing = False

    def read_newest_image(self, timeout_ms: int = 1000):
        """
        读取最新一帧图像
        :param timeout_ms: 超时时间（毫秒）
        :return: 2D numpy 图像数组 (uint8 或 uint16)，失败返回 None
        """
        if not self.is_open:
            return None

        if not self.is_grabbing:
            self.start_acquisition()

        frame = SC_Frame()
        try:
            n_ret = self.sdk.SC_GetFrame(frame, timeout_ms)
            if n_ret != SC_OK:
                return None

            image = _frame_to_numpy(frame)
            self.sdk.SC_ReleaseFrame(frame)
            return image
        except Exception as e:
            try:
                self.sdk.SC_ReleaseFrame(frame)
            except Exception:
                pass
            print(f"SCSDK 获取图像异常: {e}")
            return None

    def get_frame_period(self) -> float:
        """
        获取当前帧周期
        :return: 周期时间，单位：秒 (S)
        """
        if not self.is_open:
            return 0.0
        try:
            fps_val = c_double(0.0)
            n_ret = self.sdk.SC_GetFloatFeatureValue("AcquisitionFrameRate", fps_val)
            if n_ret == SC_OK and fps_val.value > 0:
                return 1.0 / fps_val.value
            return 0.0
        except Exception:
            return 0.0

    # ========================== 扩展属性与控制方法 ==========================

    def snap(self):
        """拍摄单帧图像"""
        was_grabbing = self.is_grabbing
        if not was_grabbing:
            self.start_acquisition()
        image = self.read_newest_image()
        if not was_grabbing:
            self.stop_acquisition()
        return image

    def set_frame_rate(self, frame_rate: float):
        """设置相机帧率 (FPS)"""
        if not self.is_open:
            return
        try:
            n_ret = self.sdk.SC_SetFloatFeatureValue("AcquisitionFrameRate", float(frame_rate))
            if n_ret == SC_OK:
                print(f"帧率已设置为: {frame_rate} FPS")
            else:
                print(f"设置帧率失败，错误码: {n_ret}")
        except Exception as e:
            print(f"设置帧率异常: {e}")

    def set_trigger_mode(self, mode: str):
        """
        设置触发模式
        mode: 'software' (软触发, TriggerInType=Software_Trigger) 或 'continuous' (连续)
        注意: 软触发模式下 TriggerSoftware 命令节点才可用
        """
        if not self.is_open:
            return
        try:
            was_grabbing = self.is_grabbing
            if was_grabbing:
                self.stop_acquisition()

            if mode == 'software':
                # 软触发：TriggerInType 设为软件触发 (参考 SoftwareTrigger 示例)
                value = c_uint64(5)
                n_ret = self.sdk.SC_SetEnumFeatureValue('TriggerInType', value.value)
                if n_ret != SC_OK:
                    print(f"设置软触发失败，错误码: {n_ret}")
                    return
                print("SCSDK: 已切换到 [软触发] 模式")
            else:
                value = c_uint64(0)
                n_ret = self.sdk.SC_SetEnumFeatureValue('TriggerInType', value.value)
                if n_ret != SC_OK:
                    print(f"设置连续模式失败，错误码: {n_ret}")
                    return
                print("SCSDK: 已切换到 [连续] 模式")

            if was_grabbing:
                self.start_acquisition()
        except Exception as e:
            print(f"设置触发模式异常: {e}")

    def trigger(self):
        """
        发送一次软触发指令 (需先 set_trigger_mode('software'))
        注意: 采集流刚启动时的首次触发可能被丢弃，待流稳定(约1s)后一次触发出一帧
        """
        if not self.is_open:
            return
        try:
            n_ret = self.sdk.SC_ExecuteCommandFeature("TriggerSoftware")
            if n_ret != SC_OK:
                print(f"软触发指令发送失败，错误码: {n_ret}")
        except Exception as e:
            print(f"软触发异常: {e}")

    def set_roi(self, width: int, height: int, offset_x: int = 0, offset_y: int = 0):
        """设置感光区域 (ROI)"""
        if not self.is_open:
            return
        try:
            was_grabbing = self.is_grabbing
            if was_grabbing:
                self.stop_acquisition()

            n_ret = self.sdk.SC_SetROI(width, height, offset_x, offset_y)
            if n_ret == SC_OK:
                print(f"ROI 设置成功: {width}x{height} (Offset: {offset_x}, {offset_y})")
            else:
                print(f"设置 ROI 失败，错误码: {n_ret}")

            if was_grabbing:
                self.start_acquisition()
        except Exception as e:
            print(f"设置 ROI 异常: {e}")

    def get_bit_depth(self) -> int:
        """获取当前相机位深"""
        if not self.is_open:
            return self._current_bit_depth
        try:
            symbol_str = SC_String()
            n_ret = self.sdk.SC_GetEnumFeatureSymbol("PixelFormat", symbol_str)
            if n_ret == SC_OK:
                fmt_name = symbol_str.str.decode("utf-8")
                if "8" in fmt_name:
                    self._current_bit_depth = 8
                elif "10" in fmt_name:
                    self._current_bit_depth = 10
                elif "12" in fmt_name:
                    self._current_bit_depth = 12
                elif "16" in fmt_name:
                    self._current_bit_depth = 16
            return self._current_bit_depth
        except Exception:
            return self._current_bit_depth

    def set_bit_depth(self, bit_depth: int):
        """设置位深 (如 8, 12, 16)"""
        if not self.is_open:
            return
        try:
            target_symbol = f"Mono{bit_depth}"
            n_ret = self.sdk.SC_SetEnumFeatureSymbol("PixelFormat", target_symbol)
            if n_ret == SC_OK:
                self._current_bit_depth = bit_depth
                print(f"位深已设置为: {bit_depth}")
            else:
                print(f"设置位深失败，错误码: {n_ret}")
        except Exception as e:
            print(f"设置位深异常: {e}")

    # ========================== 通用 Feature 读写 ==========================

    def get_feature(self, name: str):
        """
        按 GenICam 节点类型自动读取 Feature 值
        :return: 读取值，失败返回 None
        """
        if not self.is_open:
            return None
        try:
            type_value = c_uint32(0)
            if not self.sdk.SC_GetFeatureType(name, type_value):
                return None

            t = type_value.value
            if t == SC_EFeatureType.eFeatureInt.value:
                value = c_int64(0)
                if self.sdk.SC_GetIntFeatureValue(name, value) == SC_OK:
                    return value.value
            elif t == SC_EFeatureType.eFeatureFloat.value:
                value = c_double(0)
                if self.sdk.SC_GetFloatFeatureValue(name, value) == SC_OK:
                    return value.value
            elif t == SC_EFeatureType.eFeatureBool.value:
                value = c_bool(False)
                if self.sdk.SC_GetBoolFeatureValue(name, value) == SC_OK:
                    return value.value
            elif t == SC_EFeatureType.eFeatureEnum.value:
                symbol = SC_String()
                if self.sdk.SC_GetEnumFeatureSymbol(name, symbol) == SC_OK:
                    return symbol.str.decode("utf-8")
                value = c_uint64(0)
                if self.sdk.SC_GetEnumFeatureValue(name, value) == SC_OK:
                    return value.value
            elif t == SC_EFeatureType.eFeatureString.value:
                value_str = SC_String()
                if self.sdk.SC_GetStringFeatureValue(name, value_str) == SC_OK:
                    return value_str.str.decode("utf-8")
            return None
        except Exception as e:
            print(f"读取 Feature [{name}] 异常: {e}")
            return None

    def set_feature(self, name: str, value) -> bool:
        """
        按 GenICam 节点类型自动写入 Feature 值
        """
        if not self.is_open:
            return False
        try:
            if isinstance(value, bool):
                n_ret = self.sdk.SC_SetBoolFeatureValue(name, value)
            elif isinstance(value, int):
                n_ret = self.sdk.SC_SetIntFeatureValue(name, value)
            elif isinstance(value, float):
                n_ret = self.sdk.SC_SetFloatFeatureValue(name, value)
            elif isinstance(value, str):
                n_ret = self.sdk.SC_SetEnumFeatureSymbol(name, value)
            else:
                print(f"不支持的 Feature 值类型: {type(value)}")
                return False
            return n_ret == SC_OK
        except Exception as e:
            print(f"写入 Feature [{name}] 异常: {e}")
            return False

    def get_enum_entries(self, name: str) -> list:
        """获取枚举 Feature 的可选值列表 [(value, name), ...]"""
        if not self.is_open:
            return []
        try:
            entry_num = c_uint32(0)
            if self.sdk.SC_GetEnumFeatureEntryNum(name, entry_num) != SC_OK:
                return []
            buffer = (SC_EnumEntryInfo * entry_num.value)()
            enum_entry_list = SC_EnumEntryList()
            enum_entry_list.nEnumEntryBufferSize = entry_num.value
            enum_entry_list.pEnumEntryInfo = cast(buffer, POINTER(SC_EnumEntryInfo))
            if self.sdk.SC_GetEnumFeatureEntrys(name, enum_entry_list) != SC_OK:
                return []
            return [
                (buffer[i].value, buffer[i].name.decode('utf-8'))
                for i in range(entry_num.value)
            ]
        except Exception as e:
            print(f"读取枚举列表 [{name}] 异常: {e}")
            return []

    # ========================== 异步回调采集 ==========================

    def attach_frame_callback(self, callback):
        """
        注册帧数据回调（异步采集模式）
        :param callback: 函数 callback(p_frame, p_user)，p_frame 为 POINTER(SC_Frame)
        """
        if not self.is_open:
            return False
        try:
            # 保持回调对象存活，避免被 Python GC 后 C 侧仍调用
            self._frame_callback_ref = FrameInfoCallBack(callback)
            n_ret = self.sdk.SC_AttachGrabbing(self._frame_callback_ref, None)
            return n_ret == SC_OK
        except Exception as e:
            print(f"注册帧回调异常: {e}")
            return False

    # ========================== 录像/导出 ==========================

    def open_record(self, count: int = 10, folder: str = 'export',
                    file_name: str = 'test',
                    video_type: int = SC_EVideoType.eTypeVideoFormatTIFF) -> bool:
        """
        打开录像（从当前采集流记录 count 帧）
        """
        if not self.is_open:
            return False
        try:
            record_param = SC_RecordParam()
            record_param.startFrame = 0
            record_param.count = count
            record_param.recordFormat = video_type
            record_param.recordFilePath = folder.encode('utf-8')
            record_param.fileName = file_name.encode('utf-8')
            record_param.reserved = (c_uint * 5)(0, 0, 0, 0, 0)

            n_ret = self.sdk.SC_OpenRecord(record_param)
            return n_ret == SC_OK
        except Exception as e:
            print(f"打开录像异常: {e}")
            return False

    def close_record(self):
        """关闭录像"""
        if not self.is_open:
            return
        try:
            self.sdk.SC_CloseRecord()
        except Exception:
            pass

    # ========================== 生命周期 ==========================

    def close(self):
        """释放并关闭相机"""
        if self.is_open:
            try:
                self.stop_acquisition()
                self.sdk.SC_Close()
                self.sdk.SC_DestroyHandle()
            except Exception:
                pass
            self.is_open = False
            print("SCSDK 相机已关闭")

    def __del__(self):
        self.close()


if __name__ == "__main__":
    # 自动选择第一台真实相机（跳过虚拟/模拟相机）
    index = find_camera_index()
    if index < 0:
        raise RuntimeError("未发现可用相机")

    # 实例化相机
    cam = SCSDKCamera(camera_index=index)

    # 1. 设置曝光时间为 20 毫秒 (0.02 秒) 并读回验证
    cam.set_ex_time(0.02)
    print(f"曝光时间设置 0.02s，读回: {cam.get_ex_time():.6f} s")

    # 2. 启动采集流
    cam.start_acquisition()
    time.sleep(0.5)

    # 3. 读取最新一帧并查看属性
    img = cam.read_newest_image()
    if img is not None:
        print(f"获取图像成功: 形状={img.shape}, 类型={img.dtype}, "
              f"最大值={img.max()}, 均值={img.mean():.2f}")
    else:
        print("获取图像失败")

    # 4. 获取帧周期
    frame_period = cam.get_frame_period()
    print(f"当前帧周期: {frame_period:.4f} s "
          f"(约 {1.0 / frame_period if frame_period > 0 else 0:.1f} FPS)")

    # 5. 位深
    print(f"当前位深: {cam.get_bit_depth()} bit")

    # 6. 关闭相机
    cam.close()
