图像采集程序

H5 图像数据统一使用无符号 16 位（`uint16`）保存。8 位和 12 位数据仅转换
存储类型，不移位、不缩放：原值 255、4095 保存后仍为 255、4095。
采集帧和暗场图的 TIF 按采集位深选择最小存储类型：8 位使用 `uint8`，
12 位使用 `uint16`（当前 TIF 写入方式不支持打包 12 位），16 位使用 `uint16`。
TIF 同样保留像素原值。扣暗场流程仍按原有逻辑执行。

## 环境配置

在项目根目录打开 PowerShell，使用 `project_environment.yaml` 创建环境：

```powershell
conda env create -f project_environment.yaml
conda activate acquisition_env
python main.py
```

已有 `acquisition_env` 时更新依赖：

```powershell
conda env update -n acquisition_env -f project_environment.yaml
```

环境使用 Python 3.11，包含界面、H5/TIF 保存、PCO、IDS、Thorlabs 和 Newport
所需的 Python 依赖，其中 PCO 保持 `pco==2.6.0`，Newport CONEX-CC 使用
`pythonnet`。厂商原生 SDK、相机驱动及 CONEX-CC 软件仍需单独安装。
Photometrics、Basler 和 QHY 独立示例的可选依赖见环境文件中的注释。

使用ids时，需要把环境中的pylablib中的uc480.py替换掉。

在初始化Newportxps()对象时，如出现SFTP报错的情况，按照提示使用ssh-keyscan (IP of motion controller) >> ~/.ssh/known_hosts 更新公钥。
注意在Windows系统上使用此命令获取的konwn_hosts文件的编码方式可能为UTF-16，需要转换为UTF-8，否则仍会报错。

## PM 相机
启动前必须把曝光调整到大于10ms，不然无法读图

## Newport 串口位移台（CONEX-CC）

在“位移台”中选择 `newports`（`NewPort` 为网口 XPS 控制器）。串口号与
`NewPort` 的 IP 一样在程序中配置：修改 `main.py` 的 `DeviceLoader.run()`
中 `case "newports"` 下的 `port_x="COM3"`、`port_y="COM4"`，以设备管理器
为准。窗口不提供串口编辑框。
需要安装 Newport CONEX-CC 软件；环境文件已包含
[`pythonnet`](https://pypi.org/project/pythonnet/) 依赖。

点击“连接”后，再点击“初始化（寻零/使能）”。未建立参考点的轴会执行寻零，
禁用的轴会被使能，已就绪的轴保持当前位置。初始化在后台依次处理 X/Y 轴，
每轴最多等待 60 秒；双轴就绪后才允许移动或扫描。失败原因显示在日志中，
排除问题后可再次点击初始化。寻零超时会尝试停止该轴。

“归零”返回初始化完成时记录的位置；初始化不会修改现有坐标偏移
`init_pos=(-13.0, -13.0)`，因此参考点处的逻辑坐标通常显示为 -13 mm。

模拟测试（无需连接硬件）：

```powershell
python -m unittest discover -s tests -p "test_newport_initialization.py" -v
```

命令及状态处理依据 Newport 官方
[控制器手册](https://www.newport.com/mam/celum/celum_assets/resources/CONEX-CC_-_Controller_Documentation.pdf)
和[命令接口手册](https://www.newport.com/medias/sys_master/resources/hb8/h1c/9954226831390/CONEX-CC%20-%20Command%20Interface%20Manual/CONEX-CC-Command-Interface-Manual.pdf)。

## PCO 相机

PCO 使用官方 `pco` 库，独立集成文件为 `hardware/PCO/pco_camera.py`。
在界面选择 PCO 即可；原有 `from camera import PCOCamera` 仍然可用。

### 安装

使用项目配置的 Python 3.11 环境，安装相机对应的 PCO 驱动，再执行：

```powershell
python -m pip install pco==2.6.0
```

`pco 2.6.0` 要求 Python >=3.8 且 <3.13；不要在 Python 3.13 环境安装。
启动程序前关闭占用相机的 Camware。PCO 接入不再依赖 pylablib 的 SC2 DLL
搜索路径或 `PCO_SC2_DLL`；其他使用 pylablib 的相机不受影响。

### 独立采集

在项目根目录运行下面的 Python 代码：

```python
from hardware.PCO import PCOCamera

with PCOCamera(frame_timeout_s=5.0, buffer_count=8) as cam:
    cam.set_ex_time(0.01)  # 秒，即 10 ms
    cam.start_acquisition()
    image = cam.read_newest_image()
    print(image.shape, image.dtype, cam.get_bit_depth())
    print(cam.last_metadata)
```

多相机时可以指定 `serial_number=相机序列号` 和 `interface="USB 3.0"`。
连续预览使用环形缓冲（至少 4 帧），输出独立的二维 Mono16 数组；
`get_bit_depth()` 返回传感器位深。每次读取等待未读的新帧，超时或 SDK 错误
会传到界面日志，不再静默返回 `None`。默认等待上限为 5 秒，长曝光时自动延长
至相机帧周期加 2 秒。修改曝光会重建正在使用的缓冲，排除旧曝光图像。

扫描流程自动切换到软件触发，每个位移点到位后触发一次；独立使用时依次调用
`set_trigger_mode("software")`、`start_acquisition()`、`trigger()`、
`read_newest_image()`。`flush_image_queue()` 跳过已完成的旧帧；连续模式下已开始
曝光的帧仍可能在清空后到达，因此按点扫描应使用软件触发。

### 验证与排查

```powershell
python -m unittest discover -s tests -p "test_pco_camera.py" -v
```

这些测试使用模拟 SDK，验证新帧等待、清空缓冲、曝光切换、软件触发和资源释放。
实机还需验证连续预览、修改曝光、短扫描及关闭后重连。若报错，保留完整错误码；
先在 Camware 确认相机能够取图，再关闭 Camware 重试程序。

接口依据：[官方 pco 包](https://pypi.org/project/pco/2.6.0/)、
[pco.python 手册](https://filehub.excelitas.com/api/public/dl/MMIlwdGz/PCO_MA_PCOPYTHON.pdf)。
