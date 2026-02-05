from PyQt6.QtCore import QThread, pyqtSignal

class DeviceLoader(QThread):
    """
    负责后台加载硬件驱动，防止界面卡死。
    支持传入 extra_configs 字典来配置特定硬件（如 XPS Group）。
    """
    finished_signal = pyqtSignal(bool, object)

    def __init__(self, device_type, device_name, extra_configs=None):
        super().__init__()
        self.device_type = device_type 
        self.device_name = device_name
        self.configs = extra_configs if extra_configs else {}

    def run(self):
        try:
            device_instance = None
            
            # --- 相机加载逻辑 ---
            if self.device_type == 'camera':
                match(self.device_name):
                    case "IDS":
                        from camera import IDS
                        device_instance = IDS()
                        device_instance.set_pixel_rate(7e7)
                    case "Ham":
                        from camera import Ham
                        device_instance = Ham()
                    case "Lucid":
                        from lucid import LucidCamera
                        device_instance = LucidCamera(max_tries=1, wait_time=1)
                    case "PM":
                        from photometrics import PyVCAM
                        device_instance = PyVCAM() 
                    case "IDS_Peak":
                        from peak import IDSPeakCamera
                        device_instance = IDSPeakCamera()
                    case "PI-mte3":
                        from pi_camera import PICamera                        
                        device_instance = PICamera()
                    case "VSY":
                        from new_vsy_camera import NewVSYCamera                     
                        device_instance = NewVSYCamera()
                    case "Galaxy":
                        from camera import GalaxyCamera                        
                        device_instance = GalaxyCamera()
                    case "QHY":
                        from QHY import QHYCamera
                        device_instance = QHYCamera()
                        device_instance.set_bit_depth(16)
            
            # --- 位移台加载逻辑 ---
            elif self.device_type == 'stage':
                match(self.device_name):
                    case "NewPort":
                        from motion_controller import xps
                        # 从配置中读取 IP，如果没有则默认
                        ip = self.configs.get('ip', '192.168.0.254')
                        device_instance = xps(IP=ip)
                        
                        # 关键：从入口文件传递进来的 Group 配置
                        groups = self.configs.get('xps_groups', ['Group1', 'Group2'])
                        device_instance.init_groups(groups)
                        
                    case "Nators":
                        from motion_controller import nators
                        device_instance = nators(ip_address="192.168.0.254")
                        device_instance.open_system()
                    case "SmartAct":
                        from motion_controller import smartact
                        device_instance = smartact()

            if device_instance:
                self.finished_signal.emit(True, device_instance)
            else:
                self.finished_signal.emit(False, f"未找到驱动: {self.device_name}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.finished_signal.emit(False, str(e))