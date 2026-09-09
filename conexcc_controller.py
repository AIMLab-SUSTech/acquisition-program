import os
import sys
import time
import importlib
from typing import Optional, Tuple

try:
    # Use the same abstract interface as your existing motion_controller.py
    from motion_controller import MotionController
except ImportError:
    # Allows this file to run standalone for quick hardware tests.
    class MotionController:
        pass


class ConexCCController(MotionController):
    """
    Newport CONEX-CC dual-axis controller.

    Axis convention:
        axis=0 -> X axis
        axis=1 -> Y axis

    Position unit:
        mm

    The class uses Newport.CONEXCC.CommandInterface.dll through pythonnet.
    """

    READY_STATES = {"32", "33", "34", "36", "37", "38"}

    def __init__(
        self,
        port_x: str = "COM4",
        port_y: str = "COM5",
        dll_dir: Optional[str] = None,
        init_pos=(-13.0, -13.0),
        controller_address: int = 1,
        auto_open: bool = True,
    ):
        self.port_x = port_x
        self.port_y = port_y
        self.init_pos = [float(init_pos[0]), float(init_pos[1])]
        self.controller_address = int(controller_address)

        self.xstage = None
        self.ystage = None
        self.is_open = False

        self.ConexCC = self._load_driver(dll_dir)

        if auto_open:
            self.open()

    @staticmethod
    def _load_driver(dll_dir: Optional[str]):
        """Load Newport.CONEXCC.CommandInterface.dll and return ConexCC class."""
        try:
            import clr
        except ImportError as exc:
            raise RuntimeError(
                "pythonnet is not installed. Run: pip install pythonnet"
            ) from exc

        candidate_dirs = []
        if dll_dir:
            candidate_dirs.append(dll_dir)

        candidate_dirs.extend(
            [
                r"C:\Program Files\Newport\MotionControl\CONEX-CC\Bin",
                r"C:\Program Files (x86)\Newport\MotionControl\CONEX-CC\Bin",
            ]
        )

        dll_name = "Newport.CONEXCC.CommandInterface.dll"
        loaded = False
        last_error = None

        for folder in candidate_dirs:
            if not folder or not os.path.isdir(folder):
                continue

            if folder not in sys.path:
                sys.path.append(folder)

            dll_path = os.path.join(folder, dll_name)
            if not os.path.isfile(dll_path):
                continue

            try:
                # Modern pythonnet generally accepts the full path.
                clr.AddReference(dll_path)
                loaded = True
                break
            except Exception as exc:
                last_error = exc
                # Compatibility with older pythonnet/Newport examples.
                try:
                    if hasattr(clr, "AddReferenceToFile"):
                        clr.AddReferenceToFile(dll_name)
                        loaded = True
                        break
                except Exception as exc2:
                    last_error = exc2

        if not loaded:
            try:
                clr.AddReference("Newport.CONEXCC.CommandInterface")
                loaded = True
            except Exception as exc:
                last_error = exc

        if not loaded:
            raise RuntimeError(
                "Cannot load Newport.CONEXCC.CommandInterface.dll. "
                "Install Newport CONEX-CC software or pass dll_dir explicitly. "
                f"Last error: {last_error}"
            )

        # Newport documentation uses namespace `CommandInterface`.
        # Some installations/wrappers expose `CommandInterfaceConexCC` instead.
        for module_name in ("CommandInterface", "CommandInterfaceConexCC"):
            try:
                module = importlib.import_module(module_name)
                return getattr(module, "ConexCC")
            except (ImportError, AttributeError):
                pass

        raise RuntimeError(
            "DLL loaded, but ConexCC class was not found in CommandInterface "
            "or CommandInterfaceConexCC namespace."
        )

    def _stage(self, axis: int):
        if axis == 0:
            return self.xstage
        if axis == 1:
            return self.ystage
        raise ValueError("axis must be 0 (X) or 1 (Y)")

    def _port(self, axis: int) -> str:
        return self.port_x if axis == 0 else self.port_y

    def open(self):
        """Open X and Y CONEX-CC controllers."""
        if self.is_open:
            return

        self.xstage = self.ConexCC()
        self.ystage = self.ConexCC()

        ret_x = self.xstage.OpenInstrument(self.port_x)
        if ret_x != 0:
            self.xstage = None
            self.ystage = None
            raise RuntimeError(f"Failed to open X axis on {self.port_x}, return={ret_x}")

        ret_y = self.ystage.OpenInstrument(self.port_y)
        if ret_y != 0:
            try:
                self.xstage.CloseInstrument()
            except Exception:
                pass
            self.xstage = None
            self.ystage = None
            raise RuntimeError(f"Failed to open Y axis on {self.port_y}, return={ret_y}")

        self.is_open = True
        print(f"CONEX-CC connected: X={self.port_x}, Y={self.port_y}")

        # Print controller revisions when available.
        for axis, name in ((0, "X"), (1, "Y")):
            try:
                rev = self.get_revision(axis)
                print(f"{name} revision: {rev}")
            except Exception as exc:
                print(f"{name} revision read failed: {exc}")

    def close(self, move_to_zero: bool = False):
        """
        Close both controllers.

        move_to_zero=False by default. This is safer than automatically moving
        the stage before closing the connection.
        """
        if not self.is_open:
            return

        if move_to_zero:
            self.move_to(0.0, 0, wait=True)
            self.move_to(0.0, 1, wait=True)

        for stage in (self.xstage, self.ystage):
            if stage is not None:
                try:
                    stage.CloseInstrument()
                except Exception:
                    pass

        self.xstage = None
        self.ystage = None
        self.is_open = False
        print("CONEX-CC disconnected")

    def get_revision(self, axis: int) -> str:
        stage = self._stage(axis)
        ret, revision, err = stage.VE(self.controller_address)
        if ret != 0:
            raise RuntimeError(f"VE failed on axis {axis}: {err}")
        return str(revision)

    def get_position(self, axis: int) -> float:
        """Return logical position in mm."""
        stage = self._stage(axis)
        ret, controller_pos, err = stage.TP(self.controller_address)
        if ret != 0:
            raise RuntimeError(f"TP failed on axis {axis}: {err}")

        # Match the coordinate convention used in the supplied MATLAB class:
        # logical position = controller position + Init_pos
        return float(controller_pos) + self.init_pos[axis]

    def move_to(self, position: float, axis: int, wait: bool = True, timeout: float = 30.0):
        """Absolute move to logical position, unit: mm."""
        stage = self._stage(axis)

        controller_target = float(position) - self.init_pos[axis]
        ret, err = stage.PA_Set(self.controller_address, controller_target)
        if ret != 0:
            raise RuntimeError(
                f"PA_Set failed on axis {axis}, target={position} mm: {err}"
            )

        if wait:
            self.wait_until_ready(axis, timeout=timeout)

    def move_by(self, distance: float, axis: int, wait: bool = True, timeout: float = 30.0):
        """Relative move, unit: mm."""
        stage = self._stage(axis)

        # Relative move does not need Init_pos conversion.
        ret, err = stage.PR_Set(self.controller_address, float(distance))
        if ret != 0:
            raise RuntimeError(
                f"PR_Set failed on axis {axis}, distance={distance} mm: {err}"
            )

        if wait:
            self.wait_until_ready(axis, timeout=timeout)

    def home(self, axis: int, wait: bool = True, timeout: float = 60.0):
        """Execute HOME search."""
        stage = self._stage(axis)
        ret, err = stage.OR(self.controller_address)
        if ret != 0:
            raise RuntimeError(f"HOME failed on axis {axis}: {err}")

        if wait:
            self.wait_until_ready(axis, timeout=timeout)

    def reset(self, axis: int):
        """Reset controller. Note: reset normally makes the axis not referenced."""
        stage = self._stage(axis)
        ret, err = stage.RS(self.controller_address)
        if ret != 0:
            raise RuntimeError(f"RS failed on axis {axis}: {err}")

    def stop(self, axis: int):
        """Stop current motion."""
        stage = self._stage(axis)
        # ST signature follows the same Newport Command Interface pattern.
        result = stage.ST(self.controller_address)
        if isinstance(result, tuple):
            ret = result[0]
            err = result[-1] if len(result) > 1 else ""
        else:
            ret = result
            err = ""
        if ret != 0:
            raise RuntimeError(f"ST failed on axis {axis}: {err}")

    def get_status(self, axis: int) -> Tuple[str, str]:
        """
        Return (positioner_error_code, controller_state).

        Official TS signature:
            TS(address) -> ret, errorCode, controllerState, errString
        """
        stage = self._stage(axis)
        result = stage.TS(self.controller_address)

        if not isinstance(result, tuple) or len(result) != 4:
            raise RuntimeError(f"Unexpected TS return value on axis {axis}: {result!r}")

        ret, error_code, controller_state, err = result
        if ret != 0:
            raise RuntimeError(f"TS failed on axis {axis}: {err}")

        return str(error_code).strip(), str(controller_state).strip().upper()

    def wait_until_ready(self, axis: int, timeout: float = 30.0, poll_interval: float = 0.05):
        """Wait until the controller enters a READY state."""
        t0 = time.monotonic()
        last_state = None

        while True:
            error_code, state = self.get_status(axis)
            last_state = state

            if error_code not in ("0000", "0", ""):
                # TS reads/clears the controller error buffer; report it immediately.
                raise RuntimeError(
                    f"CONEX-CC axis {axis} reports error code {error_code}, state={state}"
                )

            if state in self.READY_STATES:
                return state

            if time.monotonic() - t0 > timeout:
                raise TimeoutError(
                    f"Axis {axis} motion timeout after {timeout:.1f}s, last state={last_state}"
                )

            time.sleep(poll_interval)

    def set_zero(self, axis: int, wait: bool = True):
        """Move the logical coordinate to 0 mm. This does NOT redefine encoder zero."""
        self.move_to(0.0, axis, wait=wait)

    def __enter__(self):
        if not self.is_open:
            self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close(move_to_zero=False)


if __name__ == "__main__":
    # Example: change COM ports if Windows Device Manager shows different values.
    cc = ConexCCController(
        port_x="COM4",
        port_y="COM5",
        init_pos=(-13.0, -13.0),
    )

    try:
        print("X position:", cc.get_position(0), "mm")
        print("Y position:", cc.get_position(1), "mm")

        # Test with a small displacement first.
        cc.move_by(0.10, axis=0)
        print("X after move:", cc.get_position(0), "mm")

        # Absolute logical-coordinate move example:
        # cc.move_to(-12.0, axis=0)

        # Home example. Use only when you really want a HOME search:
        # cc.home(0)
        # cc.home(1)

    finally:
        cc.close(move_to_zero=False)
