/**
  TpadAcpiProbe.c —— 【探针版】只验证"固件认不认 DriverOrder"，什么都不改。

  行为：在屏幕反白打一段字，停 3 秒，然后返回（让启动继续）。
        不找 DSDT、不改任何内存、不碰 ACPI 表、不占用控制台。

  编译：见同目录 build.bat（MSVC，不需 EDK2）
  部署：UEFI Shell 里
          bcfg driver add 0 fs0:\EFI\Tpad\TpadAcpiProbe.efi "TpadAcpiProbe"
  判据：重启后看到那段反白文字 = 固件会处理 Driver#### ⇒ driver#### 方案可行
        什么都没有、直接进系统   = 固件不处理       ⇒ 回 OpenCore 方案（结果等价）
  清理：bcfg driver rm 0
**/

#include "miniefi.h"

EFI_STATUS
EFIAPI
TpadAcpiProbeEntry (
  EFI_HANDLE        ImageHandle,
  EFI_SYSTEM_TABLE  *SystemTable
  )
{
  EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL  *ConOut;

  (VOID)ImageHandle;

  if (SystemTable == 0) {
    return EFI_SUCCESS;
  }

  ConOut = SystemTable->ConOut;
  if (ConOut != 0) {
    /* 反白，避免满屏启动信息里被忽略 */
    ConOut->SetAttribute (ConOut, 0x17 /* 白字蓝底 */);
    ConOut->OutputString (
               ConOut,
               L"\r\n"
               L"==================================================\r\n"
               L"  DriverOrder 探针：TpadAcpiProbe\r\n"
               L"  看到这一行 = 固件会在启动前加载 Driver#### 项\r\n"
               L"  => driver#### 方案可行\r\n"
               L"  （3 秒后自动继续启动；清理：bcfg driver rm 0）\r\n"
               L"==================================================\r\n"
               );
    ConOut->SetAttribute (ConOut, 0x07 /* 浅灰字黑底 */);
  }

  /* 停 3 秒，保证不可能看漏 */
  if ((SystemTable->BootServices != 0) &&
      (SystemTable->BootServices->Stall != 0)) {
    SystemTable->BootServices->Stall (3000000);
  }

  return EFI_SUCCESS;
}
