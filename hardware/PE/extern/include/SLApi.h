#ifndef SLAPI_H
#define SLAPI_H

#include "SLApiDefine.h"

#ifdef	__cplusplus
extern "C" {
#endif	/*	__cplusplus	*/


///@~chinese
/// \brief SLIF_Init   初始化(全局必须调用一次)
/// \return 0:成功 -1:失败
///
///@~english
/// \brief SLIF_Init Initialization (must be called once globally)
/// \return 0: success -1: failure
SLAPISHARED_API int SLIF_Init();


///@~chinese
/// \brief SLIF_UnInit    结束初始化
/// \return 0:成功 -1:失败
///
///@~english
/// \brief SLIF_UnInit End initialization
/// \return 0: success -1: failure
SLAPISHARED_API int SLIF_UnInit();

///@~chinese
/// \brief SLIF_GetLastErrorInfo   获取最后的错误信息
/// \param sErrText                 错误信息文本(in)
/// \param piSize                   错误信息大小(in out)
/// \return                         0:成功 -1:失败
///
///@~english
/// \brief SLIF_GetLastErrorInfo   Get the last error information
/// \param sErrText                 Error information text (in)
/// \param piSize                   Error information size (in out)
/// \return 0: Success -1: Failure
///
SLAPISHARED_API int SLIF_GetLastErrorInfo(char* sErrText, int* piSize);

///
/// \brief SLIF_GetSupportTLayerTypeList   获取当前版本支持的传输层协议类型链表
/// \param nTLayerTypeList                  协议链表
/// \param piTLayerTypeNum                  链表个数
/// \return                                 0:成功 -1:失败
///
SLAPISHARED_API int SLIF_GetSupportTLayerTypeList(unsigned int* nTLayerTypeList, int* piTLayerTypeNum);

///
/// \brief SLIF_GetTLayerTypeName         获取传输层协议名称
/// \param nTLayerType                     传输层协议
/// \param pBuffer                         传输层名称缓存
/// \param piSize                          传输层名称缓存大小
/// \return                                0:成功 -1:失败
///
SLAPISHARED_API int SLIF_GetTLayerTypeName(unsigned int nTLayerType, char *pBuffer, int* piSize);

///
/// \brief SLIF_GetTLayerTypeInitResult   获取传输层初始化结果
/// \param nTLayerType                     传输层协议
/// \param pBuffer                         传输层初始化信息缓存
/// \param piSize                          传输层初始化信息大小
/// \return                                0:成功 -1:失败
///
SLAPISHARED_API int SLIF_GetTLayerTypeInitResult(unsigned int nTLayerType, char *pBuffer, int* piSize);
///
/// \brief SLIF_DetectBoardCard        搜索Interface
/// \param pShsHandle                   SHS SDK句柄(in)
/// \param pCardInfoList                采集卡搜索枚举信息(out)
/// \return                             0:成功 -1:失败 (错误信息:通过SLIF_GetLastErrorInfo读取)
///
SLAPISHARED_API int SLIF_DetectInterfaces(unsigned int nTLayerType,SL_INTERFACE_INFO_LIST *pstInterfaceList,void* pUser,int pUserOpt);

///
/// \brief SLIF_DetectDevices          搜索Device
/// \param nTLayerType                  传输层协议类型
/// \param pstDevList                   设备搜索枚举信息(out)
/// \param pUser                        预留(填NULL)
/// \param pUserOpt                     预留(填0)
/// \return                             0:成功 -1:失败 (错误信息:通过SLIF_GetLastErrorInfo读取)
///
SLAPISHARED_API int SLIF_DetectDevices(unsigned int nTLayerType,SL_DEVICE_INFO_LIST* pstDevList,void* pUser,int pUserOpt);

///
/// \brief SLIF_OpenDevice     打开设备
/// \param pstDevInfo           设备id(in 0 ~ SL_DEVICE_INFO_LIST::nDeviceNum)
/// \param pDevHandle           设备句柄(in out)
/// \return                     0:成功 -1:失败 (错误信息:通过SLIF_GetLastErrorInfo读取)
///
SLAPISHARED_API int SLIF_OpenDevice(unsigned int nTLayerType,unsigned int nInterfaceId,unsigned int nDeviceId,void**pDevHandle);

///
/// \brief SLIF_CloseDevice    关闭设备
/// \param pDevHandle           设备句柄(in)
/// \return                     0:成功 -1:失败 (错误信息:通过SLIF_GetLastErrorInfo读取)
///注意:此接口调用成功后，设备句柄将会失效
SLAPISHARED_API int SLIF_CloseDevice(void*pDevHandle);

///@~chinese
/// \brief SLIF_RegisterEventCallBack  注册事件回调(不需要可不调用)
/// \param pDevHandle                   设备句柄(in)
/// \param callback                     事件回调函数
/// \param pUser                        用户自定义句柄
/// \return                             0:成功 -1:失败 (错误信息:通过SLIF_GetLastErrorInfo读取)
///
///@~english
/// \brief SLIF_RegisterEventCallBack  registers event callback (fill NULL if not needed)
/// \param pShsHandle                   device handle
/// \param callback                     event callback function
/// \param pUser                        user-defined handle
/// \return 0: success -1: failure (error information: read through SLIF_GetLastErrorInfo)
///
SLAPISHARED_API int SLIF_RegisterEventCallBack(void*pDevHandle,SL_EVENT_CALLBACK callback,void*pUser);

///
/// \brief SLIF_RegisterStreamCallBack  注册数据流图像回调函数
/// \param pDevHandle                   设备句柄(in)
/// \param callback                     数据流图像回调函数(in)
/// \param pUser                        用户自定义参数指针(in，在回调函数触发时透传给用户)
/// \return                             0:成功  -1:失败(错误信息:通过 SLIF_GetLastErrorInfo 读取)
///
/// \note 注册成功后，图像到达时将通过回调函数异步返回。
/// \note 回调函数中应避免执行耗时操作，以免影响取流性能。
///
SLAPISHARED_API int SLIF_RegisterStreamCallBack(void*pDevHandle,SL_STREAM_CALLBACK callback,void*pUser);

///
/// \brief SLIF_StartCapture   打开设备流传输
/// \param pDevHandle           设备句柄(in)
/// \return                     0:成功 -1:失败 (错误信息:通过SLIF_GetLastErrorInfo读取)
///
SLAPISHARED_API int SLIF_StartCapture(void*pDevHandle);

///
/// \brief SLIF_StopCapture    关闭设备流传输
/// \param pDevHandle           设备句柄(in)
/// \return                     0:成功 -1:失败 (错误信息:通过SLIF_GetLastErrorInfo读取)
///
SLAPISHARED_API int SLIF_StopCapture(void*pDevHandle);

///
/// \brief SLIF_AcquirePreviewFrameRef  获取预览图像指针(非实时获取，从数据流中抽帧.如需获取实时流，请使用SLIF_RegisterStreamCallBack)
/// \param pDevHandle                 设备句柄(in)
/// \param ppData                     图像数据指针(out，由接口返回图像地址,拿到地址需要拷贝，如果不拷贝则会被覆盖)
/// \param pParam                     图像参数信息(out)
/// \param timeout                    请求超时，单位毫秒(in)
/// \return                           0:成功  -1:失败(错误信息:通过 SLIF_GetLastErrorInfo 读取)
///
/// \note 仅在打开流传输后才能请求图像；如果请求失败，可适当增加延迟后重试。
///
SLAPISHARED_API int SLIF_AcquirePreviewFrameRef(void* pDevHandle,unsigned char** data,SL_REQIMAGES_PARAM* param,unsigned int timeout);

///
/// \brief SLIF_ReadGenICamXmlToMemory 读取指定设备的XML至内存
/// \param pDevHandle                   设备句柄(in)
/// \param xml_buf                      内存地址(in out 如需获取xml大小可传入NULL)
/// \param psize                        xml大小(in out)
/// \return                             0:成功 -1:失败 (错误信息:通过SLIF_GetLastErrorInfo读取)
///
SLAPISHARED_API int SLIF_ReadGenICamXmlToMemory(void*pDevHandle, char* xml_buf, uint64_t* psize);

///
/// \brief SLIF_ReadGenICamXmlToFile   读取指定设备的XML至文件
/// \param pDevHandle                   设备句柄(in)
/// \param xmlFilePath                  文件绝对路径(c:/xxx.xml or c:/xxx.zip)
/// \return                             0:成功 -1:失败 (错误信息:通过SLIF_GetLastErrorInfo读取)
///
SLAPISHARED_API int SLIF_ReadGenICamXmlToFile(void*pDevHandle,const char* xmlFilePath);

///@~chinese
/// \brief 使用 string 类型命令设置采集卡、设备或相机的参数
/// \param pDevHandle     设备句柄（输入）
/// \param pFeature       参数名（输入）
/// \param pStr           设置的字符串参数值（输入）
/// \return               0：成功，-1：失败（请调用 SLIF_GetLastErrorInfo 获取错误信息）
///

/// \~english
/// \brief Set a string-type parameter on frame grabber, device, or camera
/// \param pDevHandle     Device handle (in)
/// \param pFeature       Parameter name (in)
/// \param pStr           String value to set (in)
/// \return               0: Success, -1: Failure (use SLIF_GetLastErrorInfo to retrieve error info)
///
SLAPISHARED_API int SLIF_SetString(void *pDevHandle, const char* pFeature, const char* pStr);

///@~chinese
/// \brief 使用 string 类型命令读取采集卡、设备或相机的参数
/// \param pDevHandle     设备句柄（输入）
/// \param pFeature       参数名（输入）
/// \param pStr           输出缓冲区指针（输出）
/// \param piSize         输入：缓冲区大小，输出：实际写入的大小（单位：字节）
/// \return               0：成功，-1：失败
///

///@~english
/// \brief Get a string-type parameter from frame grabber, device, or camera
/// \param pDevHandle     Device handle (in)
/// \param pFeature       Parameter name (in)
/// \param pStr           Output buffer (out)
/// \param piSize         In: buffer size; Out: actual size written in bytes
/// \return               0: Success, -1: Failure
///
SLAPISHARED_API int SLIF_GetString(void *pDevHandle, const char* pFeature, char* pStr, uint64_t* piSize);

///@~chinese
/// \brief 设置 command 类型的参数（通常为只写权限）
/// \param pDevHandle     设备句柄（输入）
/// \param pFeature       参数名（输入）
/// \return               0：成功，-1：失败
///

///@~english
/// \brief Set a command-type parameter (usually write-only)
/// \param pDevHandle     Device handle (in)
/// \param pFeature       Parameter name (in)
/// \return               0: Success, -1: Failure
///
SLAPISHARED_API int SLIF_SetCommand(void *pDevHandle, const char* pFeature);


///@~chinese
/// \brief 设置整型类型参数（支持：整型、布尔、枚举）
/// \param pDevHandle     设备句柄（输入）
/// \param pFeature       参数名（输入）
/// \param iValue         设置的数值（输入）
/// \param ValType        参数类型（输入）：0=整型，1=布尔，2=枚举
/// \return               0：成功，-1：失败
///

///@~english
/// \brief Set an integer-type parameter (supports int, bool, enum)
/// \param pDevHandle     Device handle (in)
/// \param pFeature       Parameter name (in)
/// \param iValue         Value to set (in)
/// \param ValType        Value type: 0=int, 1=bool, 2=enum (default: 0)
/// \return               0: Success, -1: Failure
///
SLAPISHARED_API int SLIF_SetInteger(void *pDevHandle, const char* pFeature, int64_t iValue, int ValType = PARAM_VALUE_INT);

///@~chinese
/// \brief 读取整型类型参数（支持：整型、布尔、枚举）
/// \param pDevHandle     设备句柄（输入）
/// \param pFeature       参数名（输入）
/// \param piValue        返回读取的数值（输出）
/// \param ValType        参数类型（输入）：0=整型，1=布尔，2=枚举
/// \return               0：成功，-1：失败
///

///@~english
/// \brief Get an integer-type parameter (supports int, bool, enum)
/// \param pDevHandle     Device handle (in)
/// \param pFeature       Parameter name (in)
/// \param piValue        Retrieved value (out)
/// \param ValType        Value type: 0=int, 1=bool, 2=enum (default: 0)
/// \return               0: Success, -1: Failure
///
SLAPISHARED_API int SLIF_GetInteger(void *pDevHandle, const char* pFeature, int64_t* piValue, int ValType = PARAM_VALUE_INT);


///@~chinese
/// \brief 读取枚举类型参数的可选项列表
/// \param pDevHandle     设备句柄（输入）
/// \param pFeature       参数名（输入）
/// \param pItems         返回枚举项数组（输出）；当传 NULL 时，仅获取数量
/// \param pCount         枚举项数量（输入/输出）；
///                       输入时表示 pItems 可容纳的元素个数，
///                       输出时返回实际枚举项总数
/// \return               0：成功，-1：失败
///
///@~english
/// \brief Get the selectable item list of an enumeration parameter
/// \param pDevHandle     Device handle (in)
/// \param pFeature       Parameter name (in)
/// \param pItems         Output enum item array; if NULL, only the count is queried
/// \param pCount         Enum item count (in/out);
///                       input means the capacity of pItems,
///                       output returns the actual total number of enum items
/// \return               0: Success, -1: Failure
///
SLAPISHARED_API int SLIF_GetEnumItems(void* pDevHandle,const char* pFeature,SLEnumItem* pItems,int64_t* pCount);


///@~chinese
/// \brief 设置浮点型参数
/// \param pDevHandle     设备句柄（输入）
/// \param pFeature       参数名（输入）
/// \param fValue         设置的浮点值（输入）
/// \return               0：成功，-1：失败
///

///@~english
/// \brief Set a floating-point type parameter
/// \param pDevHandle     Device handle (in)
/// \param pFeature       Parameter name (in)
/// \param fValue         Value to set (in)
/// \return               0: Success, -1: Failure
///
SLAPISHARED_API int SLIF_SetFloat(void *pDevHandle, const char* pFeature, double fValue);

///@~chinese
/// \brief 读取浮点型参数
/// \param pDevHandle     设备句柄（输入）
/// \param pFeature       参数名（输入）
/// \param pfValue        返回读取的浮点值（输出）
/// \return               0：成功，-1：失败
///

///@~english
/// \brief Get a floating-point type parameter
/// \param pDevHandle     Device handle (in)
/// \param pFeature       Parameter name (in)
/// \param pfValue        Retrieved value (out)
/// \return               0: Success, -1: Failure
///
SLAPISHARED_API int SLIF_GetFloat(void *pDevHandle, const char* pFeature, double* pfValue);

#ifdef	__cplusplus
}
#endif	/*	__cplusplus	*/
#endif // SLAPI_H
