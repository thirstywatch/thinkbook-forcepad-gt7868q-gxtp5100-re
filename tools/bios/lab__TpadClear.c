/**
  TpadClear.c —— Rescue / cleanup application.  ASCII OUTPUT ONLY.

  把 Driver#### / DriverOrder 相关变量全部删掉，让机器回到"没登记过任何驱动"的状态。

  用途：万一装了驱动后机器启动异常，把本文件复制成 U 盘上的 \EFI\BOOT\BOOTX64.EFI，
        从 F12 选 U 盘跑一次即可清除；跑完重启就恢复正常。

  删除方式：SetVariable(名字, GUID, 0, 0, NULL)，这是 UEFI 规定的删除变量的方式。

  编译：build.bat（MSVC，Subsystem 10）
**/

#include "miniefi.h"

static CHAR16 *mNames[] = {
  L"Driver0000",
  L"Driver0001",
  L"DriverOrder",
  L"TpadPatchState"
};

static VOID Print (EFI_SYSTEM_TABLE *ST, CHAR16 *S)
{
  if ((ST != 0) && (ST->ConOut != 0)) {
    ST->ConOut->OutputString (ST->ConOut, S);
  }
}

EFI_STATUS
EFIAPI
TpadClearEntry (
  EFI_HANDLE        ImageHandle,
  EFI_SYSTEM_TABLE  *SystemTable
  )
{
  UINTN       i;
  EFI_STATUS  st;

  (VOID)ImageHandle;

  if (SystemTable == 0) {
    return EFI_SUCCESS;
  }

  if (SystemTable->ConOut != 0) {
    SystemTable->ConOut->SetAttribute (SystemTable->ConOut, 0x17);
  }

  Print (SystemTable, L"\r\n");
  Print (SystemTable, L"===== TpadClear : remove Driver#### registration =====\r\n");
  Print (SystemTable, L"\r\n");

  if ((SystemTable->RuntimeServices == 0) ||
      (SystemTable->RuntimeServices->SetVariable == 0)) {
    Print (SystemTable, L"SetVariable unavailable - cannot clear\r\n");
  } else {
    for (i = 0; i < (sizeof (mNames) / sizeof (mNames[0])); i++) {
      st = SystemTable->RuntimeServices->SetVariable (mNames[i],
                                                      (EFI_GUID *)&gEfiGlobalVariableGuid,
                                                      0, 0, 0);
      Print (SystemTable, L"  ");
      Print (SystemTable, mNames[i]);
      Print (SystemTable, L"  -> ");
      if (st == 0) {
        Print (SystemTable, L"DELETED\r\n");
      } else if (st == EFI_NOT_FOUND) {
        Print (SystemTable, L"was not present\r\n");
      } else {
        Print (SystemTable, L"failed / not present\r\n");
      }
    }
  }

  Print (SystemTable, L"\r\n");
  Print (SystemTable, L"===== done, continuing boot in 5s =====\r\n");

  if (SystemTable->ConOut != 0) {
    SystemTable->ConOut->SetAttribute (SystemTable->ConOut, 0x07);
  }

  if ((SystemTable->BootServices != 0) && (SystemTable->BootServices->Stall != 0)) {
    SystemTable->BootServices->Stall (5000000);
  }

  return EFI_SUCCESS;
}
