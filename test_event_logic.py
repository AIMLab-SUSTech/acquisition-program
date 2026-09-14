# -*- coding: utf-8 -*-
"""
event.py 回归测试（P1 修复 + 输入可用性 + h5 暗减帧/PNG 原始帧 + h5 位置/时间戳）

运行（qt 环境，无显示要求）:
    D:\\miniconda\\envs\\qt\\python.exe test_event_logic.py

- offscreen Qt，不需要显示器
- 桩掉硬件依赖（pyueye / imagingcontrol4 / pylablib），不接触真实相机与位移台
"""
import os
import sys
import time
import shutil
import tempfile
import types

# ----------------------------------------------------------------------
# 1) 桩掉硬件依赖（必须在 import event 之前）
# ----------------------------------------------------------------------
def _stub(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


class _Dummy:
    def __init__(self, *a, **k):
        pass


_stub('pyueye', ueye=_Dummy())

ic4 = _stub('imagingcontrol4')
ic4.QueueSinkListener = type('QueueSinkListener', (), {})
ic4.QueueSink = type('QueueSink', (), {})
ic4.ImageType = type('ImageType', (), {})
ic4.IC4Exception = type('IC4Exception', (Exception,), {})

_stub('pylablib')
devices = _stub('pylablib.devices')
devices.uc480 = types.SimpleNamespace(
    list_cameras=lambda backend=None: [],
    UC480Camera=type('UC480Camera', (), {}))
devices.DCAM = types.SimpleNamespace(
    get_cameras_number=lambda: 0,
    DCAMCamera=type('DCAMCamera', (), {}))
devices.SmarAct = types.SimpleNamespace(
    list_msc2_devices=lambda: [],
    MCS2=type('MCS2', (), {}))

# ----------------------------------------------------------------------
# 2) offscreen Qt + 导入被测模块
# ----------------------------------------------------------------------
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PyQt5.QtWidgets import QApplication  # noqa: E402
import numpy as np  # noqa: E402

from event import MainWindow  # noqa: E402

app = QApplication(sys.argv)

# ----------------------------------------------------------------------
# 3) 测试替身
# ----------------------------------------------------------------------
class FakeCamera:
    def __init__(self, img):
        self.img = img
        self.frame_period_s = 0.02
        self.exposure_log = []

    def read_newest_image(self):
        return self.img

    def get_frame_period(self):
        return self.frame_period_s

    def set_ex_time(self, t):
        self.exposure_log.append(t)

    def start_acquisition(self):
        pass


class FakeMotion:
    """模拟位移台：记录指令；move_fail_at 指定第几次 move_by 抛异常。"""

    def __init__(self, move_fail_at=None, wait_ok=True):
        self.moves = []
        self.stop_all_called = 0
        self.wait_idle_called = 0
        self.move_fail_at = move_fail_at
        self.wait_ok = wait_ok

    def move_by(self, distance, axis, relative=True):
        self.moves.append((distance, axis))
        if self.move_fail_at is not None and len(self.moves) > self.move_fail_at:
            raise RuntimeError(f'fake move failure at call {len(self.moves)}')

    def wait_idle(self, timeout=30.0):
        self.wait_idle_called += 1
        return self.wait_ok

    def stop_all(self):
        self.stop_all_called += 1


def make_window(tmpdir, img, camera_period=0.02):
    w = MainWindow()
    w.xpixel_num = 8
    w.ypixel_num = 8
    w.step = 0.3
    w.scan_num = 2
    w.ui.save_path.setText(tmpdir)  # 触发 _on_save_path_changed
    w.camera = FakeCamera(img)
    return w


def pump_until_idle(w, timeout=10.0):
    """驱动 Qt 事件循环，直到扫描链结束（完成或中止）或超时"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        if not w.scan_active:
            return True
        time.sleep(0.02)
    return False


RESULTS = []


def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond)))
    print(('PASS' if cond else 'FAIL'), name, detail if not cond else '')


# ----------------------------------------------------------------------
# 4) 测试
# ----------------------------------------------------------------------
tmpdir = tempfile.mkdtemp(prefix='evt_test_')

# --- T1: h5 存暗减帧、PNG 存原始帧 + 记录位置与时间戳 -----------------
img = np.full((16, 16), 30, dtype=np.uint16)
w = make_window(tmpdir, img)
w.save_image(0)  # 采集暗帧（值 30，裁剪后 8x8）
bright = np.tile(np.array([5, 60, 30], dtype=np.uint16), (16, 6))[:, :16]
w.camera = FakeCamera(bright)
w.abs_x = [0.0, 0.3, 0.6]
w.abs_y = [0.0, 0.0, 0.3]
t_before = time.time()
w.save_image(1)
expected_raw = bright[4:12, 4:12]
expected_sub = np.clip(expected_raw.astype(np.int32) - 30, 0, 65535).astype(np.uint16)
check('T1a h5 frame is dark-subtracted, no uint16 wraparound (P1-1)',
      len(w.dps) == 1 and np.array_equal(w.dps[0], expected_sub) and (w.dps[0] == 0).any(),
      f'got corner={w.dps[0][0, 0] if w.dps else None} (5-30 应截断为 0，旧 bug 回绕成 65511)')
from PIL import Image as PILImage
png = np.array(PILImage.open(os.path.join(tmpdir, '1.png')).convert('I;16'))
check('T1b saved PNG is raw frame (not dark-subtracted)',
      np.array_equal(png.astype(np.uint16), expected_raw),
      f'png max={png.max() if png.size else None}, expect raw max=60')
check('T1c position recorded (frame 1 <- scan point 0)',
      w.pos_x == [0.0] and w.pos_y == [0.0],
      f'pos_x={w.pos_x}, pos_y={w.pos_y}')
check('T1d timestamp recorded (finite, plausible)',
      len(w.timestamp) == 1 and np.isfinite(w.timestamp[0]) and w.timestamp[0] >= t_before - 1,
      f'ts={w.timestamp}')

# --- T1e: 暗帧与图像形状不一致 → 明确报错 ----------------------------
w.dark = np.zeros((4, 4), dtype=np.uint16)
w.camera = FakeCamera(np.zeros((8, 8), dtype=np.uint16))
try:
    w.save_image(2)
    check('T1e shape mismatch raises RuntimeError', False, 'no exception')
except RuntimeError as e:
    check('T1e shape mismatch raises RuntimeError', '形状' in str(e), str(e))

# --- T3: 输入安全解析（不必回车 + 输错不崩） -------------------------
w.ui.step.setText('0.5')
check('T3a step textChanged applies', w.step == 0.5)
w.ui.step.setText('abc')
check('T3b invalid step keeps previous value', w.step == 0.5)
w.ui.step.setText('')
check('T3c empty step keeps previous value', w.step == 0.5)
w.ui.scan_num.setText('3')
check('T3d scan_num applies', w.scan_num == 3)
w.ui.scan_num.setText('x')
check('T3e invalid scan_num keeps previous value', w.scan_num == 3)
w.ui.xpixel_num.setText('-5')
check('T3f negative pixel num rejected', w.xpixel_num == 8)
w.ui.ex_time.setText('20')
check('T3g ex_time applies to camera (ms->s)',
      w.ex_time == 0.02 and w.camera.exposure_log[-1] == 0.02)
w.ui.ex_time.setText('oops')
check('T3h invalid ex_time ignored without crash', w.ex_time == 0.02)

# --- T4: 帧周期保护（P1-9） -----------------------------------------
check('T4a normal period', MainWindow._frame_period_ms(0.02) == 20)
check('T4b inf falls back to default', MainWindow._frame_period_ms(float('inf')) == 100)
check('T4c zero falls back to default', MainWindow._frame_period_ms(0) == 100)
check('T4d negative falls back to default', MainWindow._frame_period_ms(-1) == 100)
check('T4e sub-ms clamped to floor', MainWindow._frame_period_ms(0.0004) == 10)
check('T4f None falls back to default', MainWindow._frame_period_ms(None) == 100)

# --- T5: 完整扫描链 + 重扫重置（P1-11/P1-7） -------------------------
img = np.full((16, 16), 100, dtype=np.uint16)

# 未采暗帧时扫描必须被拒绝（h5 需要暗减）
w0 = make_window(tmpdir, img)
w0.motion = FakeMotion()
w0._start_scan()
check('T5a scan without dark frame rejected',
      not w0.scan_active and len(w0.dps) == 0 and len(w0.motion.moves) == 0)

w = make_window(tmpdir, img)
w.save_image(0)  # 采集暗帧（值 100）
w.motion = FakeMotion()
w._start_scan()
ok = pump_until_idle(w)
check('T5b scan completes', ok and not w.scan_active,
      f'cur_point={w.cur_point}, len(x)={len(w.x)}')
n_points = len(w.x)
check('T5c all frames saved', len(w.dps) == n_points,
      f'dps={len(w.dps)}, points={n_points}')
check('T5d settle wait used for each step (incl. return-to-zero)',
      w.motion.wait_idle_called == n_points + 2,
      f'wait_idle_called={w.motion.wait_idle_called}, expect {n_points + 2}')
h5_path = os.path.join(tmpdir, 'dps.h5')
check('T5e dps.h5 written', os.path.exists(h5_path))

# h5 内容：暗减帧 + 扫描位置 + 时间戳（重扫前读取，避免被覆盖）
import h5py
with h5py.File(h5_path, 'r') as f:
    check('T5f h5 datasets complete',
          set(['dps', 'pos_x', 'pos_y', 'timestamp']).issubset(set(f.keys())),
          f'keys={list(f.keys())}')
    px, py, ts = f['pos_x'][:], f['pos_y'][:], f['timestamp'][:]
    check('T5g h5 shapes', f['dps'].shape == (n_points, 8, 8) and px.shape == (n_points,),
          f'dps={f["dps"].shape}, pos_x={px.shape}')
    check('T5h h5 positions match scan path',
          np.allclose(px, [0, 0.3, 0.3, 0], atol=1e-9) and np.allclose(py, [0, 0, 0.3, 0.3], atol=1e-9),
          f'px={px.tolist()}, py={py.tolist()}')
    check('T5i h5 timestamps finite & non-decreasing',
          np.all(np.isfinite(ts)) and np.all(np.diff(ts) >= 0), f'ts={ts.tolist()}')
    check('T5j h5 dps is dark-subtracted (100-100=0)',
          int(f['dps'][0][0, 0]) == 0, f'got {f["dps"][0][0, 0]}')
png1 = np.array(PILImage.open(os.path.join(tmpdir, '1.png')).convert('I;16'))
check('T5k PNG 1.png is raw frame (value 100, not dark-subtracted)',
      int(png1[0, 0]) == 100, f'got {png1[0, 0]}')

# 重扫：原 bug 会在 self.x[self.cur_point] 越界
w.motion = FakeMotion()
w._start_scan()
ok2 = pump_until_idle(w)
check('T5l rescan works (cur_point/dps/pos reset)',
      ok2 and not w.scan_active and len(w.dps) == n_points
      and len(w.pos_x) == n_points and w.cur_point == n_points,
      f'dps={len(w.dps)}, cur_point={w.cur_point}')

# --- T6: 移动失败 → 中止扫描 + 停台 + 保存部分数据（P1-7） -----------
w2 = make_window(tmpdir, img)
w2.save_image(0)
w2.motion = FakeMotion(move_fail_at=2)  # 第 3 次 move_by 失败
w2._start_scan()
ok3 = pump_until_idle(w2)
check('T6a scan aborted on move failure', ok3 and not w2.scan_active)
check('T6b partial data saved', len(w2.dps) >= 1 and os.path.exists(h5_path))
check('T6c stop_all issued on abort', w2.motion.stop_all_called >= 1)
with h5py.File(h5_path, 'r') as f:
    check('T6e partial h5: positions/timestamps consistent with frame count',
          f['pos_x'].shape[0] == f['dps'].shape[0] == f['timestamp'].shape[0] == len(w2.dps),
          f'pos={f["pos_x"].shape[0]}, dps={f["dps"].shape[0]}, ts={f["timestamp"].shape[0]}')

# --- T6d: 台子超时不到位 → 中止 --------------------------------------
w3 = make_window(tmpdir, img)
w3.save_image(0)
w3.motion = FakeMotion(wait_ok=False)
w3._start_scan()
ok4 = pump_until_idle(w3)
check('T6d settle timeout aborts scan', ok4 and not w3.scan_active
      and w3.motion.stop_all_called >= 1 and len(w3.dps) == 0)

# --- T7: 终止按钮（P1-12） ------------------------------------------
w4 = make_window(tmpdir, img)
w4.save_image(0)
w4.motion = FakeMotion()
w4.ui.init_motion_ctr.setText('开始扫描')
w4._start_scan()
pump_until_idle(w4)
w4.ui.init_motion_ctr.setText('终止位移台移动')
w4.init_mtn_ctr()  # 走"终止"分支
check('T7 stop button stops motion and resets state',
      w4.motion.stop_all_called >= 1 and not w4.scan_active
      and w4.ui.init_motion_ctr.text() == '开始扫描')

# --- T8: 保存路径输入 -------------------------------------------------
w5 = make_window(tmpdir, img)
w5.ui.save_path.setText('')
check('T8a empty save path -> None', w5.save_path is None)
w5.ui.save_path.setText('D:/some/path')
check('T8b save path applied without Enter', w5.save_path == 'D:/some/path')

# ----------------------------------------------------------------------
# 汇总
# ----------------------------------------------------------------------
passed = sum(1 for _, ok in RESULTS if ok)
print('-' * 60)
print(f'TOTAL: {passed}/{len(RESULTS)} passed')
shutil.rmtree(tmpdir, ignore_errors=True)
sys.exit(0 if passed == len(RESULTS) else 1)
