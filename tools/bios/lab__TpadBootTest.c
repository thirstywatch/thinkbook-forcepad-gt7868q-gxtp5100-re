/**
  TpadBootTest.c —— Boot-time diagnostic application.  ASCII OUTPUT ONLY.

  为什么全英文：UEFI 固件控制台不带中文字库，中文会显示成白色方块（实测）。

  放在 U 盘的 \EFI\BOOT\BOOTX64.EFI，F12 选 U 盘即被固件加载执行（不需要 Shell）。
  做四件事：
    1. 打一屏 ASCII 大字（看到它 = 固件会执行 U 盘上的 EFI 程序）
    2. dump 三个 UEFI 变量，并把 TpadPatchState 翻译成一句人话
    3. 打印 Driver0000 指向的目标文件名
    4. 用【本程序自己被加载的设备】重写 Driver0000/DriverOrder，保证路径有效
  另外：8 秒内按任意键 = 清除 Driver#### 登记（救命用）。不做别的修改。

  编译：build.bat（MSVC，Subsystem 10）
**/

#include "miniefi.h"

/*
 * 用 /NODEFAULTLIB 链接，但 /O2 会把循环优化成 memcpy/memset 调用 ⇒ 自己提供。
 * MSVC 默认把它们当内部函数，故先 #pragma function 关掉；体内用 volatile 防止再被识别。
 */
#pragma function(memcpy, memset)

void *memcpy (void *dst, const void *src, unsigned long long n)
{
  volatile unsigned char  *d = (volatile unsigned char *)dst;
  const unsigned char     *s = (const unsigned char *)src;
  unsigned long long       i;

  for (i = 0; i < n; i++) {
    d[i] = s[i];
  }

  return dst;
}

void *memset (void *dst, int c, unsigned long long n)
{
  volatile unsigned char  *d = (volatile unsigned char *)dst;
  unsigned long long       i;

  for (i = 0; i < n; i++) {
    d[i] = (unsigned char)c;
  }

  return dst;
}

static CHAR16  mHex[] = L"0123456789ABCDEF";

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
    buf[i] = mHex[(V >> ((Digits - 1 - i) * 4)) & 0xF];
  }

  buf[Digits] = 0;
  Print (ST, buf);
}

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

static VOID DumpVar (EFI_SYSTEM_TABLE *ST, CHAR16 *Name)
{
  UINT8   data[256];
  UINTN   size;
  UINTN   i;

  Print (ST, L"  ");
  Print (ST, Name);
  Print (ST, L" : ");

  if (!ReadVar (ST, Name, data, sizeof (data), &size)) {
    Print (ST, L"NOT FOUND\r\n");
    return;
  }

  Print (ST, L"size=");
  PrintHex (ST, size, 4);
  Print (ST, L" data=");
  for (i = 0; (i < size) && (i < 128); i++) {
    if ((i % 16) == 0) {
      Print (ST, L"\r\n          ");
    }

    PrintHex (ST, data[i], 2);
    Print (ST, L" ");
  }

  Print (ST, L"\r\n");
}

/* 把 TpadPatchState 翻译成一句人话 */
static VOID DecodePatchState (EFI_SYSTEM_TABLE *ST)
{
  UINT8   b[64];
  UINTN   sz;
  UINT32  ofs;

  if (!ReadVar (ST, L"TpadPatchState", b, sizeof (b), &sz)) {
    Print (ST, L"  >>> driver DID NOT RUN this boot (no state variable)\r\n");
    return;
  }

  if ((sz < 8) || (b[0] != 0xA5)) {
    Print (ST, L"  >>> variable exists but format unexpected\r\n");
    return;
  }

  ofs = (UINT32)b[4] | ((UINT32)b[5] << 8) | ((UINT32)b[6] << 16) | ((UINT32)b[7] << 24);

  Print (ST, L"  >>> driver DID RUN this boot\r\n");
  Print (ST, L"  >>> DSDT found      : ");
  Print (ST, b[1] ? L"YES\r\n" : L"NO\r\n");
  Print (ST, L"  >>> patch hits      : ");
  PrintHex (ST, b[2], 2);
  Print (ST, L"\r\n");
  Print (ST, L"  >>> checksum fixed  : ");
  Print (ST, b[3] ? L"YES\r\n" : L"NO\r\n");
  Print (ST, L"  >>> hit offset      : 0x");
  PrintHex (ST, ofs, 6);
  Print (ST, L"\r\n");

  if (b[2] == 1) {
    Print (ST, L"  >>> RESULT: PATCH APPLIED OK (expect offset 0x0704AF)\r\n");
  } else if (b[1] == 1) {
    Print (ST, L"  >>> RESULT: DSDT found but pattern NOT found\r\n");
  } else {
    Print (ST, L"  >>> RESULT: DSDT not found - lookup problem\r\n");
  }
}

/* 打印 Driver0000 里记录的目标文件名 */
static VOID PrintDriverPath (EFI_SYSTEM_TABLE *ST)
{
  UINT8   buf[512];
  UINTN   sz;
  UINT16  pathLen;
  CHAR16 *desc;
  UINTN   descChars;
  UINT8  *p;
  UINTN   off;
  UINT8  *found;

  if (!ReadVar (ST, L"Driver0000", buf, sizeof (buf), &sz) || (sz < 8)) {
    Print (ST, L"  >>> cannot read Driver0000\r\n");
    return;
  }

  pathLen   = (UINT16)(buf[4] | (buf[5] << 8));
  desc      = (CHAR16 *)(buf + 6);
  descChars = 0;
  while ((((UINT8 *)(desc + descChars)) < (buf + sz)) && (desc[descChars] != 0)) {
    descChars++;
  }

  Print (ST, L"  >>> description   : ");
  Print (ST, desc);
  Print (ST, L"\r\n");
  Print (ST, L"  >>> pathlist len  : 0x");
  PrintHex (ST, pathLen, 4);
  Print (ST, L"\r\n");

  p     = buf + 6 + (descChars + 1) * 2;
  off   = 0;
  found = 0;

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

  Print (ST, L"  >>> target file   : ");
  if (found != 0) {
    Print (ST, (CHAR16 *)(found + 4));
  } else {
    Print (ST, L"(no file node found)");
  }

  Print (ST, L"\r\n");
}

/* ---- 用本程序自己被加载的设备重写 Driver0000 ---- */

static UINTN BuildPathTail (EFI_DEVICE_PATH_PROTOCOL *src, UINT8 *out, UINTN cap, CHAR16 *file)
{
  UINTN  off;
  UINTN  i;
  UINTN  n;

  off = 0;

  if (src != 0) {
    UINT8 *p = (UINT8 *)src;

    for (;;) {
      EFI_DEVICE_PATH_PROTOCOL *node = (EFI_DEVICE_PATH_PROTOCOL *)p;

      if ((node->Length < 4) || (node->Type == END_DEVICE_PATH_TYPE)) {
        break;
      }

      if ((node->Type == MEDIA_DEVICE_PATH) && (node->SubType == MEDIA_FILEPATH_DP)) {
        break;
      }

      if ((off + node->Length) > cap) {
        break;
      }

      for (i = 0; i < node->Length; i++) {
        out[off + i] = p[i];
      }

      off += node->Length;
      p   += node->Length;
    }
  }

  n = 0;
  while (file[n] != 0) {
    n++;
  }

  {
    UINTN                     nodeLen = 4 + (n + 1) * 2;
    EFI_DEVICE_PATH_PROTOCOL *node    = (EFI_DEVICE_PATH_PROTOCOL *)(out + off);
    UINT8                    *q       = (UINT8 *)(node + 1);

    node->Type    = MEDIA_DEVICE_PATH;
    node->SubType = MEDIA_FILEPATH_DP;
    node->Length  = (UINT16)nodeLen;

    for (i = 0; i <= n; i++) {
      q[i * 2]     = (UINT8)(file[i] & 0xFF);
      q[i * 2 + 1] = (UINT8)((file[i] >> 8) & 0xFF);
    }

    off += nodeLen;
  }

  out[off]     = END_DEVICE_PATH_TYPE;
  out[off + 1] = 0xFF;
  out[off + 2] = 4;
  out[off + 3] = 0;
  off         += 4;

  return off;
}

static VOID InstallDriverOption (EFI_SYSTEM_TABLE *ST, EFI_HANDLE ImageHandle)
{
  static const UINT32         attr = 0x00000001 | 0x00000002 | 0x00000004;
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
    Print (ST, L"  no HandleProtocol, skip\r\n");
    return;
  }

  st = ((EFI_STATUS (*)(EFI_HANDLE, EFI_GUID *, VOID **))ST->BootServices->HandleProtocol) (
         ImageHandle, (EFI_GUID *)&gEfiLoadedImageProtocolGuid, (VOID **)&li);
  if ((st != 0) || (li == 0)) {
    Print (ST, L"  no LoadedImage, skip\r\n");
    return;
  }

  pathLen = BuildPathTail (li->FilePath, path, sizeof (path), L"\\EFI\\Tpad\\TpadAcpiProbe.efi");

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

  st = ST->RuntimeServices->SetVariable (L"Driver0000", (EFI_GUID *)&gEfiGlobalVariableGuid,
                                         attr, 6 + descLen + pathLen, opt);
  Print (ST, L"  rewrite Driver0000  : ");
  Print (ST, (st == 0) ? L"OK\r\n" : L"FAIL\r\n");

  order = 0;
  st    = ST->RuntimeServices->SetVariable (L"DriverOrder", (EFI_GUID *)&gEfiGlobalVariableGuid,
                                            attr, 2, &order);
  Print (ST, L"  rewrite DriverOrder : ");
  Print (ST, (st == 0) ? L"OK\r\n" : L"FAIL\r\n");
}

/* ---- 救命：清除登记 ---- */

static CHAR16 *mKillNames[] = {
  L"Driver0000", L"Driver0001", L"DriverOrder", L"TpadPatchState"
};

static VOID ClearRegistrations (EFI_SYSTEM_TABLE *ST)
{
  UINTN  i;

  if ((ST->RuntimeServices == 0) || (ST->RuntimeServices->SetVariable == 0)) {
    Print (ST, L"  SetVariable unavailable\r\n");
    return;
  }

  for (i = 0; i < (sizeof (mKillNames) / sizeof (mKillNames[0])); i++) {
    ST->RuntimeServices->SetVariable (mKillNames[i], (EFI_GUID *)&gEfiGlobalVariableGuid,
                                      0, 0, 0);
    Print (ST, L"  cleared: ");
    Print (ST, mKillNames[i]);
    Print (ST, L"\r\n");
  }
}

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

  if (ST->ConIn->Reset != 0) {
    ((EFI_STATUS (*)(EFI_SIMPLE_TEXT_INPUT_PROTOCOL *, UINT8))ST->ConIn->Reset) (ST->ConIn, 0);
  }

  for (i = 0; i < (ms / 100); i++) {
    if (ST->ConIn->ReadKeyStroke (ST->ConIn, &key) == 0) {
      return 1;
    }

    ST->BootServices->Stall (100000);
  }

  return 0;
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
    SystemTable->ConOut->SetAttribute (SystemTable->ConOut, 0x17);
  }

  Print (SystemTable, L"\r\n");
  Print (SystemTable, L"############### TpadBootTest (ASCII) ################\r\n");
  Print (SystemTable, L"##                                                  ##\r\n");
  Print (SystemTable, L"##  If you can read this, the firmware DOES execute ##\r\n");
  Print (SystemTable, L"##  EFI programs from this USB stick.               ##\r\n");
  Print (SystemTable, L"##                                                  ##\r\n");
  Print (SystemTable, L"######################################################\r\n");
  Print (SystemTable, L"\r\n");

  Print (SystemTable, L"[1] UEFI variables:\r\n");
  DumpVar (SystemTable, L"DriverOrder");
  DumpVar (SystemTable, L"Driver0000");
  DumpVar (SystemTable, L"TpadPatchState");
  Print (SystemTable, L"\r\n");

  Print (SystemTable, L"[2] TpadPatchState decoded (byte0=0xA5 means driver ran):\r\n");
  DecodePatchState (SystemTable);
  Print (SystemTable, L"\r\n");

  Print (SystemTable, L"[3] Where Driver0000 points to:\r\n");
  PrintDriverPath (SystemTable);
  Print (SystemTable, L"\r\n");

  Print (SystemTable, L"[4] Rewriting registration using THIS device path:\r\n");
  if ((SystemTable->RuntimeServices != 0) &&
      (SystemTable->RuntimeServices->SetVariable != 0)) {
    InstallDriverOption (SystemTable, ImageHandle);
  } else {
    Print (SystemTable, L"  RuntimeServices unavailable\r\n");
  }

  Print (SystemTable, L"\r\n");
  Print (SystemTable, L"##### PRESS ANY KEY within 8s = CLEAR Driver#### #####\r\n");
  Print (SystemTable, L"##### (no key = change nothing, just continue)   #####\r\n");
  Print (SystemTable, L"\r\n");

  if (WaitKeyOrTimeout (SystemTable, 8000)) {
    Print (SystemTable, L"key detected -> clearing:\r\n");
    ClearRegistrations (SystemTable);
    Print (SystemTable, L"done. reboot to return to unregistered state.\r\n");
  } else {
    Print (SystemTable, L"no key -> nothing changed, continuing boot.\r\n");
  }

  if (SystemTable->ConOut != 0) {
    SystemTable->ConOut->SetAttribute (SystemTable->ConOut, 0x07);
  }

  if ((SystemTable->BootServices != 0) && (SystemTable->BootServices->Stall != 0)) {
    SystemTable->BootServices->Stall (4000000);
  }

  return EFI_SUCCESS;
}
