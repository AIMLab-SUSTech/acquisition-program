import numpy as np
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene
from PyQt6.QtGui import QImage, QPixmap, QPen, QColor
from PyQt6.QtCore import Qt, pyqtSignal

class InteractiveImageView(QGraphicsView):
    mouse_hover_signal = pyqtSignal(int, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pixmap_item = None
        self.np_img = None 
        self.setMouseTracking(True) 
        self.setStyleSheet("background: #000; border: 0px;")
        
        self.v_line = None
        self.h_line = None
        self.circle = None

    def update_image(self, image_data, show_mask=False):
        # 保存原始数据引用
        self.np_img = image_data
        
        # 转换数据用于显示
        if image_data.dtype == np.uint16:
            display_data = image_data # 显示时通常需要压缩位深，这里保持原逻辑
        else:
            display_data = image_data.astype(np.uint16)

        h, w = display_data.shape
        # 注意：这里假设 format 是 Grayscale16，根据实际情况可能需调整
        qimg = QImage(display_data.data, w, h, w * 2, QImage.Format.Format_Grayscale16)
        pix = QPixmap.fromImage(qimg)
        
        # 更新图片对象
        if self.pixmap_item is None:
            self.pixmap_item = self.scene.addPixmap(pix)
            self.pixmap_item.setZValue(0)
        else:
            self.pixmap_item.setPixmap(pix)

        # 绘制 Mask
        self._draw_mask(w, h, show_mask)

        # 自动适应视图大小
        self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def _draw_mask(self, w, h, show_mask):
        # 清理旧图形
        if self.v_line: self.scene.removeItem(self.v_line); self.v_line = None
        if self.h_line: self.scene.removeItem(self.h_line); self.h_line = None
        if self.circle: self.scene.removeItem(self.circle); self.circle = None

        if show_mask:
            cx, cy = w / 2, h / 2
            r = min(w, h) / 2 - 10
            
            pen_v = QPen(QColor("red"), 2, Qt.PenStyle.DashLine)
            pen_h = QPen(QColor("blue"), 2, Qt.PenStyle.DashLine)
            pen_c = QPen(QColor("green"), 2, Qt.PenStyle.SolidLine)

            self.v_line = self.scene.addLine(cx, 0, cx, h, pen_v)
            self.h_line = self.scene.addLine(0, cy, w, cy, pen_h)
            self.circle = self.scene.addEllipse(cx-r, cy-r, r*2, r*2, pen_c)
            
            self.v_line.setZValue(10)
            self.h_line.setZValue(10)
            self.circle.setZValue(10)

    def mouseMoveEvent(self, event):
        if self.np_img is not None and self.pixmap_item is not None:
            scene_pos = self.mapToScene(event.pos())
            item_pos = self.pixmap_item.mapFromScene(scene_pos)
            x, y = int(item_pos.x()), int(item_pos.y())

            h, w = self.np_img.shape
            if 0 <= x < w and 0 <= y < h:
                val = self.np_img[y, x]
                self.mouse_hover_signal.emit(x, y, val)
            else:
                self.mouse_hover_signal.emit(-1, -1, 0)
        super().mouseMoveEvent(event)