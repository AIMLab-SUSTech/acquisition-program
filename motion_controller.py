import time
from pylablib.devices import SmarAct
from abc import ABC, abstractmethod


class MotionController(ABC):
    def __init__(self):
        super().__init__()

    @abstractmethod
    def move_by(self, distance, axis):
        """移动指定轴。移动命令下发失败时必须抛出异常（不允许静默吞掉）。"""
        pass

    def wait_idle(self, timeout=30.0):
        """等待所有轴停止移动。返回 True 表示已静止，False 表示超时。"""
        raise NotImplementedError('wait_idle not implemented')

    def stop_all(self):
        """停止所有轴移动。"""
        raise NotImplementedError('stop_all not implemented')


class smartact(MotionController):
    def __init__(self):
        super().__init__()
        device = SmarAct.list_msc2_devices()
        if len(device) == 0:
            print('没有位移台')
        else:
            print(device[0])
            self.motion = SmarAct.MCS2(device[0])

    def home(self, axis=0):
        self.motion.home(axis=axis)

    def move_by(self, distance, axis=0):
        # pylablib 的 move_by 内部失败即抛异常，向上传播给调用方
        self.motion.move_by(distance / 1000, axis=axis)

    def wait_idle(self, timeout=30.0):
        try:
            self.motion.wait_move('all', timeout=timeout)
            return True
        except Exception:
            return False

    def stop_all(self):
        if self.motion.is_moving(axis=0):
            self.motion.stop(axis=0)
        if self.motion.is_moving(axis=1):
            self.motion.stop(axis=1)


class xps(MotionController):
    def __init__(self, IP='192.168.254.254', username: str = 'Administrator', password: str = 'Administrator',
                 port: int = 5001) -> None:
        super().__init__()
        try:
            global NewportXPS
            from newportxps import NewportXPS
            self.xps = NewportXPS(IP, username=username, password=password, port=port)
            self.groups = []
        except Exception as e:
            print(f'XPS 初始化失败{e}')

    def init_groups(self, groups: list = []):
        try:
            if groups:
                for i in groups:
                    self.xps.initialize_group(i)
                    time.sleep(0.5)
                    self.xps.home_group(i)
                    self.groups.append(i)
        except Exception as e:
            print(f'初始化xps异常，请检查是否重复初始化:{e}')
            # 初始化失败时不登记组，保证后续 move_by 显式报错而不是静默无效
            self.groups = []

    def init_all_groups(self):
        self.xps.initialize_allgroups()

    def stop_all(self):
        for group in self.groups:
            self.xps.kill_group(group)

    def move_by(self, distance: int, axis: int, relative: bool = True):
        if axis >= len(self.groups):
            raise RuntimeError(f'xps轴序号越界：axis={axis}，已初始化组={self.groups}')
        # 失败时抛出异常，由调用方决定是否中止扫描
        self.xps.move_stage(value=distance, stage=f'{self.groups[axis]}.Pos', relative=relative)

    def wait_idle(self, timeout=30.0, poll_interval=0.05):
        """轮询各组状态字符串，直到不含 'Moving'（不区分大小写）。超时返回 False。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                status = self.xps.get_group_status()
            except Exception:
                time.sleep(poll_interval)
                continue
            if not any('mov' in str(status.get(g, '')).lower() for g in self.groups):
                return True
            time.sleep(poll_interval)
        return False

    def status_report(self):
        return self.xps.status_report()

    def set_velocity(self, stage: str = None, velocity: int = 2.5, acceleration: int = None, min_jerktime: int = None,
                     max_jerktime: int = None):
        self.xps.set_velocity(stage, velocity, acceleration, min_jerktime, max_jerktime)


import ctypes
from ctypes import create_string_buffer, c_uint


class nators(MotionController):
    def __init__(self, settle_time=1.0):
        super().__init__()
        # NTControl 封装未暴露运动状态查询，wait_idle 用固定沉降时间代替
        self.settle_time = settle_time
        dll_path = 'C:/Windows/System32/NTControl.dll'
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
        if self.system_index is None:
            raise RuntimeError("nators系统未打开，无法移动")

        diff_nanometers = int(distance * 1e6)

        result = self.stage_dll.NT_GotoPositionRelative_S(self.system_index, channel[axis],
                                                          ctypes.c_int(diff_nanometers))

        if result != 0:
            raise RuntimeError(f"nators移动失败：通道 {channel[axis]}，错误代码 {result}")
        print(f"成功将通道 {channel[axis]} 移动 {distance} 毫米")

    def wait_idle(self, timeout=30.0):
        # NTControl 封装未暴露运动状态查询，用固定沉降时间代替（保守值，可在构造时调整）
        time.sleep(min(self.settle_time, timeout))
        return True


if __name__ == "__main__":
    a = xps()
    a.init_groups(['Group3', 'Group4'])
    a.move_by(0.1, 0)
    # print(a.status_report())
    # a.kill_all_groups()
