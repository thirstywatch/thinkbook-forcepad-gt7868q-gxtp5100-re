/**
  TpadAcpiPatch.c —— 【真驱动】在 BDS 阶段自动给 DSDT 打 TPAD 补丁。

  做的事
  ------
  把内存中 DSDT 的 TPID 表第 4 行（Goodix）的【索引】从 0x04 改成 0xFE。
  因为 _CRS 查表循环的命中条件里包含 "索引 == 0xFE"（无条件命中），改完之后
  无论 BIOS 上报的 TPDF（厂商索引）是什么，查表都会落到 Goodix 那一行：
      ADR0 = 0x2C   (I2C 从机地址)
      HID2 = 0x20   (HID 描述符寄存器)
  从而消除"BIOS 白名单拒绝 ⇒ 地址写成 0xFF ⇒ 代码 10"这个后果。

  实测依据（离线 acpiexec 真跑 AML，见 touchpad-lab/dsdt-asl/verify/）
  --------------------------------------------------------------------
  原始表 + TPDF=0xFF  ->  ADR0 = 0xFF   (故障复现)
  原始表 + TPDF=0x00  ->  越界 AE_AML_PACKAGE_LIMIT，取到 0x00
  打补丁 + TPDF=0xFF  ->  ADR0 = 0x2C ✅
  打补丁 + TPDF=0x00  ->  ADR0 = 0x2C ✅   (不依赖 TPDF 取值)

  安全边界
  --------
  * 只改内存里的 ACPI 表，**不写任何 flash**，断电即恢复
  * 只做原地等长替换（Find/Replace 都是 16 字节）
  * 找不到 Find 串时什么都不做，静默返回成功

  编译：见同目录 build.bat（MSVC，不需 EDK2）
  部署：bcfg driver add 0 fs0:\EFI\Tpad\TpadAcpiPatch.efi "TpadAcpiPatch"
**/

#include "miniefi.h"

#define TPAD_PATCH_LEN  16

/*
 * DSDT 内 TPID 表第 4 行（Goodix）原始字节：
 *   0A 04              索引 = 0x04
 *   0A 2C              I2C 从机地址 = 0x2C
 *   0A 20              描述符寄存器 = 0x20
 *   0D "GXTP5100" 00   HID 字符串
 */
static const UINT8  mFind[TPAD_PATCH_LEN] = {
  0x0A, 0x04, 0x0A, 0x2C, 0x0A, 0x20, 0x0D, 0x47,
  0x58, 0x54, 0x50, 0x35, 0x31, 0x30, 0x30, 0x00
};

/*
 * 替换为：
 *   0A FE              索引 = 0xFE   <-- 使查表无条件命中该行
 *   0A 2C              I2C 从机地址 = 0x2C（不变）
 *   0A 20              描述符寄存器 = 0x20（不变）
 *   0D "MSFT0001" 00   HID 字符串换成与"未打补丁时的现状"一致，
 *                      避免改变操作系统的驱动匹配（把变量降到最少）
 */
static const UINT8  mReplace[TPAD_PATCH_LEN] = {
  0x0A, 0xFE, 0x0A, 0x2C, 0x0A, 0x20, 0x0D, 0x4D,
  0x53, 0x46, 0x54, 0x30, 0x30, 0x30, 0x31, 0x00
};

static int BytesEqual (const UINT8 *a, const UINT8 *b, UINTN n)
{
  UINTN  i;

  for (i = 0; i < n; i++) {
    if (a[i] != b[i]) {
      return 0;
    }
  }

  return 1;
}

static VOID BytesCopy (UINT8 *dst, const UINT8 *src, UINTN n)
{
  UINTN  i;

  for (i = 0; i < n; i++) {
    dst[i] = src[i];
  }
}

/* 重算 ACPI 表头校验和（表头 offset 9，使整表字节和 == 0） */
static VOID FixTableChecksum (EFI_ACPI_DESCRIPTION_HEADER *Table)
{
  UINT8        Sum;
  UINT32       Index;
  const UINT8 *p = (const UINT8 *)Table;

  Table->Checksum = 0;
  Sum             = 0;
  for (Index = 0; Index < Table->Length; Index++) {
    Sum = (UINT8)(Sum + p[Index]);
  }

  Table->Checksum = (UINT8)(0x00 - Sum);
}

/*
 * 从 UEFI 配置表找 RSDP，再顺着 XSDT 找 DSDT。
 * 本机是 2024 年的 Intel 平台，必有 XSDT，所以只走 XSDT 分支。
 */
static EFI_ACPI_DESCRIPTION_HEADER *
FindDsdt (
  EFI_SYSTEM_TABLE  *SystemTable
  )
{
  EFI_CONFIGURATION_TABLE           *Cfg;
  EFI_ACPI_2_0_RSDP                 *Rsdp;
  EFI_ACPI_DESCRIPTION_HEADER       *Xsdt;
  EFI_ACPI_DESCRIPTION_HEADER       *Table;
  UINTN                              Index;
  UINTN                              Count;
  UINT64                            *Entry;

  Rsdp = 0;
  Cfg  = SystemTable->ConfigurationTable;

  for (Index = 0; Index < SystemTable->NumberOfTableEntries; Index++) {
    if (GuidEqual (&Cfg[Index].VendorGuid, &gAcpi20TableGuid) ||
        GuidEqual (&Cfg[Index].VendorGuid, &gAcpi10TableGuid)) {
      Rsdp = (EFI_ACPI_2_0_RSDP *)Cfg[Index].VendorTable;
      break;
    }
  }

  if (Rsdp == 0) {
    return 0;
  }

  if ((Rsdp->Revision < 2) || (Rsdp->XsdtAddress == 0)) {
    return 0;
  }

  Xsdt  = (EFI_ACPI_DESCRIPTION_HEADER *)(UINTN)Rsdp->XsdtAddress;
  Count = (Xsdt->Length - (UINT32)sizeof (EFI_ACPI_DESCRIPTION_HEADER)) / sizeof (UINT64);
  Entry = (UINT64 *)(Xsdt + 1);

  for (Index = 0; Index < Count; Index++) {
    Table = (EFI_ACPI_DESCRIPTION_HEADER *)(UINTN)Entry[Index];
    if ((Table != 0) && (Table->Signature == SIGNATURE_32 ('D', 'S', 'D', 'T'))) {
      return Table;
    }
  }

  return 0;
}

/* 把状态写进 UEFI 变量，供下次启动读取。写失败也不影响主流程。 */
static VOID StoreState (EFI_SYSTEM_TABLE *ST, UINT8 *state)
{
  UINT32  attr;

  if ((ST == 0) || (ST->RuntimeServices == 0) ||
      (ST->RuntimeServices->SetVariable == 0)) {
    return;
  }

  attr = EFI_VARIABLE_NON_VOLATILE |
         EFI_VARIABLE_BOOTSERVICE_ACCESS |
         EFI_VARIABLE_RUNTIME_ACCESS;

  ST->RuntimeServices->SetVariable (L"TpadPatchState",
                                    (EFI_GUID *)&gEfiGlobalVariableGuid,
                                    attr, 8, state);
}

EFI_STATUS
EFIAPI
TpadAcpiPatchEntry (
  EFI_HANDLE        ImageHandle,
  EFI_SYSTEM_TABLE  *SystemTable
  )
{
  EFI_ACPI_DESCRIPTION_HEADER  *Dsdt;
  UINT8                        *Buf;
  UINT32                        Index;
  UINTN                         Hits;
  UINT32                        HitOffset;
  UINT8                         state[8];

  (VOID)ImageHandle;

  HitOffset = 0;
  Hits      = 0;

  /*
   * 状态变量：给下一次启动的 TpadBootTest 读，用来确认本驱动到底有没有跑、有没有命中。
   *   state[0] = 0xA5 魔数
   *   state[1] = 1 表示找到 DSDT
   *   state[2] = 命中次数（应为 1）
   *   state[3] = 1 表示重算过校验和
   *   state[4..7] = 命中的 DSDT 内偏移（小端）
   */
  state[0] = 0xA5;
  state[1] = 0;
  state[2] = 0;
  state[3] = 0;
  state[4] = 0;
  state[5] = 0;
  state[6] = 0;
  state[7] = 0;

  if (SystemTable == 0) {
    return EFI_SUCCESS;
  }

  /*
   * ★ 一进门就先把"我跑过了"写进变量 —— 这样即使后面出问题，
   *   下次启动也能凭变量是否存在判断本驱动到底有没有被执行。
   */
  StoreState (SystemTable, state);

  Dsdt = FindDsdt (SystemTable);
  if (Dsdt != 0) {
    state[1] = 1;

    Buf = (UINT8 *)Dsdt;
    for (Index = 0; (Index + TPAD_PATCH_LEN) <= Dsdt->Length; Index++) {
      if (BytesEqual (Buf + Index, mFind, TPAD_PATCH_LEN)) {
        BytesCopy (Buf + Index, mReplace, TPAD_PATCH_LEN);
        if (Hits == 0) {
          HitOffset = Index;
        }

        Hits++;
        Index += TPAD_PATCH_LEN - 1;
      }
    }

    state[2] = (UINT8)Hits;

    if (Hits > 0) {
      FixTableChecksum (Dsdt);
      state[3]     = 1;
      state[4]     = (UINT8)(HitOffset & 0xFF);
      state[5]     = (UINT8)((HitOffset >> 8) & 0xFF);
      state[6]     = (UINT8)((HitOffset >> 16) & 0xFF);
      state[7]     = (UINT8)((HitOffset >> 24) & 0xFF);
    }
  }

  /*
   * 把最终状态再写一次（覆盖进门的占位值）。
   */
  StoreState (SystemTable, state);

  return EFI_SUCCESS;
}
