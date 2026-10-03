/** @file
  TpadAcpiPatch - 在 BDS 阶段自动给 DSDT 打 TPAD 补丁。

  原理
  ----
  UEFI 固件在 BDS 阶段会【先处理 DriverOrder】（加载 Driver#### 变量指向的驱动），
  【再处理 BootOrder】（引导操作系统）。本驱动就挂在 DriverOrder 上，所以每次开机
  都会在"操作系统启动之前"被自动加载并执行 —— 不依赖启动顺序，也不需要 OpenCore。

  它做的事
  --------
  把内存中 DSDT 的 TPID 表第 4 行（Goodix）的【索引】从 0x04 改成 0xFE。
  因为 _CRS 的查表循环命中条件里包含 "索引 == 0xFE"（无条件命中），改完之后
  无论 BIOS 上报的 TPDF（厂商索引）是什么，查表都会落到 Goodix 那一行：
      ADR0 = 0x2C  (I2C 从机地址)
      HID2 = 0x20  (HID 描述符寄存器)
  从而消除"BIOS 白名单拒绝 ⇒ 地址写成 0xFF ⇒ 代码 10"这个后果。

  实测依据（离线 acpiexec 验证）
  -----------------------------
  原始表 + TPDF=0xFF  ->  ADR0 = 0xFF  (故障复现)
  打补丁 + TPDF=0xFF  ->  ADR0 = 0x2C  ✅
  打补丁 + TPDF=0x00  ->  ADR0 = 0x2C  ✅  (不依赖 TPDF 取值)

  安全边界
  --------
  * 只改内存里的 ACPI 表副本，**不写任何 flash**，断电即恢复
  * 只做原地等长替换（Find/Replace 均为 16 字节）
  * 找不到 Find 串时什么都不做，静默成功

  编译与部署见同目录 README.md
**/

#include <Uefi.h>
#include <Library/BaseLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/UefiDriverEntryPoint.h>
#include <IndustryStandard/Acpi.h>

#define TPAD_PATCH_LEN  16

//
// DSDT 内 TPID 表第 4 行（Goodix）原始字节：
//   0A 04             索引 = 0x04
//   0A 2C             I2C 从机地址 = 0x2C
//   0A 20             描述符寄存器 = 0x20
//   0D "GXTP5100" 00  HID 字符串
//
STATIC CONST UINT8  mFind[TPAD_PATCH_LEN] = {
  0x0A, 0x04, 0x0A, 0x2C, 0x0A, 0x20, 0x0D, 0x47,
  0x58, 0x54, 0x50, 0x35, 0x31, 0x30, 0x30, 0x00
};

//
// 替换为：
//   0A FE             索引 = 0xFE   ← ★ 使查表无条件命中该行
//   0A 2C             I2C 从机地址 = 0x2C（不变）
//   0A 20             描述符寄存器 = 0x20（不变）
//   0D "MSFT0001" 00  HID 字符串换成与"未打补丁时的现状"一致，避免改变 OS 的驱动匹配
//
STATIC CONST UINT8  mReplace[TPAD_PATCH_LEN] = {
  0x0A, 0xFE, 0x0A, 0x2C, 0x0A, 0x20, 0x0D, 0x4D,
  0x53, 0x46, 0x54, 0x30, 0x30, 0x30, 0x31, 0x00
};

/**
  重算 ACPI 表头校验和（表头 offset 9，使整表字节和 == 0）。
**/
STATIC
VOID
FixTableChecksum (
  IN EFI_ACPI_DESCRIPTION_HEADER  *Table
  )
{
  UINT8  Sum;
  UINTN  Index;

  Table->Checksum = 0;
  Sum             = 0;
  for (Index = 0; Index < Table->Length; Index++) {
    Sum = (UINT8)(Sum + ((UINT8 *)Table)[Index]);
  }

  Table->Checksum = (UINT8)(0x00 - Sum);
}

/**
  从 UEFI 配置表里找 RSDP，再顺着 XSDT 找到 DSDT。

  @return DSDT 表指针；找不到返回 NULL。
**/
STATIC
EFI_ACPI_DESCRIPTION_HEADER *
FindDsdt (
  VOID
  )
{
  EFI_CONFIGURATION_TABLE                       *Cfg;
  EFI_ACPI_2_0_ROOT_SYSTEM_DESCRIPTION_POINTER  *Rsdp;
  EFI_ACPI_DESCRIPTION_HEADER                   *Xsdt;
  EFI_ACPI_DESCRIPTION_HEADER                   *Table;
  UINTN                                          Index;
  UINTN                                          Count;
  UINT64                                         *Entry;

  Rsdp = NULL;
  Cfg  = gST->ConfigurationTable;
  for (Index = 0; Index < gST->NumberOfTableEntries; Index++) {
    if (CompareGuid (&Cfg[Index].VendorGuid, &gEfiAcpi20TableGuid) ||
        CompareGuid (&Cfg[Index].VendorGuid, &gEfiAcpi10TableGuid)) {
      Rsdp = (EFI_ACPI_2_0_ROOT_SYSTEM_DESCRIPTION_POINTER *)Cfg[Index].VendorTable;
      break;
    }
  }

  if (Rsdp == NULL) {
    return NULL;
  }

  //
  // ACPI 2.0+ 走 XSDT（64 位表指针）。本机是 2024 年的 Intel 平台，必有 XSDT。
  //
  if ((Rsdp->Revision < 2) || (Rsdp->XsdtAddress == 0)) {
    return NULL;
  }

  Xsdt  = (EFI_ACPI_DESCRIPTION_HEADER *)(UINTN)Rsdp->XsdtAddress;
  Count = (Xsdt->Length - sizeof (EFI_ACPI_DESCRIPTION_HEADER)) / sizeof (UINT64);
  Entry = (UINT64 *)(Xsdt + 1);
  for (Index = 0; Index < Count; Index++) {
    Table = (EFI_ACPI_DESCRIPTION_HEADER *)(UINTN)Entry[Index];
    if ((Table != NULL) && (Table->Signature == SIGNATURE_32 ('D', 'S', 'D', 'T'))) {
      return Table;
    }
  }

  return NULL;
}

/**
  驱动入口：找 DSDT -> 原地替换 -> 重算校验和。

  @retval EFI_SUCCESS  无论是否命中，都返回成功，避免影响后续启动流程。
**/
EFI_STATUS
EFIAPI
TpadAcpiPatchEntry (
  IN EFI_HANDLE        ImageHandle,
  IN EFI_SYSTEM_TABLE  *SystemTable
  )
{
  EFI_ACPI_DESCRIPTION_HEADER  *Dsdt;
  UINT8                        *Buf;
  UINTN                         Index;
  UINTN                         Hits;

  Dsdt = FindDsdt ();
  if (Dsdt == NULL) {
    return EFI_SUCCESS;
  }

  Buf  = (UINT8 *)Dsdt;
  Hits = 0;

  for (Index = 0; (Index + TPAD_PATCH_LEN) <= Dsdt->Length; Index++) {
    if (CompareMem (Buf + Index, mFind, TPAD_PATCH_LEN) == 0) {
      CopyMem (Buf + Index, mReplace, TPAD_PATCH_LEN);
      Hits++;
      Index += TPAD_PATCH_LEN - 1;
    }
  }

  if (Hits > 0) {
    FixTableChecksum (Dsdt);
  }

  return EFI_SUCCESS;
}
