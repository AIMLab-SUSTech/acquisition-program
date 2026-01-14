from abc import ABC, abstractmethod
import ctypes
from ctypes import create_string_buffer, c_uint

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
    def __init__(self, IP='192.168.0.254', username='Administrator', password='Administrator'):
        super().__init__()
        self.xps = None
        self.groups = []
        self._xps = None
        self._sid = None
        self.host = IP
        self.username = username
        self.password = password
        self.port = 5001
        self.timeout = 10
        
        try:
            from newportxps.XPS_C8_drivers import XPS
            self._xps = XPS()
            # 直接通过 TCP 连接到服务器，绕过 SFTP
            self._sid = self._xps.TCP_ConnectToServer(self.host, self.port, self.timeout)
            if self._sid < 0:
                print(f"XPS 连接失败: 无效的 socket ID {self._sid}")
                self._sid = None
            else:
                try:
                    err, msg = self._xps.Login(self._sid, self.username, self.password)
                    if err != 0:
                        print(f"XPS 登录失败: 错误码 {err}, {msg}")
                        self._sid = None
                    else:
                        print(f"XPS: 已连接到 {IP}")
                except Exception as e:
                    print(f"XPS 登录失败: {e}")
                    self._sid = None
        except Exception as e:
            print(f'XPS 连接失败: {e}')
            self._xps = None
            self._sid = None

    def init_groups(self, group_list=[]):
        """初始化轴组"""
        if not self._xps or self._sid is None:
            return
        
        self.groups = []
        
        # 直接添加用户指定的轴组，不依赖于 system.ini
        for g in group_list:
            self.groups.append(g)
            print(f"已手动加载轴组: {g}")
            
            # 尝试初始化轴组
            print(f"尝试初始化轴组 {g}...")
            try:
                # 1. 先 Kill 轴组
                kill_result = self._xps.GroupKill(self._sid, g)
                if kill_result[0] != 0:
                    print(f"XPS Kill 轴组 {g} 失败: 错误码 {kill_result[0]}, {kill_result[1]}")
                
                # 2. 初始化轴组
                init_result = self._xps.GroupInitialize(self._sid, g)
                if init_result[0] != 0:
                    print(f"XPS 初始化轴组 {g} 失败: 错误码 {init_result[0]}, {init_result[1]}")
                
                # 3. 执行 Home Search
                home_result = self._xps.GroupHomeSearch(self._sid, g)
                if home_result[0] != 0:
                    print(f"XPS Home Search 轴组 {g} 失败: 错误码 {home_result[0]}, {home_result[1]}")
                
                print(f"XPS 轴组 {g} 初始化完成")
            except Exception as e:
                print(f"XPS 轴组 {g} 初始化失败: {e}")

    def move_by(self, distance, axis):
        """相对移动：通过计算绝对坐标实现"""
        if axis < 0 or axis >= len(self.groups):
            return
        
        group_name = self.groups[axis]
        if not self._xps or self._sid is None:
            return
        
        try:
            # 1. 检查轴组状态
            status_result = self._xps.GroupStatusGet(self._sid, group_name)
            if status_result[0] != 0:
                print(f"XPS 获取组状态失败 (Axis {axis}): 错误码 {status_result[0]}")
                # 尝试初始化轴组
                print(f"尝试初始化轴组 {group_name}...")
                self._xps.GroupKill(self._sid, group_name)
                self._xps.GroupInitialize(self._sid, group_name)
                self._xps.GroupHomeSearch(self._sid, group_name)
            
            # 2. 获取当前位置（假设每个组只有一个 positioner）
            pos_result = self._xps.GroupPositionCurrentGet(self._sid, group_name, 1)
            if pos_result[0] != 0:
                print(f"XPS 获取位置失败 (Axis {axis}): 错误码 {pos_result[0]}")
                return
            # 3. 检查当前位置是否为 None 或空列表
            if len(pos_result) < 2 or pos_result[1] is None:
                print(f"XPS: 无法获取 {group_name} 的当前位置，跳过移动")
                return
            current_pos = pos_result[1]
            # 4. 计算目标位置
            target_pos = current_pos + distance
            # 5. 执行移动
            move_result = self._xps.GroupMoveAbsolute(self._sid, group_name, [target_pos])
            if move_result[0] != 0:
                print(f"XPS 移动失败 (Axis {axis}): 错误码 {move_result[0]}, {move_result[1]}")
        except Exception as e:
            print(f"XPS 相对移动失败 (Axis {axis}): {e}")

    def move_to(self, position, axis):
        """绝对移动"""
        if axis < 0 or axis >= len(self.groups):
            return
        
        group_name = self.groups[axis]
        if not self._xps or self._sid is None:
            return
        
        try:
            move_result = self._xps.GroupMoveAbsolute(self._sid, group_name, [position])
            if move_result[0] != 0:
                print(f"XPS 移动失败 (Axis {axis}): 错误码 {move_result[0]}, {move_result[1]}")
        except Exception as e:
            print(f"XPS 绝对移动失败 (Axis {axis}): {e}")

    def get_position(self, axis):
        """获取当前位置"""
        if axis < 0 or axis >= len(self.groups):
            return 0.0
        
        group_name = self.groups[axis]
        if not self._xps or self._sid is None:
            return 0.0
        
        try:
            pos_result = self._xps.GroupPositionCurrentGet(self._sid, group_name, 1)
            if pos_result[0] != 0:
                print(f"XPS 读取位置失败 (Axis {axis}): 错误码 {pos_result[0]}")
                return 0.0
            # 检查返回值是否为 None 或空列表
            if len(pos_result) < 2 or pos_result[1] is None:
                print(f"XPS: {group_name} 位置为 None，返回默认值 0.0")
                return 0.0
            return pos_result[1]
        except Exception as e:
            print(f"XPS 读取位置失败 (Axis {axis}): {e}")
        return 0.0

    def status_report(self):
        """返回状态报告"""
        if not self._xps or self._sid is None:
            return {}
        
        try:
            err, uptime = self._xps.ElapsedTimeGet(self._sid)
            if err != 0:
                print(f"获取运行时间失败: 错误码 {err}")
                uptime = 0
            
            err, firmware = self._xps.FirmwareVersionGet(self._sid)
            if err != 0:
                print(f"获取固件版本失败: 错误码 {err}")
                firmware = "Unknown"
            
            return {
                "uptime": uptime,
                "firmware": firmware,
                "groups": self.groups
            }
        except Exception as e:
            print(f"获取状态报告失败: {e}")
            return {}

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
