import ids_peak.ids_peak as ids_peak
import ids_peak_ipl.ids_peak_ipl as ids_ipl
import ids_peak.ids_peak_ipl_extension as ids_ipl_extension
import numpy as np
from abc import ABC, abstractmethod
from camera import Camera
import copy


class IDSPeakCamera(Camera):
    def __init__(self, device_index=0):
        super().__init__()
        self.device_index = device_index
        self.device = None
        self.remote_device_nodemap = None
        self.datastream = None
        self.buffers = []
        self.is_acquiring = False

        # 初始化库
        ids_peak.Library.Initialize()

        # 查找并打开设备
        self._open_device()

        # 配置相机
        self._configure_camera()

        # 分配缓冲区
        self._allocate_buffers()

    def _open_device(self):
        """打开指定的IDS相机设备"""
        device_manager = ids_peak.DeviceManager.Instance()
        device_manager.Update()
        device_descriptors = device_manager.Devices()

        if len(device_descriptors) == 0:
            raise RuntimeError("No IDS cameras found")

        if self.device_index >= len(device_descriptors):
            raise RuntimeError(
                f"Device index {self.device_index} out of range. Found {len(device_descriptors)} devices.")

        print(f"Found Devices: {len(device_descriptors)}")
        for i, device_descriptor in enumerate(device_descriptors):
            marker = " -> SELECTED" if i == self.device_index else ""
            print(f"{i}: {device_descriptor.DisplayName()}{marker}")

        self.device = device_descriptors[self.device_index].OpenDevice(ids_peak.DeviceAccessType_Control)
        print(f"Opened Device: {self.device.DisplayName()}")

        # 获取远程设备节点映射
        self.remote_device_nodemap = self.device.RemoteDevice().NodeMaps()[0]

    def _set_mono12_pixel_format(self):
        """设置像素格式为Mono12"""
        # 列出可用 PixelFormat（可选，便于调试）
        entries = self.remote_device_nodemap.FindNode("PixelFormat").Entries()
        available = [e.SymbolicValue() for e in entries]

        print("Available PixelFormat:", available)

        # 优先尝试 "Mono12"（unpacked 16-bit per pixel）；如无则尝试其它 12-bit 名称
        preferred = ["Mono12"]
        for name in preferred:
            if name in available:
                self.remote_device_nodemap.FindNode("PixelFormat").SetCurrentEntry(name)
                print("Set PixelFormat ->", name)
                return name
        raise RuntimeError("No suitable Mono pixel format available")

    def _configure_camera(self):
        """配置相机参数"""
        # 设置像素格式为Mono12
        self._set_mono12_pixel_format()

        # 配置触发模式
        self.remote_device_nodemap.FindNode("TriggerSelector").SetCurrentEntry("ExposureStart")
        self.remote_device_nodemap.FindNode("TriggerSource").SetCurrentEntry("Software")
        self.remote_device_nodemap.FindNode("TriggerMode").SetCurrentEntry("On")

        # 设置默认曝光时间20ms
        self.set_ex_time(0.02)

    def _allocate_buffers(self):
        """分配数据流缓冲区"""
        self.datastream = self.device.DataStreams()[0].OpenDataStream()
        payload_size = self.remote_device_nodemap.FindNode("PayloadSize").Value()

        # 分配和宣布缓冲区
        min_required_buffers = self.datastream.NumBuffersAnnouncedMinRequired()
        for i in range(min_required_buffers):
            buffer = self.datastream.AllocAndAnnounceBuffer(payload_size)
            self.datastream.QueueBuffer(buffer)
            self.buffers.append(buffer)
    
    def get_bit_depth(self):
        try:
            # IDS Peak Python SDK 访问节点
            # remote_device = self.device.RemoteDevice()
            # pixel_format = remote_device.NodeMaps()[0].FindNode("PixelFormat").CurrentEntry().SymbolicValue()
            
            # 简化假设，如果您的封装类有名为 pixel_format 的属性
            pf = self.cam.PixelFormat.Value() # 假设写法
            
            if "8" in pf: return 8
            if "10" in pf: return 10
            if "12" in pf: return 12
            return 8
        except:
            return 12 # 默认
            
    def set_ex_time(self, ex_time):
        """设置曝光时间, ex_time: 秒"""
        # 转换为微秒
        ex_time_us = int(ex_time * 1e6)
        self.remote_device_nodemap.FindNode("ExposureTime").SetValue(ex_time_us)
        print(f"Exposure time set to {ex_time_us} μs ({ex_time} s)")

    def start_acquisition(self):
        """开始图像采集"""
        if self.is_acquiring:
            print("Acquisition already started")
            return

        self.datastream.StartAcquisition()
        self.remote_device_nodemap.FindNode("AcquisitionStart").Execute()
        self.remote_device_nodemap.FindNode("AcquisitionStart").WaitUntilDone()
        self.is_acquiring = True
        print("Acquisition started")

    def read_newest_image(self):
        """读取最新的图像"""
        if not self.is_acquiring:
            raise RuntimeError("Acquisition not started. Call start_acquisition() first.")

        # 触发图像采集
        self.remote_device_nodemap.FindNode("TriggerSoftware").Execute()

        # 等待完成的缓冲区
        buffer = self.datastream.WaitForFinishedBuffer(5000)

        # 转换为图像
        raw_image = ids_ipl_extension.BufferToImage(buffer)

        # 转换为Mono12格式
        image16 = raw_image.ConvertTo(ids_ipl.PixelFormatName_Mono12, ids_ipl.ConversionMode_Fast)

        # 获取numpy数组
        picture = image16.get_numpy_2D_16().copy()

        # 重新将缓冲区加入队列
        self.datastream.QueueBuffer(buffer)

        return picture

    def get_frame_period(self):
        """获取帧率，返回：秒"""
        frame_rate = self.remote_device_nodemap.FindNode("AcquisitionFrameRate").Value()
        if frame_rate <= 0:
            return float('inf')  # 处理零或负帧率
        return 1.0 / frame_rate

    def stop_acquisition(self):
        """停止图像采集（非抽象方法，但很有用）"""
        if not self.is_acquiring:
            print("Acquisition not running")
            return

        self.datastream.StopAcquisition()
        self.is_acquiring = False
        print("Acquisition stopped")

    def close(self):
        """关闭相机（非抽象方法，但很有用）"""
        if self.is_acquiring:
            self.stop_acquisition()

        # 刷新数据流
        self.datastream.Flush(ids_peak.DataStreamFlushMode_DiscardAll)

        # 停止采集并撤销缓冲区
        for buffer in self.buffers:
            self.datastream.RevokeBuffer(buffer)

        # 关闭设备
        if self.device:
            self.device = None

        ids_peak.Library.Close()

        print("Camera closed")

    def __del__(self):
        """析构函数，确保资源被正确释放"""
        try:
            self.close()
        except:
            pass  # 避免在析构时抛出异常


# 使用示例
if __name__ == "__main__":
    try:
        # 创建相机实例
        camera = IDSPeakCamera(device_index=0)

        # 开始采集
        camera.start_acquisition()

        # 获取帧周期
        frame_period = camera.get_frame_period()
        print(f"Frame period: {frame_period:.4f} s ({1.0 / frame_period:.2f} FPS)")

        # 设置曝光时间
        # camera.set_ex_time(0.01)  # 10ms

        # 获取一帧图像
        image = camera.read_newest_image()
        print(f"Image shape: {image.shape}, dtype: {image.dtype}")
        print(f"Max value: {image.max()}")

        # 停止采集
        camera.stop_acquisition()

        # 关闭相机
        camera.close()

    except Exception as e:
        print(f"Error: {e}")