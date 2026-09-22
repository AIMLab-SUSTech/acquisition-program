图像采集程序

使用ids时，需要把环境中的pylablib中的uc480.py替换掉。

在初始化Newportxps()对象时，如出现SFTP报错的情况，按照提示使用ssh-keyscan (IP of motion controller) >> ~/.ssh/known_hosts 更新公钥。
注意在Windows系统上使用此命令获取的konwn_hosts文件的编码方式可能为UTF-16，需要转换为UTF-8，否则仍会报错。

## 索雷博科学相机

界面中的 `Thorlabs` 选项通过 `pylablib.devices.Thorlabs.ThorlabsTLCamera`
控制 Zelux、Kiralux、Quantalux 等紧凑型科学相机；旧式 uc480 相机仍使用
`IDS` 路径。不需要安装索雷博官方 Python 包。

1. 安装 ThorCam（提供设备驱动和原生 DLL）。
2. 在项目的 Python 环境中安装 `pylablib`。
3. 使用本程序前退出 ThorCam，避免相机被独占。

PyLabLib 默认从 ThorCam 安装目录查找 DLL。如果 DLL 位于其他目录，可将环境变量
`THORLABS_TLCAM_DLL_PATH` 指向 DLL 所在目录。
