import sys
import os
import time
import numpy as np
import h5py
import datetime
import clr  # 需要 pip install pythonnet

# --- 导入你的自定义模块 ---
try:
    from motion_controller import xps
    from Scanner import Scanner
except ImportError as e:
    print(f"错误: 找不到依赖文件 ({e})。请确保 Scanner.py 和 motion_controller.py 在同一目录下。")
    sys.exit(1)

# ==============================================================================
#  1. 全局配置 (CONFIG)
# ==============================================================================
CONFIG = {
    # --- 文件保存 ---
    "save_dir": r"D:\Experiment_Data",   # 数据保存路径
    "filename_prefix": "scan_matrix",    # 文件名前缀
    
    # --- 扫描参数 (Scanner) ---
    "scan_range_x": 0.5,    # 扫描范围 X (mm)
    "scan_range_y": 0.5,    # 扫描范围 Y (mm)
    "step_size": 0.1,       # 步长 (mm)
    "scan_mode": "rectangle", # 'rectangle', 'round', 'fermat'
    
    # --- 运动控制 (XPS) ---
    "xps_ip": "192.168.0.254",    # XPS IP地址
    "xps_groups": ['Group3', 'Group4'], # [X轴, Y轴]
    "settle_time": 0.2,     # 移动后稳定时间(秒)
    
    # --- 相机参数 ---
    "exposure_time": 20.0,  # 曝光时间 (ms)
    "temperature": -20.0,   # 制冷温度
}

# ==============================================================================
#  2. 相机驱动封装 (PI LightField)
# ==============================================================================
class PICameraDriver:
    def __init__(self):
        self.experiment = None
        print("[Camera] 正在连接 LightField...")
        try:
            # 获取 LightField 路径
            lf_root = os.environ.get('LIGHTFIELD_ROOT', r"C:\Program Files\Princeton Instruments\LightField")
            sys.path.append(lf_root)
            sys.path.append(os.path.join(lf_root, "AddInViews"))
            
            # 加载 DLL
            clr.AddReference('PrincetonInstruments.LightFieldViewV5')
            clr.AddReference('PrincetonInstruments.LightField.AutomationV5')
            clr.AddReference('PrincetonInstruments.LightFieldAddInSupportServices')
            
            from PrincetonInstruments.LightField.Automation import Automation
            from System.Collections.Generic import List
            from System import String
            
            self.auto = Automation(True, List[String]())
            self.experiment = self.auto.LightFieldApplication.Experiment
            
            # 引入枚举
            from PrincetonInstruments.LightField.AddIns import CameraSettings, RegionOfInterest
            self.CameraSettings = CameraSettings
            self.RegionOfInterest = RegionOfInterest
            
            print("[Camera] 连接成功")
            
        except Exception as e:
            print(f"[Camera] 初始化失败: {e}")
            self.experiment = None

    def set_exposure(self, ms):
        if self.experiment and self.experiment.Exists(self.CameraSettings.ShutterTimingExposureTime):
            self.experiment.SetValue(self.CameraSettings.ShutterTimingExposureTime, float(ms))

    def set_temperature(self, temp):
        if self.experiment and self.experiment.Exists(self.CameraSettings.SensorTemperatureSetPoint):
            self.experiment.SetValue(self.CameraSettings.SensorTemperatureSetPoint, float(temp))

    def snap(self):
        """采集并返回 numpy 数组"""
        if not self.experiment: return None
        try:
            # Capture(1) 采集 1 帧
            dataset = self.experiment.Capture(1)
            if dataset is None: return None
            
            frame = dataset.GetFrame(0, 0)
            raw_data = frame.GetData() # System.UInt16[]
            
            # 转换为 Numpy
            h, w = frame.Height, frame.Width
            img = np.fromiter(raw_data, dtype=np.uint16).reshape((h, w))
            
            dataset.Dispose()
            return img
        except Exception as e:
            print(f"[Camera] 采集错误: {e}")
            return None

    def close(self):
        pass

# ==============================================================================
#  3. 主实验逻辑
# ==============================================================================
def run_scan():
    # --- 1. 初始化硬件 ---
    print("\n=== 初始化硬件 ===")
    
    # 连接 XPS
    # 注意：motion_controller.py 里的 xps 类需要 IP
    stage = xps(IP=CONFIG['xps_ip'])
    stage.init_groups(CONFIG['xps_groups'])
    
    # 连接 相机
    cam = PICameraDriver()
    cam.set_exposure(CONFIG['exposure_time'])
    cam.set_temperature(CONFIG['temperature'])
    
    # --- 2. 初始化 Scanner ---
    print("\n=== 生成路径 ===")
    # Scanner(step, range_x, range_y, mode...)
    scanner = Scanner(
        step=CONFIG['step_size'],
        scan_range_x=CONFIG['scan_range_x'],
        scan_range_y=CONFIG['scan_range_y'],
        mode=CONFIG['scan_mode']
    )
    
    total_points = len(scanner.abs_x)
    print(f"扫描模式: {CONFIG['scan_mode']}")
    print(f"总点数: {total_points}")

    # --- 3. 记录起始位置 (用于归位) ---
    try:
        # 获取当前物理位置作为原点
        # Axis 0 -> Group3, Axis 1 -> Group4
        start_x_phys = stage.get_position(0)
        start_y_phys = stage.get_position(1)
        print(f"当前起点: X={start_x_phys:.4f}, Y={start_y_phys:.4f}")
    except Exception as e:
        print(f"无法获取起始位置: {e}")
        return

    # 数据缓存
    buffer_imgs = []
    buffer_real_x = [] # 存储 XPS 返回的真实位置
    buffer_real_y = []

    print("\n=== 开始扫描 ===")
    start_time = time.time()

    try:
        for i in range(total_points):
            # 1. 计算目标绝对坐标
            # Scanner 生成的是相对起点的绝对偏移量 (abs_x)，我们需要加上物理起点
            target_x = start_x_phys + scanner.abs_x[i]
            target_y = start_y_phys + scanner.abs_y[i]
            
            # 2. 移动位移台 (绝对移动)
            stage.move_to(target_x, axis=0)
            stage.move_to(target_y, axis=1)
            
            # 3. 等待稳定
            time.sleep(CONFIG['settle_time'])
            
            # 4. 【关键】读取实际物理位置
            real_x = stage.get_position(0)
            real_y = stage.get_position(1)
            
            # 5. 相机采集
            img = cam.snap()
            
            if img is not None:
                buffer_imgs.append(img)
                buffer_real_x.append(real_x)
                buffer_real_y.append(real_y)
            else:
                print(f"[警告] 第 {i} 点采集失败")

            # 进度打印
            if (i+1) % 5 == 0:
                print(f"进度: {i+1}/{total_points} | 当前位置: ({real_x:.3f}, {real_y:.3f})")

    except KeyboardInterrupt:
        print("\n[中断] 用户停止扫描！准备保存已有数据...")
    except Exception as e:
        print(f"\n[错误] 扫描出错: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # --- 4. 实验结束/中断后的处理 ---
        print("\n=== 正在归位 (Return to Origin) ===")
        try:
            # 回到扫描前的起点
            stage.move_to(start_x_phys, axis=0)
            stage.move_to(start_y_phys, axis=1)
            print(f"已回到起点: ({start_x_phys:.4f}, {start_y_phys:.4f})")
        except Exception as e:
            print(f"归位失败: {e}")

        # --- 5. 保存数据 (H5) ---
        if len(buffer_imgs) > 0:
            save_data_h5(buffer_imgs, buffer_real_x, buffer_real_y)
        else:
            print("没有有效数据需要保存。")
            
        # 释放资源
        cam.close()

def save_data_h5(images, pos_x, pos_y):
    """统一保存数据到 H5"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = os.path.join(CONFIG['save_dir'], f"{CONFIG['filename_prefix']}_{timestamp}")
    
    if not os.path.exists(folder):
        os.makedirs(folder)
        
    h5_path = os.path.join(folder, "scan_data.h5")
    
    print(f"\n正在写入文件: {h5_path} ...")
    try:
        with h5py.File(h5_path, 'w') as f:
            # 写入图片数据 (uint16)
            f.create_dataset("images", data=np.array(images, dtype=np.uint16), compression="gzip")
            
            # 写入 XPS 返回的真实位置
            f.create_dataset("x_actual", data=np.array(pos_x))
            f.create_dataset("y_actual", data=np.array(pos_y))
            
            # 写入实验元数据
            f.attrs['exposure_ms'] = CONFIG['exposure_time']
            f.attrs['timestamp'] = timestamp
            f.attrs['scan_mode'] = CONFIG['scan_mode']
            
        print("保存完成！")
        
        # 可选：保存第一张图作为预览 PNG
        try:
            from PIL import Image
            preview_path = os.path.join(folder, "preview_first_frame.png")
            img_vis = (images[0] / 256).astype(np.uint8) # 简单压缩用于预览
            Image.fromarray(img_vis).save(preview_path)
            print(f"生成预览图: {preview_path}")
        except:
            pass
            
    except Exception as e:
        print(f"保存 H5 失败: {e}")

if __name__ == "__main__":
    run_scan()