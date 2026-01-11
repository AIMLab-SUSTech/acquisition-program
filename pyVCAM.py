from pyvcam import pvc
from pyvcam.camera import Camera


class pyVcamera(Camera):

    def __init__(self):
        pvc.init_pvcam()
        camera_list = Camera.get_available_camera_names()
        if len(camera_list) == 0:
            raise RuntimeError('pyVCAM未检测到相机')
        super().__init__(camera_list[0])
        self.open()


    def set_ex_time(self, ex_time):
        # 单位是ms
        try:
            self.exp_time = ex_time
        except Exception as e:
            print(f'pyVCAM曝光时间设置失败：{e}')
            

    def snap(self):
        try:
            return self.get_frame(exp_time=self.exp_time)
        except Exception as e:
            print(f'pyVCAM单帧采集失败：{e}')
            return None
    

    def start_acquisition(self):
        try:
            self.start_live(exp_time=self.exp_time)
        except Exception as e:
            print(f'pyVCAM开始采集失败：{e}')



    def read_newest_image(self):
        try:
            frame,fps,count = self.poll_frame(timeout_ms=0,oldestFrame=False)
            if frame is not None and frame.get('pixel_data') is not None:
                return frame['pixel_data']
            else:
                return None
        except Exception as e:
            print(f'pyVCAM获取图像失败：{e}')

    

    def get_frame_period(self):
        try:
            frame, fps, frame_count = self.poll_frame(timeout_ms=1000,oldestFrame=True,copyData=True)
            if fps > 0:
                frame_period_us = 1000000.0 / fps  
                return frame_period_us
            else:
                return 0.0    
        except Exception as e:
            print(f"获取帧周期失败: {e}")
            return 0.0

    def stop_acquisition(self):
        try:
            self.finish()
        except Exception as e:
            print(f'pyVCAM停止采集失败：{e}')

    def close(self):
        super().close()

        


