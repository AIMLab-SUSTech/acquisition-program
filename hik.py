import sys
sys.path.append(r"C:\Program Files (x86)\MVS\Development\Samples\Python")

import numpy as np
import time
from ctypes import c_ubyte
from camera import Camera  # 请确保项目中有 camera.py 定义 Camera 基类


class HikrobotCamera(Camera):
    """海康机器人 MV-CH120-10UM 相机类（使用官方 MVS SDK）"""
    def __init__(self, camera_index=0):
        super().__init__()
        self.cam = None
        self.device_info = None
        self.is_opened = False
        self.is_streaming = False
        self._frame_period = 0.0
        self._bit_depth = 12  # 默认初始化为 12

        # ---------- 导入 SDK ----------
        try:
            from MvImport.MvCameraControl_class import MvCamera
            from MvImport.CameraParams_const import MV_USB_DEVICE, MV_GIGE_DEVICE
            from MvImport.PixelType_header import (
                PixelType_Gvsp_Mono8, PixelType_Gvsp_Mono10,
                PixelType_Gvsp_Mono12, PixelType_Gvsp_Mono16,
                PixelType_Gvsp_RGB8_Packed
            )
            from MvImport.CameraParams_header import (
                MV_CC_DEVICE_INFO_LIST, MV_CC_DEVICE_INFO,
                MVCC_ENUMVALUE, MVCC_FLOATVALUE, MVCC_INTVALUE_EX,
                MV_FRAME_OUT_INFO_EX
            )
            from MvImport.MvErrorDefine_const import MV_OK
        except ImportError as e:
            print(f"错误: 无法导入 MVS SDK，请检查 MvImport 路径。\n{e}")
            return

        # 保存引用
        self.MvCamera = MvCamera
        self.MV_USB_DEVICE = MV_USB_DEVICE
        self.MV_GIGE_DEVICE = MV_GIGE_DEVICE
        self.PixelType_Gvsp_Mono8 = PixelType_Gvsp_Mono8
        self.PixelType_Gvsp_Mono10 = PixelType_Gvsp_Mono10
        self.PixelType_Gvsp_Mono12 = PixelType_Gvsp_Mono12
        self.PixelType_Gvsp_Mono16 = PixelType_Gvsp_Mono16
        self.PixelType_Gvsp_RGB8_Packed = PixelType_Gvsp_RGB8_Packed
        self.MV_CC_DEVICE_INFO_LIST = MV_CC_DEVICE_INFO_LIST
        self.MV_CC_DEVICE_INFO = MV_CC_DEVICE_INFO
        self.MVCC_ENUMVALUE = MVCC_ENUMVALUE
        self.MVCC_FLOATVALUE = MVCC_FLOATVALUE
        self.MVCC_INTVALUE_EX = MVCC_INTVALUE_EX
        self.MV_FRAME_OUT_INFO_EX = MV_FRAME_OUT_INFO_EX
        self.MV_OK = MV_OK

        # 2. 初始化 SDK
        ret = MvCamera.MV_CC_Initialize()
        if ret != MV_OK:
            print(f"SDK 初始化失败，错误码: {ret}")
            return

        # 3. 枚举设备
        self.device_list = MV_CC_DEVICE_INFO_LIST()
        ret = MvCamera.MV_CC_EnumDevices(MV_USB_DEVICE, self.device_list)
        if ret != MV_OK or self.device_list.nDeviceNum == 0:
            ret = MvCamera.MV_CC_EnumDevices(MV_GIGE_DEVICE, self.device_list)
        if ret != MV_OK or self.device_list.nDeviceNum == 0:
            print("未发现海康相机，请检查连接和驱动")
            return

        # 4. 选择设备
        if camera_index >= self.device_list.nDeviceNum:
            print(f"相机索引 {camera_index} 超出范围（共 {self.device_list.nDeviceNum} 台）")
            return

        self.device_info = self.device_list.pDeviceInfo[camera_index]

        # 5. 创建设备句柄
        self.cam = MvCamera()
        ret = self.cam.MV_CC_CreateHandle(self.device_info.contents)
        if ret != MV_OK:
            print(f"创建设备句柄失败，错误码: {ret}")
            self.cam = None
            return

        # 6. 打开设备
        ret = self.cam.MV_CC_OpenDevice()
        if ret != MV_OK:
            print(f"打开设备失败，错误码: {ret}")
            self.cam = None
            return

        self.is_opened = True
        print("海康相机已成功打开")

        # 7. 尝试设置为 Mono12（如果支持），否则 Mono10
        self._set_preferred_pixel_format()

        # 8. 获取实际位深和帧周期
        self._update_bit_depth()
        self._update_frame_period()

    # ---------- 内部辅助 ----------
    def _set_preferred_pixel_format(self):
        """尝试设置像素格式为 Mono12，失败则 Mono10，再失败则保持当前"""
        if not self.is_opened or self.cam is None:
            return
        try:
            # 优先尝试 Mono12
            ret = self.cam.MV_CC_SetEnumValue("PixelFormat", self.PixelType_Gvsp_Mono12)
            if ret == self.MV_OK:
                print("像素格式已设置为 Mono12")
                return
            # 尝试 Mono10
            ret = self.cam.MV_CC_SetEnumValue("PixelFormat", self.PixelType_Gvsp_Mono10)
            if ret == self.MV_OK:
                print("像素格式已设置为 Mono10")
                return
            print("警告: 无法设置 Mono12 或 Mono10，保持当前像素格式")
        except Exception as e:
            print(f"设置像素格式异常: {e}")

    def _update_bit_depth(self):
        if not self.is_opened or self.cam is None:
            return
        try:
            enum_val = self.MVCC_ENUMVALUE()
            ret = self.cam.MV_CC_GetEnumValue("PixelFormat", enum_val)
            if ret == self.MV_OK:
                pixel_format = enum_val.nCurValue
                if pixel_format in (self.PixelType_Gvsp_Mono8, self.PixelType_Gvsp_RGB8_Packed):
                    self._bit_depth = 8
                elif pixel_format == self.PixelType_Gvsp_Mono10:
                    self._bit_depth = 10
                elif pixel_format == self.PixelType_Gvsp_Mono12:
                    self._bit_depth = 12
                elif pixel_format == self.PixelType_Gvsp_Mono16:
                    self._bit_depth = 16
                # 其他格式保持默认12
        except Exception as e:
            print(f"获取位深失败: {e}")

    def _update_frame_period(self):
        if not self.is_opened or self.cam is None:
            return
        try:
            float_val = self.MVCC_FLOATVALUE()
            ret = self.cam.MV_CC_GetFloatValue("AcquisitionFrameRate", float_val)
            if ret == self.MV_OK and float_val.fCurValue > 0:
                self._frame_period = 1.0 / float_val.fCurValue
            else:
                ret = self.cam.MV_CC_GetFloatValue("ResultingFrameRate", float_val)
                if ret == self.MV_OK and float_val.fCurValue > 0:
                    self._frame_period = 1.0 / float_val.fCurValue
                else:
                    self._frame_period = 0.0
        except:
            self._frame_period = 0.0

    # ---------- 公共接口 ----------
    def set_ex_time(self, ex_time):
        if not self.is_opened or self.cam is None:
            print("相机未打开")
            return
        try:
            exposure_us = ex_time * 1e6
            float_val = self.MVCC_FLOATVALUE()
            ret = self.cam.MV_CC_GetFloatValue("ExposureTime", float_val)
            if ret == self.MV_OK:
                if exposure_us < float_val.fMin:
                    exposure_us = float_val.fMin
                elif exposure_us > float_val.fMax:
                    exposure_us = float_val.fMax
            ret = self.cam.MV_CC_SetFloatValue("ExposureTime", exposure_us)
            if ret != self.MV_OK:
                print(f"设置曝光时间失败，错误码: {ret}")
        except Exception as e:
            print(f"设置曝光时间异常: {e}")

    def start_acquisition(self):
        if not self.is_opened or self.cam is None:
            print("相机未打开")
            return
        if self.is_streaming:
            return
        try:
            ret = self.cam.MV_CC_StartGrabbing()
            if ret != self.MV_OK:
                print(f"开始采集失败，错误码: {ret}")
            else:
                self.is_streaming = True
                self._update_frame_period()
        except Exception as e:
            print(f"开始采集异常: {e}")

    def stop_acquisition(self):
        if not self.is_streaming:
            return
        try:
            self.cam.MV_CC_StopGrabbing()
            self.is_streaming = False
        except Exception as e:
            print(f"停止采集异常: {e}")

    def read_newest_image(self):
        if not self.is_streaming or self.cam is None:
            print("相机未处于采集状态")
            return None

        try:
            # 获取像素格式、宽、高
            enum_val = self.MVCC_ENUMVALUE()
            ret = self.cam.MV_CC_GetEnumValue("PixelFormat", enum_val)
            if ret != self.MV_OK:
                print("获取像素格式失败")
                return None
            pixel_format = enum_val.nCurValue

            int_val = self.MVCC_INTVALUE_EX()
            ret = self.cam.MV_CC_GetIntValueEx("Width", int_val)
            if ret != self.MV_OK:
                print("获取宽度失败")
                return None
            width = int_val.nCurValue

            ret = self.cam.MV_CC_GetIntValueEx("Height", int_val)
            if ret != self.MV_OK:
                print("获取高度失败")
                return None
            height = int_val.nCurValue

            # 计算每像素字节数
            if pixel_format == self.PixelType_Gvsp_Mono8:
                bytes_per_pixel = 1
                dtype = np.uint8
            elif pixel_format in (self.PixelType_Gvsp_Mono10,
                                  self.PixelType_Gvsp_Mono12,
                                  self.PixelType_Gvsp_Mono16):
                bytes_per_pixel = 2
                dtype = np.uint16
            elif pixel_format == self.PixelType_Gvsp_RGB8_Packed:
                bytes_per_pixel = 3
                dtype = np.uint8
            else:
                bytes_per_pixel = 1
                dtype = np.uint8

            n_data_size = width * height * bytes_per_pixel
            pData = (c_ubyte * n_data_size)()
            frame_info = self.MV_FRAME_OUT_INFO_EX()
            ret = self.cam.MV_CC_GetOneFrameTimeout(pData, n_data_size, frame_info, 1000)
            if ret != self.MV_OK:
                print(f"获取图像帧失败，错误码: {ret}")
                return None

            buffer = bytearray(pData)
            if bytes_per_pixel == 1:
                img = np.frombuffer(buffer, dtype=np.uint8).reshape((height, width))
            elif bytes_per_pixel == 2:
                img = np.frombuffer(buffer, dtype=np.uint16).reshape((height, width))
            elif bytes_per_pixel == 3:
                img = np.frombuffer(buffer, dtype=np.uint8).reshape((height, width, 3))
            else:
                img = np.frombuffer(buffer, dtype=np.uint8).reshape((height, width))

            return img

        except Exception as e:
            print(f"读取图像异常: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_frame_period(self):
        if not self.is_streaming:
            self._update_frame_period()
        return self._frame_period

    def get_bit_depth(self):
        return self._bit_depth
    
    # ----- 为兼容 ScanWorker 添加的触发模式方法（空实现）-----
    def set_trigger_mode(self, mode):
        # 海康相机在连续模式下主动取帧，不需要切换触发模式
        pass

    def trigger(self):
        # 软触发无动作
        pass

    def close(self):
        self.stop_acquisition()
        if self.is_opened and self.cam is not None:
            self.cam.MV_CC_CloseDevice()
            self.cam.MV_CC_DestroyHandle()
            self.is_opened = False
            self.cam = None
            print("相机已关闭")

    def __del__(self):
        self.close()


# ---------- 简单测试 ----------
if __name__ == '__main__':
    cam = HikrobotCamera()
    if cam.cam is not None:
        cam.set_ex_time(0.02)
        cam.start_acquisition()
        time.sleep(0.5)
        img = cam.read_newest_image()
        print(img)
        if img is not None:
            print(f"图像形状: {img.shape}, dtype: {img.dtype}")
            print(f"图像最大值: {img.max()}, 最小值: {img.min()}")
        else:
            print("未能获取图像")
        print(f"帧周期: {cam.get_frame_period()} s")
        print(f"位深: {cam.get_bit_depth()}")
        cam.close()