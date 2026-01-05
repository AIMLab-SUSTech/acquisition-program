import numpy as np
import pylablib as pll
# pll.par["device/dlls/picam"] = "Princeton Instruments/PICam/Runtime/x64/picam.dll"
from pylablib.devices import PrincetonInstruments as pi
from camera import Camera

class PICamera(Camera):
    def __init__(self):
        super().__init__()
        self.cam = None
        self.is_acquiring = False
        
        print("正在扫描 PI 相机...")
        try:
            # 获取相机列表
            cams = pi.PicamCamera.list_cameras()
            if not cams:
                raise RuntimeError("未检测到 PI 相机，请检查驱动及连接。")
            
            print(f"检测到的相机: {cams}")
            # 打开第一个相机
            self.cam = pi.PicamCamera(cams[0])
            print(f"成功打开相机: {cams[0]}")
            
            # 设置默认参数
            self._configure_camera()
            
        except Exception as e:
            print(f"PI 相机初始化失败: {e}")
            raise e

    def _configure_camera(self):
        """配置基础参数"""
        try:
            # 清除之前的 ROI 设置，使用全画幅
            self.cam.clear_roi()
            # 设置采集模式为连续采集 (Run Till Abort)
            # pylablib 中通常默认支持，但在 start_acquisition 时指定
            pass
        except Exception as e:
            print(f"配置相机参数失败: {e}")

    def get_bit_depth(self):
        """
        获取相机 ADC 位深
        返回: int (例如 16)
        """
        if self.cam:
            try:
                bit_depth = self.cam.get_attribute_value("AdcBitDepth")
                return int(bit_depth)
            except Exception as e:
                print(f"读取位深失败，使用默认值 16: {e}")
                # PI-MTE3 通常是 16-bit 科学级相机，如果读取失败，默认 16 是最安全的
                return 16
        return 16

    def set_ex_time(self, ex_time):
        """
        设置曝光时间
        参数: ex_time (秒)
        """
        if self.cam:
            try:
                # pylablib 的 set_exposure 通常接受秒为单位
                self.cam.set_exposure(ex_time)
                print(f"PI 相机曝光设置为: {ex_time} s")
            except Exception as e:
                print(f"设置曝光时间失败: {e}")

    def start_acquisition(self):
        """开始采集"""
        if self.cam:
            try:
                # 设置为连续采集模式
                self.cam.set_acquisition_mode(mode="run_till_abort")
                self.cam.start_acquisition()
                self.is_acquiring = True
                print("PI 相机开始采集")
            except Exception as e:
                print(f"开始采集失败: {e}")

    def stop_acquisition(self):
        """停止采集"""
        if self.cam and self.is_acquiring:
            try:
                self.cam.stop_acquisition()
                self.is_acquiring = False
                print("PI 相机停止采集")
            except Exception as e:
                print(f"停止采集失败: {e}")

    def read_newest_image(self):
        """
        读取最新一帧图像
        返回: numpy array (uint16)
        """
        if self.cam and self.is_acquiring:
            try:
                # read_newest_image 返回最新的图像数据
                # 如果没有新图像，可能会返回 None 或旧图像，具体取决于 pylablib 版本
                # 这里我们尝试读取最新的一帧
                img = self.cam.read_newest_image()
                
                if img is not None:
                    return img.astype(np.uint16)
            except Exception as e:
                # 忽略读取过程中的瞬时错误，防止崩毁
                print(f"读取图像失败: {e}") 
        return None

    def get_frame_period(self):
        """获取帧周期 (秒)"""
        if self.cam:
            try:
                # pylablib 通常提供 get_frame_period 或 get_detector_readout_time
                return self.cam.get_frame_period()
            except:
                # 如果获取失败，返回当前曝光时间作为估算值
                return self.cam.get_exposure()
        return 0.1

    def get_bit_depth(self):
        # PICam 几乎总是 16-bit ADC
        return 16

    def close(self):
        """关闭相机资源"""
        if self.cam:
            try:
                if self.is_acquiring:
                    self.stop_acquisition()
                self.cam.close()
                print("PI 相机已关闭")
            except Exception as e:
                print(f"关闭相机失败: {e}")
            finally:
                self.cam = None

# 测试代码
if __name__ == '__main__':
    try:
        cam = PICamera()
        cam.set_ex_time(0.05) # 50ms
        cam.start_acquisition()
        import time
        time.sleep(1)
        img = cam.read_newest_image()
        if img is not None:
            print(f"获取图像成功，形状: {img.shape}, 最大值: {np.max(img)}")
        print(f"帧周期: {cam.get_frame_period()}")
        cam.close()
    except Exception as e:
        print(f"测试失败: {e}")