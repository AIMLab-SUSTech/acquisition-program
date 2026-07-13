import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QFrame, QLabel, QPushButton, QLineEdit, QComboBox,
    QRadioButton, QDialog, QScrollArea, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QColor

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib

# 优化 Matplotlib 现代渲染样式
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'sans-serif']
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['grid.color'] = '#E2E8F0'
matplotlib.rcParams['grid.linestyle'] = '--'

# 现代扁平化样式表 (QSS)
MODERN_STYLE = """
QMainWindow {
    background-color: #F1F5F9;
}
QWidget #Sidebar {
    background-color: #FFFFFF;
    border-right: 1px solid #E2E8F0;
}
/* 卡片式设计 */
QFrame.Card {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
}
QFrame.Card:hover {
    border: 1px solid #CBD5E1;
}
/* 分组小标题 */
QLabel#SectionTitle {
    color: #1E293B;
    font-size: 13px;
    font-weight: bold;
    padding-bottom: 4px;
    border-bottom: 2px solid #3B82F6;
}
/* 现代输入框与下拉框 */
QLineEdit, QComboBox {
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 5px 8px;
    background-color: #FFFFFF;
    color: #334155;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #3B82F6;
}
/* 现代主动作按钮 */
QPushButton#PrimaryBtn {
    background-color: #2563EB;
    color: white;
    font-weight: bold;
    border: none;
    padding: 8px 12px;
    border-radius: 6px;
}
QPushButton#PrimaryBtn:hover {
    background-color: #1D4ED8;
}
/* 成功/绿色按钮 */
QPushButton#SuccessBtn {
    background-color: #16A34A;
    color: white;
    font-weight: bold;
    border: none;
    padding: 10px 12px;
    border-radius: 6px;
}
QPushButton#SuccessBtn:hover {
    background-color: #15803D;
}
/* 危险/红色按钮 */
QPushButton#DangerBtn {
    background-color: #EF4444;
    color: white;
    font-weight: bold;
    border: none;
    padding: 8px 12px;
    border-radius: 6px;
}
QPushButton#DangerBtn:hover {
    background-color: #DC2626;
}
/* 普通/次要按钮 */
QPushButton#SecondaryBtn {
    background-color: #F8FAFC;
    color: #475569;
    border: 1px solid #CBD5E1;
    padding: 6px 12px;
    border-radius: 6px;
}
QPushButton#SecondaryBtn:hover {
    background-color: #F1F5F9;
    border: 1px solid #94A3B8;
}
"""

class IndividualChartCanvas(FigureCanvas):
    """独立的单张图表画布"""
    def __init__(self, title):
        fig = Figure(figsize=(4, 3), dpi=100)
        fig.patch.set_facecolor('#FFFFFF')
        self.ax = fig.add_subplot(111)
        
        # 现代极简图表轴设计
        self.ax.set_title(title, fontsize=11, fontweight='bold', color='#1E293B', pad=10)
        self.ax.set_xlim(0, 1)
        self.ax.set_ylim(0, 1)
        self.ax.set_xlabel("X 轴", fontsize=9, color='#64748B')
        self.ax.set_ylabel("Y 轴", fontsize=9, color='#64748B')
        self.ax.grid(True)
        self.ax.tick_params(direction='in', colors='#94A3B8', labelsize=8)
        
        fig.tight_layout()
        super().__init__(fig)


class ModernChartCard(QFrame):
    """支持双击无缝弹窗放大的现代图表卡片组件"""
    def __init__(self, title, row, col, grid_layout):
        super().__init__()
        self.title = title
        self.row = row
        self.col = col
        self.grid_layout = grid_layout
        self.is_popped_out = False
        
        # 声明样式类名
        self.setObjectName("ChartCard")
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            #ChartCard {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 12px;
            }
        """)
        
        # 布局布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        
        # 嵌入画布
        self.canvas = IndividualChartCanvas(title)
        layout.addWidget(self.canvas)

    def mouseDoubleClickEvent(self, event):
        """捕获双击事件"""
        if event.button() == Qt.LeftButton:
            if not self.is_popped_out:
                self.pop_out()
            else:
                self.dialog.close()

    def pop_out(self):
        """将当前卡片脱离原生网格，切入弹窗模式"""
        self.is_popped_out = True
        
        # 1. 从主界面的网格布局中剥离
        self.grid_layout.removeWidget(self)
        
        # 2. 创建一个现代清爽的对话框窗口
        self.dialog = QDialog(self.window())
        self.dialog.setWindowTitle(f"高级分析视图 - {self.title}")
        self.dialog.resize(900, 650)
        self.dialog.setMinimumSize(600, 450)
        
        dialog_layout = QVBoxLayout(self.dialog)
        dialog_layout.setContentsMargins(12, 12, 12, 12)
        # 将卡片塞入新窗口中（Qt会自动处理组件的Parent转移）
        dialog_layout.addWidget(self)
        
        # 3. 拦截弹窗关闭事件，确保关闭时能触发安全收回
        self.dialog.closeEvent = self.dialog_close_event
        self.dialog.show()
        self.canvas.draw_idle()

    def dialog_close_event(self, event):
        """弹窗关闭时的回位逻辑"""
        # 从弹窗中卸载本身
        self.setParent(None)
        
        # 完美重新塞回原来的网格行列坐标
        self.grid_layout.addWidget(self, self.row, self.col)
        self.is_popped_out = False
        
        # 刷新画布尺寸自适应
        self.canvas.draw_idle()
        event.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CMI采集重构系统")
        self.resize(1300, 850)
        self.setStyleSheet(MODERN_STYLE)
        
        # 主框架容器
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # ==================== 左侧：现代感侧边栏控制面板 ====================
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(310)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 16, 16, 16)
        sidebar_layout.setSpacing(14)
        
        # 使用可滚动区域封装左侧控制卡片，防止低分辨率屏幕溢出
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_content = QWidget()
        self.ctrl_layout = QVBoxLayout(scroll_content)
        self.ctrl_layout.setContentsMargins(0, 0, 4, 0)
        self.ctrl_layout.setSpacing(14)
        
        self.build_camera_section()
        self.build_settings_section()
        self.build_recon_section()
        self.build_data_section()
        self.build_results_section()
        
        scroll_area.setWidget(scroll_content)
        sidebar_layout.addWidget(scroll_area)
        
        # 底部状态栏
        status_card = QFrame()
        status_card.setStyleSheet("background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px;")
        status_layout = QHBoxLayout(status_card)
        status_layout.setContentsMargins(8, 6, 8, 6)
        status_lbl = QLabel("系统状态:")
        status_lbl.setStyleSheet("color: #475569; font-weight: bold; font-size:11px;")
        self.status_val = QLabel("设备就绪 (Ready)")
        self.status_val.setStyleSheet("color: #16A34A; font-weight: bold; font-size:11px;")
        status_layout.addWidget(status_lbl)
        status_layout.addWidget(self.status_val)
        status_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        sidebar_layout.addWidget(status_card)
        
        main_layout.addWidget(sidebar)
        
        # ==================== 右侧：现代卡片式 2x2 数据图表网格 ====================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        
        chart_grid_widget = QWidget()
        self.chart_grid = QGridLayout(chart_grid_widget)
        self.chart_grid.setContentsMargins(0, 0, 0, 0)
        self.chart_grid.setSpacing(14)  # 卡片间距
        
        # 初始化 4 个高度独立的、支持双击无缝放大的现代卡片
        self.card1 = ModernChartCard("记录衍射图谱 (Diffraction)", 0, 0, self.chart_grid)
        self.card2 = ModernChartCard("波前重构结果 (Reconstruction)", 0, 1, self.chart_grid)
        self.card3 = ModernChartCard("3D 能量伪彩形貌 (3D Profile)", 1, 0, self.chart_grid)
        self.card4 = ModernChartCard("多维数据统计分析 (Analysis)", 1, 1, self.chart_grid)
        
        # 装载进网格
        self.chart_grid.addWidget(self.card1, 0, 0)
        self.chart_grid.addWidget(self.card2, 0, 1)
        self.chart_grid.addWidget(self.card3, 1, 0)
        self.chart_grid.addWidget(self.card4, 1, 1)
        
        right_layout.addWidget(chart_grid_widget, stretch=1)
        main_layout.addWidget(right_panel, stretch=1)

    def create_card_container(self, title_text):
        """辅助函数：创建美观、统一的现代化表单白色卡片"""
        card = QFrame()
        card.setProperty("class", "Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        title = QLabel(title_text)
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        
        return card, layout

    def build_camera_section(self):
        card, layout = self.create_card_container("相机控制")
        
        btn_layout = QHBoxLayout()
        btn_conn = QPushButton("连接设备")
        btn_conn.setObjectName("PrimaryBtn")
        btn_disconn = QPushButton("断开连接")
        btn_disconn.setObjectName("SecondaryBtn")
        btn_layout.addWidget(btn_conn)
        btn_layout.addWidget(btn_disconn)
        layout.addLayout(btn_layout)
        
        h_layout = QHBoxLayout()
        h_layout.addWidget(QLabel("采集模式:"))
        r_con = QRadioButton("连续 (Con)")
        r_tri = QRadioButton("触发 (Tri)")
        r_con.setChecked(True)
        h_layout.addWidget(r_con)
        h_layout.addWidget(r_tri)
        layout.addLayout(h_layout)
        
        self.ctrl_layout.addWidget(card)

    def build_settings_section(self):
        card, layout = self.create_card_container("参数配置")
        
        grid = QGridLayout()
        grid.setSpacing(8)
        grid.addWidget(QLabel("曝光时间 (ms):"), 0, 0)
        grid.addWidget(QLineEdit("10.0"), 0, 1)
        
        grid.addWidget(QLabel("最大光子阈值:"), 1, 0)
        grid.addWidget(QLineEdit("4096"), 1, 1)
        
        grid.addWidget(QLabel("光学 F 数:"), 2, 0)
        combo = QComboBox()
        combo.addItems(["F/10", "F/12", "F/16"])
        grid.addWidget(combo, 2, 1)
        layout.addLayout(grid)
        
        btn_grid = QGridLayout()
        btn_grid.setSpacing(6)
        btn_grid.addWidget(QPushButton("采集暗场"), 0, 0)
        btn_grid.addWidget(QPushButton("采集衍射"), 0, 1)
        btn_grid.addWidget(QPushButton("Log 对数转换"), 1, 0)
        btn_grid.addWidget(QPushButton("应用掩膜 Mask"), 1, 1)
        
        # 批量应用次要按钮样式
        for i in range(btn_grid.count()):
            btn_grid.itemAt(i).widget().setObjectName("SecondaryBtn")
            
        layout.addLayout(btn_grid)
        self.ctrl_layout.addWidget(card)

    def build_recon_section(self):
        card, layout = self.create_card_container("重构算法内核")
        
        btn_ref = QPushButton("校准并保存参考波前")
        btn_ref.setObjectName("SecondaryBtn")
        layout.addWidget(btn_ref)
        
        btn_recon = QPushButton("🚀 开始单次重构运算")
        btn_recon.setObjectName("SuccessBtn")
        layout.addWidget(btn_recon)
        
        h_layout = QHBoxLayout()
        h_layout.addWidget(QLabel("实时循环恢复:"))
        r_off = QRadioButton("关闭")
        r_on = QRadioButton("开启")
        r_off.setChecked(True)
        h_layout.addWidget(r_off)
        h_layout.addWidget(r_on)
        layout.addLayout(h_layout)
        
        self.ctrl_layout.addWidget(card)

    def build_data_section(self):
        card, layout = self.create_card_container("数据归档")
        btn_layout = QHBoxLayout()
        b1 = QPushButton("导出数据集")
        b1.setObjectName("SecondaryBtn")
        b2 = QPushButton("导入历史文件")
        b2.setObjectName("SecondaryBtn")
        btn_layout.addWidget(b1)
        btn_layout.addWidget(b2)
        layout.addLayout(btn_layout)
        self.ctrl_layout.addWidget(card)

    def build_results_section(self):
        card, layout = self.create_card_container("质量指标检测结果")
        
        grid = QGridLayout()
        grid.setSpacing(6)
        grid.addWidget(QLabel("PV 峰谷值 (nm):"), 0, 0)
        e1 = QLineEdit("0.142")
        e1.setReadOnly(True)
        grid.addWidget(e1, 0, 1)
        
        grid.addWidget(QLabel("RMS 均方根 (nm):"), 1, 0)
        e2 = QLineEdit("0.024")
        e2.setReadOnly(True)
        grid.addWidget(e2, 1, 1)
        
        grid.addWidget(QLabel("像素偏移 X/Y:"), 2, 0)
        h_box = QHBoxLayout()
        h_box.addWidget(QLineEdit("0"))
        h_box.addWidget(QLabel(" / "))
        h_box.addWidget(QLineEdit("0"))
        grid.addLayout(h_box, 2, 1)
        
        layout.addLayout(grid)
        self.ctrl_layout.addWidget(card)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置应用级的优雅现代全局字体
    font = QFont("Segoe UI", 9)
    # 中文字体退化支持
    font.setFamilies(["Segoe UI", "Microsoft YaHei", "Arial"])
    app.setFont(font)
    
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())