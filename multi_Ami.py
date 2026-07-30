import socket
import subprocess
import time
from typing import Tuple


class MultiAxisController:
    """
    双控制器三轴同步控制器
    - 轴1、轴2 → 控制器1 (IP: 192.168.0.7:32500)
    - 轴3     → 控制器2 (IP: 192.168.0.8:32500)
    """

    def __init__(self, exe_path: str = "./pvcsvr/pvcsvr.exe"):
        """
        :param exe_path: pvcsvr.exe 路径
        """
        self.exe_path = exe_path
        self._process = None          # 第一个服务进程
        self._sock1 = None            # 连接第一个服务 (端口32323)
        self._sock2 = None            # 连接第二个服务 (端口32324)
        self._pos_cache = {1: 0.0, 2: 0.0, 3: 0.0}   # 毫米

    # ---------- 内部通信工具 ----------
    def _send_and_wait(self, sock, command: str, expected_keyword: str, timeout: float = 2.0) -> str:
        """发送命令，阻塞直到收到包含 expected_keyword 的响应行"""
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
            # 未找到则继续循环接收

    def _parse_position(self, resp: str) -> Tuple[float, float]:
        """解析位置响应，返回 (x_pm, y_pm)"""
        if "ACK0:" in resp:
            start = resp.find("ACK0:") + len("ACK0:")
        else:
            start = resp.find("ACK:") + len("ACK:")
        value_part = resp[start:].strip().rstrip(';').rstrip(',')
        parts = value_part.split(',')
        if len(parts) != 2:
            raise ValueError(f"位置数据格式错误: {resp}")
        return float(parts[0].strip()), float(parts[1].strip())

    # ---------- 初始化与连接 ----------
    def connect_all(self):
        """
        完整初始化：
        1. 启动第一个 pvcsvr.exe（监听 32323）
        2. 连接第一个服务，发送 newinstance 创建第二个服务（监听 32324）
        3. 连接两个服务
        4. 连接两个控制器并使能系统
        """
        # 1. 启动第一个服务
        self._process = subprocess.Popen(
            [self.exe_path],
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1.5)   # 等待进程初始化

        # 2. 连接第一个服务 (32323)
        self._sock1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock1.settimeout(5.0)
        self._sock1.connect(("127.0.0.1", 32323))

        # 3. 发送 newinstance 创建第二个服务
        self._send_and_wait(self._sock1, "newinstance -p=32324", "ACK")
        time.sleep(2)     # 等待第二个进程启动

        # 4. 连接第二个服务 (32324)
        self._sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock2.settimeout(5.0)
        self._sock2.connect(("127.0.0.1", 32324))

        # 5. 连接控制器1 (192.168.0.7)
        self._send_and_wait(self._sock1, "connect dev 192.168.0.7:32500", "ACK: connected")
        # 6. 连接控制器2 (192.168.0.8)
        self._send_and_wait(self._sock2, "connect dev 192.168.0.8:32500", "ACK: connected")

        # 7. 使能两个系统
        self._send_and_wait(self._sock1, "SysCfg c:OnOff dat:1", "ACK: Done")
        self._send_and_wait(self._sock2, "SysCfg c:OnOff dat:1", "ACK: Done")

        print("✅ 两个控制器均已连接并系统使能")

    def enable_axis(self, axis: int, on: bool):
        """使能/禁用指定轴通道（1~3）"""
        val = 1 if on else 0
        if axis == 1:
            self._send_and_wait(self._sock1, f"TB_ChCfg r:Channel=1 c:Enable dat:{val}", "ACK: Done")
        elif axis == 2:
            self._send_and_wait(self._sock1, f"TB_ChCfg r:Channel=2 c:Enable dat:{val}", "ACK: Done")
        elif axis == 3:
            self._send_and_wait(self._sock2, f"TB_ChCfg r:Channel=1 c:Enable dat:{val}", "ACK: Done")
        else:
            raise ValueError("轴号必须为 1, 2, 3")

    def enable_all_axes(self, on: bool = True):
        """一次性使能/禁用所有三个轴"""
        for ax in (1, 2, 3):
            self.enable_axis(ax, on)

    # ---------- 运动控制 ----------
    def move_to(self, axis: int, position_mm: float):
        """绝对移动（毫米）"""
        pm = int(round(position_mm * 1e9))
        if axis == 1:
            self._send_and_wait(self._sock1, f"SignalExtInput c:Ref0 r:ItemName=ExternalReference dat:{pm}", "ACK")
        elif axis == 2:
            self._send_and_wait(self._sock1, f"SignalExtInput c:Ref1 r:ItemName=ExternalReference dat:{pm}", "ACK")
        elif axis == 3:
            self._send_and_wait(self._sock2, f"SignalExtInput c:Ref0 r:ItemName=ExternalReference dat:{pm}", "ACK")
        else:
            raise ValueError("轴号必须为 1, 2, 3")

    def move_by(self, axis: int, delta_mm: float):
        """相对移动（毫米），等待前一次移动完成后基于当前位置执行"""
        self._wait_for_stop(axis)          # 等待该轴所在控制器停止
        current = self.get_position(axis)  # 读取实时位置
        self.move_to(axis, current + delta_mm)

    # ---------- 位置读取 ----------
    def get_position(self, axis: int) -> float:
        """读取指定轴的当前实际位置（毫米），并更新缓存"""
        if axis in (1, 2):
            resp = self._send_and_wait(self._sock1, "VolatileDevData r:item=Position l:16", "ACK0:")
            x_pm, y_pm = self._parse_position(resp)
            self._pos_cache[1] = x_pm / 1e9
            self._pos_cache[2] = y_pm / 1e9
            return self._pos_cache[axis]
        elif axis == 3:
            resp = self._send_and_wait(self._sock2, "VolatileDevData r:item=Position l:16", "ACK0:")
            x_pm, y_pm = self._parse_position(resp)
            self._pos_cache[3] = x_pm / 1e9   # 只取第一个通道
            return self._pos_cache[3]
        else:
            raise ValueError("轴号必须为 1, 2, 3")

    # ---------- 等待运动停止 ----------
    def _wait_for_stop(self, axis: int = None, timeout: float = 10.0):
        """
        等待指定轴所在的所有通道停止。
        若 axis 为 None，则等待两个控制器全部停止。
        """
        def _wait_single(sock):
            start = time.time()
            while time.time() - start < timeout:
                resp = self._send_and_wait(sock, "SysCmd r:item=SettleStatus syn", "ACK:")
                val_str = resp.split("dat:")[-1].strip().rstrip(';').rstrip(',')
                val = int(val_str)
                if val == 3 or val == 1:   # 两个通道均停止
                    return
                time.sleep(0.05)
            raise TimeoutError("等待停止超时")

        if axis is None or axis in (1, 2):
            _wait_single(self._sock1)
        if axis is None or axis == 3:
            _wait_single(self._sock2)

    # ---------- 清理 ----------
    def close(self):
        """关闭所有连接并终止服务进程"""
        if self._sock1:
            self._sock1.close()
            self._sock1 = None
        if self._sock2:
            self._sock2.close()
            self._sock2 = None
        if self._process and self._process.poll() is None:
            self._process.terminate()
            self._process.wait(timeout=2)