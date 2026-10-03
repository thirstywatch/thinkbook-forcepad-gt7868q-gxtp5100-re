/*=============================================================================
  GdixSpbProbe.c  --  最小只读 SPB 客户端驱动（KMDF）
  -----------------------------------------------------------------------------
  目的：绕过 hidi2c.sys，直接向 Goodix GT7868Q 触控 IC 发只读 I2C 事务。
  第一目标：读到 CFG_START_ADDR(0x96F8) 与 VER_ADDR(0x4014)。
  读到 = 通路打通。

  ★ 架构（经微软文档确认）
  ---------------------------------------------------------------------------
  应用层不能直接发 IOCTL_SPB_EXECUTE_SEQUENCE —— 该 IOCTL 只允许内核态驱动发送。
  所以正确做法是：
      [用户态 exe] --自定义IOCTL--> [本驱动] --IOCTL_SPB_EXECUTE_SEQUENCE--> [I2C]

  本驱动不实现 SPB 控制器，只作为 *客户端*：
    1. 从 ACPI 设备继承父级 I2C 目标的文件对象（WdfIoTargetOpen / RemoteTarget）
    2. 用 Spb.h 的 SPB_TRANSFER_LIST 组包
    3. 发 IOCTL_SPB_EXECUTE_SEQUENCE 给那条 I2C 目标

  ★ 只读。不写任何寄存器。不碰 flash。不碰刷机三连。
  安全约束（硬编码，勿改）：
    - 单次事务 <= 32 字节
    - 两次事务之间强制间隔 >= 500 ms
    - 只允许读地址白名单：0x96F8 / 0x4014 / 0x1800 / 0x3800
    - 拒绝任何写操作
=============================================================================*/

#include <ntddk.h>
#include <wdf.h>
#include <spb.h>            /* 客户端用这个，不是 spbcx.h */
#include <wdm.h>
#include <wdmsec.h>

#define GDIX_TAG            'biSG'

/* --- 与 round64_readback.py 保持一致的 Goodix 私有封装 --- */
#define HID_PKG_SYNC        0x0E
#define HID_PKG_DIRECT_RW   0x20        /* _I2C_DIRECT_RW */

/* --- 只允许读这些寄存器（白名单） --- */
#define REG_CFG_START       0x96F8
#define REG_VER             0x4014
#define REG_PARAM_A         0x1800
#define REG_PARAM_B         0x3800

#define MAX_XFER            32          /* 单次上限 */
#define MIN_GAP_MS          500         /* 事务最小间隔 */

/* --- 自定义 IOCTL（用户态 → 驱动） --- */
#define IOCTL_GDIX_READ_REG \
    CTL_CODE(FILE_DEVICE_UNKNOWN, 0x801, METHOD_BUFFERED, FILE_ANY_ACCESS)

#define IOCTL_GDIX_STATUS \
    CTL_CODE(FILE_DEVICE_UNKNOWN, 0x802, METHOD_BUFFERED, FILE_ANY_ACCESS)

typedef struct _GDIX_READ_REQ {
    USHORT Address;
    USHORT Length;
} GDIX_READ_REQ, *PGDIX_READ_REQ;

typedef struct _GDIX_READ_RSP {
    NTSTATUS Status;
    ULONG    BytesReturned;
    UCHAR    Data[MAX_XFER];
} GDIX_READ_RSP, *PGDIX_READ_RSP;

/*=============================================================================
  设备上下文
=============================================================================*/
typedef struct _DEVICE_CONTEXT {
    WDFIOTARGET     I2CTarget;      /* 指向父级 I2C 目标的 IO 目标 */
    LARGE_INTEGER   LastXferTime;   /* 节流用 */
    ULONG           TotalXfers;
    ULONG           FailedXfers;
} DEVICE_CONTEXT, *PDEVICE_CONTEXT;

WDF_DECLARE_CONTEXT_TYPE_WITH_NAME(DEVICE_CONTEXT, GetDeviceContext)

/*=============================================================================
  前向声明
=============================================================================*/
DRIVER_INITIALIZE DriverEntry;
EVT_WDF_DRIVER_DEVICE_ADD          EvtDeviceAdd;
EVT_WDF_DEVICE_PREPARE_HARDWARE    EvtPrepareHardware;
EVT_WDF_DEVICE_RELEASE_HARDWARE    EvtReleaseHardware;
EVT_WDF_IO_QUEUE_IO_DEVICE_CONTROL EvtIoDeviceControl;

static NTSTATUS GdixBuildReadPkg(
    _In_  USHORT Address,
    _In_  USHORT Length,
    _Out_writes_(MAX_XFER) PUCHAR Buffer,
    _Out_ PULONG PkgLen);

static VOID GdixThrottle(_Inout_ PDEVICE_CONTEXT ctx);

/*=============================================================================
  DriverEntry
=============================================================================*/
NTSTATUS
DriverEntry(
    _In_ PDRIVER_OBJECT  DriverObject,
    _In_ PUNICODE_STRING RegistryPath)
{
    WDF_DRIVER_CONFIG config;
    NTSTATUS status;

    KdPrint(("[GdixSpbProbe] DriverEntry\n"));

    WDF_DRIVER_CONFIG_INIT(&config, EvtDeviceAdd);

    status = WdfDriverCreate(
        DriverObject,
        RegistryPath,
        WDF_NO_OBJECT_ATTRIBUTES,
        &config,
        WDF_NO_HANDLE);

    if (!NT_SUCCESS(status)) {
        KdPrint(("[GdixSpbProbe] WdfDriverCreate failed 0x%08X\n", status));
    }
    return status;
}

/*=============================================================================
  EvtDeviceAdd
=============================================================================*/
NTSTATUS
EvtDeviceAdd(
    _In_ WDFDRIVER        Driver,
    _Inout_ PWDFDEVICE_INIT DeviceInit)
{
    NTSTATUS              status;
    WDFDEVICE             device;
    WDF_OBJECT_ATTRIBUTES attributes;
    WDF_IO_QUEUE_CONFIG   queueConfig;
    PDEVICE_CONTEXT       ctx;
    UNICODE_STRING        symLink;

    UNREFERENCED_PARAMETER(Driver);

    KdPrint(("[GdixSpbProbe] EvtDeviceAdd\n"));

    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(&attributes, DEVICE_CONTEXT);

    status = WdfDeviceCreate(&DeviceInit, &attributes, &device);
    if (!NT_SUCCESS(status)) {
        KdPrint(("[GdixSpbProbe] WdfDeviceCreate failed 0x%08X\n", status));
        return status;
    }

    ctx = GetDeviceContext(device);
    RtlZeroMemory(ctx, sizeof(*ctx));

    /* 创建符号链接，供用户态 CreateFile("\\\\.\\GdixSpbProbe") */
    RtlInitUnicodeString(&symLink, L"\\DosDevices\\GdixSpbProbe");
    status = WdfDeviceCreateSymbolicLink(device, &symLink);
    if (!NT_SUCCESS(status)) {
        KdPrint(("[GdixSpbProbe] CreateSymbolicLink failed 0x%08X (continuing)\n",
                 status));
    }

    /* 拿父设备（ACPI\GXTP5100\1 的父级 —— I2C 控制器栈） */
    (VOID)WdfDeviceWdmGetPhysicalDevice(device);

    WDF_IO_QUEUE_CONFIG_INIT_DEFAULT_QUEUE(
        &queueConfig,
        WdfIoQueueDispatchSequential);
    queueConfig.EvtIoDeviceControl = EvtIoDeviceControl;

    status = WdfIoQueueCreate(
        device,
        &queueConfig,
        WDF_NO_OBJECT_ATTRIBUTES,
        WDF_NO_HANDLE);
    if (!NT_SUCCESS(status)) {
        KdPrint(("[GdixSpbProbe] WdfIoQueueCreate failed 0x%08X\n", status));
        return status;
    }

    return STATUS_SUCCESS;
}

/*=============================================================================
  EvtPrepareHardware -- 建立到 I2C 的 IO 目标
=============================================================================*/
NTSTATUS
EvtPrepareHardware(
    _In_ WDFDEVICE    Device,
    _In_ WDFCMRESLIST ResourcesRaw,
    _In_ WDFCMRESLIST ResourcesTranslated)
{
    NTSTATUS          status;
    PDEVICE_CONTEXT   ctx = GetDeviceContext(Device);
    WDF_IO_TARGET_OPEN_PARAMS openParams;
    WDF_OBJECT_ATTRIBUTES     attr;
    UNICODE_STRING            targetName;

    UNREFERENCED_PARAMETER(ResourcesRaw);
    UNREFERENCED_PARAMETER(ResourcesTranslated);

    KdPrint(("[GdixSpbProbe] EvtPrepareHardware\n"));

    /*
      目标设备名。GXTP5100 的 PDO 名（见 ACPI 导出 Device_PDOName = \Device\0000008a）。
      注意：PDO 名每次枚举可能变化，故同时准备备用名。
    */
    RtlInitUnicodeString(&targetName, L"\\Device\\0000008a");

    /*
      关键：打开 *父设备* 的远程 IO 目标。

      我们的设备节点（本驱动）是挂在 ACPI\GXTP5100\1 之下的过滤/子设备，
      其父设备正是 I2C 栈上的目标从设备。
      SPB 客户端就是通过"父设备的文件对象"发 IOCTL_SPB_EXECUTE_SEQUENCE。

      用 WDF_IO_TARGET_OPEN_PARAMS_INIT_OPEN_BY_FILE 拿到父级文件对象。
    */
    WDF_OBJECT_ATTRIBUTES_INIT(&attr);
    attr.ParentObject = Device;

    status = WdfIoTargetCreate(Device, &attr, &ctx->I2CTarget);
    if (!NT_SUCCESS(status)) {
        KdPrint(("[GdixSpbProbe] WdfIoTargetCreate failed 0x%08X\n", status));
        return status;
    }

    {
        PDEVICE_OBJECT parentPdo = IoGetAttachedDeviceReference(
                                        WdfDeviceWdmGetDeviceObject(Device));
        if (parentPdo != NULL) {
            KdPrint(("[GdixSpbProbe] parent device object @ %p\n", parentPdo));
            ObDereferenceObject(parentPdo);
        }
    }

    WDF_IO_TARGET_OPEN_PARAMS_INIT_OPEN_BY_NAME(
        &openParams,
        &targetName,
        GENERIC_READ | GENERIC_WRITE);

    openParams.ShareAccess = FILE_SHARE_READ | FILE_SHARE_WRITE;

    status = WdfIoTargetOpen(ctx->I2CTarget, &openParams);
    if (!NT_SUCCESS(status)) {
        KdPrint(("[GdixSpbProbe] WdfIoTargetOpen failed 0x%08X\n", status));
        KdPrint(("[GdixSpbProbe] -> set IoDeviceObjectName in INF for the target\n"));
        /* 不返回失败：允许设备加载，后续 IOCTL 会给出更明确的错误 */
    } else {
        KdPrint(("[GdixSpbProbe] I2C target OPENED. READY.\n"));
    }

    KeQuerySystemTimePrecise(&ctx->LastXferTime);

    KdPrint(("[GdixSpbProbe] prepare done\n"));
    return STATUS_SUCCESS;
}

/*=============================================================================
  EvtReleaseHardware
=============================================================================*/
NTSTATUS
EvtReleaseHardware(
    _In_ WDFDEVICE    Device,
    _In_ WDFCMRESLIST ResourcesTranslated)
{
    PDEVICE_CONTEXT ctx = GetDeviceContext(Device);
    UNREFERENCED_PARAMETER(ResourcesTranslated);

    KdPrint(("[GdixSpbProbe] EvtReleaseHardware (xfer=%lu fail=%lu)\n",
             ctx->TotalXfers, ctx->FailedXfers));

    if (ctx->I2CTarget != NULL) {
        WdfIoTargetClose(ctx->I2CTarget);
        ctx->I2CTarget = NULL;
    }
    return STATUS_SUCCESS;
}

/*=============================================================================
  构造 Goodix 私有读包
=============================================================================*/
static NTSTATUS
GdixBuildReadPkg(
    _In_  USHORT Address,
    _In_  USHORT Length,
    _Out_writes_(MAX_XFER) PUCHAR Buffer,
    _Out_ PULONG PkgLen)
{
    if (Length == 0 || Length > MAX_XFER) {
        return STATUS_INVALID_PARAMETER;
    }

    RtlZeroMemory(Buffer, MAX_XFER);
    Buffer[0] = HID_PKG_SYNC;
    Buffer[1] = HID_PKG_DIRECT_RW;
    Buffer[4] = 5;
    Buffer[5] = 1;                          /* read */
    Buffer[6] = (UCHAR)((Address >> 8) & 0xFF);
    Buffer[7] = (UCHAR)(Address & 0xFF);
    Buffer[8] = (UCHAR)((Length >> 8) & 0xFF);
    Buffer[9] = (UCHAR)(Length & 0xFF);

    *PkgLen = 10;
    return STATUS_SUCCESS;
}

/*=============================================================================
  节流
=============================================================================*/
static VOID
GdixThrottle(_Inout_ PDEVICE_CONTEXT ctx)
{
    LARGE_INTEGER now, delta;
    LONGLONG      elapsedMs;

    KeQuerySystemTimePrecise(&now);
    delta.QuadPart = now.QuadPart - ctx->LastXferTime.QuadPart;
    elapsedMs = delta.QuadPart / 10000LL;

    if (ctx->LastXferTime.QuadPart != 0 && elapsedMs < MIN_GAP_MS) {
        LARGE_INTEGER interval;
        LONGLONG waitMs = MIN_GAP_MS - elapsedMs;
        interval.QuadPart = -waitMs * 10000LL;
        KdPrint(("[GdixSpbProbe] throttle %lld ms\n", waitMs));
        KeDelayExecutionThread(KernelMode, FALSE, &interval);
    }

    KeQuerySystemTimePrecise(&ctx->LastXferTime);
}

/*=============================================================================
  发一次真正的 SPB 序列：写命令包 + 读回数据
=============================================================================*/
static NTSTATUS
GdixSpbXfer(
    _In_  PDEVICE_CONTEXT ctx,
    _In_  PUCHAR          CmdPkg,
    _In_  ULONG           CmdLen,
    _Out_writes_(RspLen) PUCHAR RspBuf,
    _In_  ULONG           RspLen,
    _Out_ PULONG          BytesXfer)
{
    NTSTATUS status;
    SPB_TRANSFER_LIST_AND_ENTRIES(2) seq;
    WDF_MEMORY_DESCRIPTOR cmdDesc, rspDesc;
    WDF_REQUEST_SEND_OPTIONS opts;

    SPB_TRANSFER_LIST_INIT(&seq.List, 2);
    seq.List.Transfers[0] = SPB_TRANSFER_LIST_ENTRY_INIT_SIMPLE(
                                SpbTransferDirectionToDevice,
                                0,
                                CmdPkg,
                                CmdLen);
    seq.List.Transfers[1] = SPB_TRANSFER_LIST_ENTRY_INIT_SIMPLE(
                                SpbTransferDirectionFromDevice,
                                0,
                                RspBuf,
                                RspLen);

    WDF_MEMORY_DESCRIPTOR_INIT_BUFFER(&cmdDesc, &seq, sizeof(seq));
    WDF_MEMORY_DESCRIPTOR_INIT_BUFFER(&rspDesc, NULL, 0);

    WDF_REQUEST_SEND_OPTIONS_INIT(&opts, WDF_REQUEST_SEND_OPTION_SYNCHRONOUS);
    WDF_REQUEST_SEND_OPTIONS_SET_TIMEOUT(&opts, WDF_REL_TIMEOUT_IN_SEC(2));

    ULONG_PTR         xferBytes = 0;

    status = WdfIoTargetSendIoctlSynchronously(
                ctx->I2CTarget,
                NULL,
                IOCTL_SPB_EXECUTE_SEQUENCE,
                &cmdDesc,
                &rspDesc,
                &opts,
                &xferBytes);

    if (BytesXfer != NULL) {
        *BytesXfer = (ULONG)xferBytes;
    }

    if (!NT_SUCCESS(status)) {
        KdPrint(("[GdixSpbProbe] SendIoctlSynchronously failed 0x%08X\n", status));
    }
    return status;
}

/*=============================================================================
  EvtIoDeviceControl
=============================================================================*/
VOID
EvtIoDeviceControl(
    _In_ WDFQUEUE   Queue,
    _In_ WDFREQUEST Request,
    _In_ size_t     OutputBufferLength,
    _In_ size_t     InputBufferLength,
    _In_ ULONG      IoControlCode)
{
    WDFDEVICE       device = WdfIoQueueGetDevice(Queue);
    PDEVICE_CONTEXT ctx    = GetDeviceContext(device);
    NTSTATUS        status = STATUS_INVALID_DEVICE_REQUEST;
    PGDIX_READ_REQ  req    = NULL;
    PGDIX_READ_RSP  rsp    = NULL;
    UCHAR           pkg[MAX_XFER];
    UCHAR           dat[MAX_XFER];
    ULONG           pkgLen = 0;
    ULONG           xfer   = 0;
    PVOID           inBuf  = NULL;
    PVOID           outBuf = NULL;

    UNREFERENCED_PARAMETER(InputBufferLength);
    UNREFERENCED_PARAMETER(OutputBufferLength);

    switch (IoControlCode) {

    case IOCTL_GDIX_STATUS:
        status = WdfRequestRetrieveOutputBuffer(Request,
                     sizeof(GDIX_READ_RSP), &outBuf, NULL);
        if (!NT_SUCCESS(status)) break;
        RtlZeroMemory(outBuf, sizeof(GDIX_READ_RSP));
        ((PGDIX_READ_RSP)outBuf)->Status        = STATUS_SUCCESS;
        ((PGDIX_READ_RSP)outBuf)->BytesReturned = ctx->TotalXfers;
        ((PGDIX_READ_RSP)outBuf)->Data[0]       = (UCHAR)(ctx->FailedXfers & 0xFF);
        WdfRequestCompleteWithInformation(Request, STATUS_SUCCESS,
                                          sizeof(GDIX_READ_RSP));
        return;

    case IOCTL_GDIX_READ_REG:
        status = WdfRequestRetrieveInputBuffer(Request,
                     sizeof(GDIX_READ_REQ), &inBuf, NULL);
        if (!NT_SUCCESS(status)) break;
        req = (PGDIX_READ_REQ)inBuf;

        /* 白名单 */
        if (req->Address != REG_CFG_START &&
            req->Address != REG_VER &&
            req->Address != REG_PARAM_A &&
            req->Address != REG_PARAM_B) {
            KdPrint(("[GdixSpbProbe] REJECT addr 0x%04X\n", req->Address));
            status = STATUS_ACCESS_DENIED;
            break;
        }
        if (req->Length == 0 || req->Length > MAX_XFER) {
            status = STATUS_INVALID_PARAMETER;
            break;
        }

        status = WdfRequestRetrieveOutputBuffer(Request,
                     sizeof(GDIX_READ_RSP), &outBuf, NULL);
        if (!NT_SUCCESS(status)) break;
        rsp = (PGDIX_READ_RSP)outBuf;
        RtlZeroMemory(rsp, sizeof(GDIX_READ_RSP));

        GdixThrottle(ctx);

        status = GdixBuildReadPkg(req->Address, req->Length, pkg, &pkgLen);
        if (!NT_SUCCESS(status)) break;

        KdPrint(("[GdixSpbProbe] READ addr=0x%04X len=%u\n",
                 req->Address, req->Length));

        RtlZeroMemory(dat, sizeof(dat));
        status = GdixSpbXfer(ctx, pkg, pkgLen, dat, req->Length, &xfer);

        if (!NT_SUCCESS(status)) {
            ctx->FailedXfers++;
            rsp->Status = status;
            KdPrint(("[GdixSpbProbe] xfer FAILED 0x%08X\n", status));
            WdfRequestCompleteWithInformation(Request, status,
                                              sizeof(GDIX_READ_RSP));
            return;
        }

        RtlCopyMemory(rsp->Data, dat, req->Length);
        ctx->TotalXfers++;
        rsp->Status = STATUS_SUCCESS;
        rsp->BytesReturned = xfer;

        KdPrint(("[GdixSpbProbe] xfer OK (#%lu) bytes=%lu\n",
                 ctx->TotalXfers, xfer));
        WdfRequestCompleteWithInformation(Request, STATUS_SUCCESS,
                                          sizeof(GDIX_READ_RSP));
        return;

    default:
        break;
    }

    WdfRequestComplete(Request, status);
}
