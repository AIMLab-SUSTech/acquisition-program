import math
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
import random
import os


class Scanner:
    """
    Ptychography扫描器类，用于生成标准的扫描点位置。
    支持多种扫描模式：圆形(round)、矩形(rectangle)和费马螺旋线(fermat)。
    可选添加随机偏移。
    支持将扫描点位置保存为npy格式。
    """
    def __init__(self, step, scan_range_x, scan_range_y, mode='round', nth=6, random_offset=False, offset_ratio=0.2):
        """
        初始化扫描器
        
        参数:
            step: 扫描步长
            scan_range_x: 扫描范围x轴
            scan_range_y: 扫描范围y轴
            mode: 扫描模式，可选 'round', 'rectangle', 'fermat'
            nth: 圆形扫描模式下控制基础角度数目
            random_offset: 是否添加随机偏移
            offset_ratio: 随机偏移比例，相对于step的比例
        """
        self.step = float(step)
        self.scan_range_x = float(scan_range_x)
        self.scan_range_y = float(scan_range_y)
        self.mode = mode
        self.nth = nth  # 控制基础角度数目
        self.random_offset = random_offset  # 是否添加随机偏移
        self.offset_ratio = offset_ratio  # 随机偏移比例
        self.x = []
        self.y = []
        self.abs_x = []
        self.abs_y = []
        self.final_pos = (0, 0)
        self.generate_scan_points()
    
    def _apply_random_offset(self, pos_absolute):
        """
        对绝对位置应用随机偏移
        
        参数:
            pos_absolute: 绝对位置坐标列表 [(x1,y1), (x2,y2), ...]
            
        返回:
            添加随机偏移后的位置列表
        """
        if not self.random_offset:
            return pos_absolute
            
        max_offset = self.step * self.offset_ratio
        offset_pos = []
        
        for x, y in pos_absolute:
            # 对每个点添加随机偏移，但保持第一个点（原点）不变
            if x == 0.0 and y == 0.0 and len(offset_pos) == 0:
                offset_pos.append((x, y))
            else:
                dx = random.uniform(-max_offset, max_offset)
                dy = random.uniform(-max_offset, max_offset)
                offset_pos.append((x + dx, y + dy))
                
        return offset_pos

    def generate_scan_points(self):
        """生成扫描点位置"""
        pos_absolute = []
        
        if self.mode == 'round':
            # === 圆形/椭圆模式 ===
            # 1. 计算半轴长 (a: X轴半径, b: Y轴半径)
            # scan_range_x 是物理直径(mm)，所以除以2得到半径
            a = self.scan_range_x / 2.0
            b = self.scan_range_y / 2.0
            
            # 2. 确定最大扫描半径
            # 必须覆盖到椭圆的最长边，否则长轴方向扫不全
            max_r = max(a, b)
            
            # 3. 估算需要的层数
            # 向上取整，确保能覆盖最边缘
            max_layers = int(math.ceil(max_r / self.step)) + 1
            
            pos_absolute = [(0.0, 0.0)]
            
            for ir in range(1, max_layers):
                rr = ir * self.step # 当前圆环的物理半径
                
                # 优化：如果当前半径已经超过了长轴，不仅这一层没点，后面层也没点，直接退出
                if rr > max_r: 
                    break
                
                # 计算当前层的点数（保持原有逻辑）
                nth_angles = self.nth * ir
                dth = 2 * math.pi / nth_angles
                
                for ith in range(nth_angles):
                    theta = ith * dth
                    x = rr * math.sin(theta)
                    y = rr * math.cos(theta)
                    
                    # 使用 <= 1.0000001 防止浮点数误差漏掉边缘点
                    if (x / a)**2 + (y / b)**2 <= 1.0000001:
                        pos_absolute.append((x, y))
                    
        elif self.mode == 'rectangle':
            # === 矩形模式 (从中心开始的回字扫描) ===
            nx = int(math.ceil(self.scan_range_x / self.step))
            ny = int(math.ceil(self.scan_range_y / self.step))
            
            nx = max(1, nx)
            ny = max(1, ny)
            
            # 计算中心索引（取整，确保是整数网格坐标）
            center_x = nx // 2
            center_y = ny // 2
            
            pos_absolute = []
            x_offset = (nx - 1) * self.step / 2.0
            y_offset = (ny - 1) * self.step / 2.0
            
            # 从中心开始向外，一圈一圈扫描
            max_radius = max(center_x, center_y, nx - center_x - 1, ny - center_y - 1)
            
            for r in range(max_radius + 1):
                # 当前圈的边界
                left = center_x - r
                right = center_x + r
                top = center_y - r
                bottom = center_y + r
                
                # 生成当前圈的所有点（按顺时针方向）
                current_ring = []
                
                # 上边（从左到右）
                if top >= 0 and top < ny:
                    for x in range(left, right + 1):
                        if 0 <= x < nx:
                            current_ring.append((top, x))
                
                # 右边（从上到下，跳过右上角）
                if right >= 0 and right < nx:
                    for y in range(top + 1, bottom + 1):
                        if 0 <= y < ny:
                            current_ring.append((y, right))
                
                # 下边（从右到左，跳过右下角）
                if bottom >= 0 and bottom < ny and r > 0:
                    for x in range(right - 1, left - 1, -1):
                        if 0 <= x < nx:
                            current_ring.append((bottom, x))
                
                # 左边（从下到上，跳过左下角和左上角）
                if left >= 0 and left < nx and r > 0:
                    for y in range(bottom - 1, top, -1):
                        if 0 <= y < ny:
                            current_ring.append((y, left))
                
                # 蛇形处理：奇数圈反向扫描
                if r % 2 == 1:
                    current_ring.reverse()
                
                # 转换为物理坐标
                for y_idx, x_idx in current_ring:
                    x = x_idx * self.step - x_offset
                    y = y_idx * self.step - y_offset
                    pos_absolute.append((x, y))
                    
        elif self.mode == 'fermat':
            # === 费马螺旋模式 (支持椭圆) ===
            
            # 2. 确定最大生成半径
            # 为了覆盖整个椭圆，必须生成到长轴的长度，然后再裁剪
            max_r = max(self.scan_range_x, self.scan_range_y)
            
            # 3. 黄金角 (保持您原有的参数逻辑)
            golden_angle = math.pi / self.nth
            
            pos_absolute = [(0.0, 0.0)]
            i = 0
            while True:
                i += 1
                theta = i * golden_angle
                
                # 费马螺旋线半径公式 (保持您原有的逻辑)
                # r 随 theta 的平方根增长
                r = self.step * math.sqrt(theta)
                
                # 停止条件：如果半径超过了椭圆的长轴，停止生成
                if r > max_r:
                    break
                
                x = r * math.cos(theta)
                y = r * math.sin(theta)
                
                # === 椭圆筛选 ===
                # 标准椭圆方程: (x/a)^2 + (y/b)^2 <= 1
                if (x / self.scan_range_x)**2 + (y / self.scan_range_y)**2 <= 1.0000001:
                    pos_absolute.append((x, y))
        
        # 应用随机偏移（如果启用）
        pos_absolute = self._apply_random_offset(pos_absolute)
            
        # 转换为相对位移
        self.x = [0]
        self.y = [0]
        for i in range(1, len(pos_absolute)):
            prev_x, prev_y = pos_absolute[i - 1]
            curr_x, curr_y = pos_absolute[i]
            self.x.append(curr_x - prev_x)
            self.y.append(curr_y - prev_y)
            
        # 计算绝对坐标
        current_x, current_y = 0.0, 0.0
        self.abs_x = []
        self.abs_y = []
        for dx, dy in zip(self.x, self.y):
            current_x += dx
            current_y += dy
            self.abs_x.append(current_x)
            self.abs_y.append(current_y)
            
        self.final_pos = (current_x, current_y)
        
    def save_to_npy(self, save_path, filename=None):
        """
        将扫描点位置保存为npy格式
        
        参数:
            save_path: 保存路径，可以是文件夹路径或完整文件路径
            filename: 文件名（可选），如果save_path是文件夹路径，则需要提供
            
        返回:
            保存的文件路径
        """
        # 检查保存路径
        if os.path.isdir(save_path):
            if filename is None:
                # 如果未提供文件名，则自动生成
                filename = f"scan_{self.mode}_step{self.step}_num{self.scan_num}"
                if self.random_offset:
                    filename += f"_random{self.offset_ratio}"
                filename += ".npy"
            save_file = os.path.join(save_path, filename)
        else:
            # 如果提供的是完整文件路径
            save_file = save_path
            # 确保文件扩展名为.npy
            if not save_file.endswith('.npy'):
                save_file += '.npy'
                
        # 创建要保存的数据字典
        scan_data = {
            'mode': self.mode,
            'step': self.step,
            'scan_num': self.scan_num,
            'nth': self.nth,
            'random_offset': self.random_offset,
            'offset_ratio': self.offset_ratio,
            'x': np.array(self.x),
            'y': np.array(self.y),
            'abs_x': np.array(self.abs_x),
            'abs_y': np.array(self.abs_y),
            'final_pos': self.final_pos
        }
        
        # 保存为npy格式
        np.save(save_file, scan_data)
        print(f"扫描点位置已保存至: {save_file}")
        
        return save_file
        
    @classmethod
    def load_from_npy(cls, file_path):
        """
        从npy文件加载扫描点位置
        
        参数:
            file_path: npy文件路径
            
        返回:
            Scanner对象
        """
        # 加载npy文件
        scan_data = np.load(file_path, allow_pickle=True).item()
        
        # 创建Scanner对象
        scanner = cls(
            step=scan_data['step'],
            scan_range_x=scan_data['scan_range_x'],
            scan_range_y=scan_data['scan_range_y'],
            mode=scan_data['mode'],
            nth=scan_data['nth'],
            random_offset=scan_data['random_offset'],
            offset_ratio=scan_data['offset_ratio']
        )
        
        # 覆盖自动生成的扫描点
        scanner.x = scan_data['x'].tolist()
        scanner.y = scan_data['y'].tolist()
        scanner.abs_x = scan_data['abs_x'].tolist()
        scanner.abs_y = scan_data['abs_y'].tolist()
        scanner.final_pos = scan_data['final_pos']
        
        print(f"已从文件加载扫描点位置: {file_path}")
        return scanner


def visualize_scan_path(scanner:Scanner, save_path=None, dpi=100):
    """
    可视化扫描路径

    参数：
    scanner - 包含扫描数据的Scanner对象
    save_path - 图片保存路径（可选）
    dpi - 输出分辨率（默认100）
    """
    # 检查是否有扫描数据
    if not hasattr(scanner, 'abs_x') or not hasattr(scanner, 'abs_y'):
        raise ValueError("Scanner对象缺少坐标数据")

    x = np.array(scanner.abs_x)
    y = np.array(scanner.abs_y)

    if len(x) == 0 or len(y) == 0:
        raise ValueError("坐标数据为空")

    plt.figure(figsize=(10, 10))
    ax = plt.gca()

    # 创建颜色映射（按扫描顺序）
    colors = np.arange(len(x))
    norm = Normalize(vmin=0, vmax=len(x) - 1)
    cmap = plt.get_cmap('viridis')

    # 绘制连接线（带箭头指示方向）
    for i in range(1, len(x)):
        dx = x[i] - x[i - 1]
        dy = y[i] - y[i - 1]
        ax.arrow(x[i - 1], y[i - 1], dx, dy,
                 shape='full', lw=1,
                 color=cmap(norm(i - 1)),
                 length_includes_head=True,
                 head_width=0.3 * scanner.step,
                 head_length=0.5 * scanner.step)

    # 绘制扫描点
    scatter = ax.scatter(x, y, c=colors, cmap=cmap,
                         s=50, zorder=3, edgecolor='w')

    # 标注起点和终点
    ax.scatter(x[0], y[0], s=200, marker='*',
               c='limegreen', edgecolor='k', label='Start')
    ax.scatter(x[-1], y[-1], s=200, marker='X',
               c='orangered', edgecolor='k', label='End')

    # 设置坐标轴
    ax.set_aspect('equal')
    ax.grid(True, linestyle=':', alpha=0.5)
    ax.set_xlabel('X Position')
    ax.set_ylabel('Y Position')

    # 添加图例
    ax.legend(loc='upper right')

    # 设置标题
    title = f"{scanner.mode.capitalize()} Scan Path\n"
    title += f"Step: {scanner.step}, Steps: {scanner.scan_range_x} x {scanner.scan_range_y}"
    if scanner.mode == 'round' and hasattr(scanner, 'nth'):
        title += f", Nth: {scanner.nth}"
    plt.title(title)

    # 保存或显示图像
    if save_path:
        plt.savefig(save_path, dpi=dpi, bbox_inches='tight')
        print(f"图像已保存至：{save_path}")
    else:
        plt.show()

    plt.close()


if __name__ == '__main__':
    # scanner = Scanner(0.3, 5, nth=6,mode='rectangle', random_offset=True, offset_ratio=0.1)
    scanner = Scanner(1, 8, 5,mode='rectangle')
    # mat_struct = {
    #     # 'sz_fft': np.int32(params.sz_fft),
    #     # 'wavelength': np.float64(params.wavelength),
    #     # 'IDS_dx': np.float64(params.pixel_size),
    #     'pos': {'x': scanner.abs_x, 'y': scanner.abs_y}
    # }
    # from scipy.io import savemat
    # savemat('expt_para.mat', {'g': mat_struct})
    print(len(scanner.x))
    # print(scanner.y)
    # print(f'{scanner.abs_x}')
    # print(f'{scanner.abs_y}')
    visualize_scan_path(
        scanner,
        # save_path='scan_path.png',
        dpi=150
    )
