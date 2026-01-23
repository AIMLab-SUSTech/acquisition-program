import cv2
import numpy as np
import ctypes
from ctypes import *
from enum import Enum

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

qhyccddll = cdll.LoadLibrary('dll\QHY\qhyccd.dll')

# get camera id
qhyccddll.GetQHYCCDId.argtypes = [ctypes.c_uint32, ctypes.c_char_p]
# get handle via camera id
qhyccddll.OpenQHYCCD.argtypes = [ctypes.c_char_p]
qhyccddll.OpenQHYCCD.restype = ctypes.c_void_p
# close camera
qhyccddll.CloseQHYCCD.argtypes = [ctypes.c_void_p]

# read mode
qhyccddll.GetQHYCCDNumberOfReadModes.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
qhyccddll.GetQHYCCDReadModeName.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p]
qhyccddll.GetQHYCCDReadModeResolution.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32),
                                                 ctypes.POINTER(ctypes.c_uint32)]
qhyccddll.SetQHYCCDReadMode.argtypes = [ctypes.c_void_p, ctypes.c_uint32]

# set single stream mode or live stream mode
qhyccddll.SetQHYCCDStreamMode.argtypes = [ctypes.c_void_p, ctypes.c_uint32]

# initialize camera
qhyccddll.InitQHYCCD.argtypes = [ctypes.c_void_p]

# get camera chip information
qhyccddll.GetQHYCCDChipInfo.argtypes = [ctypes.c_void_p,
                                       ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
                                       ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32),
                                       ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
                                       ctypes.POINTER(ctypes.c_uint32)]
# get parameters value
qhyccddll.GetQHYCCDParam.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
qhyccddll.GetQHYCCDParam.restype = ctypes.c_double

# set parameters
qhyccddll.SetQHYCCDParam.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_double]
# set debayer on or off, only for color camera
qhyccddll.SetQHYCCDDebayerOnOff.argtypes = [ctypes.c_void_p, ctypes.c_bool]
# set bin mode
qhyccddll.SetQHYCCDBinMode.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
# set resolution and ROI
qhyccddll.SetQHYCCDResolution.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32,
                                         ctypes.c_uint32]

# start single stream mode exposing
qhyccddll.ExpQHYCCDSingleFrame.argtypes = [ctypes.c_void_p]
# get single frame data
qhyccddll.GetQHYCCDSingleFrame.argtypes = [ctypes.c_void_p,
                                          ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32),
                                          ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32),
                                          ctypes.POINTER(ctypes.c_uint8)]
# cancel single exposing and camera will NOT output frame data
qhyccddll.CancelQHYCCDExposingAndReadout.argtypes = [ctypes.c_void_p]

# start live stream mode
qhyccddll.BeginQHYCCDLive.argtypes = [ctypes.c_void_p]
# get live frame data
qhyccddll.GetQHYCCDLiveFrame.argtypes = [ctypes.c_void_p,
                                        ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32),
                                        ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32),
                                        ctypes.POINTER(ctypes.c_uint8)]
# stop live stream mode
qhyccddll.StopQHYCCDLive.argtypes = [ctypes.c_void_p]

# convert image data
qhyccddll.Bits16ToBits8.argtypes = [ctypes.c_void_p,
                                      ctypes.POINTER(ctypes.c_uint8), ctypes.POINTER(ctypes.c_uint8),
                                      ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint16, ctypes.c_uint16]

class CONTROL_ID(Enum):
    CONTROL_BRIGHTNESS = 0
    CONTROL_CONTRAST = 1
    CONTROL_WBR = 2
    CONTROL_WBB = 3
    CONTROL_WBG = 4
    CONTROL_GAMMA = 5
    CONTROL_GAIN = 6
    CONTROL_OFFSET = 7
    CONTROL_EXPOSURE = 8
    CONTROL_SPEED = 9
    CONTROL_TRANSFERBIT = 10
    CONTROL_CHANNELS = 11
    CONTROL_USBTRAFFIC = 12
    CONTROL_CURTEMP = 14
    CONTROL_CURPWM = 15
    CONTROL_MANULPWM = 16
    CONTROL_CFWPORT = 17
    CONTROL_COOLER = 18
    CONTROL_ST4PORT = 19
    CAM_COLOR = 20
    CAM_BIN1X1MODE = 21
    CAM_BIN2X2MODE = 22
    CAM_BIN3X3MODE = 23
    CAM_BIN4X4MODE = 24
    CAM_8BITS = 34
    CAM_16BITS = 35
    CAM_GPS = 36
    CONTROL_AMPV = 41
    CONTROL_CFWSLOTSNUM = 44
    CAM_SINGLEFRAMEMODE = 57
    CAM_LIVEVIDEOMODE = 58
    CAM_IS_COLOR = 59


camhandle = 0

ret = qhyccddll.InitQHYCCDResource()
print("InitQHYCCDResource() ret =", ret)

num = qhyccddll.ScanQHYCCD()
print("ScanQHYCCD() num =", num)

for index in range(num):
    print("index =", index)

    id_buffer = ctypes.create_string_buffer(40)
    ret = qhyccddll.GetQHYCCDId(index, id_buffer)
    result_id = id_buffer.value.decode("utf-8")
    print("GetQHYCCDId() ret =", ret, "id =", result_id)

    camhandle = qhyccddll.OpenQHYCCD(id_buffer)
    print("OpenQHYCCD() camhandle =", hex(camhandle))
    if camhandle != 0:
        break

readmodenum = ctypes.c_uint32()
ret = qhyccddll.GetQHYCCDNumberOfReadModes(camhandle, byref(readmodenum))
print("GetQHYCCDNumberOfReadModes() ret =", ret, "num =", readmodenum.value)

for index in range(readmodenum.value):
    print("index =", index)

    name_buffer = ctypes.create_string_buffer(40)
    ret = qhyccddll.GetQHYCCDReadModeName(camhandle, index, name_buffer)
    result_name = name_buffer.value.decode("utf-8")
    print("GetQHYCCDReadModeName() ret =", ret, "name =", result_name)

    width = ctypes.c_uint32()
    height = ctypes.c_uint32()
    ret = qhyccddll.GetQHYCCDReadModeResolution(camhandle, index, byref(width), byref(height))
    print("GetQHYCCDReadModeResolution() ret =", ret, "width =", width.value, "height =", height.value)

ret = qhyccddll.SetQHYCCDReadMode(camhandle, 0)
print("SetQHYCCDReadMode() ret =", ret)

ret = qhyccddll.SetQHYCCDStreamMode(camhandle, 1)
print("SetQHYCCDStreamMode() ret =", ret)

ret = qhyccddll.InitQHYCCD(camhandle)
print("InitQHYCCD() ret =", ret)

ret = qhyccddll.SetQHYCCDParam(camhandle, CONTROL_ID.CONTROL_TRANSFERBIT.value, 8.0)
print("SetQHYCCDParam() 16 bits ret = ", ret)

ret = qhyccddll.SetQHYCCDDebayerOnOff(camhandle, True)
print("SetQHYCCDDebayerOnOff() false ret =", ret)

chipW = ctypes.c_double()
chipH = ctypes.c_double()
imageW = ctypes.c_uint32()
imageH = ctypes.c_uint32()
pixelW = ctypes.c_double()
pixelH = ctypes.c_double()
imageB = ctypes.c_uint32()
ret = qhyccddll.GetQHYCCDChipInfo(camhandle, byref(chipW), byref(chipH), byref(imageW), byref(imageH), byref(pixelW),
                                  byref(pixelH), byref(imageB))
print("GetQHYCCDChipInfo() ret =", ret)
print("GetQHYCCDChipInfo() chip  info =", chipW.value, "x", chipH.value, "mm")
print("GetQHYCCDChipInfo() pixel info =", pixelW.value, "x", pixelH.value, "um")
print("GetQHYCCDChipInfo() image info =", imageW.value, "x", imageH.value, imageB.value, "bits")

ret = qhyccddll.SetQHYCCDBinMode(camhandle, 1, 1)
print("SetQHYCCDBinMode() ret =", ret)

ret = qhyccddll.SetQHYCCDResolution(camhandle, 0, 0, imageW.value, imageH.value)
print("SetQHYCCDResolution() ret =", ret)

ret = qhyccddll.SetQHYCCDParam(camhandle, CONTROL_ID.CONTROL_EXPOSURE.value, 100000.0)
print("SetQHYCCDParam() exposure 20ms ret =", ret)

ret = qhyccddll.SetQHYCCDParam(camhandle, CONTROL_ID.CONTROL_GAIN.value, 50.0)
print("SetQHYCCDParam() gain 40 ret =", ret)

ret = qhyccddll.SetQHYCCDParam(camhandle, CONTROL_ID.CONTROL_OFFSET.value, 80.0)
print("SetQHYCCDParam() offset 60 ret =", ret)

ret = qhyccddll.SetQHYCCDParam(camhandle, CONTROL_ID.CONTROL_USBTRAFFIC.value, 0.0)
print("SetQHYCCDParam() usbtraffic 0 ret =", ret)

w = ctypes.c_uint32()
h = ctypes.c_uint32()
b = ctypes.c_uint32()
c = ctypes.c_uint32()
length = imageW.value * imageH.value * 4
print("datasize =", length)
imgdata = (ctypes.c_uint8 * length)()
length = imageW.value * imageH.value
imgdata_raw = (ctypes.c_uint8 * length)()

ret = qhyccddll.BeginQHYCCDLive(camhandle)
print("ExpQHYCCDSingleFrame() ret =", ret)

cv2.namedWindow("Show", 0)
count = 0
while count < 100:
    ret = qhyccddll.GetQHYCCDLiveFrame(camhandle, byref(w), byref(h), byref(b), byref(c), imgdata)
    if ret == 0:
        count = count + 1
        print("GetQHYCCDSingleFrame() ret =", ret, "w =", w.value, "h =", h.value, "b =", b.value, "c =", c.value, "count =", count,
          "data size =", int(w.value * h.value * b.value * c.value / 8))
        img = 0
        if b.value == 16 and c.value == 1:
            ret = qhyccddll.Bits16ToBits8(camhandle, imgdata, imgdata_raw, w.value, h.value, 0, 65535)
            img = np.empty((h.value, w.value), dtype=np.uint8)
            img.data = imgdata_raw
        elif b.value == 8 and c.value == 1:
            img = np.empty((h.value, w.value), dtype=np.uint8)
            img.data = imgdata
        elif b.value == 8 and c.value == 3:
            img = np.empty((h.value, w.value, 3), dtype=np.uint8)
            img.data = imgdata
            # img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        cv2.imshow("Show", img)
        cv2.waitKey(50)

cv2.destroyAllWindows()

ret = qhyccddll.StopQHYCCDLive(camhandle)
print("StopQHYCCDLive() ret =", ret)

ret = qhyccddll.CloseQHYCCD(camhandle)
print("CloseQHYCCD() ret =", ret)

ret = qhyccddll.ReleaseQHYCCDResource()
print("ReleaseQHYCCDResource() ret =", ret)
