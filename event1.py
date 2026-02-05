import sys
from PyQt6.QtWidgets import QApplication
from LogicWindow import LogicWindow

if __name__ == '__main__':
    # 1. 创建应用
    app = QApplication(sys.argv)
    
    # 2. 实例化主逻辑窗口
    window = LogicWindow()
    
    # ==========================================
    #在此处配置参数
    # ==========================================
    
    # 配置 NewPort XPS 控制器的 Group 名称
    # 如果您使用的是 Group3 和 Group4，请修改下方列表
    window.set_xps_groups(['Group3', 'Group4'])
    
    # 配置相机像素尺寸 (单位: um)
    window.set_pixel_size(3.45)
    
    # ==========================================
    
    # 3. 显示并运行
    window.show()
    sys.exit(app.exec())