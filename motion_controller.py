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
    """
    适配 newportxps 2025.1.0 版本的 XPS 控制器类
    主要改进:
    1. 使用高层 NewportXPS 接口，自动读取 system.ini
    2. 使用 stages 字典管理轴组，避免手动初始化
    3. 智能状态检测，只在必要时 home
    """
    def __init__(self, IP='192.168.0.254', username='Administrator', password='Administrator'):
        super().__init__()
        self.xps = None
        self.groups = []
        self.stages = {}  # 存储 stage 信息
        self._stage_to_axis = {}  # axis index 到 stage name 的映射
        
        try:
            from newportxps import NewportXPS
            # 新版本会自动读取控制器上的 system.ini
            self.xps = NewportXPS(IP, username=username, password=password)
            print(f"XPS: 已连接到 {IP}")
            
        except Exception as e:
            print(f'XPS 初始化失败: {e}')
            print('尝试使用底层驱动...')
            self._init_lowlevel(IP, username, password)

    def _init_lowlevel(self, IP, username, password):
        """备用方案：使用底层驱动"""
        try:
            from newportxps.XPS_C8_drivers import XPS
            self._xps = XPS()
            self._sid = self._xps.TCP_ConnectToServer(IP, 5001, 10)
            
            if self._sid < 0:
                print(f"XPS 连接失败: 无效的 socket ID {self._sid}")
                self._sid = None
            else:
                err, msg = self._xps.Login(self._sid, username, password)
                if err != 0:
                    print(f"XPS 登录失败: 错误码 {err}, {msg}")
                    self._sid = None
                else:
                    print(f"XPS: 已通过底层驱动连接到 {IP}")
        except Exception as e:
            print(f'底层驱动初始化失败: {e}')
            self._xps = None
            self._sid = None

    def init_groups(self, group_list=[]):
        """
        初始化轴组（兼容旧代码）
        新版本：优先使用高层接口
        旧版本：回退到底层驱动
        """
        if self.xps is not None:
            # 使用高层接口
            self._init_groups_highlevel(group_list)
        else:
            # 使用底层驱动
            self._init_groups_lowlevel(group_list)

    def _init_groups_highlevel(self, group_list):
        """使用高层 NewportXPS 接口初始化"""
        self.groups = []
        self._stage_to_axis = {}
        
        # 获取当前轴组状态
        status = self.xps.get_group_status()
        
        for idx, group_name in enumerate(group_list):
            if group_name not in self.xps.groups:
                print(f"警告: 轴组 {group_name} 不在配置中")
                continue
            
            # 检查状态
            current_status = status.get(group_name, '')
            
            # 如果已经 Ready，直接使用
            if current_status.startswith('Ready'):
                print(f"轴组 {group_name} 已就绪 (状态: {current_status})，保持当前位置")
                self.groups.append(group_name)
                
                # 映射 axis 到对应的 stage
                group_info = self.xps.groups.get(group_name, {})
                positioners = group_info.get('positioners', [])
                if positioners:
                    stage_name = f"{group_name}.{positioners[0]}"
                    self._stage_to_axis[idx] = stage_name
                    print(f"  Axis {idx} -> Stage {stage_name}")
            else:
                # 需要初始化
                print(f"轴组 {group_name} 未就绪 (状态: {current_status})")
                try:
                    # 尝试初始化（不 home）
                    self.xps.initialize_group(group_name)
                    
                    # 检查是否需要 home
                    new_status = self.xps.get_group_status().get(group_name, '')
                    if new_status.startswith('Ready'):
                        print(f"轴组 {group_name} 初始化成功，无需 home")
                        self.groups.append(group_name)
                        
                        # 映射 axis
                        group_info = self.xps.groups.get(group_name, {})
                        positioners = group_info.get('positioners', [])
                        if positioners:
                            stage_name = f"{group_name}.{positioners[0]}"
                            self._stage_to_axis[idx] = stage_name
                            print(f"  Axis {idx} -> Stage {stage_name}")
                    else:
                        print(f"轴组 {group_name} 需要 home (状态: {new_status})")
                        print(f"请手动执行: xps.home_group('{group_name}')")
                        
                except Exception as e:
                    print(f"轴组 {group_name} 初始化失败: {e}")

    def _init_groups_lowlevel(self, group_list):
        """使用底层驱动初始化（原有逻辑的改进版）"""
        if not hasattr(self, '_xps') or self._sid is None:
            print("底层驱动未初始化")
            return
        
        self.groups = []
        
        for group_name in group_list:
            try:
                # 检查状态
                status_result = self._xps.GroupStatusGet(self._sid, group_name)
                # 状态码 10-19: Ready states
                # 状态码 42-46: Ready from various operations
                if status_result[0] == 0:
                    status_code = status_result[1]
                    
                    if (10 <= status_code < 20) or (42 <= status_code <= 46):
                        print(f"轴组 {group_name} 已就绪 (状态码: {status_code})，保持位置")
                        self.groups.append(group_name)
                        continue
                
                # 需要初始化
                print(f"轴组 {group_name} 需要初始化 (状态码: {status_result[1] if status_result[0] == 0 else 'unknown'})")
                
                # Kill -> Initialize (不 home)
                self._xps.GroupKill(self._sid, group_name)
                init_result = self._xps.GroupInitialize(self._sid, group_name)
                
                if init_result[0] == 0:
                    # 再次检查状态
                    status_result = self._xps.GroupStatusGet(self._sid, group_name)
                    if status_result[0] == 0 and 10 <= status_result[1] < 50:
                        print(f"轴组 {group_name} 初始化成功，跳过 home")
                        self.groups.append(group_name)
                    else:
                        print(f"轴组 {group_name} 初始化后需要 home (状态: {status_result[1]})")
                        print(f"如需 home，请手动调用底层命令")
                else:
                    print(f"轴组 {group_name} 初始化失败: {init_result}")
                    
            except Exception as e:
                print(f"处理轴组 {group_name} 时出错: {e}")

    def move_by(self, distance, axis):
        """相对移动"""
        if self.xps is not None:
            # 使用高层接口
            stage_name = self._stage_to_axis.get(axis)
            if stage_name:
                try:
                    current_pos = self.xps.get_stage_position(stage_name)
                    target_pos = current_pos + distance
                    self.xps.move_stage(stage_name, target_pos)
                except Exception as e:
                    print(f"XPS 移动失败 (Axis {axis}, Stage {stage_name}): {e}")
            else:
                print(f"Axis {axis} 未映射到 stage")
        else:
            # 使用底层驱动（原有逻辑）
            self._move_by_lowlevel(distance, axis)

    def _move_by_lowlevel(self, distance, axis):
        """底层驱动的相对移动"""
        if axis < 0 or axis >= len(self.groups):
            return
        
        group_name = self.groups[axis]
        if not hasattr(self, '_xps') or self._sid is None:
            return
        
        try:
            # 获取当前位置
            pos_result = self._xps.GroupPositionCurrentGet(self._sid, group_name, 1)
            if pos_result[0] != 0 or len(pos_result) < 2 or pos_result[1] is None:
                print(f"XPS 无法获取位置 (Axis {axis})")
                return
            
            current_pos = pos_result[1]
            target_pos = current_pos + distance
            
            # 执行移动
            move_result = self._xps.GroupMoveAbsolute(self._sid, group_name, [target_pos])
            if move_result[0] != 0:
                print(f"XPS 移动失败 (Axis {axis}): 错误码 {move_result[0]}")
        except Exception as e:
            print(f"XPS 相对移动失败 (Axis {axis}): {e}")

    def move_to(self, position, axis):
        """绝对移动"""
        if self.xps is not None:
            # 使用高层接口
            stage_name = self._stage_to_axis.get(axis)
            if stage_name:
                try:
                    self.xps.move_stage(stage_name, position)
                except Exception as e:
                    print(f"XPS 移动失败 (Axis {axis}, Stage {stage_name}): {e}")
            else:
                print(f"Axis {axis} 未映射到 stage")
        else:
            # 使用底层驱动（原有逻辑）
            self._move_to_lowlevel(position, axis)

    def _move_to_lowlevel(self, position, axis):
        """底层驱动的绝对移动"""
        if axis < 0 or axis >= len(self.groups):
            return
        
        group_name = self.groups[axis]
        if not hasattr(self, '_xps') or self._sid is None:
            return
        
        try:
            move_result = self._xps.GroupMoveAbsolute(self._sid, group_name, [position])
            if move_result[0] != 0:
                print(f"XPS 移动失败 (Axis {axis}): 错误码 {move_result[0]}")
        except Exception as e:
            print(f"XPS 绝对移动失败 (Axis {axis}): {e}")

    def get_position(self, axis):
        """获取当前位置"""
        if self.xps is not None:
            # 使用高层接口
            stage_name = self._stage_to_axis.get(axis)
            if stage_name:
                try:
                    return self.xps.get_stage_position(stage_name)
                except Exception as e:
                    print(f"XPS 读取位置失败 (Axis {axis}, Stage {stage_name}): {e}")
                    return 0.0
            else:
                print(f"Axis {axis} 未映射到 stage")
                return 0.0
        else:
            # 使用底层驱动
            return self._get_position_lowlevel(axis)

    def _get_position_lowlevel(self, axis):
        """底层驱动获取位置"""
        if axis < 0 or axis >= len(self.groups):
            return 0.0
        
        group_name = self.groups[axis]
        if not hasattr(self, '_xps') or self._sid is None:
            return 0.0
        
        try:
            pos_result = self._xps.GroupPositionCurrentGet(self._sid, group_name, 1)
            if pos_result[0] != 0 or len(pos_result) < 2 or pos_result[1] is None:
                return 0.0
            return pos_result[1]
        except Exception as e:
            print(f"XPS 读取位置失败 (Axis {axis}): {e}")
            return 0.0

    def status_report(self):
        """返回状态报告"""
        if self.xps is not None:
            # 使用高层接口
            try:
                report = self.xps.status_report()
                return {
                    "report": report,
                    "groups": self.groups,
                    "stages": list(self._stage_to_axis.values())
                }
            except Exception as e:
                print(f"获取状态报告失败: {e}")
                return {"groups": self.groups}
        else:
            # 使用底层驱动（原有逻辑）
            return self._status_report_lowlevel()

    def _status_report_lowlevel(self):
        """底层驱动状态报告"""
        if not hasattr(self, '_xps') or self._sid is None:
            return {}
        
        try:
            err, uptime = self._xps.ElapsedTimeGet(self._sid)
            if err != 0:
                uptime = 0
            
            err, firmware = self._xps.FirmwareVersionGet(self._sid)
            if err != 0:
                firmware = "Unknown"
            
            return {
                "uptime": uptime,
                "firmware": firmware,
                "groups": self.groups
            }
        except Exception as e:
            print(f"获取状态报告失败: {e}")
            return {}

    def set_velocity(self, stage: str = None, velocity: float = 2.5, 
                     acceleration: float = None, min_jerktime: float = None,
                     max_jerktime: float = None):
        """设置速度参数"""
        if self.xps is not None and hasattr(self.xps, 'set_velocity'):
            try:
                self.xps.set_velocity(stage, velocity, acceleration, 
                                     min_jerktime, max_jerktime)
            except Exception as e:
                print(f"设置速度失败: {e}")
        else:
            print("set_velocity 仅在高层接口中可用")

            return {}

import ctypes
from ctypes import create_string_buffer, c_uint

class nators():
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
