"""PyLabLib adapter for Thorlabs compact scientific cameras."""

from __future__ import annotations

import os
from typing import Any

import numpy as np

from camera import Camera


def _load_backend() -> Any:
    """Load PyLabLib lazily so other camera drivers remain usable without it."""
    try:
        import pylablib as pll

        dll_directory = os.getenv("THORLABS_TLCAM_DLL_PATH")
        if dll_directory:
            pll.par["devices/dlls/thorlabs_tlcam"] = dll_directory

        from pylablib.devices import Thorlabs
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "索雷博相机驱动加载失败。请在当前 Python 环境安装 pylablib，"
            "并确认 ThorCam 已安装。"
        ) from exc
    return Thorlabs


def list_cameras(backend: Any | None = None) -> list[str]:
    """Return serial numbers reported by PyLabLib's TLCamera backend."""
    thorlabs = backend or _load_backend()
    return list(thorlabs.list_cameras_tlcam())


class ThorlabsCamera(Camera):
    """Expose ``ThorlabsTLCamera`` through the project's ``Camera`` API."""

    supports_software_trigger = True
    read_waits_for_new_frame = True
    trigger_mode_settle_s = 0.0

    def __init__(
        self,
        serial_number: str | None = None,
        frame_timeout_s: float = 2.0,
        buffer_count: int = 32,
        backend: Any | None = None,
    ) -> None:
        super().__init__()
        if frame_timeout_s <= 0:
            raise ValueError("frame_timeout_s 必须大于 0")
        if buffer_count <= 0:
            raise ValueError("buffer_count 必须大于 0")

        self.cam: Any | None = None
        self.serial_number: str | None = None
        self.is_open = False
        self.is_grabbing = False
        self._trigger_mode = "continuous"
        self._frame_timeout_s = float(frame_timeout_s)
        self._buffer_count = int(buffer_count)

        thorlabs = backend or _load_backend()
        serials = list(thorlabs.list_cameras_tlcam())
        if not serials:
            raise RuntimeError(
                "未发现索雷博科学相机，请关闭 ThorCam 并检查相机连接和驱动"
            )
        if serial_number is not None and serial_number not in serials:
            raise ValueError(
                f"未找到序列号 {serial_number!r}；可用相机: {', '.join(serials)}"
            )

        selected_serial = serial_number or serials[0]
        try:
            self.cam = thorlabs.ThorlabsTLCamera(serial=selected_serial)
            self.cam.set_color_format(color_output="raw")
            self.cam.set_trigger_mode("int")
            self.serial_number = selected_serial
            self.is_open = True
        except Exception:
            self.close()
            raise

        device_info = self.cam.get_device_info()
        model = getattr(device_info, "model", "Thorlabs")
        print(
            f"索雷博科学相机已初始化 ({model}, SN: {self.serial_number}, "
            f"位深: {self.get_bit_depth()}bit)"
        )

    def _require_open_camera(self) -> Any:
        if not self.is_open or self.cam is None:
            raise RuntimeError("索雷博科学相机未打开或已关闭")
        return self.cam

    def set_ex_time(self, ex_time: float) -> None:
        """Set exposure in seconds, matching ``Camera.set_ex_time``."""
        exposure_seconds = float(ex_time)
        if exposure_seconds <= 0:
            raise ValueError("曝光时间必须大于 0 秒")
        self._require_open_camera().set_exposure(exposure_seconds)

    def get_ex_time(self) -> float:
        """Return exposure in seconds."""
        return float(self._require_open_camera().get_exposure())

    def start_acquisition(self) -> None:
        """Start continuous streaming or arm one-frame software triggering."""
        camera = self._require_open_camera()
        if self.is_grabbing:
            return

        camera.set_trigger_mode("int")
        if self._trigger_mode == "continuous":
            camera.start_acquisition(
                frames_per_trigger=None,
                auto_start=True,
                nframes=self._buffer_count,
            )
        else:
            camera.start_acquisition(
                frames_per_trigger=1,
                auto_start=False,
                nframes=self._buffer_count,
            )
        self.is_grabbing = True

    def stop_acquisition(self) -> None:
        """Stop acquisition; safe to call repeatedly."""
        if self.cam is None or not self.is_grabbing:
            return
        try:
            self.cam.stop_acquisition()
        finally:
            self.is_grabbing = False

    def set_trigger_mode(self, mode: str) -> None:
        """Select continuous streaming or one frame per software trigger."""
        normalized_mode = mode.strip().lower()
        if normalized_mode not in {"continuous", "software"}:
            raise ValueError("触发模式仅支持 'continuous' 或 'software'")
        if normalized_mode == self._trigger_mode:
            return

        was_grabbing = self.is_grabbing
        if was_grabbing:
            self.stop_acquisition()
        self._trigger_mode = normalized_mode
        if was_grabbing:
            self.start_acquisition()

    def trigger(self) -> None:
        """Send one PyLabLib software trigger."""
        camera = self._require_open_camera()
        if self._trigger_mode != "software":
            raise RuntimeError("发送软触发前请先调用 set_trigger_mode('software')")
        if not self.is_grabbing:
            self.start_acquisition()
        camera.send_software_trigger()

    def read_newest_image(self) -> np.ndarray | None:
        """Wait for a new frame and return the newest unread image."""
        camera = self._require_open_camera()
        if not self.is_grabbing:
            self.start_acquisition()

        try:
            camera.wait_for_frame(timeout=self._frame_timeout_s)
        except Exception as exc:
            timeout_error = getattr(camera, "TimeoutError", None)
            if timeout_error is not None and isinstance(exc, timeout_error):
                return None
            raise

        image = camera.read_newest_image()
        return None if image is None else np.array(image, copy=True)

    def flush_image_queue(self) -> bool:
        """Mark every currently buffered PyLabLib frame as read."""
        camera = self._require_open_camera()
        # Reading the newest frame advances PyLabLib's read pointer past all
        # older buffered frames without racing a continuously arriving stream.
        camera.read_newest_image()
        return True

    def get_frame_period(self) -> float:
        """Return the current frame period in seconds."""
        return float(self._require_open_camera().get_frame_period())

    def set_frame_rate(self, frame_rate: float) -> None:
        """Set frame-rate control in frames per second."""
        requested_rate = float(frame_rate)
        if requested_rate <= 0:
            raise ValueError("帧率必须大于 0 FPS")
        self._require_open_camera().set_frame_period(1.0 / requested_rate)

    def get_bit_depth(self) -> int:
        """Return sensor bit depth reported by PyLabLib."""
        sensor_info = self._require_open_camera().get_sensor_info()
        if hasattr(sensor_info, "bit_depth"):
            return int(sensor_info.bit_depth)
        return int(sensor_info[1])

    def snap(self) -> np.ndarray | None:
        """Acquire one image while preserving the previous acquisition mode."""
        was_grabbing = self.is_grabbing
        previous_mode = self._trigger_mode
        if was_grabbing:
            self.stop_acquisition()
        try:
            self._trigger_mode = "software"
            self.start_acquisition()
            self.trigger()
            return self.read_newest_image()
        finally:
            self.stop_acquisition()
            self._trigger_mode = previous_mode
            if was_grabbing:
                self.start_acquisition()

    def close(self) -> None:
        """Close the PyLabLib camera connection."""
        if self.cam is None:
            return
        camera = self.cam
        try:
            self.stop_acquisition()
        finally:
            try:
                camera.close()
            finally:
                self.cam = None
                self.is_open = False

    def __enter__(self) -> "ThorlabsCamera":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
