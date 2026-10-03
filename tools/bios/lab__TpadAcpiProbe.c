/** @file
  TpadAcpiProbe - 【探针版】只验证"固件认不认 DriverOrder"，什么都不改。

  它和 TpadAcpiPatch 的唯一区别：
    * 不找 DSDT、不改任何内存、不碰 ACPI 表
    * 只在屏幕上打一段醒目文字，停 3 秒，然后返回（让启动继续）

  用途
  ----
  配合 UEFI Shell 的 bcfg 命令，验证 UEFI 固件在 BDS 阶段是否会处理
  DriverOrder（即 Driver#### 变量指向的驱动）。

       bcfg driver add 0 fs0:\TpadAcpiProbe.efi "TpadAcpiProbe"

  判据
  ----
  * 重启后屏幕上出现下面那段文字  ->  固件认 DriverOrder，这条路可行
  * 屏幕上什么都没有、直接进系统  ->  固件不处理，别再折腾这条路

  安全
  ----
  它不做任何写操作，最坏情况就是"多显示一行字"。
  随时可用 `bcfg driver rm 0` 清除。
**/

#include <Uefi.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/UefiDriverEntryPoint.h>

EFI_STATUS
EFIAPI
TpadAcpiProbeEntry (
  IN EFI_HANDLE        ImageHandle,
  IN EFI_SYSTEM_TABLE  *SystemTable
  )
{
  if (gST->ConOut != NULL) {
    //
    // 反白显示，避免在满屏启动信息里被忽略
    //
    gST->ConOut->SetAttribute (gST->ConOut, EFI_WHITE | EFI_BACKGROUND_BLUE);
    gST->ConOut->OutputString (
                    gST->ConOut,
                    L"\r\n"
                    L"==================================================\r\n"
                    L"  DriverOrder 探针：TpadAcpiProbe\r\n"
                    L"  看到这一行 = 固件会在启动前加载 Driver#### 项\r\n"
                    L"  => driver#### 方案可行\r\n"
                    L"  （3 秒后自动继续启动；清理：bcfg driver rm 0）\r\n"
                    L"==================================================\r\n"
                    );
    gST->ConOut->SetAttribute (gST->ConOut, EFI_LIGHTGRAY | EFI_BACKGROUND_BLACK);
  }

  //
  // 停 3 秒，保证不可能看漏
  //
  if (gBS != NULL) {
    gBS->Stall (3000000);
  }

  //
  // 返回成功，不驻留、不干扰后续启动流程
  //
  return EFI_SUCCESS;
}
