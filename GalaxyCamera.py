import sys
import os
import time
import numpy as np

# =========================================================================
# 1. 路径修复 (保持不变，这部分是好的)
# =========================================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
sdk_root = os.path.join(current_dir, "dll", "Galaxy")

if sdk_root not in sys.path:
    sys.path.append(sdk_root)

if hasattr(os, 'add_dll_directory'):
    if os.path.exists(sdk_root):
        os.add_dll_directory(sdk_root)
else:
    os.environ['PATH'] = sdk_root + os.pathsep + os.environ['PATH']

# 导入 SDK
try:
    import gxipy as gx
    from gxipy.gxidef import *
    from gxipy.ImageProc import Utility
except ImportError as e:
    print(f"❌ 无法导入 gxipy: {e}")
    raise e

# =========================================================================
# 2. 相机类 (移除了报错的 get_device_class)
# =========================================================================
class GalaxyCamera:
    def __init__(self):
        self.dm = gx.DeviceManager()
        self.cam = None
        self.data_stream = None
        self.is_open = False
        
        # 1. 枚举设备
        dev_num, dev_info_list = self.dm.update_all_device_list()
        if dev_num == 0:
            raise RuntimeError("未发现 Galaxy 相机，请检查连接！")
        
        # 2. 打开第一台相机
        try:
            # 这里的 index 是从 1 开始的
            self.cam = self.dm.open_device_by_index(1)
            
            # 获取流通道
            if self.cam.data_stream:
                self.data_stream = self.cam.data_stream[0]
            else:
                raise RuntimeError("无法获取数据流通道")
            
            # --- 【修正点】移除了 get_device_class 的判断 ---
            # USB 相机不需要设置 GevSCPSPacketSize，直接跳过即可。
            
            # 准备图像格式转换工具
            self.image_convert = self.dm.create_image_format_convert()
            
            self.is_open = True
            self.set_bit_depth(12)
            print(f"✅ Galaxy 相机已初始化")
            
        except Exception as e:
            print(f"❌ 打开相机失败: {e}")
            raise e

    def start_acquisition(self):
        """开始采集"""
        if self.cam and self.is_open:
            try:
                # 设置为连续采集模式
                self.cam.TriggerMode.set(gx.GxSwitchEntry.OFF)
                self.cam.stream_on()
                print("相机开始采集流...")
            except Exception as e:
                print(f"开始采集失败: {e}")

    def stop_acquisition(self):
        """停止采集"""
        if self.cam and self.is_open:
            try:
                self.cam.stream_off()
            except:
                pass

    def set_ex_time(self, exposure_time_sec):
        """设置曝光时间 (输入单位: 秒)"""
        if not self.cam: return
        try:
            # 秒 -> 微秒
            exposure_us = exposure_time_sec * 1_000_000.0
            
            # 获取当前支持的范围 (字典形式)
            exp_range = self.cam.ExposureTime.get_range()
            min_v = exp_range['min']
            max_v = exp_range['max']
            
            target_val = max(min_v, min(exposure_us, max_v))
            self.cam.ExposureTime.set(target_val)
            
        except Exception as e:
            print(f"设置曝光失败: {e}")

    def get_bit_depth(self):
        # 1. 获取 FeatureControl 对象 (基于 FeatureControl.py)
        remote_device_feature = self.cam.get_remote_device_feature_control()
        
        # 2. 获取 "PixelFormat" 枚举特征对象 (基于 FeatureControl.py 的 get_enum_feature)
        pixel_format_feature = remote_device_feature.get_enum_feature("PixelFormat")
        
        # 3. 读取当前值 (基于 Feature_s.py 中 EnumFeature_s.get 方法)
        # 返回值通常是 tuple: (int_value, str_symbol)
        _, pixel_format_str = pixel_format_feature.get()
        
        # 4. 解析字符串获取位深
        if "8" in pixel_format_str:
            return 8
        elif "10" in pixel_format_str:
            return 10
        elif "12" in pixel_format_str:
            return 12
        elif "16" in pixel_format_str:
            return 16
        return 8

    def set_bit_depth(self, bit_depth):
        # 1. 获取控制对象
        remote_device_feature = self.cam.get_remote_device_feature_control()
        pixel_format_feature = remote_device_feature.get_enum_feature("PixelFormat")
        
        # 2. 构造目标格式字符串 (假设是黑白相机)
        target_format = f"Mono{bit_depth}" # 例如 "Mono8", "Mono12"
        
        # 3. 检查相机是否支持该格式 (基于 Feature_s.py 的 get_range 获取支持列表)
        # get_range 返回一个字典或列表，包含支持的枚举值
        supported_formats = pixel_format_feature.get_range()
        
        # 这里的 supported_formats 结构取决于 Feature_s.py 的具体实现
        # 在 Feature_s.py 中，get_range 返回一个包含字典的列表 [{'value':..., 'symbolic':...}, ...]
        is_supported = False
        for item in supported_formats:
            if item['symbolic'] == target_format:
                is_supported = True
                break
                
        if is_supported:
            # 4. 设置位深 (基于 Feature_s.py 中 EnumFeature_s.set 方法)
            pixel_format_feature.set(target_format)
            print(f"位深已设置为: {bit_depth} (Format: {target_format})")
        else:
            print(f"不支持设置位深: {bit_depth}")

    def read_newest_image(self):
        """获取最新一帧 (返回 numpy 数组)"""
        if not self.data_stream: return None
        
        try:
            # 获取图像 (超时 1000ms)
            raw_image = self.data_stream.get_image(timeout=1000)
            
            if raw_image is None or raw_image.get_status() != gx.GxFrameStatusList.SUCCESS:
                return None

            # 获取 Numpy 数组
            numpy_image = raw_image.get_numpy_array()
            if numpy_image is None: return None

            # 如果是二维数组(黑白)，直接返回
            if numpy_image.ndim == 2:
                return numpy_image
            
            # 如果是三维数组(彩色)或其他格式，转为 Mono8
            # event1.py 需要二维数组才能正常显示
            self.image_convert.set_dest_format(gx.GxPixelFormatEntry.MONO8)
            output_img = self.image_convert.convert(raw_image)[0]
            # 重新 reshape
            return np.frombuffer(output_img, dtype=np.ubyte).reshape(raw_image.get_height(), raw_image.get_width())

        except Exception as e:
            # print(f"获取图像异常: {e}") # 避免刷屏
            return None

    def close_device(self):
        """关闭资源"""
        if self.cam:
            try:
                self.cam.stream_off()
                self.cam.close_device()
            except:
                pass
        self.is_open = False

    def __del__(self):
        self.close_device()