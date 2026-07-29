# controller.py
import socket
import subprocess
from abc import ABC, abstractmethod
from typing import Optional, Tuple
from time import sleep


class MotionController(ABC):
    """抽象运动控制器接口（单位：毫米）"""
    @abstractmethod
    def move_by(self, delta: float, axis: int):
        pass

    @abstractmethod
    def move_to(self, position: float, axis: int):
        pass

    @abstractmethod
    def get_position(self, axis: int) -> float:
        pass


class PvcsvrController(MotionController):
    """
    极简同步控制器，无定时器、无线程，所有命令阻塞等待回应。
    连接与使能合并为一个函数。
    """

    def __init__(self, exe_path: Optional[str] = "./pvcsvr/pvcsvr.exe"):
        """
        :param exe_path: pvcsvr.exe 路径，若为 None 则不自动启动
        """
        self.exe_path = exe_path
        self._socket = None
        self._connected = False
        self._positions = (0.0, 0.0)  # 缓存最新位置

        if self.exe_path:
            self._launch_exe()

    def _launch_exe(self):
        """启动后台服务进程"""
        try:
            subprocess.Popen([self.exe_path],
                             creationflags=subprocess.CREATE_NO_WINDOW,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"启动服务失败: {e}")

    def _send_and_wait(self, command: str, expected_keyword: str, timeout: float = 2.0) -> str:
        """
        发送命令并等待回应包含指定关键字，超时抛出异常。
        """
        if not self._socket:
            raise RuntimeError("未连接服务器，请先调用 connect_and_enable()")

        self._socket.send((command + "\n").encode())
        self._socket.settimeout(timeout)
        while True:
            try:
                data = self._socket.recv(4096).decode()
            except socket.timeout:
                raise TimeoutError(f"等待 '{expected_keyword}' 超时")
            if not data:
                raise ConnectionError("连接断开")
            # 处理粘包，按行检查
            for line in data.splitlines():
                line = line.strip()
                if expected_keyword in line:
                    return line
            # 如果没找到关键行，继续接收（可能数据被拆分）
            # 但为简化，继续循环接收，直到超时或找到

    def connect_and_enable(
        self,
        server_ip="127.0.0.1",
        server_port=32323,
        controller_ip="192.168.0.7",
        controller_port=32500
    ):
        """
        一步完成：连接服务程序 → 连接控制器 → 使能系统。
        成功返回 True，失败抛出异常。
        """
        # 1. 连接服务程序
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(5.0)
        self._socket.connect((server_ip, server_port))
        # 2. 连接控制器
        resp = self._send_and_wait(
            f"connect dev {controller_ip}:{controller_port}",
            "ACK: connected"
        )
        print("控制器连接成功:", resp)
        # 3. 使能系统
        resp = self._send_and_wait(
            "SysCfg c:OnOff dat:1",
            "ACK: Done"
        )
        print("系统使能成功:", resp)
        self._connected = True
        return True

    def enable_channel(self, channel: int, on: bool):
        """使能/禁用通道（1 或 2）"""
        val = 1 if on else 0
        resp = self._send_and_wait(
            f"TB_ChCfg r:Channel={channel} c:Enable dat:{val}",
            "ACK: Done"
        )
        print(f"通道{channel} {'使能' if on else '禁用'}成功:", resp)

    def move_to(self, position: float, axis: int):
        """绝对移动（毫米）"""
        if axis not in (1, 2):
            raise ValueError("轴号必须是 1 或 2")
        pm = int(round(position * 1e9))
        ref = "Ref0" if axis == 1 else "Ref1"
        resp = self._send_and_wait(
            f"SignalExtInput c:{ref} r:ItemName=ExternalReference dat:{pm}",
            "ACK"
        )
        self.wait_for_stop()       # 等待所有轴停止
        print(f"轴{axis}移动到 {position} mm 成功:", resp)

    def wait_for_stop(self, timeout: float = 10.0):
        """
        阻塞等待所有轴停止运动。
        :param timeout: 超时秒数，超时抛出 TimeoutError
        """
        import time
        start = time.time()
        while time.time() - start < timeout:
            resp = self._send_and_wait(
                "SysCmd r:item=SettleStatus syn",
                "ACK:"
            )
            # 解析 dat 值
            if "dat:" in resp:
                val_str = resp.split("dat:")[-1].strip().rstrip(';').rstrip(',')
                val = int(val_str)
                # 根据文档: dat:3 表示两个通道都停止
                if val == 3:
                    return
            time.sleep(0.05)  # 短暂轮询
        raise TimeoutError("等待运动停止超时")

    def move_by(self, delta: float, axis: int):
        """相对移动（毫米），先等待前一次移动完成，再基于当前位置移动"""

        self.read_position()       # 更新缓存
        current = self.get_position(axis)
        self.move_to(current + delta, axis)
        self.wait_for_stop()

    def read_position(self) -> Tuple[float, float]:
        """
        阻塞读取当前位置，返回 (x_mm, y_mm)
        """
        resp = self._send_and_wait(
            "VolatileDevData r:item=Position l:16",
            "ACK0:"  # 也兼容 "ACK:"
        )
        # 解析
        try:
            if "ACK0:" in resp:
                start = resp.find("ACK0:") + len("ACK0:")
            else:
                start = resp.find("ACK:") + len("ACK:")
            values_part = resp[start:].strip().rstrip(';').rstrip(',')
            parts = values_part.split(',')
            if len(parts) == 2:
                x_pm = float(parts[0].strip())
                y_pm = float(parts[1].strip())
                x_mm = x_pm / 1e9
                y_mm = y_pm / 1e9
                self._positions = (x_mm, y_mm)
                return x_mm, y_mm
            else:
                raise ValueError(f"位置数据格式错误: {resp}")
        except Exception as e:
            raise RuntimeError(f"解析位置失败: {e}")

    def get_position(self, axis: int) -> float:
        """返回缓存的最新位置（需要先调用 read_position 更新）"""
        self.read_position()
        if axis not in (1, 2):
            raise ValueError("轴号必须是 1 或 2")
        return self._positions[axis - 1]

    def close(self):
        """关闭 socket 和后台进程"""
        if self._socket:
            self._socket.close()
            self._socket = None
        self._connected = False
        # 关闭 exe（可选）
        # 注意：这里无法直接关闭由 subprocess 启动的后台进程，需要额外管理，可以省略。



if __name__ == "__main__":
    # 创建控制器（自动启动 pvcsvr.exe）
    ctrl = PvcsvrController(exe_path="./pvcsvr/pvcsvr.exe")

    # 一步连接+使能
    try:
        ctrl.connect_and_enable()
    except Exception as e:
        print("初始化失败:", e)
        exit()

    # 使能通道1和通道2
    ctrl.enable_channel(1, True)
    ctrl.enable_channel(2, True)
    x, y = ctrl.read_position()
    print(f"当前位置: X={x:.6f} mm, Y={y:.6f} mm")
    # 移动轴1到 5.0 mm
    ctrl.move_to(-5.0, 1)

    # 移动轴2到 -2.5 mm
    ctrl.move_to(2.5, 2)
    # 读取当前位置
    x, y = ctrl.read_position()
    print(f"当前位置: X={x:.6f} mm, Y={y:.6f} mm")

    # 相对移动：轴1 移动 +0.1 mm
    ctrl.move_by(0.1, 1)
    
    x, y = ctrl.read_position()
    print(f"当前位置: X={x:.6f} mm, Y={y:.6f} mm")

    # 关闭连接
    ctrl.close()