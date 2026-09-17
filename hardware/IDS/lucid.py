import ctypes
import time
from pathlib import Path
from abc import ABC, abstractmethod
import numpy as np
from PIL import Image as PIL_Image
from arena_api.system import system
from camera import Camera


class LucidCamera(Camera):
    def __init__(self, device_index=0, max_tries=6, wait_time=10):
        """
        初始化Lucid相机
        
        参数:
            device_index: 设备索引，默认为0（第一个设备）
            max_tries: 最大尝试连接次数
            wait_time: 每次尝试等待时间（秒）
        """
        super().__init__()
        self.device = None
        self.tl_stream_nodemap = None
        self.nodemap = None
        self.is_streaming = False

        # 连接设备
        self._connect_device(max_tries, wait_time)

        # 初始化节点映射
        self.tl_stream_nodemap = self.device.tl_stream_nodemap
        self.nodemap = self.device.nodemap

        # 配置流参数
        self._configure_stream()

        # 配置相机参数
        self._configure_camera()

        print(f"Lucid相机初始化成功: {self.device}")

    def _connect_device(self, max_tries, wait_time):
        """连接设备"""
        tries = 0
        while tries < max_tries:
            devices = system.create_device()
            if devices:
                if len(devices) > 0:
                    self.device = devices[0]  # 选择第一个设备
                    return
            print(f'尝试 {tries + 1}/{max_tries}: 等待 {wait_time} 秒设备连接...')
            time.sleep(wait_time)
            tries += 1

        raise Exception("未找到设备！请检查相机连接后重新运行。")

    def _configure_stream(self):
        """配置流参数"""
        # 启用流自动协商数据包大小
        self.tl_stream_nodemap['StreamAutoNegotiatePacketSize'].value = True
        # 启用流数据包重传
        self.tl_stream_nodemap['StreamPacketResendEnable'].value = True

    def _configure_camera(self):
        """配置相机基本参数"""
        nodes = self.nodemap.get_node(['Width', 'Height', 'PixelFormat'])

        # 设置最大分辨率
        nodes['Width'].value = min(nodes['Width'].max, 2048)
        nodes['Height'].value = min(nodes['Height'].max, 2048)

        # 设置像素格式为Mono12（可根据需要修改）
        for i in ['Mono16', 'Mono12']:
            try:
                self.pixel_format = i
                nodes['PixelFormat'].value = self.pixel_format
                break
            except Exception as e:
                print(f'设置像素格式 {i} 失败：{e}')

    def set_ex_time(self, ex_time):
        """
        设置曝光时间
        
        参数:
            ex_time: 曝光时间，单位秒 (S)
        """
        try:
            # 将秒转换为微秒
            ex_time_us = ex_time * 1e6

            # 关闭自动曝光
            self.nodemap['ExposureAuto'].value = 'Off'
            # 设置曝光时间
            self.nodemap['ExposureTime'].value = ex_time_us
            print(
                f"曝光时间设置为: {ex_time} 秒 ({ex_time_us} 微秒), 实际时间为{self.nodemap['ExposureTime'].value} 微秒")

        except Exception as e:
            print(f'设置曝光时间失败：{e}')

    def set_pixel_format(self, pixel_format):
        """
        设置像素格式
        
        参数:
            pixel_format: 像素格式字符串，如 'Mono8', 'Mono12', 'RGB8' 等
        """
        try:
            self.nodemap['PixelFormat'].value = pixel_format
            self.pixel_format = pixel_format
            print(f"像素格式设置为: {pixel_format}")
        except Exception as e:
            print(f'设置像素格式失败：{e}')

    def start_acquisition(self):
        """开始图像采集"""
        if not self.is_streaming:
            self.device.start_stream()
            self.is_streaming = True
            print("开始图像采集...")

    def stop_acquisition(self):
        """停止图像采集"""
        if self.is_streaming:
            self.device.stop_stream()
            self.is_streaming = False
            print("停止图像采集")

    def read_newest_image(self, timeout=2000):
        """
        读取最新的图像
        
        参数:
            timeout: 超时时间，毫秒
            
        返回:
            numpy数组形式的图像数据，失败时返回None
        """
        try:
            if not self.is_streaming:
                self.start_acquisition()

            # 获取图像缓冲区
            image_buffer = self.device.get_buffer(timeout=timeout)

            # 根据像素格式处理图像数据
            if self.pixel_format in ['Mono8', 'Mono12', 'Mono12p', 'Mono16']:
                # 处理单通道图像
                if self.pixel_format == 'Mono12' or self.pixel_format == 'Mono16':
                    # Mono12: 16位数据，实际使用12位
                    pdata_as16 = ctypes.cast(image_buffer.pdata,
                                             ctypes.POINTER(ctypes.c_ushort))
                    image_array = np.ctypeslib.as_array(
                        pdata_as16,
                        (image_buffer.height, image_buffer.width)
                    )
                elif self.pixel_format == 'Mono12p':
                    image_array = self._unpack_mono12p(
                        image_buffer.pdata,
                        image_buffer.width,
                        image_buffer.height
                    )
                else:
                    # Mono8: 8位数据
                    image_array = np.ctypeslib.as_array(
                        image_buffer.pdata,
                        (image_buffer.height, image_buffer.width)
                    )
            else:
                # 其他格式可以在这里扩展
                print(f"警告: 像素格式 {self.pixel_format} 的处理未实现")
                image_array = None

            # 归还缓冲区
            self.device.requeue_buffer(image_buffer)

            return image_array

        except Exception as e:
            print(f'获取图像失败：{e}')
            return None

    def save_image(self, image_array, filename, format='PNG'):
        """
        保存图像到文件
        
        参数:
            image_array: 图像数据数组
            filename: 文件名
            format: 图像格式 ('PNG', 'JPEG', 'BMP'等)
        """
        try:
            if image_array is not None:
                if self.pixel_format == 'Mono12':
                    # Mono12的特殊处理
                    image_array_as_bytes = image_array.tobytes()
                    pil_image = PIL_Image.new('I', image_array.T.shape)
                    pil_image.frombytes(image_array_as_bytes, 'raw', 'I;16')
                else:
                    # 其他格式
                    pil_image = PIL_Image.fromarray(image_array)

                pil_image.save(filename, format=format)
                print(f"图像已保存: {Path(filename).absolute()}")
            else:
                print("无法保存空图像")
        except Exception as e:
            print(f'保存图像失败：{e}')

    def get_frame_period(self):
        """
        获取帧周期（帧率的倒数）
        
        返回:
            帧周期，单位秒 (S)
        """
        try:
            frame_rate = self.nodemap['AcquisitionFrameRate'].value
            frame_period = 1.0 / frame_rate if frame_rate > 0 else 0
            return frame_period
        except Exception as e:
            print(f'获取帧率失败：{e}')
            return 0

    def get_frame_rate(self):
        """
        获取帧率
        
        返回:
            帧率，单位Hz
        """
        try:
            frame_rate = self.nodemap['AcquisitionFrameRate'].value
            return frame_rate
        except Exception as e:
            print(f'获取帧率失败：{e}')
            return 0

    def set_frame_rate(self, frame_rate):
        """
        设置帧率
        
        参数:
            frame_rate: 帧率，单位Hz
        """
        try:
            self.nodemap['AcquisitionFrameRateEnable'].value = True
            self.nodemap['AcquisitionFrameRate'].value = frame_rate
            print(f"帧率设置为: {frame_rate} Hz")
        except Exception as e:
            print(f'设置帧率失败：{e}')

    def _unpack_mono12p(self, packed_data, width, height):
        """
        解包Mono12p格式数据

        Mono12p格式说明:
        - 每3个字节存储2个12位像素
        - 字节排列: [像素1低8位] [像素2低4位 + 像素1高4位] [像素2高8位]
        - 或者: [字节0] [字节1] [字节2] 对应:
          像素1 = (字节1的低4位 << 8) | 字节0
          像素2 = (字节2 << 4) | (字节1的高4位)
        """
        # 将打包数据转换为numpy数组
        packed_array = np.ctypeslib.as_array(
            ctypes.cast(packed_data, ctypes.POINTER(ctypes.c_ubyte)),
            (height, width * 3 // 2)  # 每行字节数 = 宽度 * 1.5
        )

        # 创建输出数组
        unpacked_array = np.zeros((height, width), dtype=np.uint16)

        for y in range(height):
            for x in range(0, width, 2):
                # 每3个字节处理2个像素
                idx = x * 3 // 2
                if idx + 2 < packed_array.shape[1]:
                    byte0 = packed_array[y, idx]  # 第一个像素的低8位
                    byte1 = packed_array[y, idx + 1]  # 第二个像素低4位 + 第一个像素高4位
                    byte2 = packed_array[y, idx + 2]  # 第二个像素的高8位

                    # 解包第一个像素: (byte1的低4位 << 8) | byte0
                    pixel1 = ((byte1 & 0x0F) << 8) | byte0
                    # 解包第二个像素: (byte2 << 4) | (byte1的高4位)
                    pixel2 = (byte2 << 4) | ((byte1 & 0xF0) >> 4)

                    unpacked_array[y, x] = pixel1
                    if x + 1 < width:
                        unpacked_array[y, x + 1] = pixel2

        return unpacked_array

    def __del__(self):
        """析构函数，确保资源被正确释放"""
        try:
            if self.is_streaming:
                self.stop_acquisition()
            if self.device:
                system.destroy_device()
        except:
            pass

    def get_bit_depth(self):
        try:
            # 读取 PixelFormat 节点
            # 假设 self.cam 是设备对象，有 nodemap
            # 伪代码: pf = self.cam.get_node("PixelFormat").value
            
            # 或者如果封装得比较好，可能有 pixel_format 属性
            pf = self.cam.pixel_format 
            
            if "8" in pf: return 8
            if "10" in pf: return 10
            if "12" in pf: return 12
            if "16" in pf: return 16
            return 8
        except:
            return 12 # Lucid 工业相机常用 12-bit


# 使用示例
if __name__ == '__main__':
    try:
        # 创建相机实例
        camera = LucidCamera()

        # 设置曝光时间 (0.01秒)
        camera.set_ex_time(0.01)

        # 设置帧率 (30 Hz)
        # camera.set_frame_rate(30.0)

        # 开始采集
        camera.start_acquisition()

        # 获取并显示帧率信息
        frame_rate = camera.get_frame_rate()
        frame_period = camera.get_frame_period()
        print(f"帧率: {frame_rate} Hz, 帧周期: {frame_period} 秒")

        # 捕获图像
        for i in range(10):
            image = camera.read_newest_image()
            if image is not None:
                print(f"图像尺寸: {image.shape}, {image.max()}")

            # 保存图像
            # camera.save_image(image, 'test_image.png')

        # 停止采集
        camera.stop_acquisition()

    except Exception as e:
        print(f"相机操作失败: {e}")
