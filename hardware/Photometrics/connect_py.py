import threading
import time
from abc import ABC
import numpy as np
from abc import ABC, abstractmethod

# 需要安装 pyvcam： pip install PyVCAM
from pyvcam import pvc
from pyvcam.camera import Camera as PyVcamCamera
# from camera import Camera

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

class PyVCAM(Camera):
    def __init__(self, cam_name: str = None, default_ex_time_s: float = 0.02):
        """
        cam_name: 可选，相机的名字（如 'PMUSBCam00'），不指定则使用detect第一个相机
        default_ex_time_s: 默认曝光（秒）
        """
        super().__init__()
        # init pvcam once
        try:
            pvc.init_pvcam()
        except Exception:
            # 如果已经初始化会抛出，忽略
            pass

        # detect / open camera
        if cam_name is None:
            # detect_camera 返回生成器，取第一个
            cam_gen = PyVcamCamera.detect_camera()
            try:
                self.cam = next(cam_gen)
            except StopIteration:
                raise RuntimeError("未找到任何 PyVCAM 相机。请确认 PVCAM 驱动安装并连接相机。")
        else:
            self.cam = PyVcamCamera(cam_name)

        # 不自动 open，显式打开
        self.cam.open()

        # 暴露给外部的曝光时间（以秒为单位）
        self._ex_time_s = default_ex_time_s

        # 尝试把曝光时间写回相机（若相机支持）
        self.set_ex_time(self._ex_time_s)

    def set_ex_time(self, ex_time):
        """
        ex_time: 秒
        内部会把秒->毫秒传给 pyvcam（pyvcam 示例通常使用 ms）
        """
        self._ex_time_s = float(ex_time)
        exp_ms = int(self._ex_time_s * 1000)

        # 尝试几种常见接口设置曝光（容错）
        try:
            self.cam.finish()
            self.cam.start_live(exp_time=exp_ms, buffer_frame_count=1
                                )
        except Exception:
            # 不要因为设置失败而中断；直接在后续的 get_frame/start_live 时传 exp_time
            pass


    def start_acquisition(self):
        """启动后台连续采集（如果已在采集则不重复启动）"""
        win_name = 'Live Mode'
        try:
            self.cam.start_live(exp_time=self._ex_time_s * 1000, buffer_frame_count=1)
            self._acquiring = True
        except Exception as e:
            print(f'开始采集失败：{e}')

    def stop_acquisition(self, wait: bool = False):
        """停止后台采集"""
        self.cam.finish()

    def read_newest_image(self):
        """返回最新一帧 numpy 数组（或 None）。线程安全。"""
        try:
            image, fps, frame_count = self.cam.poll_frame()
        except Exception as e:
            print(f'获取图像失败：{e}')
        return image['pixel_data']

    def get_frame_period(self):
        """
        返回帧周期（秒/帧）的近似值；优先使用历史时间戳计算平均间隔，
        否则尝试从相机属性读取（如果存在）。
        """
        try:
            time.sleep(0.3)
            image, fps, frame_count = self.cam.poll_frame()
        except Exception as e:
            print(f'获取帧率失败：{e}')
        return 1 / fps

    def close(self):
        """关闭相机并清理"""
        try:
            self.stop_acquisition(wait=True)
        except Exception:
            pass
        try:
            if hasattr(self.cam, "close"):
                self.cam.close()
                pvc.uninit_pvcam()
        except Exception:
            pass
        try:
            pvc.uninit_pvcam()
        except Exception:
            pass

    def get_bit_depth(self):
        try:
            # PyVCAM 通常直接有这个属性
            return self.cam.bit_depth
        except:
            # 如果没有，尝试从 pixel format 推断
            return 16

if __name__ == "__main__":
    cam = PyVCAM()  # 自动检测并打开第1个相机
    cam.set_ex_time(0.005)  # 50 ms 曝光（传入单位为秒）
    cam.start_acquisition()  # 启动后台连续采集

    # 在主线程随时读最新帧
    img = cam.read_newest_image()
    if img is not None:
        print("frame shape:", img.shape)

    fps_period = cam.get_frame_period()
    print("frame period (s):", fps_period)

    cam.stop_acquisition()
    cam.close()
