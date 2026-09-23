图像采集程序

使用ids时，需要把环境中的pylablib中的uc480.py替换掉。

在初始化Newportxps()对象时，如出现SFTP报错的情况，按照提示使用ssh-keyscan (IP of motion controller) >> ~/.ssh/known_hosts 更新公钥。
注意在Windows系统上使用此命令获取的konwn_hosts文件的编码方式可能为UTF-16，需要转换为UTF-8，否则仍会报错。

## PM 相机
启动前必须把曝光调整到大于10ms，不然无法读图
