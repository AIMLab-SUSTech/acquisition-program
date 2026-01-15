import numpy as np
from pylablib.devices import uc480, DCAM
from abc import ABC, abstractmethod
import time
import os
import sys


class Camera(ABC):
    def __init__(self):
        super().__init__()

    @abstractmethod
    def set_ex_time(self, ex_time):
        """设置曝光时间, ex_time : S"""
        pass

    @abstractmethod
    def start_acquisition(self):
        """开始图像采集"""
        pass

    @abstractmethod
    def read_newest_image(self):
        """读取最新的图像"""
        pass

    @abstractmethod
    def get_frame_period(self):
        """获取帧率，返回：S"""
        pass


class IDS(Camera):
    def __init__(self):
        # self.cam = uc480.UC480Camera(backend='ueye')
        super().__init__()
        print((uc480.list_cameras(backend='ueye')))
        # print(uc480.UC480Camera.get_all_color_modes())
        cam_id = uc480.list_cameras(backend='ueye')[0][0]
        self.cam = uc480.UC480Camera(cam_id, backend='ueye')
        try:
            # 尝试设置为 16-bit
            self.cam.set_color_mode('mono16') 
            self._current_bit_depth = 16
        except:
            # 如果不支持，回退到 12-bit
            self.cam.set_color_mode('mono12')
            self._current_bit_depth = 12

    def set_pixel_rate(self, pixel_rate):
        try:
            self.cam.set_pixel_rate(pixel_rate)
        except Exception as e:
            print(f'设置pixel rate失败：{e}')

    def set_color_mode(self, color_mode):
        try:
            self.cam.set_color_mode(color_mode)
        except Exception as e:
            print(f'IDS设置颜色模式错误：{e}')

    def set_ex_time(self, ex_time):
        try:
            self.cam.set_exposure(ex_time)
        except Exception as e:
            print(f'IDS曝光时间设置失败：{e}')

    def snap(self):
        image = self.cam.snap()
        return image

    def start_acquisition(self):
        try:
            self.cam.start_acquisition()
        except Exception as e:
            print(f'IDS开始获取图像失败：{e}')

    def wait_for_frame(self, nframes=10):
        self.cam.wait_for_frame(nframes=nframes)

    def read_newest_image(self):
        try:
            image = self.cam.read_newest_image()
            if image is None:
                self.wait_for_frame(1)
                image = self.cam.read_newest_image()
            return image
        except Exception as e:
            print(f'IDS获取图像失败：{e}')


    def get_frame_period(self):
        return self.cam.get_frame_period()

    def get_bit_depth(self):
        return getattr(self, '_current_bit_depth', 8)
    

class Ham(Camera):
    def __init__(self):

        super().__init__()
        print(DCAM.get_cameras_number())
        try:
            self.cam = DCAM.DCAMCamera(idx=0)
        except Exception as e:
            print(e)

    def set_ex_time(self, ex_time):
        try:
            self.cam.set_exposure(ex_time)
        except Exception as e:
            print(f'IDS曝光时间设置失败：{e}')

    def snap(self):
        image = self.cam.snap()
        return image

    def start_acquisition(self):
        try:
            self.cam.start_acquisition()
        except Exception as e:
            print(f'IDS开始获取图像失败：{e}')

    def wait_for_frame(self, nframes=10):
        self.cam.wait_for_frame(nframes=nframes)

    def read_newest_image(self):
        try:
            image = self.cam.read_newest_image()
            if image is None:
                self.wait_for_frame(1)
                image = self.cam.read_newest_image()
                return image
            return image
        except Exception as e:
            print(f'Ham获取图像失败：{e}')

    def get_frame_period(self):
        return self.cam.get_frame_period()

    def get_bit_depth(self):
        try:
            # 尝试通过 DCAM 属性获取位深
            # 属性ID: DCAM_IDPROP_BITSPERCHANNEL = 0x00420010 (这取决于 pylablib/dcam 的封装)
            # 在 pylablib 中，通常可以直接访问 .get_attribute_value("bit_depth") 或类似
            
            # 如果是 pylablib.devices.DCAM
            # 常见属性名: 'bit_depth', 'bits_per_channel'
            val = self.cam.get_attribute_value("bit_depth")
            return int(val)
        except:
            # 大多数滨松科学相机 (Flash 4.0等) 默认为 16-bit
            return 16


class Basler(Camera):
    def __init__(self):
        super().__init__()
        global pylon
        from pypylon import pylon
        # 创建相机对象并连接到第一个可用的相机
        self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
        self.camera.Open()
        print(self.camera)

    def set_ex_time(self, exposure_time):
        """设置曝光时间，单位为微秒"""
        try:
            # 设置曝光时间
            self.camera.ExposureTime.Value = exposure_time * 1e6
            print(f"曝光时间设置为 {exposure_time * 1e3} 毫秒")
        except Exception as e:
            print(f"设置曝光时间失败: {e}")

    def start_acquisition(self):
        try:
            self.camera.StartGrabbing(pylon.GrabStrategy_LatestImages)
        except Exception as e:
            print(f"启动获取图像时发生错误: {e}")

    def read_newest_image(self):
        """获取一幅图像"""
        try:

            if self.camera.IsGrabbing():
                # 获取图像
                grab_result = self.camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
                # 获取图像数据（图像转换为NumPy数组）
                image = grab_result.Array
                # print(image.shape, np.unravel_index(np.argmax(image,keepdims=True),image.shape), np.mean(image),np.sort(np.unique(image))[-2],np.sort(np.unique(image))[-3])
                return image
            else:
                print("相机未准备好获取图像")
                return None

        except Exception as e:
            print(f"获取图像时发生错误: {e}")
            return None

    def set_frame_rate(self, frame_rate: float):
        """设置相机的帧率"""
        if self.camera:
            try:
                self.camera.AcquisitionFrameRate.Value = frame_rate
                print(f"帧率已设置为 {frame_rate} FPS")
            except Exception as e:
                print(f"设置帧率失败: {e}")
        else:
            print("相机未正确初始化，无法设置帧率")

    def get_frame_period(self) -> float:
        """获取当前相机的帧率"""
        if self.camera:
            try:
                frame_rate = 1 / self.camera.AcquisitionFrameRate.Value
                print(f"当前帧率为 {1 / frame_rate} FPS")
                return frame_rate
            except Exception as e:
                print(f"获取帧率失败: {e}")
                return -1
        else:
            print("相机未正确初始化，无法获取帧率")
            return -1

    def set_image_format(self, pixel_format: str):
        """设置相机的图像格式（如 Mono8、RGB8 等）"""
        if self.camera:
            try:
                self.camera.PixelFormat.Value = pixel_format
                print(f"图像格式已设置为 {pixel_format}")
            except Exception as e:
                print(f"设置图像格式失败: {e}")
        else:
            print("相机未正确初始化，无法设置图像格式")

    def get_image_format(self) -> str:
        """获取当前相机的图像格式"""
        if self.camera:
            try:
                pixel_format = self.camera.PixelFormat.Value
                print(f"当前图像格式为 {pixel_format}")
                return pixel_format
            except Exception as e:
                print(f"获取图像格式失败: {e}")
                return ""
        else:
            print("相机未正确初始化，无法获取图像格式")
            return ""

    def close(self):
        """关闭相机连接"""
        self.camera.StopGrabbing()
        self.camera.Close()
        print("相机已关闭")

    def get_bit_depth(self):
        try:
            # 获取 PixelFormat 字符串，例如 "Mono8", "Mono12", "Mono12Packed"
            pixel_format = self.camera.PixelFormat.Value
            
            if "8" in pixel_format:
                return 8
            elif "10" in pixel_format:
                return 10
            elif "12" in pixel_format:
                return 12
            elif "16" in pixel_format: # 虽然少见，有些相机支持 Mono16
                return 16
            
            return 8 # 默认值
            
        except Exception as e:
            print(f"Basler get_bit_depth error: {e}")
            return 8

class GalaxyCamera(Camera):
    def __init__(self):
        super().__init__()
        self.device_name = "Galaxy"
        self.cam = None
        
        # --- 1. 在这里尝试导入 (懒加载) ---
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            
            # 拼接出 gxipy 上一级文件夹的路径: .../dll/Galaxy
            # 注意：如果我们要 import gxipy，必须把 gxipy 的【父文件夹】加入路径
            lib_path = os.path.join(current_dir, "dll", "Galaxy")
            
            # 只有当路径不在系统路径里时才添加，防止重复添加
            if lib_path not in sys.path:
                sys.path.append(lib_path)
                # print(f"已添加库路径: {lib_path}")  # 调试用，确认路径对不对
                
            import gxipy as gx
            from gxipy import gxidef  # 显式导入 gxidef 模块
            from gxipy.ImageProc import Utility
            
            # --- 2. 关键步骤：把库绑定到 self 上 ---
            # 这样类的其他函数才能通过 self.gx, self.Utility 访问到它们
            self.gx = gx
            self.gxidef = gxidef
            self.Utility = Utility
            self.sdk_loaded = True
            
        except ImportError:
            print("警告: 未找到 gxipy 库，Galaxy相机不可用。")
            self.sdk_loaded = False
            return
        # -------------------------------------

        self.device_manager = self.gx.DeviceManager() # 使用 self.gx
        
        try:
            dev_num, dev_info_list = self.device_manager.update_all_device_list()
            if dev_num == 0:
                print("未发现 Galaxy 相机")
                return
            
            self.cam = self.device_manager.open_device_by_index(1)
            self.data_stream = self.cam.data_stream[0]
            self.feature_control = self.cam.get_remote_device_feature_control()
            self.image_convert = self.device_manager.create_image_format_convert()
            print(f"Galaxy 相机已初始化: {dev_info_list[0].get('model_name')}")
            
        except Exception as e:
            print(f"Galaxy 初始化失败: {e}")

    def set_ex_time(self, ex_time):
        if self.cam is None: return
        try:
            exposure_us = ex_time * 1e6
            float_feature = self.feature_control.get_float_feature("ExposureTime")
            range_info = float_feature.get_range()
            # print(f"调试信息 - 曝光参数范围: {range_info}")
            min_exposure = range_info['min']
            max_exposure = range_info['max']
            float_feature.set(max(min_exposure, min(exposure_us, max_exposure)))
        except Exception as e:
            print(f"Galaxy 设置曝光失败: {e}")

    def start_acquisition(self):
        if self.cam is None: return
        try:
            if self.feature_control.is_readable("TriggerMode"):
                self.feature_control.get_enum_feature("TriggerMode").set("Off")
            self.cam.stream_on()
        except Exception as e:
            print(f"Galaxy 开始采集失败: {e}")

    def stop_acquisition(self):
        if self.cam is None: return
        try:
            self.cam.stream_off()
        except Exception as e:
            print(f"Galaxy 停止采集失败: {e}")

    def read_newest_image(self):
        if self.cam is None: return None
        try:
            raw_image = self.data_stream.get_image(timeout=1000)
            if raw_image is None: return None

            # --- 3. 调用时要用 self.gxidef 和 self.Utility ---
            # 注意：这里不能直接写 GxFrameStatusList，要写 self.gxidef.GxFrameStatusList
            if raw_image.get_status() == self.gxidef.GxFrameStatusList.SUCCESS:
                pixel_format = raw_image.get_pixel_format()
                
                # 使用 self.Utility
                if self.Utility.is_gray(pixel_format):
                    numpy_image = raw_image.get_numpy_array()
                    if numpy_image is None:
                        # 使用 self.gxidef
                        self.image_convert.set_dest_format(self.gxidef.GxPixelFormatEntry.MONO8)
                        output_image = self.image_convert.convert(raw_image)[0]
                        numpy_image = np.frombuffer(output_image, dtype=np.ubyte).reshape(raw_image.get_height(), raw_image.get_width())
                else:
                    self.image_convert.set_dest_format(self.gxidef.GxPixelFormatEntry.RGB8)
                    output_image = self.image_convert.convert(raw_image)[0]
                    numpy_image = np.frombuffer(output_image, dtype=np.ubyte).reshape(raw_image.get_height(), raw_image.get_width(), 3)
                
                return numpy_image
            return None
        except Exception as e:
            print(f"Galaxy 获取图像失败: {e}")
            return None

    def get_frame_period(self):
        if self.cam is None: return 0
        try:
            current_fps = self.feature_control.get_float_feature("AcquisitionFrameRate").get()
            return 1.0 / current_fps if current_fps > 0 else 0.0
        except:
            return 0.0

    def get_bit_depth(self):
        if self.cam is None: return 8
        try:
            pixel_format_str = self.feature_control.get_enum_feature("PixelFormat").get()[1]
            if "8" in pixel_format_str: return 8
            elif "10" in pixel_format_str: return 10
            elif "12" in pixel_format_str: return 12
            elif "16" in pixel_format_str: return 16
            return 8
        except:
            return 8
    
    def set_trigger_mode(self, mode):
        """
        设置触发模式
        mode: 'continuous' (连续/内部触发) 或 'software' (软触发)
        """
        if self.cam is None: return
        try:
            # 必须先停止采集才能改 TriggerMode (部分相机要求)
            self.cam.stream_off()
            
            trigger_mode_feature = self.feature_control.get_enum_feature("TriggerMode")
            
            if mode == 'software':
                # 1. 开启触发模式
                trigger_mode_feature.set("On")
                # 2. 设置源为软触发 (Line1是硬触发, Software是软触发)
                # 注意：USB2.0相机可能不需要设Source或者Source不同，这里按标准GEV/U3V写
                if self.feature_control.is_implemented("TriggerSource"):
                    self.feature_control.get_enum_feature("TriggerSource").set("Software")
                print("Galaxy: 已切换到 [软触发] 模式")
            else:
                # 连续模式：关闭触发，相机自动跑
                trigger_mode_feature.set("Off")
                print("Galaxy: 已切换到 [连续] 模式")
                
            # 改完参数后重新开始流
            self.cam.stream_on()
            
        except Exception as e:
            print(f"设置触发模式失败: {e}")

    def trigger(self):
        """发送一次软触发指令"""
        if self.cam is None: return
        try:
            # 发送 TriggerSoftware 命令
            cmd = self.feature_control.get_command_feature("TriggerSoftware")
            cmd.send_command()
        except Exception as e:
            print(f"软触发指令发送失败: {e}")

    def close(self):
        if self.cam is not None:
            try:
                self.cam.stream_off()
                self.cam.close_device()
            except:
                pass
            self.cam = None

    def __del__(self):
        self.close()

if __name__ == '__main__':
    # camera = Camera()
    # camera.set_paramerters()

    cam = GalaxyCamera()

    cam.start_acquisition()
    cam.set_ex_time(5/1000)
    time.sleep(1)
    print(cam.read_newest_image())
    print(cam.get_frame_period())
    # cam.close()
    # cam.cam.set_exposure(0.022)
    # cam.set_pixel_rate(160000000)
    # print(cam.cam.get_pixel_rate())
    # # cam.cam.set_trigger_mode('int')
    # # cam.cam.set_frame_period(0.1)
    # print(cam.cam.get_detector_size())
    # cam.start_acquisition()

    # print(cam.cam.acquisition_in_progress())
    # cam.wait_for_frame(nframes=10)
    # print(cam.cam.get_frame_timings())
    # image = cam.read_newest_image()
    # print(image.dtype)
    # image = Image.fromarray(image)
    # image.show()
    # image.save('./test.png')

    # # print(len(image))
    # cam.cam.close()
