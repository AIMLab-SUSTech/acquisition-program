import os
import time
from time import sleep
from PyQt5.QtWidgets import QMainWindow, QApplication, QGraphicsScene, QFileDialog
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import QTimer, Qt
import sys

from gui_simple import Ui_MainWindow
from camera import IDS, Ham
from VSY import VSyCamera as vsy
from VSY import VsyGvspPixelType
from motion_controller import xps, smartact, nators
import numpy as np
from PIL import Image
from Scanner import Scanner
from copy import deepcopy

# 帧周期保护：相机不报帧率/报异常值时的回退值，以及 QTimer 间隔下限（防 0ms 忙循环）
DEFAULT_FRAME_PERIOD_MS = 100
MIN_FRAME_PERIOD_MS = 10
# 扫描：台子到位超时（秒）与相邻扫描点间隔（毫秒）
SCAN_SETTLE_TIMEOUT = 60.0
SCAN_STEP_INTERVAL_MS = 300


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.camera = None
        self.motion_controller = None
        self.photon = 20
        self.x_offset = 0
        self.y_offset = 0
        self.xpixel_num = 1024
        self.ypixel_num = 1024
        self.ex_time = 0.36
        self.save_path = None
        self.step = None
        self.scan_num = None
        self.subimage_num = None
        self.xmotion = None
        self.y_motion = None
        self.motion = None
        self.pixel_type = None
        self.scene = QGraphicsScene()  # 创建画布
        self.ui.image.setScene(self.scene)  # 把画布添加到窗口
        self.image_timer = None
        self.photon_timer = None
        self.frame_period = 0
        self.cur_point = 0
        self.scan_active = False
        self.x = []
        self.y = []
        self.abs_x = []
        self.abs_y = []
        self.final_pos = None
        self.center = None
        self.dark = None  # 暗帧参考（仅保存为 0.png，不再用于暗减）
        self.dps = []
        # 逐帧扫描位置（mm，扫描原点相对）与时间戳（Unix epoch 秒），随 dps 一并写入 h5
        self.pos_x = []
        self.pos_y = []
        self.timestamp = []

        # 这里添加事件响应
        self.ui.carmera_init.clicked.connect(self.init_camera)
        self.ui.init_motion_ctr.clicked.connect(self.init_mtn_ctr)
        self.ui.photon.returnPressed.connect(self.set_photon)
        # 数值输入改为 textChanged：修改即时生效，不必按回车；解析失败保留上次有效值
        self.ui.xbias.textChanged.connect(self._on_xbias_changed)
        self.ui.ybias.textChanged.connect(self._on_ybias_changed)
        self.ui.xpixel_num.textChanged.connect(self._on_xpixel_num_changed)
        self.ui.ypixel_num.textChanged.connect(self._on_ypixel_num_changed)
        self.ui.ex_time.textChanged.connect(self._on_ex_time_changed)
        self.ui.save_path.textChanged.connect(self._on_save_path_changed)
        self.ui.save_path_browse.clicked.connect(self._choose_save_path)
        self.ui.step.textChanged.connect(self._on_step_changed)
        self.ui.scan_num.textChanged.connect(self._on_scan_num_changed)
        # 位移台移动指令保持回车触发：textChanged 会在每次击键时驱动台子移动，不安全
        self.ui.xmotion.returnPressed.connect(self.set_xmotion)
        self.ui.y_motion.returnPressed.connect(self.set_ymotion)
        self.ui.log.clicked.connect(self.set_log)
        self.ui.save_image.clicked.connect(self.save_dark)

    # ------------------------------------------------------------------
    # 通用小工具
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_number(text, dtype, fallback=None):
        """把文本解析为 dtype；解析失败返回 fallback（不抛异常）"""
        try:
            return dtype(str(text).strip())
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _frame_period_ms(period):
        """帧周期（秒）→ QTimer 毫秒间隔；异常/非有限/<=0 用默认值，且不低于下限"""
        try:
            value = float(period)
        except (TypeError, ValueError):
            return DEFAULT_FRAME_PERIOD_MS
        if not np.isfinite(value) or value <= 0:
            return DEFAULT_FRAME_PERIOD_MS
        return max(int(value * 1000), MIN_FRAME_PERIOD_MS)

    def _show_status(self, text, timeout_ms=10000):
        """状态栏提示 + 控制台打印"""
        print(text)
        try:
            self.statusBar().showMessage(str(text), timeout_ms)
        except Exception:
            pass

    def _set_number(self, widget, dtype, attr, hint, validate=None):
        """统一的数值输入处理：解析/校验失败时保留上次有效值并提示，不抛异常"""
        text = widget.text().strip()
        value = self._parse_number(text, dtype, None)
        if value is None:
            if text:
                self._show_status(f'{hint}输入无效，保留上次值（需为{dtype.__name__}）')
            return
        if validate is not None and not validate(value):
            self._show_status(f'{hint}取值无效，保留上次值')
            return
        setattr(self, attr, value)

    # ------------------------------------------------------------------
    # 输入响应（textChanged，不必回车）
    # ------------------------------------------------------------------
    def _on_xbias_changed(self):
        self._set_number(self.ui.xbias, int, 'x_offset', 'x像素偏移')

    def _on_ybias_changed(self):
        self._set_number(self.ui.ybias, int, 'y_offset', 'y像素偏移')

    def _on_xpixel_num_changed(self):
        self._set_number(self.ui.xpixel_num, int, 'xpixel_num', 'x像素数量', lambda v: v > 0)

    def _on_ypixel_num_changed(self):
        self._set_number(self.ui.ypixel_num, int, 'ypixel_num', 'y像素数量', lambda v: v > 0)

    def _on_step_changed(self):
        self._set_number(self.ui.step, float, 'step', '步长', lambda v: v > 0)

    def _on_scan_num_changed(self):
        self._set_number(self.ui.scan_num, int, 'scan_num', '扫描次数', lambda v: v >= 0)

    def _on_ex_time_changed(self):
        """输入单位 ms；有效变化时立即应用到相机（相机未初始化/设置失败不影响程序）"""
        ms = self._parse_number(self.ui.ex_time.text(), float, None)
        if ms is None or ms <= 0:
            return
        self.ex_time = ms / 1000.0
        if self.camera is not None:
            try:
                self.camera.set_ex_time(self.ex_time)
            except Exception as e:
                self._show_status(f'设置曝光时间失败：{e}')

    def _on_save_path_changed(self):
        text = self.ui.save_path.text().strip()
        self.save_path = text if text else None

    def _choose_save_path(self):
        """通过文件管理器选择保存路径"""
        start = self.save_path if self.save_path else os.getcwd()
        directory = QFileDialog.getExistingDirectory(self, '选择保存路径', start)
        if directory:
            self.ui.save_path.setText(directory)  # 触发 _on_save_path_changed

    # ------------------------------------------------------------------
    # 相机
    # ------------------------------------------------------------------
    def init_camera(self):
        if self.ui.carmera_init.text() == '相机初始化':

            camera_flag = False
            try:
                if self.ui.select_cam.currentText() == 'IDS':
                    # IDS
                    self.camera = IDS()
                    self.camera.set_pixel_rate(16e7)
                    self.camera.set_color_mode('mono12')
                    self.camera.start_acquisition()
                    self.camera.wait_for_frame(2)
                    self.pixel_type = 'mono12'
                    camera_flag = True

                elif self.ui.select_cam.currentText() == 'VSY':
                    self.camera = vsy()
                    self.camera.set_pixel_format(VsyGvspPixelType.PixelType_Gvsp_Mono16)
                    self.pixel_type = 'mono16'
                    camera_flag = True

                elif self.ui.select_cam.currentText() == 'Lucid':
                    from lucid import LucidCamera
                    self.camera = LucidCamera()
                    self.pixel_type = 'mono12'
                    camera_flag = True

                elif self.ui.select_cam.currentText() == 'Ham':
                    self.camera = Ham()
                    camera_flag = True  # 此项必须
                    self.pixel_type = 'mono16'  # 此项必须

                elif self.ui.select_cam.currentText() == 'ids_peak':
                    from peak import IDSPeakCamera
                    self.camera = IDSPeakCamera()
                    camera_flag = True
                    self.pixel_type = 'mono12'

                elif self.ui.select_cam.currentText() == 'PM':
                    from photometrics import PyVCAM
                    self.camera = PyVCAM()
                    camera_flag = True
                    self.pixel_type = 'mono16'

            except Exception as e:
                self.camera = None
                self._show_status(f'相机初始化失败：{e}')

            if camera_flag:
                self.camera.start_acquisition()
                sleep(1)  # 部分相机启动需要时间，不能立刻获取图像
                raw_period = self.camera.get_frame_period()
                self.frame_period = self._frame_period_ms(raw_period)
                if self.frame_period == DEFAULT_FRAME_PERIOD_MS:
                    self._show_status(f'帧周期读取异常（{raw_period}），使用默认 {DEFAULT_FRAME_PERIOD_MS}ms')
                else:
                    print(self.frame_period)
                self.image_timer = QTimer(self)
                self.image_timer.timeout.connect(self.image_show)
                self.image_timer.start(self.frame_period)
                self.photon_timer = QTimer(self)
                self.photon_timer.timeout.connect(self.set_photon)
                self.photon_timer.start(1000)
                self.ui.carmera_init.setText('终止显示')
        else:
            self._stop_display()

    def _stop_display(self):
        if self.image_timer is not None:
            self.image_timer.stop()
        if self.photon_timer is not None:
            self.photon_timer.stop()
        self.ui.carmera_init.setText('相机初始化')

    # ------------------------------------------------------------------
    # 位移台
    # ------------------------------------------------------------------
    def init_mtn_ctr(self):
        text = self.ui.init_motion_ctr.text()
        if text == '位移台初始化':
            motion = self.ui.select_motion.currentText()
            self.motion = None
            candidate = None
            ok = False
            try:
                if motion == 'smartact':
                    candidate = smartact()
                    ok = getattr(candidate, 'motion', None) is not None
                elif motion == 'newportxps':
                    candidate = xps()
                    candidate.init_groups(['Group3', 'Group4'])
                    ok = bool(candidate.groups)
                elif motion == 'nators':
                    candidate = nators()
                    ok = candidate.open_system() is not None
                else:
                    self._show_status(f'未识别的位移台类型：{motion}')
            except Exception as e:
                self._show_status(f'位移台初始化失败：{e}')
            if ok:
                self.motion = candidate
                self.ui.init_motion_ctr.setText('开始扫描')
            else:
                self.motion = None
                self._show_status('位移台初始化失败，请检查设备连接后重试', timeout_ms=30000)

        elif text == '开始扫描':
            self._start_scan()

        else:  # '终止位移台移动'
            self._stop_motion()

    def _stop_motion(self):
        """终止按钮：真正下发停止命令，扫描进行中则保存已采数据"""
        was_scanning = self.scan_active
        self.scan_active = False
        if self.motion is not None:
            try:
                self.motion.stop_all()
                self._show_status('已下发位移台停止命令')
            except NotImplementedError:
                self._show_status('该位移台未实现停止命令，请手动确认设备状态', timeout_ms=30000)
            except Exception as e:
                self._show_status(f'位移台停止失败：{e}')
        if was_scanning:
            self._save_dps(partial=True)
        self.ui.init_motion_ctr.setText('开始扫描')

    # ------------------------------------------------------------------
    # 扫描
    # ------------------------------------------------------------------
    def check_path(self):
        if not self.save_path:
            self.save_path = 'data'
            self.ui.save_path.setText(self.save_path)
        try:
            os.makedirs(self.save_path, exist_ok=True)
        except Exception as e:
            self._show_status(f'保存路径错误：{e}')
            return False
        return True

    def generate_scan_point(self):
        mode = self.ui.scan_mode.currentText()
        mode_mapping = {
            '矩形': 'rectangle',
            '圆形': 'round',
        }
        normalized_mode = mode_mapping.get(mode)
        if normalized_mode is None:
            raise ValueError(f'未知扫描方式：{mode}')
        if self.step is None:
            raise ValueError('请先输入步长(mm)')
        if self.scan_num is None:
            raise ValueError('请先输入扫描次数')
        scanner = Scanner(
            step=self.step,
            scan_num=self.scan_num,
            mode=normalized_mode
        )

        attributes = ['x', 'y', 'abs_x', 'abs_y', 'final_pos']

        for attr in attributes:
            original_value = getattr(scanner, attr)
            setattr(self, attr, deepcopy(original_value) if isinstance(original_value, list) else original_value)

    def _start_scan(self):
        if self.camera is None:
            self._show_status('请先初始化相机', timeout_ms=30000)
            return
        if self.motion is None:
            self._show_status('请先初始化位移台', timeout_ms=30000)
            return
        if not self.check_path():
            return
        # h5 的 dps 数据集需要暗减，故扫描前必须先有暗帧
        if self.dark is None:
            self._show_status('请先点击"保存图片"采集暗帧', timeout_ms=30000)
            return
        try:
            self.generate_scan_point()
        except Exception as e:
            self._show_status(f'生成扫描点失败：{e}', timeout_ms=30000)
            return
        # 重置扫描状态：修复重扫时 cur_point 越界、dps 与上次数据混合
        self.cur_point = 0
        self.dps = []
        self.pos_x = []
        self.pos_y = []
        self.timestamp = []
        self.scan_active = True
        self._show_status(f'开始扫描，共 {len(self.x)} 个点')
        self._scan_step()

    def _scan_step(self):
        """单步扫描：移动→等待到位→拍照。任一步失败即中止扫描（停台+保存已采数据）。"""
        if not self.scan_active:
            return
        if self.cur_point >= len(self.x):
            self._finish_scan()
            return
        try:
            self.motion.move_by(self.x[self.cur_point], axis=0)
            self.motion.move_by(self.y[self.cur_point], axis=1)
            # P1 修复：必须确认台子到位后再拍照，替代原 sleep(0.8) 启发式
            if not self.motion.wait_idle(timeout=SCAN_SETTLE_TIMEOUT):
                raise RuntimeError('位移台未在超时内到位')
            self.cur_point += 1
            self.save_image(self.cur_point)
        except Exception as e:
            self._abort_scan(e)
            return
        QTimer.singleShot(SCAN_STEP_INTERVAL_MS, self._scan_step)

    def _abort_scan(self, error):
        self.scan_active = False
        try:
            self.motion.stop_all()
        except Exception:
            pass
        self._show_status(f'扫描中止：{error}', timeout_ms=30000)
        self._save_dps(partial=True)

    def _finish_scan(self):
        self.scan_active = False
        # 顺序回零（先 X 后 Y，与原版一致），每段移动都等待到位
        try:
            self.motion.move_by(-self.final_pos[0], axis=0)
            self.motion.wait_idle(timeout=SCAN_SETTLE_TIMEOUT)
            self.motion.move_by(-self.final_pos[1], axis=1)
            self.motion.wait_idle(timeout=SCAN_SETTLE_TIMEOUT)
        except Exception as e:
            self._show_status(f'回零失败：{e}', timeout_ms=30000)
        self._save_dps(partial=False)

    def _save_dps(self, partial=False):
        if not self.dps:
            self._show_status('没有可保存的图像数据', timeout_ms=30000)
            return
        try:
            from h5py import File
            with File(os.path.join(self.save_path, 'dps.h5'), 'w') as f:
                f.create_dataset('dps', data=self.dps)
                # 扫描位置（mm，扫描原点相对）与逐帧时间戳（Unix epoch 秒）
                f.create_dataset('pos_x', data=np.array(self.pos_x, dtype=np.float64))
                f.create_dataset('pos_y', data=np.array(self.pos_y, dtype=np.float64))
                f.create_dataset('timestamp', data=np.array(self.timestamp, dtype=np.float64))
            tag = '（部分数据）' if partial else ''
            self._show_status(f'已保存 {len(self.dps)} 帧{tag}：{os.path.join(self.save_path, "dps.h5")}',
                              timeout_ms=30000)
        except Exception as e:
            self._show_status(f'保存 dps 失败：{e}', timeout_ms=30000)

    # ------------------------------------------------------------------
    # 显示与保存
    # ------------------------------------------------------------------
    def image_show(self):
        try:
            image = self.camera.read_newest_image()
            if image is None:
                self._show_status('相机未返回图像，跳过本帧')
                return
            image = self.crop_image(image)
            self.photon = np.max(image)
            if self.ui.log.text() == '正常显示':
                image = (4095 * np.log10(9 * image / 4095 + 1)).astype(np.uint16)

            if self.pixel_type == 'mono12':
                frame = QImage(image << 4, image.shape[0], image.shape[1], QImage.Format_Grayscale16)
            elif self.pixel_type == 'mono16':
                frame = QImage(image, image.shape[0], image.shape[1], QImage.Format_Grayscale16)
            elif image.dtype == np.uint8:
                frame = QImage(image, image.shape[0], image.shape[1], QImage.Format_RGB888)
            else:
                self._show_status(f'不支持的图像类型：{image.dtype}')
                return
            frame = frame.scaled(640, 640, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pix = QPixmap.fromImage(frame)
            self.scene.clear()
            self.scene.addPixmap(pix)
        except Exception as e:
            self._show_status(f'显示图像出错：{e}')

    def save_image(self, name=0):
        """保存图像：PNG 存原始帧（不暗减），h5 的 dps 数据集存暗减后的帧。
        name=0：暗帧参考帧（保存为 0.png，不进 dps）；
        name>0：扫描帧，暗减后追加到 dps 并记录该点位置与时间戳。"""
        try:
            image_ = self.camera.read_newest_image()
            if image_ is None:
                raise RuntimeError('相机未返回图像')
            image_ = self.crop_image(image_)
            if name == 0:
                self.dark = image_.copy()
            else:
                if self.dark is None:
                    raise RuntimeError('没有暗帧，请先点击"保存图片"采集暗帧')
                if self.dark.shape != image_.shape:
                    raise RuntimeError(f'暗帧形状 {self.dark.shape} 与图像形状 {image_.shape} 不一致')
                # h5 数据集：int32 相减再截断到 [0, 65535]，避免 uint16 下溢回绕（P1-1）
                self.dps.append(np.clip(
                    image_.astype(np.int32) - self.dark.astype(np.int32),
                    0, np.iinfo(np.uint16).max
                ).astype(np.uint16))
                # 帧序号 name 对应扫描点索引 name-1（首帧存于原点）
                self.pos_x.append(self.abs_x[name - 1])
                self.pos_y.append(self.abs_y[name - 1])
                self.timestamp.append(time.time())
            # PNG 保存原始帧（不做暗场相减）
            image_ = Image.fromarray(image_)
            if not os.path.exists(self.save_path):
                os.makedirs(self.save_path, exist_ok=True)

            save_path = os.path.join(self.save_path, f'{name}.png')
            print(save_path)
            image_.save(save_path)

        except Exception as e:
            raise e

    def save_dark(self):
        if self.camera is None:
            self._show_status('请先初始化相机')
            return
        if not self.check_path():
            return
        try:
            self.save_image(0)
            self._show_status('暗帧已保存')
        except Exception as e:
            self._show_status(f'暗帧保存失败：{e}')

    def find_center(self, image):
        image = image - np.mean(image)
        image[image < 0] = 0
        image = image / np.max(image)

        total_intensity = np.sum(image)

        # 生成坐标网格
        y_indices, x_indices = np.indices(image.shape)

        # 计算加权质心坐标
        print(np.sum(x_indices * image))
        x_center = np.sum(x_indices * image) / total_intensity
        y_center = np.sum(y_indices * image) / total_intensity

        # 确保坐标在图像范围内
        x_center = np.clip(x_center, 0, image.shape[1] - 1)
        y_center = np.clip(y_center, 0, image.shape[0] - 1)

        return (int(round(x_center)), int(round(y_center)))

    def crop_image(self, image):
        if image.ndim == 2:
            width, height = image.shape
        else:
            width, height, _ = image.shape

        x1 = width // 2 - self.xpixel_num // 2
        y1 = height // 2 - self.ypixel_num // 2
        x2 = x1 + self.xpixel_num
        y2 = y1 + self.ypixel_num

        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(width, x2)
        y2 = min(height, y2)
        if image.ndim == 2:
            new_image = image[x1:x2, y1:y2]
        else:
            new_image = image[x1:x2, y1:y2, :]
        return new_image.astype(image.dtype)

    # ------------------------------------------------------------------
    # 其他 UI 操作
    # ------------------------------------------------------------------
    def set_xmotion(self):
        distance = self._parse_number(self.ui.xmotion.text(), float, None)
        if distance is None:
            self._show_status('X轴位移输入无效（单位mm）')
            return
        if self.motion is None:
            self._show_status('请先初始化位移台')
            return
        try:
            self.motion.move_by(distance, axis=0)
        except Exception as e:
            self._show_status(f'X轴移动失败：{e}')

    def set_ymotion(self):
        distance = self._parse_number(self.ui.y_motion.text(), float, None)
        if distance is None:
            self._show_status('Y轴位移输入无效（单位mm）')
            return
        if self.motion is None:
            self._show_status('请先初始化位移台')
            return
        try:
            self.motion.move_by(distance, axis=1)
        except Exception as e:
            self._show_status(f'Y轴移动失败：{e}')

    def set_photon(self):
        self.ui.photon.setText(str(self.photon))

    def set_log(self):
        if self.image_timer is None:
            self._show_status('请先初始化相机')
            return
        if self.ui.log.text() == 'log显示':
            self.ui.log.setText('正常显示')
            self.image_timer.stop()
            self.frame_period += 10
            self.image_timer.start(self.frame_period)
        else:
            self.ui.log.setText('log显示')
            self.image_timer.stop()
            self.frame_period = max(self.frame_period - 10, MIN_FRAME_PERIOD_MS)
            self.image_timer.start(self.frame_period)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
