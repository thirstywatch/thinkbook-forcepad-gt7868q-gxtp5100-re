/**
  TpadInstall.c —— Install the ACPI patch driver onto the ESP.  ASCII OUTPUT ONLY.

  为什么要它
  ----------
  把驱动放在 U 盘上、再用 Driver#### 注册，实测【固件不会执行它】——
  最可能的原因是 BDS 处理 DriverOrder 的时机太早，U 盘类设备路径解析不了。
  内建硬盘的 ESP 是标准可解析路径，所以要：把驱动【复制到 ESP】，再把登记指向 ESP。

  本程序（放在 U 盘 \EFI\BOOT\BOOTX64.EFI，F12 选 U 盘即运行）做：
    1. dump 现有 UEFI 变量
    2. 从【本程序所在设备】读 \EFI\Tpad\TpadAcpiProbe.efi
    3. 找到 ESP（含 \EFI\Microsoft\Boot\bootmgfw.efi 的那个卷），把驱动写到 ESP 的 \EFI\Tpad\
    4. 用 ESP 的卷设备路径 + 文件节点，重写 Driver0000 / DriverOrder
    5. 8 秒内按任意键 = 清除登记（救命）

  编译：build.bat（MSVC，Subsystem 10）
**/

#include "miniefi.h"

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
static UINT8   gBuf[40960];      /* 读驱动用 */
static UINT8   gPath[512];       /* 拼设备路径用 */
static EFI_HANDLE  gHandles[128];

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
  UINT32  attr;
  UINTN   sz;

  if ((ST->RuntimeServices == 0) || (ST->RuntimeServices->GetVariable == 0)) {
    return 0;
  }

  attr = 0;
  sz   = cap;
  if (ST->RuntimeServices->GetVariable (Name, (EFI_GUID *)&gEfiGlobalVariableGuid,
                                        &attr, &sz, buf) != 0) {
    return 0;
  }

  *sizeOut = sz;
  return 1;
}

static VOID DumpVar (EFI_SYSTEM_TABLE *ST, CHAR16 *Name)
{
  UINT8  d[256];
  UINTN  sz;
  UINTN  i;

  Print (ST, L"  ");
  Print (ST, Name);
  Print (ST, L" : ");
  if (!ReadVar (ST, Name, d, sizeof (d), &sz)) {
    Print (ST, L"NOT FOUND\r\n");
    return;
  }

  Print (ST, L"size=");
  PrintHex (ST, sz, 4);
  Print (ST, L"  ");
  for (i = 0; (i < sz) && (i < 64); i++) {
    PrintHex (ST, d[i], 2);
    Print (ST, L" ");
  }

  Print (ST, L"\r\n");
}

/* ---- 文件读写 ---- */

static int ReadWholeFile (EFI_FILE_PROTOCOL *Dir, CHAR16 *Path, UINT8 *buf, UINTN cap, UINTN *sizeOut)
{
  EFI_FILE_PROTOCOL  *F;
  UINTN               sz;

  if (Dir->Open (Dir, &F, Path, EFI_FILE_MODE_READ, 0) != 0) {
    return 0;
  }

  sz = cap;
  if (F->Read (F, &sz, buf) != 0) {
    F->Close (F);
    return 0;
  }

  F->Close (F);
  *sizeOut = sz;
  return 1;
}

static int WriteWholeFile (EFI_FILE_PROTOCOL *Dir, CHAR16 *Path, UINT8 *buf, UINTN size)
{
  EFI_FILE_PROTOCOL  *F;
  UINTN               sz;

  /* 先尝试删掉旧的，避免"新文件比旧的短"时残留尾巴 */
  if (Dir->Open (Dir, &F, Path, EFI_FILE_MODE_READ | EFI_FILE_MODE_WRITE, 0) == 0) {
    F->Delete (F);   /* Delete 会关闭句柄 */
  }

  if (Dir->Open (Dir, &F, Path, EFI_FILE_MODE_READ | EFI_FILE_MODE_WRITE | EFI_FILE_MODE_CREATE, 0) != 0) {
    return 0;
  }

  F->SetPosition (F, 0);
  sz = size;
  if (F->Write (F, &sz, buf) != 0) {
    F->Close (F);
    return 0;
  }

  F->Flush (F);
  F->Close (F);
  return 1;
}

static EFI_FILE_PROTOCOL *OpenSubdir (EFI_FILE_PROTOCOL *Root, CHAR16 *Dir, int create)
{
  EFI_FILE_PROTOCOL  *D;
  UINT64              mode;

  mode = EFI_FILE_MODE_READ | EFI_FILE_MODE_WRITE;

  if (Root->Open (Root, &D, Dir, mode, 0) == 0) {
    return D;   /* 已存在 */
  }

  if (!create) {
    return 0;
  }

  mode |= EFI_FILE_MODE_CREATE;
  if (Root->Open (Root, &D, Dir, mode, EFI_FILE_DIRECTORY) != 0) {
    return 0;
  }

  return D;
}

/* ---- 找 ESP：枚举所有 SimpleFileSystem 卷，含 bootmgfw.efi 的那个就是 ---- */

static int ProbeEsp (EFI_SYSTEM_TABLE *ST, EFI_HANDLE h, EFI_FILE_PROTOCOL **rootOut,
                     EFI_DEVICE_PATH_PROTOCOL **dpOut)
{
  EFI_SIMPLE_FILE_SYSTEM_PROTOCOL  *fs;
  EFI_DEVICE_PATH_PROTOCOL         *dp;
  EFI_FILE_PROTOCOL                *root;
  EFI_FILE_PROTOCOL                *probe;

  fs = 0;
  dp = 0;

  if (((EFI_STATUS (*)(EFI_HANDLE, EFI_GUID *, VOID **))ST->BootServices->HandleProtocol) (
        h, (EFI_GUID *)&gEfiSimpleFileSystemProtocolGuid, (VOID **)&fs) != 0) {
    return 0;
  }

  if (((EFI_STATUS (*)(EFI_HANDLE, EFI_GUID *, VOID **))ST->BootServices->HandleProtocol) (
        h, (EFI_GUID *)&gEfiDevicePathProtocolGuid, (VOID **)&dp) != 0) {
    return 0;
  }

  root = 0;
  if (fs->OpenVolume (fs, &root) != 0) {
    return 0;
  }

  /* 有 \EFI\Microsoft\Boot\bootmgfw.efi 的卷 = ESP */
  if (root->Open (root, &probe, L"\\EFI\\Microsoft\\Boot\\bootmgfw.efi", EFI_FILE_MODE_READ, 0) != 0) {
    root->Close (root);
    return 0;
  }

  probe->Close (probe);
  *rootOut = root;
  *dpOut   = dp;
  return 1;
}

/* ---- 拼设备路径：卷路径 + 文件节点 ---- */

static UINTN BuildPath (EFI_DEVICE_PATH_PROTOCOL *vol, UINT8 *out, UINTN cap, CHAR16 *file)
{
  UINTN  off;
  UINTN  i;
  UINTN  n;

  off = 0;

  if (vol != 0) {
    UINT8 *p = (UINT8 *)vol;

    for (;;) {
      EFI_DEVICE_PATH_PROTOCOL *node = (EFI_DEVICE_PATH_PROTOCOL *)p;

      if ((node->Length < 4) || (node->Type == END_DEVICE_PATH_TYPE)) {
        break;
      }

      /* 卷路径一般不含文件节点；万一有，丢弃 */
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

static int SetDriverOption (EFI_SYSTEM_TABLE *ST, UINT8 *path, UINTN pathLen)
{
  static const UINT32  attr = 0x00000001 | 0x00000002 | 0x00000004;
  UINT8                opt[600];
  UINTN                descLen;
  UINTN                i;
  UINT16               order;
  CHAR16              *desc = L"TpadAcpiProbe";

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

  if (ST->RuntimeServices->SetVariable (L"Driver0000", (EFI_GUID *)&gEfiGlobalVariableGuid,
                                        attr, 6 + descLen + pathLen, opt) != 0) {
    return 0;
  }

  order = 0;
  return (ST->RuntimeServices->SetVariable (L"DriverOrder", (EFI_GUID *)&gEfiGlobalVariableGuid,
                                            attr, 2, &order) == 0);
}

/* 回读 Driver0000，打印它到底指向哪个文件（用于确认登记写对了） */
static VOID PrintDriverTarget (EFI_SYSTEM_TABLE *ST)
{
  UINT8   buf[512];
  UINTN   sz;
  UINT16  pathLen;
  UINTN   descChars;
  UINT8  *p;
  UINTN   off;
  UINT8  *found;
  CHAR16 *desc;

  if (!ReadVar (ST, L"Driver0000", buf, sizeof (buf), &sz) || (sz < 8)) {
    Print (ST, L"  Driver0000 unreadable\r\n");
    return;
  }

  Print (ST, L"  total size  : 0x");
  PrintHex (ST, sz, 4);
  Print (ST, L"\r\n  Attributes  : 0x");
  PrintHex (ST, (UINT32)buf[0] | ((UINT32)buf[1] << 8) | ((UINT32)buf[2] << 16) | ((UINT32)buf[3] << 24), 8);
  Print (ST, L"\r\n  pathListLen : 0x");
  pathLen = (UINT16)(buf[4] | (buf[5] << 8));
  PrintHex (ST, pathLen, 4);
  Print (ST, L"\r\n");

  desc      = (CHAR16 *)(buf + 6);
  descChars = 0;
  while ((((UINT8 *)(desc + descChars)) < (buf + sz)) && (desc[descChars] != 0)) {
    descChars++;
  }

  Print (ST, L"  description : ");
  Print (ST, desc);
  Print (ST, L"\r\n");

  p     = buf + 6 + (descChars + 1) * 2;
  off   = 0;
  found = 0;

  while ((off + 4) <= pathLen) {
    EFI_DEVICE_PATH_PROTOCOL *n = (EFI_DEVICE_PATH_PROTOCOL *)(p + off);

    if ((n->Length < 4) || (n->Type == END_DEVICE_PATH_TYPE)) {
      break;
    }

    if ((n->Type == MEDIA_DEVICE_PATH) && (n->SubType == MEDIA_FILEPATH_DP)) {
      found = (UINT8 *)n;
    }

    off += n->Length;
  }

  Print (ST, L"  target file : ");
  if (found != 0) {
    Print (ST, (CHAR16 *)(found + 4));
  } else {
    Print (ST, L"(NO FILE NODE)");
  }

  Print (ST, L"\r\n");

  if ((pathLen + 6 + (descChars + 1) * 2) == sz) {
    Print (ST, L"  structure   : CONSISTENT\r\n");
  } else {
    Print (ST, L"  structure   : *** INCONSISTENT (pathLen+header+desc != size) ***\r\n");
  }
}

/* ---- 救命 ---- */

static CHAR16 *mKillNames[] = {
  L"Driver0000", L"Driver0001", L"DriverOrder", L"TpadPatchState"
};

static VOID ClearRegistrations (EFI_SYSTEM_TABLE *ST)
{
  UINTN  i;

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

/* ---- 主流程 ---- */

EFI_STATUS
EFIAPI
TpadInstallEntry (
  EFI_HANDLE        ImageHandle,
  EFI_SYSTEM_TABLE  *SystemTable
  )
{
  EFI_LOADED_IMAGE_PROTOCOL        *li;
  EFI_SIMPLE_FILE_SYSTEM_PROTOCOL  *usbFs;
  EFI_FILE_PROTOCOL                *usbRoot;
  EFI_FILE_PROTOCOL                *usbDir;
  EFI_FILE_PROTOCOL                *espRoot;
  EFI_FILE_PROTOCOL                *espDir;
  EFI_DEVICE_PATH_PROTOCOL         *espDp;
  EFI_HANDLE                        espHandle;
  UINTN                             nHandles;
  UINTN                             bufSize;
  UINTN                             drvSize;
  UINTN                             i;
  UINTN                             pathLen;
  int                               got;

  if (SystemTable == 0) {
    return EFI_SUCCESS;
  }

  if (SystemTable->ConOut != 0) {
    SystemTable->ConOut->SetAttribute (SystemTable->ConOut, 0x17);
  }

  Print (SystemTable, L"\r\n");
  Print (SystemTable, L"########## TpadInstall : put driver on ESP ##########\r\n");
  Print (SystemTable, L"\r\n");

  Print (SystemTable, L"[1] current variables:\r\n");
  DumpVar (SystemTable, L"DriverOrder");
  DumpVar (SystemTable, L"Driver0000");
  DumpVar (SystemTable, L"TpadPatchState");
  Print (SystemTable, L"\r\n");

  /* 取自己的 LoadedImage -> 所在卷 */
  li = 0;
  if (((EFI_STATUS (*)(EFI_HANDLE, EFI_GUID *, VOID **))SystemTable->BootServices->HandleProtocol) (
        ImageHandle, (EFI_GUID *)&gEfiLoadedImageProtocolGuid, (VOID **)&li) != 0 || li == 0) {
    Print (SystemTable, L"FATAL: no LoadedImage\r\n");
    return EFI_SUCCESS;
  }

  usbFs = 0;
  if (((EFI_STATUS (*)(EFI_HANDLE, EFI_GUID *, VOID **))SystemTable->BootServices->HandleProtocol) (
        li->DeviceHandle, (EFI_GUID *)&gEfiSimpleFileSystemProtocolGuid, (VOID **)&usbFs) != 0) {
    Print (SystemTable, L"FATAL: cannot open own volume\r\n");
    return EFI_SUCCESS;
  }

  usbRoot = 0;
  if (usbFs->OpenVolume (usbFs, &usbRoot) != 0) {
    Print (SystemTable, L"FATAL: OpenVolume failed\r\n");
    return EFI_SUCCESS;
  }

  /* 读 U 盘上的驱动 */
  Print (SystemTable, L"[2] reading driver from this USB:\r\n");
  usbDir = OpenSubdir (usbRoot, L"\\EFI\\Tpad", 0);
  if (usbDir == 0) {
    Print (SystemTable, L"  cannot open \\EFI\\Tpad on USB\r\n");
    return EFI_SUCCESS;
  }

  drvSize = 0;
  if (!ReadWholeFile (usbDir, L"\\EFI\\Tpad\\TpadAcpiProbe.efi", gBuf, sizeof (gBuf), &drvSize)) {
    Print (SystemTable, L"  cannot read \\EFI\\Tpad\\TpadAcpiProbe.efi\r\n");
    usbDir->Close (usbDir);
    return EFI_SUCCESS;
  }

  usbDir->Close (usbDir);
  Print (SystemTable, L"  OK, got ");
  PrintHex (SystemTable, drvSize, 4);
  Print (SystemTable, L" bytes\r\n\r\n");

  /* 找 ESP */
  Print (SystemTable, L"[3] locating ESP (volume holding \\EFI\\Microsoft\\Boot\\bootmgfw.efi):\r\n");
  nHandles = 0;
  bufSize  = sizeof (gHandles);
  if (((EFI_STATUS (*)(UINTN, EFI_GUID *, VOID *, UINTN *, EFI_HANDLE *))
        SystemTable->BootServices->LocateHandle) (
          BY_PROTOCOL, (EFI_GUID *)&gEfiSimpleFileSystemProtocolGuid, 0, &bufSize, gHandles) != 0) {
    Print (SystemTable, L"  LocateHandle failed\r\n");
    return EFI_SUCCESS;
  }

  nHandles = bufSize / sizeof (EFI_HANDLE);
  Print (SystemTable, L"  found ");
  PrintHex (SystemTable, nHandles, 2);
  Print (SystemTable, L" filesystem handles\r\n");

  espHandle = 0;
  espRoot   = 0;
  espDp     = 0;
  for (i = 0; i < nHandles; i++) {
    EFI_FILE_PROTOCOL        *r;
    EFI_DEVICE_PATH_PROTOCOL *dp;

    if (ProbeEsp (SystemTable, gHandles[i], &r, &dp)) {
      espHandle = gHandles[i];
      espRoot   = r;
      espDp     = dp;
      Print (SystemTable, L"  ESP found at handle #");
      PrintHex (SystemTable, i, 2);
      Print (SystemTable, L"\r\n");
      break;
    }
  }

  if (espRoot == 0) {
    Print (SystemTable, L"  ESP NOT FOUND - abort\r\n");
    return EFI_SUCCESS;
  }

  /* ---- [4] 写驱动到 ESP：多策略 + 打印确切 EFI_STATUS ---- */
  Print (SystemTable, L"[4] writing driver to ESP:\r\n");

  {
    EFI_FILE_PROTOCOL  *dir;
    EFI_FILE_PROTOCOL  *efiDir;
    EFI_FILE_PROTOCOL  *file;
    EFI_STATUS          stA, stB, stC, stD;
    UINTN               w;

    dir = 0;
    stA = espRoot->Open (espRoot, &dir, L"\\EFI\\Tpad", EFI_FILE_MODE_READ | EFI_FILE_MODE_WRITE, 0);
    Print (SystemTable, L"  A) open \\EFI\\Tpad (exist)   : 0x");
    PrintHex (SystemTable, stA, 16);
    Print (SystemTable, L"\r\n");

    if (stA != 0) {
      /* 退一步：先打开 \EFI，再在里面建 Tpad（用相对名，更保险） */
      efiDir = 0;
      stB = espRoot->Open (espRoot, &efiDir, L"\\EFI",
                           EFI_FILE_MODE_READ | EFI_FILE_MODE_WRITE, 0);
      Print (SystemTable, L"  B) open \\EFI              : 0x");
      PrintHex (SystemTable, stB, 16);
      Print (SystemTable, L"\r\n");

      if (stB == 0) {
        stC = efiDir->Open (efiDir, &dir, L"Tpad",
                            EFI_FILE_MODE_READ | EFI_FILE_MODE_WRITE | EFI_FILE_MODE_CREATE,
                            EFI_FILE_DIRECTORY);
        Print (SystemTable, L"  C) create \"Tpad\" in \\EFI : 0x");
        PrintHex (SystemTable, stC, 16);
        Print (SystemTable, L"\r\n");

        if (stC != 0) {
          /* 再退一步：直接往 \EFI 下写文件，不建子目录 */
          Print (SystemTable, L"  -> fallback: write \\EFI\\TpadAcpiProbe.efi directly\r\n");
          dir   = efiDir;
          got   = 0;
          stD   = dir->Open (dir, &file, L"TpadAcpiProbe.efi",
                             EFI_FILE_MODE_READ | EFI_FILE_MODE_WRITE | EFI_FILE_MODE_CREATE, 0);
          Print (SystemTable, L"  D) create \\EFI\\TpadAcpiProbe.efi : 0x");
          PrintHex (SystemTable, stD, 16);
          Print (SystemTable, L"\r\n");

          if (stD == 0) {
            file->SetPosition (file, 0);
            w = drvSize;
            if (file->Write (file, &w, gBuf) == 0) {
              file->Flush (file);
              got = 1;
            }

            file->Close (file);

            if (got) {
              pathLen = BuildPath (espDp, gPath, sizeof (gPath), L"\\EFI\\TpadAcpiProbe.efi");
              Print (SystemTable, L"  written (fallback path)\r\n");
              goto register_now;
            }
          }

          goto cant_write;
        }
      } else {
        goto cant_write;
      }
    }

    /* A 或 C 成功：dir 就是 ESP 上的 \EFI\Tpad */
    file = 0;
    stD  = dir->Open (dir, &file, L"TpadAcpiProbe.efi",
                      EFI_FILE_MODE_READ | EFI_FILE_MODE_WRITE | EFI_FILE_MODE_CREATE, 0);
    Print (SystemTable, L"  D) create TpadAcpiProbe.efi : 0x");
    PrintHex (SystemTable, stD, 16);
    Print (SystemTable, L"\r\n");

    if (stD != 0) {
      goto cant_write;
    }

    file->SetPosition (file, 0);
    w   = drvSize;
    got = 0;
    if (file->Write (file, &w, gBuf) == 0) {
      file->Flush (file);
      got = 1;
    }

    Print (SystemTable, L"  write result : ");
    Print (SystemTable, got ? L"OK\r\n" : L"FAILED\r\n");
    file->Close (file);

    if (!got) {
      goto cant_write;
    }

    pathLen = BuildPath (espDp, gPath, sizeof (gPath), L"\\EFI\\Tpad\\TpadAcpiProbe.efi");
  }

register_now:
  /* ---- [5] 登记指向 ESP ---- */
  Print (SystemTable, L"[5] registering Driver0000 -> ESP path (len=");
  PrintHex (SystemTable, pathLen, 4);
  Print (SystemTable, L"):\r\n");

  if (SetDriverOption (SystemTable, gPath, pathLen)) {
    Print (SystemTable, L"  registration: OK\r\n");
    Print (SystemTable, L"\r\n  >>> reboot now. the driver should run at next boot.\r\n");
    Print (SystemTable, L"  >>> then re-run this app to see TpadPatchState.\r\n");
  } else {
    Print (SystemTable, L"  registration: FAILED\r\n");
  }

  goto finished;

cant_write:
  Print (SystemTable, L"\r\n  >>> CANNOT WRITE TO ESP (see status codes above).\r\n");
  Print (SystemTable, L"  >>> 0x800000000000000F = WRITE_PROTECTED (firmware locks ESP)\r\n");
  Print (SystemTable, L"  >>> 0x8000000000000002 = INVALID_PARAMETER\r\n");
  Print (SystemTable, L"  >>> fallback: copy TpadAcpiProbe.efi into ESP:\\EFI\\Tpad\\ from Windows,\r\n");
  Print (SystemTable, L"  >>>           then re-run this app - step [5] will register it.\r\n");
  Print (SystemTable, L"\r\n");

  /* ★ 仍然按"文件将被放到 ESP"来登记，这样 Windows 侧放好文件后即可生效 */
  pathLen = BuildPath (espDp, gPath, sizeof (gPath), L"\\EFI\\Tpad\\TpadAcpiProbe.efi");
  Print (SystemTable, L"  registering ESP path anyway (len=");
  PrintHex (SystemTable, pathLen, 4);
  Print (SystemTable, L") ...\r\n");

  if (SetDriverOption (SystemTable, gPath, pathLen)) {
    Print (SystemTable, L"  registration: OK  (file must be present in ESP:\\EFI\\Tpad\\)\r\n");
  } else {
    Print (SystemTable, L"  registration: FAILED\r\n");
  }

finished:

  Print (SystemTable, L"\r\n");
  Print (SystemTable, L"##### PRESS ANY KEY within 8s = CLEAR Driver#### #####\r\n");

  if (WaitKeyOrTimeout (SystemTable, 8000)) {
    Print (SystemTable, L"key detected -> clearing:\r\n");
    ClearRegistrations (SystemTable);
  } else {
    Print (SystemTable, L"no key -> nothing changed, continuing boot.\r\n");
  }

  /* ★ 回读校验：确认登记到底写成什么样 */
  Print (SystemTable, L"\r\n[6] read back Driver0000 to verify:\r\n");
  PrintDriverTarget (SystemTable);

  if (SystemTable->ConOut != 0) {
    SystemTable->ConOut->SetAttribute (SystemTable->ConOut, 0x07);
  }

  if ((SystemTable->BootServices != 0) && (SystemTable->BootServices->Stall != 0)) {
    SystemTable->BootServices->Stall (8000000);
  }

  return EFI_SUCCESS;
}
