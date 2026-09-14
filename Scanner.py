import math
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
import random
import os

# Vogel 螺旋 r=c*sqrt(i) 的尺度常数：c=1 时中位最近邻距离（N=4000 数值计算）。
# 取 c = step / VOGEL_NEIGHBOR_SCALE 使螺旋的局部点间距约等于扫描步长（均匀密度）。
VOGEL_NEIGHBOR_SCALE = 1.688927250726361


class Scanner:
    """
    Ptychography扫描器类，用于生成标准的扫描点位置。
    支持多种扫描模式：圆形(round)、矩形(rectangle)、费马螺旋线(fermat，正确黄金角)、
    辐条螺旋(spoke，旧版费马实现，保留用于对比，别名 'fermat_old')。
    可选添加随机偏移。
    支持将扫描点位置保存为npy格式。
    """
    def __init__(self, step, scan_num, mode='round', nth=6, random_offset=False, offset_ratio=0.2):
        """
        初始化扫描器
        
        参数:
            step: 扫描步长
            scan_num: 扫描数量/范围
            mode: 扫描模式，可选 'round', 'rectangle', 'fermat'（正确黄金角）,
                  'spoke'（辐条螺旋，旧版费马实现，保留用于对比；别名 'fermat_old'）
            nth: 圆形扫描模式下控制基础角度数目
            random_offset: 是否添加随机偏移
            offset_ratio: 随机偏移比例，相对于step的比例
        """
        self.step = step
        self.scan_num = scan_num
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
            # 计算扫描区域的半长
            scan_half_length = self.step * self.scan_num
            # 生成绝对坐标列表，包含原点
            pos_absolute = [(0.0, 0.0)]
            for ir in range(1, self.scan_num + 1):
                rr = ir * self.step
                nth_angles = self.nth * ir
                dth = 2 * math.pi / nth_angles
                for ith in range(nth_angles):
                    theta = ith * dth
                    x = rr * math.sin(theta)
                    y = rr * math.cos(theta)
                    # 检查是否超出扫描区域
                    if abs(x) > scan_half_length or abs(y) > scan_half_length:
                        break
                    pos_absolute.append((x, y))
                    
        elif self.mode == 'rectangle':
            # 矩形扫描（蛇形路径）
            pos_absolute = [(0.0, 0.0)]
            for i in range(self.scan_num):
                for j in range(self.scan_num):
                    if i == 0 and j == 0:
                        continue  # 跳过原点，因为已经添加
                    
                    if i % 2 == 0:  # 偶数行从左到右
                        x = j * self.step
                    else:  # 奇数行从右到左
                        x = (self.scan_num - 1 - j) * self.step
                    
                    y = i * self.step
                    pos_absolute.append((x, y))
                    
        elif self.mode == 'fermat':
            # 费马螺旋线扫描（Vogel 模型）
            # 黄金角 = 2*pi/phi^2 = pi*(3-sqrt(5)) ≈ 2.39996 rad（≈137.5度）
            # 半径 r = c*sqrt(i)，c = step/VOGEL_NEIGHBOR_SCALE，
            # 使局部最近邻间距约等于 step（均匀点密度，见文件头部常数注释）
            golden_angle = math.pi * (3.0 - math.sqrt(5.0))

            # 计算需要的点数，确保覆盖扫描区域
            scan_radius = self.step * self.scan_num
            c = self.step / VOGEL_NEIGHBOR_SCALE

            pos_absolute = [(0.0, 0.0)]  # 起始于原点

            i = 0
            while True:
                i += 1
                theta = i * golden_angle
                r = c * math.sqrt(i)

                x = r * math.cos(theta)
                y = r * math.sin(theta)

                # 检查是否超出扫描区域
                if math.sqrt(x**2 + y**2) > scan_radius:
                    break

                pos_absolute.append((x, y))

        elif self.mode in ('spoke', 'fermat_old'):
            # 'spoke'：辐条螺旋（旧版费马实现改名保留，勿删）；'fermat_old' 为旧别名
            # 角度步长误用 math.pi / self.nth（nth=6 时为 30 度而非 137.5 度），
            # 点沿 12 条辐条聚集、覆盖不均匀。修正版见 'fermat' 分支。
            golden_angle = math.pi / self.nth

            scan_radius = self.step * self.scan_num

            pos_absolute = [(0.0, 0.0)]  # 起始于原点

            i = 0
            while True:
                i += 1
                theta = i * golden_angle
                r = self.step * math.sqrt(theta)

                x = r * math.cos(theta)
                y = r * math.sin(theta)

                # 检查是否超出扫描区域
                if math.sqrt(x**2 + y**2) > scan_radius:
                    break

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
            scan_num=scan_data['scan_num'],
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

    # 绘制扫描区域边界
    max_extent = scanner.step * scanner.scan_num
    rect = plt.Rectangle((-max_extent, -max_extent),
                         2 * max_extent, 2 * max_extent,
                         linewidth=2, linestyle='--',
                         edgecolor='gray', facecolor='none')
    ax.add_patch(rect)

    # 设置坐标轴
    buffer = scanner.step * 0.5
    ax.set_xlim(-max_extent - buffer, max_extent + buffer)
    ax.set_ylim(-max_extent - buffer, max_extent + buffer)
    ax.set_aspect('equal')
    ax.grid(True, linestyle=':', alpha=0.7)
    ax.set_xlabel('X Position')
    ax.set_ylabel('Y Position')

    # 添加颜色条
    # cbar = plt.colorbar(scatter, ax=ax)
    # cbar.set_label('Scan Order')

    # 添加图例
    ax.legend(loc='upper right')

    # 设置标题
    title = f"{scanner.mode.capitalize()} Scan Path\n"
    title += f"Step: {scanner.step}, Steps: {scanner.scan_num}"
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
    scanner = Scanner(0.3, 5, nth=6,mode='fermat')
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
