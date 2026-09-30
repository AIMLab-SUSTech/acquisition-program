"""Adapt the official pco 2.6 SDK to the acquisition application's Camera API."""

from __future__ import annotations

import math
import time
from typing import Any

import numpy as np

from camera import Camera


def _load_backend() -> Any:
    try:
        import pco
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "PCO 库加载失败：请在 Python 3.8–3.12 环境执行 "
            "python -m pip install pco==2.6.0，并确认相机驱动已安装。"
        ) from exc
    return pco


class PCOCamera(Camera):
    """Continuous preview and software-triggered scanning, with times in seconds.

    Like the other adapters, callers must serialize camera access (the GUI uses
    camera_lock and stops preview before scanning). No SDK calls run at import.
    """

    supports_software_trigger = True
    read_waits_for_new_frame = True
    trigger_mode_settle_s = 0.0
    _LATEST_IMAGE = 0xFFFFFFFF

    def __init__(
        self,
        serial_number: int | None = None,
        interface: str | None = None,
        frame_timeout_s: float = 5.0,
        buffer_count: int = 8,
        backend: Any | None = None,
    ) -> None:
        super().__init__()
        if not math.isfinite(frame_timeout_s) or frame_timeout_s <= 0:
            raise ValueError("frame_timeout_s 必须为有限正数")
        if isinstance(buffer_count, bool) or not isinstance(buffer_count, int) or buffer_count < 4:
            raise ValueError("PCO 环形缓冲 buffer_count 必须为不小于 4 的整数")
        self.cam = None
        self.is_open = False
        self.is_grabbing = False
        self._trigger_mode = "continuous"
        self._frame_timeout_s = float(frame_timeout_s)
        self._buffer_count = buffer_count
        self._last_image_number = 0
        self.last_metadata: dict = {}
        pco = backend if backend is not None else _load_backend()
        try:
            self.cam = pco.Camera(serial=serial_number, interface=interface)
            self.cam.configuration = {"trigger": "auto sequence", "acquire": "auto"}
            self.is_open = True
        except Exception as exc:
            if self.cam is not None:
                try:
                    self.cam.close()
                except Exception:
                    pass
                self.cam = None
            raise RuntimeError(
                f"PCO 相机连接或初始化失败，请检查驱动、连接并关闭 Camware：{exc}"
            ) from exc

    def _require_open_camera(self) -> Any:
        if not self.is_open or self.cam is None:
            raise RuntimeError("PCO 相机未打开或已关闭")
        return self.cam

    def start_acquisition(self) -> None:
        camera = self._require_open_camera()
        if self.is_grabbing:
            self._recording_status()
            return
        try:
            camera.record(number_of_images=self._buffer_count, mode="ring buffer")
        except Exception as exc:
            # record() can allocate/start the recorder before reporting failure.
            try:
                camera.stop()
            except Exception:
                pass
            raise RuntimeError(f"PCO 启动采集失败：{exc}") from exc
        self.is_grabbing = True
        self._last_image_number = 0
        self.last_metadata = {}

    def stop_acquisition(self) -> None:
        if self.cam is not None:
            # Also stop after a partial start or an unexpected recorder failure.
            self.cam.stop()
        self.is_grabbing = False
        self._last_image_number = 0

    def stop_acquistion(self) -> None:
        """Compatibility with the original adapter's misspelled method."""
        self.stop_acquisition()

    def set_ex_time(self, ex_time: float) -> None:
        exposure = float(ex_time)
        if not math.isfinite(exposure) or exposure <= 0:
            raise ValueError("曝光时间必须为有限正数，单位为秒")
        camera = self._require_open_camera()
        was_grabbing = self.is_grabbing
        if was_grabbing:
            self.stop_acquisition()
        try:
            camera.exposure_time = exposure
        finally:
            # Recreate the recorder so old-exposure frames cannot be returned.
            if was_grabbing:
                self.start_acquisition()

    def get_ex_time(self) -> float:
        return float(self._require_open_camera().exposure_time)

    def set_trigger_mode(self, mode: str) -> None:
        normalized = mode.strip().lower()
        if normalized not in {"continuous", "software"}:
            raise ValueError("触发模式仅支持 'continuous' 或 'software'")
        camera = self._require_open_camera()
        if normalized == self._trigger_mode:
            return
        was_grabbing = self.is_grabbing
        if was_grabbing:
            self.stop_acquisition()
        try:
            camera.configuration = {
                "trigger": "software trigger" if normalized == "software" else "auto sequence"
            }
            self._trigger_mode = normalized
        finally:
            if was_grabbing:
                self.start_acquisition()

    def trigger(self) -> None:
        camera = self._require_open_camera()
        if self._trigger_mode != "software":
            raise RuntimeError("请先调用 set_trigger_mode('software') 再触发")
        if not self.is_grabbing:
            self.start_acquisition()
        self._recording_status()
        result = camera.sdk.force_trigger()
        if result["triggered"] != "successful":
            raise RuntimeError("PCO 软件触发未被接受，相机可能仍在曝光或读出")

    def _recording_status(self) -> dict:
        status = self._require_open_camera().rec.get_status()
        error = status["dwLastError"]
        if error:
            raise RuntimeError(f"PCO Recorder 采集错误：0x{error:08X}")
        if not status["bIsRunning"]:
            raise RuntimeError("PCO Recorder 已停止，请停止采集后重新启动并检查相机连接")
        return status

    def _wait_for_count(self, target: int, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while True:
            if self._recording_status()["dwProcImgCount"] >= target:
                return
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"PCO 等待新图像超时（{timeout:.3f} 秒，{self._trigger_mode} 模式）；"
                    "请检查相机连接、曝光时间及触发信号"
                )
            time.sleep(0.001)

    def wait_for_frame(self, nframes: int = 1, timeout: float | None = None) -> None:
        """Wait for nframes after the last read/flush, without consuming an image."""
        if isinstance(nframes, bool) or not isinstance(nframes, int) or nframes < 1:
            raise ValueError("nframes 必须为正整数")
        if timeout is not None and (not math.isfinite(timeout) or timeout <= 0):
            raise ValueError("timeout 必须为有限正数")
        if not self.is_grabbing:
            self.start_acquisition()
        if timeout is None:
            # Allow long exposures/readout plus transport overhead.
            timeout = max(self._frame_timeout_s, nframes * self.get_frame_period() + 2.0)
        self._wait_for_count(self._last_image_number + nframes, timeout)

    def read_newest_image(self) -> np.ndarray:
        """Wait for an unread frame; propagate timeouts/SDK errors to the GUI."""
        camera = self._require_open_camera()
        self.wait_for_frame()
        image, metadata = camera.image(image_index=self._LATEST_IMAGE, data_format="Mono16")
        number = int(metadata["recorder image number"])
        if number <= self._last_image_number:
            raise RuntimeError("PCO 返回了重复帧，请重新启动采集")
        if image is None or image.ndim != 2 or image.size == 0:
            raise RuntimeError("PCO 返回了空图像或非二维图像")
        # Own the memory even if a subsequent SDK call reuses its image buffer.
        result = np.array(image, copy=True)
        self._last_image_number = number
        self.last_metadata = dict(metadata)
        return result

    def flush_image_queue(self) -> bool:
        """Skip completed frames; the next read must wait for a newer frame."""
        self._require_open_camera()
        if self.is_grabbing:
            self._last_image_number = int(self._recording_status()["dwProcImgCount"])
        return True

    def get_frame_period(self) -> float:
        """Return SDK camera cycle time in seconds (excluding external trigger wait)."""
        camera = self._require_open_camera()
        runtime = camera.sdk.get_coc_runtime()
        period = float(runtime["time second"]) + float(runtime["time nanosecond"]) * 1e-9
        return max(period, self.get_ex_time() + float(camera.delay_time))

    def get_bit_depth(self) -> int:
        return int(self._require_open_camera().description["bit resolution"])

    def snap(self) -> np.ndarray:
        """Acquire a fresh image and restore the prior streaming state."""
        self._require_open_camera()
        was_grabbing = self.is_grabbing
        self.stop_acquisition()
        try:
            self.start_acquisition()
            if self._trigger_mode == "software":
                self.trigger()
            return self.read_newest_image()
        finally:
            self.stop_acquisition()
            if was_grabbing:
                self.start_acquisition()

    def close(self) -> None:
        camera = self.cam
        if camera is None:
            return
        try:
            self.stop_acquisition()
        finally:
            try:
                camera.close()
            finally:
                self.cam = None
                self.is_open = False
                self.is_grabbing = False

    def __enter__(self) -> "PCOCamera":
        self._require_open_camera()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()
