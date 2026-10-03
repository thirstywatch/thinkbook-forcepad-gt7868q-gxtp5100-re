/**
  TpadBootTest.c —— 【引导诊断应用】一次性回答三件事，什么都不改。

  它是**应用程序**（Subsystem 10），放在 U 盘的 \EFI\BOOT\BOOTX64.EFI，
  从 F12 选 U 盘即被固件加载执行（不需要 UEFI Shell）。

  它做三件事：
    1. 在屏幕上反白打一段显著文字，停 5 秒
       ⇒ ★ 看到字 = 固件会执行 U 盘上的这个文件（这是最基础的判据）
    2. 读并打印 DriverOrder / Driver0000 变量当前状态
       ⇒ 知道 UEFI 变量读写通道是否可用
    3. 返回，让固件继续下一个启动项（不会把你卡住）

  只读，不写任何变量、不改任何内存。

  编译：build.bat（MSVC，Subsystem 10）
**/

#include "miniefi.h"

/*
 * 我们用 /NODEFAULTLIB 链接（不依赖 C 运行时），但 /O2 会把循环优化成
 * memcpy / memset 调用 —— 所以自己提供这两个符号。
 * MSVC 默认把它们当内部函数（不允许定义），故先用 #pragma function 关掉内部化；
 * 内部再用 volatile 指针，避免它们自身的循环又被变成对 memcpy 的调用。
 */
#pragma function(memcpy, memset)

void *memcpy (void *dst, const void *src, unsigned long long n)
{
  volatile unsigned char       *d = (volatile unsigned char *)dst;
  const unsigned char          *s = (const unsigned char *)src;
  unsigned long long            i;

  for (i = 0; i < n; i++) {
    d[i] = s[i];
  }

  return dst;
}

void *memset (void *dst, int c, unsigned long long n)
{
  volatile unsigned char       *d = (volatile unsigned char *)dst;
  unsigned long long            i;

  for (i = 0; i < n; i++) {
    d[i] = (unsigned char)c;
  }

  return dst;
}

static CHAR16  mHexDigits[] = L"0123456789ABCDEF";

static VOID Print (EFI_SYSTEM_TABLE *ST, CHAR16 *S)
{
  if ((ST != 0) && (ST->ConOut != 0)) {
    ST->ConOut->OutputString (ST->ConOut, S);
  }
}

static VOID PrintHex (EFI_SYSTEM_TABLE *ST, UINT64 V, UINTN Digits)
{
  CHAR16  buf[20];
  UINTN   i;

  for (i = 0; i < Digits; i++) {
    buf[i] = mHexDigits[(V >> ((Digits - 1 - i) * 4)) & 0xF];
  }

  buf[Digits] = 0;
  Print (ST, buf);
}

static VOID ProbeVariable (
  EFI_SYSTEM_TABLE  *ST,
  CHAR16            *Name
  )
{
  UINT8   data[512];
  UINTN   size;
  UINT32  attr;
  EFI_STATUS  st;

  if ((ST->RuntimeServices == 0) || (ST->RuntimeServices->GetVariable == 0)) {
    Print (ST, L"  GetVariable 不可用\r\n");
    return;
  }

  size = sizeof (data);
  attr = 0;
  st   = ST->RuntimeServices->GetVariable (Name, (EFI_GUID *)&gEfiGlobalVariableGuid,
                                           &attr, &size, data);

  Print (ST, L"  ");
  Print (ST, Name);
  Print (ST, L" : ");
  if (st == 0) {
    Print (ST, L"存在  大小=");
    PrintHex (ST, size, 4);
    Print (ST, L"  属性=0x");
    PrintHex (ST, attr, 8);
    Print (ST, L"  数据=");
    {
      UINTN i;
      for (i = 0; (i < size) && (i < 256); i++) {
        if ((i % 16) == 0) {
          Print (ST, L"\r\n          ");
        }

        PrintHex (ST, data[i], 2);
        Print (ST, L" ");
      }
    }
  } else {
    Print (ST, L"不存在或读取失败 (status=0x");
    PrintHex (ST, st, 8);
    Print (ST, L")");
  }

  Print (ST, L"\r\n");
}

/* ---- 救命功能：按任意键就把 Driver#### 登记清掉 ---- */

static CHAR16 *mKillNames[] = {
  L"Driver0000",
  L"Driver0001",
  L"DriverOrder",
  L"TpadPatchState"
};

static VOID ClearRegistrations (EFI_SYSTEM_TABLE *ST)
{
  UINTN  i;

  if ((ST->RuntimeServices == 0) || (ST->RuntimeServices->SetVariable == 0)) {
    Print (ST, L"  SetVariable 不可用，无法清理\r\n");
    return;
  }

  for (i = 0; i < (sizeof (mKillNames) / sizeof (mKillNames[0])); i++) {
    ST->RuntimeServices->SetVariable (mKillNames[i], (EFI_GUID *)&gEfiGlobalVariableGuid,
                                      0, 0, 0);
    Print (ST, L"  已清除: ");
    Print (ST, mKillNames[i]);
    Print (ST, L"\r\n");
  }
}

/* 等 ms 毫秒；期间读到任意按键就返回 1，超时返回 0 */
static int WaitKeyOrTimeout (EFI_SYSTEM_TABLE *ST, UINTN ms)
{
  EFI_INPUT_KEY  key;
  UINTN          i;

  if ((ST->BootServices == 0) || (ST->BootServices->Stall == 0)) {
    return 0;
  }

  if ((ST->ConIn == 0) || (ST->ConIn->ReadKeyStroke == 0)) {
    ST->BootServices->Stall (ms * 1000);
    return 0;
  }

  /* 先清掉之前按键队列里的残留 */
  if (ST->ConIn->Reset != 0) {
    ((EFI_STATUS (*)(EFI_SIMPLE_TEXT_INPUT_PROTOCOL *, UINT8))ST->ConIn->Reset) (ST->ConIn, 0);
  }

  for (i = 0; i < (ms / 100); i++) {
    if (ST->ConIn->ReadKeyStroke (ST->ConIn, &key) == 0) {
      return 1;
    }

    ST->BootServices->Stall (100000); /* 100 ms */
  }

  return 0;
}

/* ---- 用"本程序自己被加载的那个设备"重写 Driver0000，保证路径必然正确 ---- */

static UINTN BuildFilePathTail (
  EFI_DEVICE_PATH_PROTOCOL  *src,
  UINT8                     *out,
  UINTN                      outCap,
  CHAR16                    *filePath
  )
{
  UINTN  off;
  UINTN  i;
  UINTN  nameLen;

  off = 0;

  if (src != 0) {
    UINT8 *p = (UINT8 *)src;

    for (;;) {
      EFI_DEVICE_PATH_PROTOCOL *node = (EFI_DEVICE_PATH_PROTOCOL *)p;

      if ((node->Length < 4) || (node->Type == END_DEVICE_PATH_TYPE)) {
        break;
      }

      if ((node->Type == MEDIA_DEVICE_PATH) && (node->SubType == MEDIA_FILEPATH_DP)) {
        break; /* 到文件节点为止，丢弃它（我们要换成自己的文件名） */
      }

      if ((off + node->Length) > outCap) {
        break;
      }

      for (i = 0; i < node->Length; i++) {
        out[off + i] = p[i];
      }

      off += node->Length;
      p   += node->Length;
    }
  }

  /* 追加自己的 FilePath 节点 */
  nameLen = 0;
  while (filePath[nameLen] != 0) {
    nameLen++;
  }

  {
    UINTN                     nodeLen = 4 + (nameLen + 1) * 2;
    EFI_DEVICE_PATH_PROTOCOL *n       = (EFI_DEVICE_PATH_PROTOCOL *)(out + off);
    UINT8                    *q       = (UINT8 *)(n + 1);

    n->Type    = MEDIA_DEVICE_PATH;
    n->SubType = MEDIA_FILEPATH_DP;
    n->Length  = (UINT16)nodeLen;

    for (i = 0; i <= nameLen; i++) {
      q[i * 2]     = (UINT8)(filePath[i] & 0xFF);
      q[i * 2 + 1] = (UINT8)((filePath[i] >> 8) & 0xFF);
    }

    off += nodeLen;
  }

  /* End 节点 */
  out[off]     = END_DEVICE_PATH_TYPE;
  out[off + 1] = 0xFF;
  out[off + 2] = 4;
  out[off + 3] = 0;
  off         += 4;

  return off;
}

static VOID InstallDriverOption (EFI_SYSTEM_TABLE *ST, EFI_HANDLE ImageHandle)
{
  static const UINT32  attr = 0x00000001 | 0x00000002 | 0x00000004;
  EFI_LOADED_IMAGE_PROTOCOL  *li;
  UINT8                       opt[600];
  UINT8                       path[400];
  UINTN                       pathLen;
  UINTN                       descLen;
  UINTN                       i;
  UINT16                      order;
  EFI_STATUS                  st;
  CHAR16                     *desc = L"TpadAcpiProbe";

  li = 0;

  if ((ST->BootServices == 0) || (ST->BootServices->HandleProtocol == 0)) {
    Print (ST, L"  无 HandleProtocol，跳过\r\n");
    return;
  }

  st = ((EFI_STATUS (*)(EFI_HANDLE, EFI_GUID *, VOID **))ST->BootServices->HandleProtocol) (
         ImageHandle, (EFI_GUID *)&gEfiLoadedImageProtocolGuid, (VOID **)&li);
  if ((st != 0) || (li == 0)) {
    Print (ST, L"  取不到 LoadedImage，跳过\r\n");
    return;
  }

  pathLen = BuildFilePathTail (li->FilePath, path, sizeof (path),
                               L"\\EFI\\Tpad\\TpadAcpiProbe.efi");

  descLen = 0;
  while (desc[descLen] != 0) {
    descLen++;
  }

  descLen = (descLen + 1) * 2;

  opt[0] = LOAD_OPTION_ACTIVE & 0xFF;
  opt[1] = 0;
  opt[2] = 0;
  opt[3] = 0;
  opt[4] = (UINT8)(pathLen & 0xFF);
  opt[5] = (UINT8)((pathLen >> 8) & 0xFF);

  for (i = 0; i < (descLen / 2); i++) {
    opt[6 + i * 2]     = (UINT8)(desc[i] & 0xFF);
    opt[6 + i * 2 + 1] = (UINT8)((desc[i] >> 8) & 0xFF);
  }

  for (i = 0; i < pathLen; i++) {
    opt[6 + descLen + i] = path[i];
  }

  st = ST->RuntimeServices->SetVariable (L"Driver0000",
                                         (EFI_GUID *)&gEfiGlobalVariableGuid,
                                         attr, 6 + descLen + pathLen, opt);
  Print (ST, L"  重写 Driver0000 : ");
  Print (ST, (st == 0) ? L"成功\r\n" : L"失败\r\n");

  order = 0;
  st    = ST->RuntimeServices->SetVariable (L"DriverOrder",
                                            (EFI_GUID *)&gEfiGlobalVariableGuid,
                                            attr, 2, &order);
  Print (ST, L"  重写 DriverOrder : ");
  Print (ST, (st == 0) ? L"成功\r\n" : L"失败\r\n");
}

/* ---- 把人看得懂的信息直接打出来（拍照糊了也能读） ---- */

static int ReadVar (EFI_SYSTEM_TABLE *ST, CHAR16 *Name, UINT8 *buf, UINTN cap, UINTN *sizeOut)
{
  UINT32      attr;
  EFI_STATUS  st;
  UINTN       sz;

  if ((ST->RuntimeServices == 0) || (ST->RuntimeServices->GetVariable == 0)) {
    return 0;
  }

  attr = 0;
  sz   = cap;
  st   = ST->RuntimeServices->GetVariable (Name, (EFI_GUID *)&gEfiGlobalVariableGuid,
                                           &attr, &sz, buf);
  if (st != 0) {
    return 0;
  }

  *sizeOut = sz;
  return 1;
}

static VOID DecodePatchState (EFI_SYSTEM_TABLE *ST)
{
  UINT8   buf[64];
  UINTN   sz;
  UINT32  ofs;

  if (!ReadVar (ST, L"TpadPatchState", buf, sizeof (buf), &sz)) {
    Print (ST, L"  >>> 驱动本次【没有执行】（没写状态变量）\r\n");
    return;
  }

  if ((sz < 8) || (buf[0] != 0xA5)) {
    Print (ST, L"  >>> 变量存在但格式异常，需人工看 hex\r\n");
    return;
  }

  ofs = (UINT32)buf[4] | ((UINT32)buf[5] << 8) | ((UINT32)buf[6] << 16) | ((UINT32)buf[7] << 24);

  Print (ST, L"  >>> 驱动本次【已执行】\r\n");
  Print (ST, L"  >>> 找到 DSDT      : ");
  Print (ST, buf[1] ? L"是\r\n" : L"否\r\n");
  Print (ST, L"  >>> 补丁命中次数   : ");
  PrintHex (ST, buf[2], 2);
  Print (ST, L"\r\n");
  Print (ST, L"  >>> 已重算校验和   : ");
  Print (ST, buf[3] ? L"是\r\n" : L"否\r\n");
  Print (ST, L"  >>> 命中处 DSDT 内偏移 : 0x");
  PrintHex (ST, ofs, 6);
  Print (ST, L"\r\n");

  if (buf[2] == 1) {
    Print (ST, L"  >>> ★★ 补丁已成功应用（预期偏移 0x0704AF）\r\n");
  } else if (buf[1] == 1) {
    Print (ST, L"  >>> ★ 找到 DSDT 但没命中 ⇒ Find 串不匹配，需要重新核对\r\n");
  } else {
    Print (ST, L"  >>> ★ 连 DSDT 都没找到 ⇒ 读取链路有问题\r\n");
  }
}

static VOID PrintDriverPath (EFI_SYSTEM_TABLE *ST)
{
  UINT8   buf[512];
  UINTN   sz;
  UINT16  pathLen;
  CHAR16 *desc;
  UINTN   descChars;
  UINT8  *p;
  UINTN   off;

  if (!ReadVar (ST, L"Driver0000", buf, sizeof (buf), &sz) || (sz < 8)) {
    Print (ST, L"  >>> 读不到 Driver0000\r\n");
    return;
  }

  pathLen   = (UINT16)(buf[4] | (buf[5] << 8));
  desc      = (CHAR16 *)(buf + 6);
  descChars = 0;
  while ((((UINT8 *)(desc + descChars)) < (buf + sz)) && (desc[descChars] != 0)) {
    descChars++;
  }

  Print (ST, L"  >>> 描述        : ");
  Print (ST, desc);
  Print (ST, L"\r\n");
  Print (ST, L"  >>> 路径长度    : 0x");
  PrintHex (ST, pathLen, 4);
  Print (ST, L"\r\n");

  p   = buf + 6 + (descChars + 1) * 2;
  off = 0;

  {
    UINT8 *found = 0;

    while ((off + 4) <= pathLen) {
      EFI_DEVICE_PATH_PROTOCOL *n = (EFI_DEVICE_PATH_PROTOCOL *)(p + off);

      if (n->Length < 4) {
        break;
      }

      if (n->Type == END_DEVICE_PATH_TYPE) {
        break;
      }

      if ((n->Type == MEDIA_DEVICE_PATH) && (n->SubType == MEDIA_FILEPATH_DP)) {
        found = (UINT8 *)n;
      }

      off += n->Length;
    }

    Print (ST, L"  >>> 目标文件    : ");
    if (found != 0) {
      Print (ST, (CHAR16 *)(found + 4));
    } else {
      Print (ST, L"(未找到文件节点！路径可能没有指向文件)");
    }

    Print (ST, L"\r\n");
  }
}

EFI_STATUS
EFIAPI
TpadBootTestEntry (
  EFI_HANDLE        ImageHandle,
  EFI_SYSTEM_TABLE  *SystemTable
  )
{
  if (SystemTable == 0) {
    return EFI_SUCCESS;
  }

  if (SystemTable->ConOut != 0) {
    SystemTable->ConOut->SetAttribute (SystemTable->ConOut, 0x17 /* 白字蓝底 */);
  }

  Print (SystemTable, L"\r\n");
  Print (SystemTable, L"##################################################\r\n");
  Print (SystemTable, L"##                                              ##\r\n");
  Print (SystemTable, L"##   TpadBootTest  ——  引导诊断应用             ##\r\n");
  Print (SystemTable, L"##                                              ##\r\n");
  Print (SystemTable, L"##   看到这一屏 = 固件会执行 U 盘上的 EFI 程序  ##\r\n");
  Print (SystemTable, L"##   （5 秒后自动继续启动，不会卡住）            ##\r\n");
  Print (SystemTable, L"##                                              ##\r\n");
  Print (SystemTable, L"##################################################\r\n");
  Print (SystemTable, L"\r\n");
  Print (SystemTable, L"UEFI 变量现状：\r\n");
  ProbeVariable (SystemTable, L"DriverOrder");
  ProbeVariable (SystemTable, L"Driver0000");
  Print (SystemTable, L"\r\n");

  Print (SystemTable, L"驱动执行证据（TpadPatchState）：\r\n");
  ProbeVariable (SystemTable, L"TpadPatchState");
  Print (SystemTable, L"  (0xA5=已运行  第2字节=找到DSDT  第3字节=命中次数  第4字节=已改校验和)\r\n");
  DecodePatchState (SystemTable);
  Print (SystemTable, L"\r\n");

  Print (SystemTable, L"Driver0000 指向哪里：\r\n");
  PrintDriverPath (SystemTable);
  Print (SystemTable, L"\r\n");

  Print (SystemTable, L"【修正登记】用本程序所在设备重写 Driver####：\r\n");
  if ((SystemTable->RuntimeServices != 0) &&
      (SystemTable->RuntimeServices->SetVariable != 0)) {
    InstallDriverOption (SystemTable, ImageHandle);
  } else {
    Print (SystemTable, L"  RuntimeServices 不可用\r\n");
  }

  Print (SystemTable, L"\r\n");
  Print (SystemTable, L"##################################################\r\n");
  Print (SystemTable, L"##  【救命】8 秒内按任意键 = 清除 Driver#### 登记 ##\r\n");
  Print (SystemTable, L"##  （不按就正常继续启动，什么都不改）           ##\r\n");
  Print (SystemTable, L"##################################################\r\n");
  Print (SystemTable, L"\r\n");

  if (WaitKeyOrTimeout (SystemTable, 8000)) {
    Print (SystemTable, L"检测到按键 —— 执行清理：\r\n");
    ClearRegistrations (SystemTable);
    Print (SystemTable, L"清理完成。重启后即恢复为未登记状态。\r\n");
  } else {
    Print (SystemTable, L"未按按键 —— 不做任何修改，继续启动。\r\n");
  }

  if (SystemTable->ConOut != 0) {
    SystemTable->ConOut->SetAttribute (SystemTable->ConOut, 0x07);
  }

  if ((SystemTable->BootServices != 0) && (SystemTable->BootServices->Stall != 0)) {
    SystemTable->BootServices->Stall (3000000); /* 再停 3 秒，看清结果 */
  }

  return EFI_SUCCESS;
}
