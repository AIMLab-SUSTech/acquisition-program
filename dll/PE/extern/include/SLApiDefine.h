#ifndef SLAPIDEFINE_H
#define SLAPIDEFINE_H

#include <stdint.h>
#include "PFNC.h"
#ifdef _MSC_VER  // \~chinese 如果是 MSVC 编译器（Visual Studio）        \~english If using MSVC compiler (Visual Studio)
    #ifdef SLAPI_LIBRARY
        #define SLAPISHARED_API __declspec(dllexport)  // \~chinese 导出符号到 DLL            \~english Export symbols to DLL
    #else
        #define SLAPISHARED_API __declspec(dllimport)  // \~chinese 从 DLL 导入符号           \~english Import symbols from DLL
    #endif

    #pragma warning(disable:4819)  // \~chinese 禁用中文字符警告（编码警告）    \~english Disable warning about non-ASCII characters
#else  // \~chinese GCC / Clang 等平台               \~english For GCC / Clang and others
    #define SLAPISHARED_API __attribute__((visibility("default")))  // \~chinese 默认导出符号（对外可见） \~english Make symbol visible in shared library
    #define SLAPISHARED_HIDDEN_API __attribute__((visibility("hidden")))  // \~chinese 隐藏符号（内部使用）   \~english Hide symbol (internal use only)
#endif

#define SLAPI_OK         0          // \~chinese 操作成功                 \~english Operation successful
#define SLAPI_WARNNING   1          // \~chinese 操作成功(存在警告)       \~english Operation successful(Warning)
#define SLAPI_NG        -1          // \~chinese 操作失败/异常            \~english Operation failed / error


// \~chinese 传输带宽                             \~english Transmission bandwidth
#define SLPARAM_BAND_WIDTH                      "SlParamBandWidth"

// \~chinese 采集帧率                             \~english Camera capture frame rate
#define SLPARAM_CAP_FPS                         "SlParamCameraCapFps"

// \~chinese 采集模式                             \~english Capture mode
#define SLPARAM_MODE                            "SlParamMode"

// \~chinese 录制媒介(参考:SL_RECORD_MEDIA)       \~english Recording media (see: SL_RECORD_MEDIA)
#define SLPARAM_REC_MEDIA                       "SlParamRecMedia"

// \~chinese 触发模式                             \~english Trigger mode
#define SLPARAM_TRIG_MODE                       "SlParamTrigMode"

// \~chinese 是否支持录制使能                      \~english Record enable flag
#define SLPARAM_RECORD_SUPPORT                  "SlParamRecordSupport"

// \~chinese 相机帧传输大小                       \~english Camera frame transfer size
#define SLPARAM_FRAME_SIZE                      "SlParamCameraFrameSize"

// \~chinese 相机名称                             \~english Camera display name
#define SLPARAM_DISPLAY_NAME                    "SlParamCameraDisplayName"

// \~chinese interface名称                       \~english Interface display name
#define SLPARAM_INTERFACE_DISPLAY_NAME           "SlParamInterfaceDisplayName"

// \~chinese 当前缓存帧数                         \~english Current cached frame count
#define SLPARAM_CACHE_FRAMES                    "SlParamCacheFrames"

// \~chinese 缓存最大可设置帧数                   \~english Maximum configurable cache frame count
#define SLPARAM_MAXCACHE_FRAMES                 "SlParamMaxcacheFrames"

// \~chinese 当前系统内存使用的百分比             \~english Current system memory usage percentage
#define SLPARAM_MEMORYLOAD                      "SlParamMemoryload"

// \~chinese 手动触发前录制帧数                   \~english Pre-trigger frame count for manual trigger
#define SLPARAM_TRIG_MANUAL_BEFOR_FRAME         "SlParamTrigManualBeforFrame"

// \~chinese 手动触发后录制帧数                   \~english Post-trigger frame count for manual trigger
#define SLPARAM_TRIG_MANUAL_AFTER_FRAME         "SlParamTrigManualAfterFrame"

// \~chinese 磁盘录制路径                         \~english Disk recording path
#define SLPARAM_RECORD_DISK_PATH                "SlParamRecordDiskPath"

// \~chinese 磁盘录制文件名称                     \~english Disk recording file name
#define SLPARAM_RECORD_DISK_FILENAME            "SlParamRecordDiskFilename"

// \~chinese 磁盘录制文件名称标记选择串             \~english Disk recording file mark selection
#define SLPARAM_RECORD_DISK_FILEMARK            "SlParamRecordDiskFilemark"

// \~chinese 磁盘录制文件信息支持标记列表             \~english Supported disk recording file info mark list
#define SLPARAM_RECORD_DISK_FILEINFO_MARK_LIST  "SlParamRecordDiskFileinfoMarkList"

// \~chinese 磁盘录制保存参数                     \~english Full disk recording save param
#define SLPARAM_RECORD_DISK_FILEPARAM            "SlParamRecordDiskFileparam"

// \~chinese 磁盘录制文件夹名称                     \~english Disk recording folder name
#define SLPARAM_RECORD_DISK_FOLDERNAME            "SlParamRecordDiskFoldername"

// \~chinese 磁盘录制文件夹名称标记选择串             \~english Disk recording folder mark selection
#define SLPARAM_RECORD_DISK_FOLDERMARK            "SlParamRecordDiskFoldermark"

// \~chinese 磁盘录制文件夹模式(0=多文件夹模式<默认>, 1=单文件夹模式)  \~english Disk recording folder mode (0=multi-folder<default>, 1=single-folder)
#define SLPARAM_RECORD_DISKDIR_MODE              "SlParamRecordDiskdirMode"

// \~chinese 设置、获取磁盘需要录制帧数           \~english Set/Get frame count to be recorded to disk
#define SLPARAM_RECORD_DISK_RECFRAMES           "SlParamRecordDiskRecframes"

// \~chinese 设置、获取磁盘录制结束模式           \~english Set/Get disk recording end mode
#define SLPARAM_RECORD_DISK_ENDMODE             "SlParamRecordDiskEndmode"

// \~chinese 获取磁盘最大可录制帧数               \~english Get maximum recordable frames on disk
#define SLPARAM_MAXRECORD_DISK_FRAMES           "SlParamMaxrecordDiskFrames"

// \~chinese 获取磁盘剩余空间                     \~english Get disk free space
#define SLPARAM_RECORD_DISK_USED                "SlParamRecordDiskUsed"

// \~chinese 获取磁盘总空间                       \~english Get total disk space
#define SLPARAM_RECORD_DISK_TOTAL               "SlParamRecordDiskTotal"

// \~chinese 获取相机已录制帧数                   \~english Get already recorded frame count (not supported in Ready/Recording mode)
#define SLPARAM_ALREADY_RECORD_FRAMES           "SlParamAlreadyRecordFrames"

// \~chinese 获取相机已录制内存信息               \~english Get already recorded memory info (not supported in Ready/Recording mode)
#define SLPARAM_ALREADY_RECORD_MEMORY_INFO      "SlParamAlreadyRecordMemoryInfo"

// \~chinese 相机触发后已录制帧及可录制帧         \~english Recorded/recordable frames after trigger
#define SLPARAM_ALREADY_RECORD_AFTER_FRAMES     "SlParamAlreadyRecordAfterFrames"

// \~chinese 相机触发前已录制帧及可录制帧         \~english Recorded/recordable frames before trigger
#define SLPARAM_ALREADY_RECORD_BEFOR_FRAMES     "SlParamAlreadyRecordBeforFrames"

// \~chinese 相机在线状态                         \~english Camera online status
#define SLPARAM_ONLINE_STATE                    "SlParamCameraOnlineState"

// \~chinese 循环录制使能                         \~english Loop recording enable flag
#define SLPARAM_LOOP_RECORD_ENABLE              "SlParamLoopRecordEnable"

// \~chinese 手动导出内存数据到磁盘的媒介格式（参考: SL_RECORD_MEDIA；默认 RecordMedia_MRAW；不支持 RecordMedia_Memory） \~english Media format for manually exporting memory data to disk (see: SL_RECORD_MEDIA; default is RecordMedia_MRAW; RecordMedia_Memory is not supported)
#define SLPARAM_MANUL_MEM2DISK_MODE             "SlParamManaulMem2diskMode"

// \~chinese 手动内存导出至磁盘使能                \~english Enable manual memory-to-disk export
#define SLPARAM_MANUL_MEM2DISK_ENABLE           "SlParamManaulMem2diskEnable"

// \~chinese 停止内存导出至磁盘                   \~english Stop memory-to-disk export
#define SLPARAM_MANUL_MEM2DISK_STOP             "SlParamManaulMem2diskStop"

// \~chinese 内存导出至磁盘进度                   \~english Memory-to-disk export progress
#define SLPARAM_MANUL_MEM2DISK_PROGRESS         "SlParamManaulMem2diskProgress"


///< \~chinese 最大的数据信息大小       \~english Maximum data information size
#define INFO_MAX_BUFFER_SIZE            256


///< \~chinese GenTL CoaXPress相机信息      \~english Standard CoaXPress device information
typedef struct tagSL_GENTL_CXP_DEVICE_INFO
{
    unsigned char       chVendorName[INFO_MAX_BUFFER_SIZE];      ///< [OUT] \~chinese 供应商名字      \~english Vendor name
    unsigned char       chModelName[INFO_MAX_BUFFER_SIZE];       ///< [OUT] \~chinese 型号名字        \~english Model name
    unsigned char       chManufacturerInfo[INFO_MAX_BUFFER_SIZE];///< [OUT] \~chinese 厂商信息        \~english Manufacturer information
    unsigned char       chDeviceVersion[INFO_MAX_BUFFER_SIZE];   ///< [OUT] \~chinese 相机版本        \~english Device version
    unsigned char       chSerialNumber[INFO_MAX_BUFFER_SIZE];    ///< [OUT] \~chinese 序列号          \~english Serial number
    unsigned char       chUserDefinedName[INFO_MAX_BUFFER_SIZE]; ///< [OUT] \~chinese 用户自定义名字   \~english User defined name
    unsigned int        nReserved[INFO_MAX_BUFFER_SIZE];                          ///< [OUT] \~chinese 保留字段        \~english Reserved
}SL_GENTL_CXP_DEVICE_INFO;


/// \~chinese 深视自研 USB设备信息               \~english SSZN USB device info
typedef struct tagSL_OCT_USB3_DEVICE_INFO
{
    unsigned char       chVendorName[INFO_MAX_BUFFER_SIZE];         ///< [OUT] \~chinese 供应商名字             \~english Vendor Name
    unsigned char       chModelName[INFO_MAX_BUFFER_SIZE];          ///< [OUT] \~chinese 型号名字               \~english Model Name
    unsigned char       chFamilyName[INFO_MAX_BUFFER_SIZE];         ///< [OUT] \~chinese 家族名字               \~english Family Name
    unsigned char       chDeviceVersion[INFO_MAX_BUFFER_SIZE];      ///< [OUT] \~chinese 设备版本               \~english Device Version
    unsigned char       chManufacturerName[INFO_MAX_BUFFER_SIZE];   ///< [OUT] \~chinese 制造商名字             \~english Manufacturer Name
    unsigned char       chSerialNumber[INFO_MAX_BUFFER_SIZE];       ///< [OUT] \~chinese 序列号                 \~english Serial Number
    unsigned char       chUserDefinedName[INFO_MAX_BUFFER_SIZE];    ///< [OUT] \~chinese 用户自定义名字         \~english User Defined Name
    unsigned int        nReserved[2];                               ///<       \~chinese 预留                   \~english Reserved
}SL_OCT_USB3_DEVICE_INFO;


/// \~chinese 深视自研 GEV设备信息               \~english SSZN USB device info
typedef struct tagSL_SSZN_GEV_DEVICE_INFO
{
    unsigned char       chDeviceIpAddr[INFO_MAX_BUFFER_SIZE];       ///< [OUT] \~chinese 相机IP地址           \~english Camera ip addr
    unsigned char       chDeviceMacAddr[INFO_MAX_BUFFER_SIZE];      ///< [OUT] \~chinese 相机Mac地址          \~english Camera Mac Addr
    unsigned char       chDeviceUserName[INFO_MAX_BUFFER_SIZE];     ///< [OUT] \~chinese 相机别名             \~english Camera User Name
    unsigned char       chModelName[INFO_MAX_BUFFER_SIZE];          ///< [OUT] \~chinese 型号名字             \~english Model name
    unsigned char       chDeviceVersion[INFO_MAX_BUFFER_SIZE];      ///< [OUT] \~chinese 设备版本               \~english Device Version
    unsigned int        nReserved[2];                               ///<       \~chinese 预留                   \~english Reserved
}SL_SSZN_GEV_DEVICE_INFO;

///< \~chinese 设备传输层协议类型       \~english Device Transport Layer Protocol Type
#define SL_CXP_INTERFACE_UNKNOW       0x00000000          ///< \~chinese 未知接口                \~english unknow interface
#define SL_CXP_INTERFACE_FLEXIO       0x10100001          ///< \~chinese 美乐威CXP12采集卡        \~english magewell CoaXPress interface
#define SL_GEV_INTERFACE_SSZN         0x20000002          ///< \~chinese 深视自研GEV接口          \~english sszn GEV interface
#define SL_USB_INTERFACE_OCT          0x30100003          ///< \~chinese OCT U3V接口             \~english oct USB3 Version interface

/// \~chinese 设备信息                  \~english Device info
typedef struct tagSL_DEVICE_INFO
{
    unsigned int            nInterFaceIndex;                                   ///< [OUT] \~chinese 所属interface       \~english Device Transport Layer Protocol Type
    unsigned int            nDeviceIndex;                                      ///< [OUT] \~chinese 所属device           \~english Device Transport Layer Protocol Type
    unsigned int            nTLayerType;                                       ///< [OUT] \~chinese 设备传输层协议类型       \~english Device Transport Layer Protocol Type
    unsigned char           chInterfaceID[INFO_MAX_BUFFER_SIZE];               ///< [OUT] \~chinese Interface ID       \~english Interface ID of Frame Grabber
    unsigned char           chDeviceID[INFO_MAX_BUFFER_SIZE];                  ///< [OUT] \~chinese 相机ID          \~english Device ID
    unsigned char           chDeviceDisplayName[INFO_MAX_BUFFER_SIZE];         ///< [OUT] \~chinese 相机Display Name         \~english Display Name
    unsigned int            nReserved[3];                                      ///< [OUT] \~chinese 预留                    \~english Reserved
    union
    {
        SL_GENTL_CXP_DEVICE_INFO     stGenTLCXPInfo;                 ///< [OUT] \~chinese 采集卡CoaXPress设备信息     \~english CoaXPress Device Info On Frame Grabber
        SL_OCT_USB3_DEVICE_INFO      stOctUsb3VInfo;                ///< [OUT] \~chinese  Oct U3v设备信息          \~english OCT U3V Device Info On Frame Grabber
        SL_SSZN_GEV_DEVICE_INFO      stCustGevInfo;                  ///< [OUT] \~chinese 深视自研Gev设备信息         \~english GEV Device Info On Frame Grabber
    }SpecialInfo;

}SL_DEVICE_INFO;

///< \~chinese 最大支持的设备个数       \~english The maximum number of supported devices
#define SL_MAX_DEVICE_NUM               256

/// \~chinese 设备信息列表              \~english Device Information List
typedef struct tagSL_DEVICE_INFO_LIST
{
    unsigned int      nDeviceNum;                                ///< [OUT] \~chinese 在线设备数量           \~english Online Device Number
    SL_DEVICE_INFO*  pDeviceInfo[SL_MAX_DEVICE_NUM];             ///< [OUT] \~chinese 支持最多256个设备      \~english Support up to 256 devices

}SL_DEVICE_INFO_LIST;


///< \~chinese 最大支持的采集卡数量  \~english The maximum number of Frame Grabber interface supported
#define SL_MAX_INTERFACE_NUM            64

///< \~chinese 采集卡信息            \~english Interface information
typedef struct tagSL_INTERFACE_INFO
{
    unsigned char       chInterfaceID[INFO_MAX_BUFFER_SIZE];      ///< \~chinese 采集卡ID    \~english Interface ID
    unsigned char       chDisplayName[INFO_MAX_BUFFER_SIZE];      ///< \~chinese 显示名称    \~english Display name
    unsigned char       chSerialNumber[INFO_MAX_BUFFER_SIZE];     ///< \~chinese 序列号      \~english Serial number
    unsigned char       chModelName[INFO_MAX_BUFFER_SIZE];        ///< [OUT] \~chinese 型号       \~english model name
    unsigned char       chManufacturer[INFO_MAX_BUFFER_SIZE];     ///< [OUT] \~chinese 厂商       \~english manufacturer name
    unsigned char       chDeviceVersion[INFO_MAX_BUFFER_SIZE];    ///< [OUT] \~chinese 版本号     \~english device version
    unsigned char       chUserDefinedName[INFO_MAX_BUFFER_SIZE];  ///< [OUT] \~chinese 自定义名称 \~english user defined name
    unsigned int        nReserved[64];                            ///< \~chinese 保留字段     \~english Reserved
}SL_INTERFACE_INFO;

///< \~chinese 采集卡信息列表           \~english Interface Information List
typedef struct tagSL_INTERFACE_INFO_LIST
{
    unsigned int nInterfaceNum;                                     ///< [OUT] \~chinese 采集卡数量                      \~english Interface Number
    SL_INTERFACE_INFO* pInterfaceInfos[SL_MAX_INTERFACE_NUM];     ///< [OUT] \~chinese 采集卡信息, 支持最多64个设备     \~english Information of interfaces, support up to 64 interfaces
}SL_INTERFACE_INFO_LIST;



/// \~chinese 录制媒介                  \~english The media of Recording
typedef enum tatSL_RECORD_MEDIA
{
    RecordMedia_Memory      = 0,                  ///< \~chinese PC内存                     \~english PC Memory
    RecordMedia_RAWW        = 0x1001,             ///< \~chinese 磁盘多文件序列(RAWW)         \~english Multiple file Sequence on disk (RAWW)
    RecordMedia_MRAW        = 0x1002,             ///< \~chinese 磁盘单文件序列(MRAW)         \~english Disk single file sequence (MRAW)
    RecordMedia_BMP         = 0x2001,             ///< \~chinese 图像序列(BMP)               \~english Image Sequence (BMP)
    RecordMedia_PNG         = 0x2002,             ///< \~chinese 图像序列(PNG)               \~english Image Sequence (PNG)
    RecordMedia_TIFF        = 0x2003,             ///< \~chinese 图像序列(TIFF)              \~english Image Sequence (TIFF)
    RecordMedia_AVI         = 0x3001,             ///< \~chinese 视频序列(AVI)               \~english Video Sequence (AVI)
    RecordMedia_MP4         = 0x3002,             ///< \~chinese 视频序列(AVI)               \~english Video Sequence (MP4)
}SL_RECORD_MEDIA;


/// \~chinese 参数值类型枚举  \~english Enumeration of parameter value types
typedef enum {
    PARAM_VALUE_INT = 0,     ///< \~chinese 整型参数（int）                     \~english Integer type parameter (`int`)
    PARAM_VALUE_BOOL,        ///< \~chinese 布尔参数（true/false）              \~english Boolean type parameter (`true` / `false`)
    PARAM_VALUE_ENUM,        ///< \~chinese 枚举参数（带索引的整数）              \~english Enum type parameter (indexed integer)
    PARAM_VALUE_STRING,      ///< \~chinese 字符串参数                          \~english String type parameter
    PARAM_VALUE_FLOAT        ///< \~chinese 浮点数参数（float/double）          \~english Floating-point type parameter (`float` / `double`)
} PARAM_VALUE_TYPE;


typedef struct tagSLEnumItem
{
    long long nValue;           ///< \~chinese 枚举对应整数值 \~english Integer value of the enum entry
    char      strSymbolic[128]; ///< \~chinese 枚举名称     \~english Symbolic name of the enum entry
} SLEnumItem;



///\~chinese shs事件回调函数定义  \~english SHS event callback function definition
/// nMsgType:
///     0x10000001    \~chinese 相机掉线        \~english Camera disconnected
/// pUser:            \~chinese 用户自定义句柄   \~english User-defined handle

typedef void (*SL_EVENT_CALLBACK)(unsigned int nMsgType,void* pUser);


typedef struct tagSL_REQIMAGES_PARAM
{
    unsigned long long datasize;                                ///< \~chinese 图像大小（单位：字节）        \~english Image size (in bytes)
    unsigned int       Width;                                   ///< \~chinese 图像宽度                      \~english Image width
    unsigned int       Height;                                  ///< \~chinese 图像高度                      \~english Image height
    unsigned int       pixformat;                               ///< \~chinese 图像格式（参考 PFUN.h）流数据传输位宽       \~english Pixel format (refer to PFUN.h).Stream data transmission bit width.
    unsigned int       frameid;                                 ///< \~chinese 图像帧ID                      \~english Frame ID
    unsigned int       BeforeTriggerFrameALLNum;                ///< \~chinese 触发后可录制总帧数            \~english Total recordable frames after trigger
    unsigned int       AfterTriggerFrameALLNum;                 ///< \~chinese 触发前可录制总帧数            \~english Total recordable frames before trigger
    unsigned int       BeforeTriggerFrameRecNum;                ///< \~chinese 触发后已录制帧数              \~english Recorded frames after trigger
    unsigned int       AfterTriggerFrameRecNum;                 ///< \~chinese 触发前已录制帧数              \~english Recorded frames before trigger

    unsigned int       RunMode;                                 ///< \~chinese 当前运行模式（预览、回放、录制、就绪、停止） \~english Run mode (Preview, Playback, Record, Ready, Stop)

    unsigned int       CacheSize;                               ///< \~chinese 当前缓存容量（帧数）          \~english Cache size (in frames)
    unsigned int       LoopFlag;                                ///< \~chinese 是否循环存储标志              \~english Loop recording flag

    unsigned long long Frametime;                               ///< \~chinese 帧时间戳（ns[10:0], us[20:10], ms[30:20], sec[36:30], min[42:36], hour[47:42], day[56:47])
                                                                ///< \~english Frame timestamp (bitfield: ns[10:0], us[20:10], ms[30:20], sec[36:30], min[42:36], hour[47:42], day[56:47])
    unsigned int       AdcBitdepth;                             ///< \~chinese 流数据实际有效位宽              \~english Actual effective bit width of streaming data
    unsigned char      IsNewFrame;                              ///< \~chinese 是否为新帧 (1=新帧, 0=缓存帧)   \~english Whether this is a new frame (1=new, 0=cached)
    unsigned char      Reserve[255];                            ///< \~chinese 预留字段                      \~english Reserved field (255 bytes)
} SL_REQIMAGES_PARAM;


typedef void (*SL_STREAM_CALLBACK)(unsigned char* data,const SL_REQIMAGES_PARAM* pImageParam,void* pUser);
#endif // SLAPIDEFINE_H
