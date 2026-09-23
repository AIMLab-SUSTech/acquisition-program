import numpy as np
from abc import ABC, abstractmethod
import time
import os
import sys


_PCO_DLL_DIRECTORY_HANDLES = []


def _configure_pco_sc2_dll(pylablib):
    """Locate the SC2 SDK installed with recent pco.camware releases."""
    configured = os.getenv("PCO_SC2_DLL")
    candidates = []
    if configured:
        candidates.append(configured)

    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        program_files = os.getenv(env_name)
        if not program_files:
            continue
        toolbox = os.path.join(program_files, "PCO Digital Camera Toolbox")
        candidates.extend(
            [
                os.path.join(toolbox, "pco.camware"),
                os.path.join(toolbox, "pco.sdk", "bin64"),
                os.path.join(toolbox, "pco.sdk", "bin"),
            ]
        )

    for candidate in candidates:
        dll_path = candidate if candidate.lower().endswith(".dll") else os.path.join(candidate, "SC2_Cam.dll")
        if not os.path.isfile(dll_path):
            continue

        dll_dir = os.path.dirname(dll_path)
        pylablib.par["devices/dlls/pco_sc2"] = dll_dir
        if os.name == "nt" and hasattr(os, "add_dll_directory"):
            _PCO_DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(dll_dir))
        return dll_path

    return None


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
        from pylablib.devices import uc480

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
        from pylablib.devices import DCAM

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

class PCOCamera(Camera):
    def __init__(self):
        import pylablib

        _configure_pco_sc2_dll(pylablib)
        from pylablib.devices import PCO

        try:
            self.cam = PCO.PCOSC2Camera()  # 初始化PCO相机
            print("成功连接到PCO相机")
        except Exception as e:
            self.cam = None
            raise RuntimeError(f"PCO相机连接失败: {e}") from e

    def set_ex_time(self, ex_time):
        """设置曝光时间（单位：秒）"""
        if self.cam is None:
            return
        try:
            # self.cam.stop_acquisition()
            self.cam.set_exposure(ex_time)
            # self.cam.stop_acquisition()
        except Exception as e:
            print(f'PCO曝光时间设置失败：{e}')
    
    def get_ex_time(self):
        try:
            ex_time = self.cam.get_exposure()
            if ex_time is not None:
                return ex_time
        except Exception as e:
            print(f'PCO曝光时间读取失败：{e}')
        
    def snap(self):
        """拍摄单帧"""
        if self.cam is None:
            return None
        return self.cam.snap()

    def start_acquisition(self):
        """开始连续采集"""
        if self.cam is None:
            return
        try:
            self.cam.start_acquisition()
        except Exception as e:
            print(f'PCO开始采集失败：{e}')
    
    def stop_acquistion(self):
        try:
            self.cam.stop_acquisition()
        except Exception as e:
            print(f'PCO停止采集失败：{e}')

    def wait_for_frame(self, nframes=1):
        """等待指定帧数就绪"""
        if self.cam is None:
            return
        self.cam.wait_for_frame(nframes=nframes)

    def read_newest_image(self):
        """获取最新帧图像"""
        if self.cam is None:
            return None
        try:
            image = self.cam.read_newest_image()
            if image is None:
                self.wait_for_frame(1)
                image = self.cam.read_newest_image()
            return image
        except Exception as e:
            print(f'PCO获取图像失败：{e}')
            return None

    def get_frame_period(self):
        """获取帧周期（单位：秒）"""
        if self.cam is None:
            return 0
        return self.cam.get_frame_period()

    def close(self):
        """关闭相机连接"""
        if self.cam is not None:
            self.cam.close()

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
