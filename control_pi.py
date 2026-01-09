import sys
import os
import time
import numpy as np
import h5py
import datetime
import clr # 需要 pythonnet 库

# ==============================================================================
#  1. 全局配置 (CONFIG) -在此处修改参数
# ==============================================================================
CONFIG = {
    # --- 保存设置 ---
    "save_dir": r"D:\Experiment_Data",   # 结果保存根目录
    "filename": "scan_sample",    # 文件名前缀
    
    # --- 扫描参数 ---
    "scan_range_x": 0.2,    # X轴扫描范围 (mm)
    "scan_range_y": 0.2,    # Y轴扫描范围 (mm)
    "step_size": 0.1,       # 步长 (mm)
    "settle_time": 0.2,     # 电机移动后的稳定等待时间 (秒)
    
    # --- 相机参数 (LightField) ---
    "exposure_time": 20.0,  # 曝光时间 (ms)
    "temperature": -20.0,   # 目标温度 (摄氏度)
    
    # --- 采集范围 (ROI) ---
    # 格式: [x, y, width, height]
    # 设置为 None 则使用全画幅 (Full Sensor)
    "roi": [0, 0, 1024, 1024], 
    
    # --- XPS 硬件连接 ---
    "xps_ip": "192.168.0.254",
    "xps_port": 5001,
    "group_names": ['Group3', 'Group4'], # [X轴组名, Y轴组名]
}

# ==============================================================================
#  2. 硬件驱动封装
# ==============================================================================

class XPSDriver:
    """
    XPS 位移台控制类
    """
    def __init__(self, ip, port, groups):
        self.ip = ip
        self.groups = groups
        self.connected = False
        
        print(f"[XPS] 正在连接 {ip}...")
        try:
            # -----------------------------------------------------------
            # [填空] 请在此处引入 newportxps 并实例化
            from newportxps import NewportXPS
            self.xps = NewportXPS(ip, port)
            # -----------------------------------------------------------
            self.connected = True
            print("[XPS] 连接成功")
        except Exception as e:
            print(f"[XPS] 连接失败: {e}")

    def move_absolute_blocking(self, x, y):
        """执行绝对移动并阻塞等待"""
        if not self.connected: return

        print(f"[XPS] Move -> X:{x:.3f}, Y:{y:.3f}")
        
        # -----------------------------------------------------------
        # [填空] 硬件移动指令
        self.xps.group_move_absolute(self.groups[0], [x])
        self.xps.group_move_absolute(self.groups[1], [y])
        # -----------------------------------------------------------
        
        # 模拟硬件耗时 (实际请确保驱动是阻塞的，或者在这里加 while is_moving check)
        while self.xps.group_is_moving(self.groups[0]) or self.xps.group_is_moving(self.groups[1]):
            time.sleep(str2num(CONFIG["settle_time"])) 

    def close(self):
        print("[XPS] 断开连接")


class PICameraDriver:
    """
    基于 .NET 的 PI 相机控制
    """
    def __init__(self):
        self.experiment = None
        print("[Camera] 正在连接 PI 相机...")
        
        try:
            # 加载 PI 相机 .NET 库 (复用您提供的逻辑)
            # 确保环境变量 LIGHTFIELD_ROOT 存在，或者硬编码路径
            lf_root = os.environ.get('LIGHTFIELD_ROOT', r"C:\Program Files\Princeton Instruments\LightField")
            sys.path.append(lf_root)
            sys.path.append(os.path.join(lf_root, "AddInViews"))
            
            clr.AddReference('PrincetonInstruments.LightFieldViewV5')
            clr.AddReference('PrincetonInstruments.LightField.AutomationV5')
            clr.AddReference('PrincetonInstruments.LightFieldAddInSupportServices')
            
            from PrincetonInstruments.LightField.Automation import Automation
            from System.Collections.Generic import List
            from System import String
            
            # 初始化 Automation
            self.auto = Automation(True, List[String]())
            self.experiment = self.auto.LightFieldApplication.Experiment
            
            # 引入常用的 Settings 枚举以便后续使用
            from PrincetonInstruments.LightField.AddIns import CameraSettings, RegionOfInterest
            self.CameraSettings = CameraSettings
            self.RegionOfInterest = RegionOfInterest
            
            print("[Camera] LightField 连接成功")
            
        except Exception as e:
            print(f"[Camera] 初始化失败 (请检查 LightField 是否安装): {e}")
            self.experiment = None

    def set_exposure(self, ms):
        if not self.experiment: return
        try:
            #
            if self.experiment.Exists(self.CameraSettings.ShutterTimingExposureTime):
                self.experiment.SetValue(self.CameraSettings.ShutterTimingExposureTime, float(ms))
                print(f"[Camera] 曝光已设定: {ms} ms")
        except Exception as e:
            print(f"[Camera] 设置曝光失败: {e}")

    def set_temperature(self, temp_target):
        if not self.experiment: return
        try:
            #
            if self.experiment.Exists(self.CameraSettings.SensorTemperatureSetPoint):
                self.experiment.SetValue(self.CameraSettings.SensorTemperatureSetPoint, float(temp_target))
                print(f"[Camera] 目标温度已设定: {temp_target} C")
                
                # 可选: 等待温度锁定 (Wait for Lock)
                while self.experiment.GetValue(self.CameraSettings.SensorTemperatureStatus) != SensorTemperatureStatus.Locked:
                    time.sleep(0.5)
                print("[Camera] 温度已锁定")
            else:
                print("[Camera] 警告: 此相机不支持温度控制")
        except Exception as e:
            print(f"[Camera] 设置温度失败: {e}")

    def set_roi(self, roi_list):
        if not self.experiment: return
        try:
            if roi_list is None:
                self.experiment.SetFullSensorRegion()
                print("[Camera] ROI: 全画幅")
            else:
                x, y, w, h = roi_list
                #
                from System.Collections.Generic import List
                regions = List[self.RegionOfInterest]()
                # RegionOfInterest(x, y, w, h, xbin, ybin)
                regions.Add(self.RegionOfInterest(int(x), int(y), int(w), int(h), 1, 1))
                self.experiment.SetCustomRegions(regions)
                print(f"[Camera] ROI 已设定: [{x}, {y}, {w}x{h}]")
        except Exception as e:
            print(f"[Camera] 设置 ROI 失败: {e}")

    def snap(self):
        """采集图像并返回 Numpy 数组"""
        if not self.experiment:
            # 模拟数据用于测试
            return np.random.randint(0, 1000, (100, 100), dtype=np.uint16)
            
        try:
            # 采集
            #
            # 为了获取数据而不是存文件，我们通常需要使用 Capture 或者文件回读
            # 这里为了简单通用，假设我们使用 Capture 接口 (类似 synchronous_acquisition.py)
            
            # 确保设置为 1 帧
            # Capture 返回的是 IImageDataSet
            dataset = self.experiment.Capture(1)
            
            if dataset is None: return None
            
            # 获取第一帧数据 (Frame 0, Region 0)
            frame = dataset.GetFrame(0, 0)
            width = frame.Width
            height = frame.Height
            
            # 将 .NET Array 转为 Python/Numpy
            # 获取原始 buffer
            raw_data = frame.GetData() # 返回 System.UInt16[] (如果是16位)
            
            # 使用 numpy 转换 (零拷贝方式效率最高，但这里用 simple copy 兼容性好)
            np_img = np.fromiter(raw_data, dtype=np.uint16).reshape((height, width))
            
            # 释放资源
            dataset.Dispose()
            
            return np_img
            
        except Exception as e:
            print(f"[Camera] 采集出错: {e}")
            return None

    def close(self):
        # LightField Automation 不需要显式断开，但可以做清理
        pass


# ==============================================================================
#  3. 核心逻辑
# ==============================================================================

def generate_scan_points(range_x, range_y, step):
    """生成蛇形扫描路径"""
    xs = np.arange(0, range_x, step)
    ys = np.arange(0, range_y, step)
    points_x, points_y = [], []
    
    for i, y in enumerate(ys):
        row_xs = xs if i % 2 == 0 else xs[::-1]
        for x in row_xs:
            points_x.append(x)
            points_y.append(y)
    return points_x, points_y

def run_experiment():
    # 1. 准备硬件
    print("\n=== 初始化硬件 ===")
    xps = XPSDriver(CONFIG["xps_ip"], CONFIG["xps_port"], CONFIG["group_names"])
    cam = PICameraDriver()
    
    # 2. 应用配置 (曝光, 温度, ROI)
    print("\n=== 应用配置 ===")
    cam.set_exposure(CONFIG["exposure_time"])
    cam.set_temperature(CONFIG["temperature"])
    cam.set_roi(CONFIG["roi"])
    
    # 3. 准备扫描点
    scan_x, scan_y = generate_scan_points(CONFIG["scan_range_x"], CONFIG["scan_range_y"], CONFIG["step_size"])
    total_points = len(scan_x)
    print(f"\n=== 扫描准备就绪 ===")
    print(f"总点数: {total_points}")
    print(f"内存缓存模式: 开启 (扫描结束后统一写入硬盘)")
    
    # 内存缓存 (Buffer)
    buffer_images = []
    buffer_x = []
    buffer_y = []
    
    start_time = time.time()
    
    try:
        # 4. 扫描循环
        for i in range(total_points):
            tx, ty = scan_x[i], scan_y[i]
            
            # A. 移动
            xps.move_absolute_blocking(tx, ty)
            
            # B. 稳定
            time.sleep(CONFIG["settle_time"])
            
            # C. 采集
            img = cam.snap()
            
            if img is not None:
                # D. 写入缓存 (RAM)
                buffer_images.append(img) # 存入 List
                buffer_x.append(tx)
                buffer_y.append(ty)
            else:
                print(f"[Warn] 第 {i} 点采集失败")

            # 打印进度
            if (i+1) % 10 == 0:
                elapsed = time.time() - start_time
                speed = (i+1) / elapsed
                remaining = (total_points - (i+1)) / speed
                print(f"进度: {i+1}/{total_points} | 速度: {speed:.2f} fps | 剩余: {remaining:.1f} s")

    except KeyboardInterrupt:
        print("\n[Stop] 用户中断扫描！")
    except Exception as e:
        print(f"\n[Error] 发生错误: {e}")
        import traceback
        traceback.print_exc()

    # 5. 统一保存 (Save All at Once)
    if len(buffer_images) > 0:
        print("\n=== 正在写入硬盘 (请勿关闭) ===")
        
        # 准备路径
        full_dir = os.path.join(CONFIG["save_dir"], f"{CONFIG['filename']}")
        if not os.path.exists(full_dir): os.makedirs(full_dir)
        h5_path = os.path.join(full_dir, "data.h5")
        
        try:
            with h5py.File(h5_path, 'w') as f:
                # 转换 List -> Numpy Array (这一步可能消耗大量内存)
                print("正在整理内存数据...")
                np_data = np.array(buffer_images, dtype=np.uint16)
                np_x = np.array(buffer_x, dtype=np.float64)
                np_y = np.array(buffer_y, dtype=np.float64)
                
                print(f"正在写入 H5 (Size: {np_data.nbytes / 1024 / 1024:.2f} MB)...")
                # 创建数据集并写入
                # compression="gzip" 会节省空间但写入稍慢
                f.create_dataset("images", data=np_data, compression="gzip")
                f.create_dataset("pos_x", data=np_x)
                f.create_dataset("pos_y", data=np_y)
                
                # 写入元数据
                f.attrs['exposure'] = CONFIG['exposure_time']
                f.attrs['temperature'] = CONFIG['temperature']
                f.attrs['roi'] = str(CONFIG['roi'])
                
            print(f"保存成功: {h5_path}")
            
        except MemoryError:
            print("[Fatal] 内存不足，无法转换数据数组！建议减小扫描范围或分段保存。")
        except Exception as e:
            print(f"保存文件失败: {e}")
    else:
        print("未采集到有效数据，不保存文件。")

    # 6. 清理
    xps.close()
    cam.close()
    print("程序结束")

if __name__ == "__main__":
    run_experiment()