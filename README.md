图像采集程序

使用ids时，需要把环境中的pylablib中的uc480.py替换掉。

在初始化Newportxps()对象时，如出现SFTP报错的情况，按照提示使用ssh-keyscan (IP of motion controller) >> ~/.ssh/known_hosts 更新公钥。
注意在Windows系统上使用此命令获取的konwn_hosts文件的编码方式可能为UTF-16，需要转换为UTF-8，否则仍会报错。

## PM 相机
启动前必须把曝光调整到大于10ms，不然无法读图

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
