/**
  miniefi.h —— 精简 UEFI / ACPI 类型定义（不依赖 EDK2）

  用途：让我们那个几十行的 DXE 驱动能被 MSVC 直接编译 + 链接成 .efi，
        从而完全不需要搭 EDK2 工具链（也不需要 NASM / git clone）。

  只声明我们用得到的东西：
    * EFI_SYSTEM_TABLE / EFI_BOOT_SERVICES / EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL
    * EFI_CONFIGURATION_TABLE
    * ACPI RSDP / 描述符表头 / DSDT

  注意：结构体成员顺序与 UEFI 规范严格一致 —— 顺序错一个，函数指针就指错了。
        x64 上 UEFI 用的是微软标准 x64 调用约定，所以不需要 EFIAPI 修饰。
**/

#pragma once

/* x64 上 UEFI 用微软标准 x64 调用约定，不需要额外修饰 */
#ifndef EFIAPI
#define EFIAPI
#endif

typedef unsigned char       UINT8;
typedef unsigned short      UINT16;
typedef unsigned int        UINT32;
typedef unsigned long long  UINT64;
typedef unsigned long long  UINTN;
typedef void                VOID;
typedef UINTN               EFI_STATUS;
typedef VOID               *EFI_HANDLE;
typedef UINT16              CHAR16;

#define EFI_SUCCESS  0

#define SIGNATURE_32(a, b, c, d) \
  ((UINT32)(((UINT32)(a)) | ((UINT32)(b) << 8) | ((UINT32)(c) << 16) | ((UINT32)(d) << 24)))

typedef struct {
  UINT32  Data1;
  UINT16  Data2;
  UINT16  Data3;
  UINT8   Data4[8];
} EFI_GUID;

typedef struct {
  UINT64  Signature;
  UINT32  Revision;
  UINT32  HeaderSize;
  UINT32  CRC32;
  UINT32  Reserved;
} EFI_TABLE_HEADER;

typedef struct EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL;

struct EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL {
  VOID         *Reset;
  EFI_STATUS  (*OutputString)(EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *, CHAR16 *);
  VOID         *TestString;
  VOID         *QueryMode;
  VOID         *SetMode;
  EFI_STATUS  (*SetAttribute)(EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *, UINTN);
  VOID         *ClearScreen;
  VOID         *SetCursorPosition;
  VOID         *EnableCursor;
  VOID         *Mode;
};

typedef struct {
  UINT16  ScanCode;
  CHAR16  UnicodeChar;
} EFI_INPUT_KEY;

typedef struct EFI_SIMPLE_TEXT_INPUT_PROTOCOL EFI_SIMPLE_TEXT_INPUT_PROTOCOL;

struct EFI_SIMPLE_TEXT_INPUT_PROTOCOL {
  VOID         *Reset;
  EFI_STATUS  (*ReadKeyStroke)(EFI_SIMPLE_TEXT_INPUT_PROTOCOL *, EFI_INPUT_KEY *);
  VOID         *WaitForKey;
};

typedef struct {
  EFI_TABLE_HEADER  Hdr;

  VOID              *RaiseTPL;
  VOID              *RestoreTPL;
  VOID              *AllocatePages;
  VOID              *FreePages;
  VOID              *GetMemoryMap;
  VOID              *AllocatePool;
  VOID              *FreePool;
  VOID              *CreateEvent;
  VOID              *SetTimer;
  VOID              *WaitForEvent;
  VOID              *SignalEvent;
  VOID              *CloseEvent;
  VOID              *CheckEvent;
  VOID              *InstallProtocolInterface;
  VOID              *ReinstallProtocolInterface;
  VOID              *UninstallProtocolInterface;
  VOID              *HandleProtocol;
  VOID              *Reserved;
  VOID              *RegisterProtocolNotify;
  VOID              *LocateHandle;
  VOID              *LocateDevicePath;
  VOID              *InstallConfigurationTable;
  VOID              *LoadImage;
  VOID              *StartImage;
  VOID              *Exit;
  VOID              *UnloadImage;
  VOID              *ExitBootServices;
  VOID              *GetNextMonotonicCount;

  /* ★ 以下两个是我们真正要用的，偏移必须对 */
  EFI_STATUS       (*Stall)(UINTN Microseconds);

  VOID              *SetWatchdogTimer;
} EFI_BOOT_SERVICES;

typedef struct {
  EFI_TABLE_HEADER  Hdr;

  VOID              *GetTime;
  VOID              *SetTime;
  VOID              *GetWakeupTime;
  VOID              *SetWakeupTime;
  VOID              *SetVirtualAddressMap;
  VOID              *ConvertPointer;

  /* ★ 读写 UEFI 变量就是靠这两个 */
  EFI_STATUS       (*GetVariable)(CHAR16 *Name, EFI_GUID *VendorGuid,
                                  UINT32 *Attributes, UINTN *DataSize, VOID *Data);
  EFI_STATUS       (*GetNextVariableName)(UINTN *NameSize, CHAR16 *Name, EFI_GUID *VendorGuid);
  EFI_STATUS       (*SetVariable)(CHAR16 *Name, EFI_GUID *VendorGuid,
                                  UINT32 Attributes, UINTN DataSize, VOID *Data);

  VOID              *GetNextHighMonotonicCount;
  VOID              *ResetSystem;
  VOID              *UpdateCapsule;
  VOID              *QueryCapsuleCapabilities;
  VOID              *QueryVariableInfo;
} EFI_RUNTIME_SERVICES;

typedef struct {
  EFI_GUID  VendorGuid;
  VOID     *VendorTable;
} EFI_CONFIGURATION_TABLE;

/* UEFI 全局变量命名空间（Driver#### / DriverOrder 都在这里） */
static const EFI_GUID  gEfiGlobalVariableGuid = {
  0x8BE4DF61, 0x93CA, 0x11D2, { 0xAA, 0x0D, 0x00, 0xE0, 0x98, 0x03, 0x2B, 0x8C }
};

#define EFI_VARIABLE_NON_VOLATILE        0x00000001
#define EFI_VARIABLE_BOOTSERVICE_ACCESS  0x00000002
#define EFI_VARIABLE_RUNTIME_ACCESS      0x00000004
#define EFI_NOT_FOUND                    14

typedef struct {
  UINT8   Type;
  UINT8   SubType;
  UINT16  Length;
} EFI_DEVICE_PATH_PROTOCOL;

#define END_DEVICE_PATH_TYPE   0x7F
#define MEDIA_DEVICE_PATH      0x04
#define MEDIA_FILEPATH_DP      0x04

#define EFI_OPEN_PROTOCOL_GET_PROTOCOL  0x02

typedef struct {
  UINT32                            Revision;
  EFI_HANDLE                        ParentHandle;
  VOID                             *SystemTablePtr;   /* 本结构定义早于 EFI_SYSTEM_TABLE，故用 VOID* */
  EFI_HANDLE                        DeviceHandle;
  EFI_DEVICE_PATH_PROTOCOL         *FilePath;
  VOID                             *Reserved;
  UINT32                            LoadOptionsSize;
  VOID                             *LoadOptions;
  VOID                             *ImageBase;
  UINT64                            ImageSize;
  UINT32                            ImageCodeType;
  UINT32                            ImageDataType;
  VOID                             *Unload;
} EFI_LOADED_IMAGE_PROTOCOL;

static const EFI_GUID  gEfiLoadedImageProtocolGuid = {
  0x5B1B31A1, 0x9562, 0x11D2, { 0x8E, 0x3F, 0x00, 0xA0, 0xC9, 0x69, 0x72, 0x3B }
};

#define LOAD_OPTION_ACTIVE  0x00000001

/* ---- 文件系统（用来把驱动写进 ESP） ---- */

typedef struct EFI_FILE_PROTOCOL EFI_FILE_PROTOCOL;

struct EFI_FILE_PROTOCOL {
  UINT64       Revision;
  EFI_STATUS  (*Open)(EFI_FILE_PROTOCOL *, EFI_FILE_PROTOCOL **, CHAR16 *, UINT64, UINT64);
  EFI_STATUS  (*Close)(EFI_FILE_PROTOCOL *);
  EFI_STATUS  (*Delete)(EFI_FILE_PROTOCOL *);
  EFI_STATUS  (*Read)(EFI_FILE_PROTOCOL *, UINTN *, VOID *);
  EFI_STATUS  (*Write)(EFI_FILE_PROTOCOL *, UINTN *, VOID *);
  EFI_STATUS  (*GetPosition)(EFI_FILE_PROTOCOL *, UINT64 *);
  EFI_STATUS  (*SetPosition)(EFI_FILE_PROTOCOL *, UINT64);
  EFI_STATUS  (*GetInfo)(EFI_FILE_PROTOCOL *, EFI_GUID *, UINTN *, VOID *);
  EFI_STATUS  (*SetInfo)(EFI_FILE_PROTOCOL *, EFI_GUID *, UINTN, VOID *);
  EFI_STATUS  (*Flush)(EFI_FILE_PROTOCOL *);
};

typedef struct {
  UINT64       Revision;
  EFI_STATUS  (*OpenVolume)(VOID *, EFI_FILE_PROTOCOL **);
} EFI_SIMPLE_FILE_SYSTEM_PROTOCOL;

#define EFI_FILE_MODE_READ     0x0000000000000001ULL
#define EFI_FILE_MODE_WRITE    0x0000000000000002ULL
#define EFI_FILE_MODE_CREATE   0x0000000000000004ULL
#define EFI_FILE_DIRECTORY     0x0000000000000010ULL

#define EFI_BUFFER_TOO_SMALL   0x8000000000000005ULL
#define EFI_ERROR_MASK         0x8000000000000000ULL

#define ALL_HANDLES            0
#define BY_REGISTER_NOTIFY     1
#define BY_PROTOCOL            2

static const EFI_GUID  gEfiSimpleFileSystemProtocolGuid = {
  0x964E5B22, 0x6459, 0x11D2, { 0x8E, 0x39, 0x00, 0xA0, 0xC9, 0x69, 0x72, 0x3B }
};

static const EFI_GUID  gEfiDevicePathProtocolGuid = {
  0x09576E91, 0x6D3F, 0x11D2, { 0x8E, 0x39, 0x00, 0xA0, 0xC9, 0x69, 0x72, 0x3B }
};

typedef struct {
  EFI_TABLE_HEADER                     Hdr;

  CHAR16                              *FirmwareVendor;
  UINT32                               FirmwareRevision;
  UINT32                               Padding;
  EFI_HANDLE                           ConsoleInHandle;
  EFI_SIMPLE_TEXT_INPUT_PROTOCOL      *ConIn;
  EFI_HANDLE                           ConsoleOutHandle;
  EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL     *ConOut;
  EFI_HANDLE                           StandardErrorHandle;
  VOID                                *StdErr;
  EFI_RUNTIME_SERVICES                *RuntimeServices;
  EFI_BOOT_SERVICES                   *BootServices;
  UINTN                                NumberOfTableEntries;
  EFI_CONFIGURATION_TABLE             *ConfigurationTable;
} EFI_SYSTEM_TABLE;

//
// ---- ACPI ----
//

typedef struct {
  UINT32  Signature;
  UINT32  Length;
  UINT8   Revision;
  UINT8   Checksum;
  UINT8   OemId[6];
  UINT64  OemTableId;
  UINT32  OemRevision;
  UINT32  CreatorId;
  UINT32  CreatorRevision;
} EFI_ACPI_DESCRIPTION_HEADER;

typedef struct {
  UINT64  Signature;        /* "RSD PTR " */
  UINT8   Checksum;
  UINT8   OemId[6];
  UINT8   Revision;
  UINT32  RsdtAddress;
  UINT32  Length;
  UINT64  XsdtAddress;
  UINT8   ExtendedChecksum;
  UINT8   Reserved[3];
} EFI_ACPI_2_0_RSDP;

static const EFI_GUID  gAcpi20TableGuid = {
  0x8868e871, 0xe4f1, 0x11d3, { 0xbc, 0x22, 0x00, 0x80, 0xc7, 0x3c, 0x88, 0x81 }
};

static const EFI_GUID  gAcpi10TableGuid = {
  0xeb9d2d30, 0x2d88, 0x11d3, { 0x9a, 0x16, 0x00, 0x90, 0x27, 0x3f, 0xc1, 0x4d }
};

/* 按值逐字节比较 GUID（不用 CRT 的 memcmp） */
static int GuidEqual (const EFI_GUID *a, const EFI_GUID *b)
{
  const UINT8 *pa = (const UINT8 *)a;
  const UINT8 *pb = (const UINT8 *)b;
  UINTN        i;

  for (i = 0; i < sizeof (EFI_GUID); i++) {
    if (pa[i] != pb[i]) {
      return 0;
    }
  }

  return 1;
}
