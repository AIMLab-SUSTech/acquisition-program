import os
import sys
import clr
import time

# ---------------------------------------------------------
# 1. 环境配置与 .NET 引用加载
# (保留原示例文件的底层逻辑)
# ---------------------------------------------------------

# 尝试获取 LightField 根目录，如果环境变量不存在则使用默认路径
lf_root = os.environ.get('LIGHTFIELD_ROOT', r"C:\Program Files\Princeton Instruments\LightField")

if not os.path.exists(lf_root):
    raise FileNotFoundError(f"LightField root directory not found at: {lf_root}")

sys.path.append(lf_root)
sys.path.append(os.path.join(lf_root, "AddInViews"))

# 加载 Princeton Instruments 的 .NET 程序集
try:
    clr.AddReference('PrincetonInstruments.LightFieldViewV5')
    clr.AddReference('PrincetonInstruments.LightField.AutomationV5')
    clr.AddReference('PrincetonInstruments.LightFieldAddInSupportServices')
    
    # 引入 .NET 系统类型
    from System import String, Int32, Double, Boolean
    from System.Collections.Generic import List
    from System.IO import Path

    # 引入 PI 命名空间
    from PrincetonInstruments.LightField.Automation import Automation
    from PrincetonInstruments.LightField.AddIns import (
        ExperimentSettings, 
        CameraSettings, 
        DeviceType, 
        RegionOfInterest,
        SensorTemperatureStatus
    )
except Exception as e:
    print("Error loading LightField DLLs. Make sure LightField is installed.")
    raise e

# ---------------------------------------------------------
# 2. LightField 控制器类 (模仿 uc480.py 的结构)
# ---------------------------------------------------------

class PICamera:
    """
    Princeton Instruments LightField 相机控制器封装类。
    整合了 Acquisition, ROI, Temperature 等功能。
    """

    def __init__(self, visible=True):
        """
        初始化 LightField 自动化对象。
        :param visible: 是否显示 LightField 界面 (True/False)
        """
        print("正在连接 LightField Automation...")
        # 对应 multiple_roi.py 等文件中的初始化逻辑
        self.auto = Automation(visible, List[String]())
        self.application = self.auto.LightFieldApplication
        self.experiment = self.application.Experiment
        
        self._validate_device()
        print("LightField 连接成功且设备就绪。")

    def _validate_device(self):
        """检查是否连接了相机 (对应 device_found 逻辑)"""
        found = False
        for device in self.experiment.ExperimentDevices:
            if device.Type == DeviceType.Camera:
                found = True
                print(f"发现相机: {device.Model} ({device.SerialNumber})")
                break
        
        if not found:
            print("警告: 当前实验中未发现相机。")

    def shutdown(self):
        """关闭连接 (如有必要，通常 Automation 会自动处理)"""
        # LightField Automation 通常不需要显式 Dispose，但在脚本结束时可以做清理
        pass

    # --- 基础参数设置 (对应 settings.py / exposure_acquire.py) ---

    def set_exposure(self, exposure_ms):
        """设置曝光时间 (毫秒)"""
        if self.experiment.Exists(CameraSettings.ShutterTimingExposureTime):
            self.experiment.SetValue(
                CameraSettings.ShutterTimingExposureTime, 
                Double(exposure_ms)
            )
            print(f"曝光时间已设置为: {exposure_ms} ms")
        else:
            print("错误: 当前设备不支持设置曝光时间。")

    def get_exposure(self):
        """获取当前曝光时间"""
        if self.experiment.Exists(CameraSettings.ShutterTimingExposureTime):
            return self.experiment.GetValue(CameraSettings.ShutterTimingExposureTime)
        return None

    # --- ROI 设置 (对应 multiple_roi.py) ---

    def set_roi(self, x, y, width, height, x_binning=1, y_binning=1):
        """
        设置单一的自定义感兴趣区域 (ROI)。
        :param x: 起始 X
        :param y: 起始 Y
        :param width: 宽度
        :param height: 高度
        :param x_binning: X 方向合并
        :param y_binning: Y 方向合并
        """
        # 获取传感器全尺寸以进行校验 (可选)
        full_region = self.experiment.FullSensorRegion
        
        # 创建 ROI 列表
        regions = List[RegionOfInterest]()
        
        new_roi = RegionOfInterest(
            Int32(x), Int32(y), 
            Int32(width), Int32(height), 
            Int32(x_binning), Int32(y_binning)
        )
        regions.Add(new_roi)
        
        self.experiment.SetCustomRegions(regions)
        print(f"ROI 已设置: [{x}, {y}, {width}x{height}], Binning: {x_binning}x{y_binning}")

    def set_full_roi(self):
        """重置为全画幅"""
        self.experiment.SetFullSensorRegion()
        print("ROI 已重置为全传感器区域。")

    # --- 温度控制 (对应 temperature.py) ---

    def set_temperature(self, target_temp):
        """
        设置目标温度 (摄氏度)。
        """
        if self.experiment.Exists(CameraSettings.SensorTemperatureSetPoint):
            # 只有在非采集状态下才能设置
            if self.experiment.IsReadyToRun and not self.experiment.IsRunning:
                self.experiment.SetValue(
                    CameraSettings.SensorTemperatureSetPoint,
                    Double(target_temp)
                )
                print(f"温度设定点已设置为: {target_temp} C")
            else:
                print("无法设置温度: 系统正在运行或未准备就绪。")
        else:
            print("当前设备不支持温度控制。")

    def get_temperature_status(self):
        """
        获取当前温度和锁定状态。
        :return: (current_temp, status_string)
        """
        current_temp = -999.0
        status_str = "Unknown"

        if self.experiment.Exists(CameraSettings.SensorTemperatureReading):
            current_temp = self.experiment.GetValue(CameraSettings.SensorTemperatureReading)
        
        if self.experiment.Exists(CameraSettings.SensorTemperatureStatus):
            status_enum = self.experiment.GetValue(CameraSettings.SensorTemperatureStatus)
            status_str = "Locked" if status_enum == SensorTemperatureStatus.Locked else "Unlocked/Error"

        print(f"当前温度: {current_temp:.2f} C ({status_str})")
        return current_temp, status_str

    # --- 文件与采集 (对应 acquisition_filename.py) ---

    def configure_save_settings(self, directory, filename, increment=True, add_date=False):
        """
        配置文件保存路径和命名规则。
        """
        # 设置目录
        self.experiment.SetValue(ExperimentSettings.FileNameGenerationDirectory, String(directory))
        
        # 设置基础文件名
        self.experiment.SetValue(ExperimentSettings.FileNameGenerationBaseFileName, String(filename))
        
        # 设置是否自动递增
        self.experiment.SetValue(ExperimentSettings.FileNameGenerationAttachIncrement, Boolean(increment))
        
        # 设置是否附加日期时间
        self.experiment.SetValue(ExperimentSettings.FileNameGenerationAttachDate, Boolean(add_date))
        self.experiment.SetValue(ExperimentSettings.FileNameGenerationAttachTime, Boolean(add_date)) # 简单起见，同开同关
        
        print(f"文件保存设置已更新: {os.path.join(directory, filename)}")

    def acquire(self):
        """
        执行采集。
        """
        print("开始采集...")
        if self.experiment.IsReadyToRun:
            self.experiment.Acquire()
            print("采集指令已发送。")
            # 注意: Acquire 是异步的，脚本可能会立即继续。
            # 如果需要等待完成，可以使用 Event Handler (如 spe_file_access.py 所示)
            # 或者简单的轮询 IsRunning (不推荐用于复杂逻辑，但简单脚本可用)
        else:
            print("错误: 实验未准备就绪 (System Not Ready)。")

    def wait_for_acquisition(self):
        """
        简单的阻塞等待采集完成 (轮询方式，简化版)。
        更高级的方式是使用 IsRunningChanged 事件。
        """
        while self.experiment.IsRunning:
            time.sleep(0.1)
        print("采集完成。")


# ---------------------------------------------------------
# 3. 使用示例 (Main)
# ---------------------------------------------------------

if __name__ == "__main__":
    # 示例：如何调用这个封装类
    
    # 1. 实例化
    cam = PICamera(visible=True)
    
    # 2. 读取温度
    cam.get_temperature_status()
    # cam.set_temperature(-20) 
    
    # 3. 设置参数
    cam.set_exposure(50)  # 50ms
    
    # 4. 设置 ROI (例如中心区域 512x512)
    # 假设原图是 1024x1024
    cam.set_roi(x=256, y=256, width=512, height=512)
    
    # 5. 配置文件保存
    save_dir = r"C:\Data\Test"
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
        
    cam.configure_save_settings(
        directory=save_dir, 
        filename="MyData_Integrated", 
        increment=True
    )
    
    # 6. 采集
    cam.acquire()
    cam.wait_for_acquisition()
    
    print("演示结束。")