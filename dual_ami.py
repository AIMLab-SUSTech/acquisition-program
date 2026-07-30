import socket
import subprocess
import time
from typing import Optional, Tuple
from motion_controller import MotionController


class DualAmiController(MotionController):
    """
    双控制器二维扫描控制器
    - 控制器1 (192.168.0.7:32500): X轴 (axis 1 或 2，可配置)
    - 控制器2 (192.168.0.8:32500): Y轴 (axis 3)
    实现 motion_controller.MotionController 接口 (axis 0=X, 1=Y)
    """

    def __init__(self, exe_path: str = "./dll/Ami/pvcsvr.exe", x_axis: int = 1):
        super().__init__()
        self.exe_path = exe_path
        if x_axis not in (1, 2):
            raise ValueError("x_axis must be 1 or 2")
        self._x_ctrl_axis = x_axis       # 控制器1上的X轴号
        self._process = None
        self._sock1 = None                # 控制器1 socket (32323)
        self._sock2 = None                # 控制器2 socket (32324)
        self._pos_cache = {0: 0.0, 1: 0.0}

    # ---------- 内部通信 ----------

    def _send_and_wait(self, sock, command: str, expected_keyword: str, timeout: float = 2.0) -> str:
        sock.send((command + "\n").encode())
        sock.settimeout(timeout)
        while True:
            try:
                data = sock.recv(4096).decode()
            except socket.timeout:
                raise TimeoutError(f"等待 '{expected_keyword}' 超时")
            if not data:
                raise ConnectionError("连接断开")
            for line in data.splitlines():
                line = line.strip()
                if expected_keyword in line:
                    return line

    def _parse_position(self, resp: str) -> Tuple[float, float]:
        if "ACK0:" in resp:
            start = resp.find("ACK0:") + len("ACK0:")
        else:
            start = resp.find("ACK:") + len("ACK:")
        value_part = resp[start:].strip().rstrip(';').rstrip(',')
        parts = value_part.split(',')
        if len(parts) != 2:
            raise ValueError(f"位置数据格式错误: {resp}")
        return float(parts[0].strip()), float(parts[1].strip())

    # ---------- 连接与初始化 ----------

    def connect(self):
        """
        完整初始化:
        1. 启动 pvcsvr.exe
        2. 连接第一个服务 (32323) → 连接控制器1 (192.168.0.7)
        3. newinstance 创建第二个服务 (32324) → 连接控制器2 (192.168.0.8)
        4. 使能系统
        """
        self._process = subprocess.Popen(
            [self.exe_path],
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1.5)

        self._sock1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock1.settimeout(5.0)
        self._sock1.connect(("127.0.0.1", 32323))

        self._send_and_wait(self._sock1, "newinstance -p=32324", "ACK")
        time.sleep(2)

        self._sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock2.settimeout(5.0)
        self._sock2.connect(("127.0.0.1", 32324))

        self._send_and_wait(self._sock1, "connect dev 192.168.0.7:32500", "ACK: connected")
        print("控制器1 (192.168.0.7) 连接成功")

        self._send_and_wait(self._sock2, "connect dev 192.168.0.8:32500", "ACK: connected")
        print("控制器2 (192.168.0.8) 连接成功")

        self._send_and_wait(self._sock1, "SysCfg c:OnOff dat:1", "ACK: Done")
        self._send_and_wait(self._sock2, "SysCfg c:OnOff dat:1", "ACK: Done")
        print("两个控制器均已使能")

    def enable_channels(self):
        """使能所有通道"""
        for ch in (1, 2):
            self._send_and_wait(self._sock1, f"TB_ChCfg r:Channel={ch} c:Enable dat:1", "ACK: Done")
        self._send_and_wait(self._sock2, "TB_ChCfg r:Channel=1 c:Enable dat:1", "ACK: Done")
        print("所有通道已使能")

    # ---------- MotionController 接口 ----------

    def move_by(self, distance: float, axis: int):
        if axis == 0:
            self._wait_for_stop(self._sock1)
            current = self.get_position(0)
            self.move_to(current + distance, 0)
        elif axis == 1:
            self._wait_for_stop(self._sock2)
            current = self.get_position(1)
            self.move_to(current + distance, 1)
        else:
            raise ValueError("axis must be 0 (X) or 1 (Y)")

    def move_to(self, position: float, axis: int):
        pm = int(round(position * 1e9))
        if axis == 0:
            ref = "Ref0" if self._x_ctrl_axis == 1 else "Ref1"
            self._send_and_wait(
                self._sock1,
                f"SignalExtInput c:{ref} r:ItemName=ExternalReference dat:{pm}",
                "ACK"
            )
            self._wait_for_stop(self._sock1)
            self._pos_cache[0] = position
        elif axis == 1:
            self._send_and_wait(
                self._sock2,
                f"SignalExtInput c:Ref0 r:ItemName=ExternalReference dat:{pm}",
                "ACK"
            )
            self._wait_for_stop(self._sock2)
            self._pos_cache[1] = position
        else:
            raise ValueError("axis must be 0 (X) or 1 (Y)")

    def get_position(self, axis: int) -> float:
        if axis == 0:
            resp = self._send_and_wait(self._sock1, "VolatileDevData r:item=Position l:16", "ACK0:")
            x_pm, _ = self._parse_position(resp)
            mm = x_pm / 1e9
            self._pos_cache[0] = mm
            return mm
        elif axis == 1:
            resp = self._send_and_wait(self._sock2, "VolatileDevData r:item=Position l:16", "ACK0:")
            x_pm, _ = self._parse_position(resp)
            mm = x_pm / 1e9
            self._pos_cache[1] = mm
            return mm
        else:
            raise ValueError("axis must be 0 (X) or 1 (Y)")

    def _wait_for_stop(self, sock, timeout: float = 10.0):
        start = time.time()
        while time.time() - start < timeout:
            resp = self._send_and_wait(sock, "SysCmd r:item=SettleStatus syn", "ACK:")
            val_str = resp.split("dat:")[-1].strip().rstrip(';').rstrip(',')
            val = int(val_str)
            if val == 3 or val == 1:
                return
            time.sleep(0.05)
        raise TimeoutError("等待运动停止超时")

    def close(self):
        if self._sock1:
            self._sock1.close()
            self._sock1 = None
        if self._sock2:
            self._sock2.close()
            self._sock2 = None
        if self._process and self._process.poll() is None:
            self._process.terminate()
            self._process.wait(timeout=2)


if __name__ == "__main__":
    ctrl = DualAmiController(exe_path="./dll/Ami/pvcsvr.exe", x_axis=1)
    try:
        ctrl.connect()
        ctrl.enable_channels()
        x = ctrl.get_position(0)
        y = ctrl.get_position(1)
        print(f"当前位置: X={x:.6f} mm, Y={y:.6f} mm")
        ctrl.move_to(1.0, 0)
        ctrl.move_to(-1.0, 1)
        x = ctrl.get_position(0)
        y = ctrl.get_position(1)
        print(f"移动后位置: X={x:.6f} mm, Y={y:.6f} mm")
        ctrl.move_by(-0.5, 0)
        ctrl.move_by(0.5, 1)
        x = ctrl.get_position(0)
        y = ctrl.get_position(1)
        print(f"相对移动后: X={x:.6f} mm, Y={y:.6f} mm")
    except Exception as e:
        print(f"错误: {e}")
    finally:
        ctrl.close()
