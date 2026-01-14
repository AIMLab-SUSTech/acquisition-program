import time
from pylablib.devices import SmarAct
from abc import ABC, abstractmethod


class MotionController(ABC):
    def __init__(self):
        super().__init__()

    @abstractmethod
    def move_by(self, distance: float, axis: int):
        """相对移动: distance (mm), axis (0=X, 1=Y)"""
        pass

    @abstractmethod
    def move_to(self, position: float, axis: int):
        """绝对移动: position (mm), axis (0=X, 1=Y)"""
        pass

    @abstractmethod
    def get_position(self, axis: int) -> float:
        """获取当前位置: return mm"""
        pass


class smartact(MotionController):
    def __init__(self):
        super().__init__()
        try:
            from pylablib.devices import SmarAct
            devices = SmarAct.list_msc2_devices()
            if not devices:
                print('SmartAct: 未找到设备')
                self.motion = None
            else:
                print(f'SmartAct: 连接到 {devices[0]}')
                self.motion = SmarAct.MCS2(devices[0])
        except Exception as e:
            print(f'SmartAct 初始化失败: {e}')
            self.motion = None

    def move_by(self, distance, axis=0):
        if self.motion:
            # SmartAct 单位通常是米，这里做 mm -> m 转换
            self.motion.move_by(distance / 1000.0, axis=axis)

    def move_to(self, position, axis=0):
        if self.motion:
            self.motion.move_to(position / 1000.0, axis=axis)

    def get_position(self, axis=0):
        if self.motion:
            return self.motion.get_position(axis) * 1000.0
        return 0.0

    def home(self, axis=0):
        if self.motion:
            self.motion.home(axis=axis)

class xps(MotionController):
    def __init__(self, IP='192.168.0.254'):
        super().__init__()
        self.xps = None
        self.groups = []
        try:
            from newportxps import NewportXPS
            # 注意: 用户名密码通常是 Administrator
            self.xps = NewportXPS(IP, username='Administrator', password='Administrator')
            print(f"XPS: 已连接到 {IP}")
        except Exception as e:
            print(f'XPS 初始化失败: {e}')

    def init_groups(self, group_list=[]):
        # """初始化轴组"""
        if not self.xps: return
        self.groups = []
        
        # 获取所有组的状态
        try:
            status = self.xps.get_group_status()
        except Exception as e:
            print(f"获取状态列表失败: {e}")
            status = {}

        for g in group_list:
            # 1. 判断是否已经 Ready 
            if status.get(g, '').startswith('Ready'):
                print(f"轴组 {g} 已经是 Ready 状态，跳过初始化，保持当前位置。")
                self.groups.append(g)
            
            # 2. 如果没 Ready，再执行那一套繁琐的流程
            else:
                print(f"轴组 {g} 未就绪 (状态: {status.get(g, '')})，开始初始化...")
                try:
                    self.xps.kill_group(g) # 先强制关闭
                    self.xps.initialize_group(g) # 再初始化
                    self.xps.home_group(g)
                    self.groups.append(g)
                    print(f"XPS: {g} 初始化完成")
                except Exception as e:
                    # 这里捕获了 system.ini 错误，防止程序崩溃
                    print(f"XPS: {g} 初始化失败: {e}, 尝试强制加入列表")
                    self.groups.append(g)

    def _get_stage_name(self, axis):
        """内部辅助: 获取 Group.Pos 字符串"""
        if 0 <= axis < len(self.groups):
            return f'{self.groups[axis]}.Pos'
        return None

    def move_by(self, distance, axis):
        stage = self._get_stage_name(axis)
        if stage and self.xps:
            # relative=True 代表相对移动
            self.xps.move_stage(stage, distance, relative=True)

    def move_to(self, position, axis):
        stage = self._get_stage_name(axis)
        if stage and self.xps:
            # relative=False 代表绝对移动
            self.xps.move_stage(stage, position, relative=False)

    def get_position(self, axis):
        stage = self._get_stage_name(axis)
        if stage and self.xps:
            return self.xps.get_stage_position(stage)
        return 0.0

    def status_report(self):
        return self.xps.status_report()

    def set_velocity(self, stage: str = None, velocity: int = 2.5, acceleration: int = None, min_jerktime: int = None,
                     max_jerktime: int = None):
        self.xps.set_velocity(stage, velocity, acceleration, min_jerktime, max_jerktime)


import ctypes
from ctypes import create_string_buffer, c_uint


class nators(MotionController):
    def __init__(self):
        super().__init__()
        dll_path = 'C:/Windows/System32/NTControl.dll'
        self._x = 0.0  # 【新增】防止报错
        self._y = 0.0  # 【新增】防止报错
        # 加载 DLL
        try:
            self.stage_dll = ctypes.CDLL(dll_path)
            print(f"成功加载 DLL: {dll_path}")
        except Exception as e:
            print(f"加载 DLL 时发生错误: {e}")
            self.stage_dll = None

        # 定义 C 数据类型
        self.NT_STATUS = ctypes.c_int
        self.NT_INDEX = ctypes.c_uint

        # 设置 NT_GotoPositionRelative_S 函数的参数类型
        if self.stage_dll:
            self.stage_dll.NT_GotoPositionRelative_S.argtypes = [
                self.NT_INDEX,  # systemIndex
                self.NT_INDEX,  # channelIndex
                ctypes.c_int  # diff
            ]

            self.stage_dll.NT_GotoPositionRelative_S.restype = self.NT_STATUS

        self.system_index = None

    def get_position(self, axis):
        return self._x if axis == 0 else self._y

    def open_system(self, system_locator='usb:id:0685782677', options="sync"):
        """打开系统并返回系统索引"""
        try:
            system_index = self.NT_INDEX(0)
            options_encoded = options.encode('utf-8')

            result = self.stage_dll.NT_OpenSystem(
                ctypes.byref(system_index),
                system_locator.encode('utf-8'),
                options_encoded
            )

            if result == 0:
                self.system_index = system_index.value
                print(f"成功连接到系统: {system_locator}")
                return self.system_index
            else:
                print(f"Error: Failed to open system, result code {result}")
                return None
        except Exception as e:
            print(f"在打开系统时发生错误: {e}")
            return None

    def close_system(self):
        try:
            result = self.stage_dll.NT_CloseSystem(self.NT_INDEX(self.system_index))
            if result == 0:
                self.system_index = None
            return result
        except Exception as e:
            print(f"在关闭系统时发生错误: {e}")
            return None

    def call_nt_find_systems(self, options=""):
        """查找可用系统并返回系统定位符列表"""
        try:
            options_encoded = options.encode('utf-8')

            out_buffer_size = 4096
            out_buffer = create_string_buffer(out_buffer_size)

            io_buffer_size = c_uint(out_buffer_size)

            result = self.stage_dll.NT_FindSystems(options_encoded, out_buffer, ctypes.byref(io_buffer_size))

            actual_size = io_buffer_size.value

            result_data = out_buffer.raw[:actual_size]
            print(f"成功找到系统: {result_data}")
            return result_data
        except Exception as e:
            print(f"查找系统时发生错误: {e}")
            return None

    def move_by(self, distance, axis):
        """ input:distance(mm)
            channel(正放): 2 垂直方向 1 水平方向 0 前后方向 """

        channel = [1, 2, 0]
        try:
            if self.system_index is None:
                print("系统未打开，无法移动")
                return

            diff_nanometers = int(distance * 1e6)

            result = self.stage_dll.NT_GotoPositionRelative_S(self.system_index, channel[axis],
                                                              ctypes.c_int(diff_nanometers))

            if result == 0:
                print(f"成功将通道 {channel[axis]} 移动 {distance} 毫米")
            else:
                print(f"错误: 无法移动通道 {channel[axis]}，错误代码: {result}")
        except Exception as e:
            print(f"移动定位台时发生错误: {e}")


if __name__ == "__main__":
    a = xps()
    a.init_groups(['Group3', 'Group4'])
    a.move_by(0.1, 0)
    # print(a.status_report())
    # a.kill_all_groups()
