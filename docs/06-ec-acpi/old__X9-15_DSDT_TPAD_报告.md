# 联想 ThinkPad X9-15 Gen 1 (BIOS 1.09 / N4CUJ09W) —— DSDT 提取与 TPAD 节点分析报告

> 结论先行：**本机 DSDT 里没有 `Device(TPAD)`**。`TPAD` 在这台机器上只是
> **EC/GNVS 的 8 位字段名**（DSDT `0x2F0B`）。本机真正的触控板设备节点是
> **`Device (TPD0)`**，完整路径 `\_SB.PC00.I2C5.TPD0`，位于 DSDT **`0x17331`–`0x17637`（774 字节）**。
> 该节点的厂商表里 I2C 从机地址 = **0x2C**、HID 描述符寄存器 = **0x20**，与参照机
> （ThinkBook 14 G6+ IMH）**完全一致**；但**中断 GPIO 引脚不是静态常量**（见 §6）。

---

## 1. 怎么解出来的（可复现链路）

| 步骤 | 做法 | 结果 |
|---|---|---|
| 1 | ISO9660 主卷 / Joliet 卷目录树 | **都是空的**（只有 `.` / `..`） |
| 2 | El Torito 启动目录表（LBA 20，`0xA000`） | 硬盘仿真（media `0x04`），引导镜像起始 **LBA 27 = `0xD800`**，占满剩余 127 MB |
| 3 | 引导镜像 MBR（`0xD800`）分区表 | 分区 0：type `0x0B`(FAT32)、LBA 32 → 卷起始 = 镜像起点 + 32×512 = **文件偏移 `0x11800`** |
| 4 | FAT32 遍历 | `/EFI/Boot/BootX64.efi`、`/Flash/N4CSG21W/$0AN4C00.SC1`(44,097,616 B)、`$0AN4C00.SC2`(51,490,896 B)、`B06D0.PAT`/`B06D1.PAT`(EC 补丁)、`BCP.EVS` |
| 5 | `SC1`/`SC2` 结构 | 头部 `0x50` 字节，其后为固件卷 FV（GUID `5473C07A-3DCB-4DCA-BD6F-1E9689E7349A`，FvLength = 整个文件） |
| 6 | FV → FFS → Section 递归 | 段类型 `0x02` (GUID_DEFINED) + GUID `EE4E5898-3914-4259-9D6E-DC7BD79403CF` = **LZMA** |
| 7 | **卡点**：LZMA 段的数据布局 | **数据从「段起点 + DataOffset」开始**（不是「段起点+4+DataOffset」），且帧格式是 **LZMA-alone**：`5B` 属性(5B) + 原始长度(u64 LE) + 原始流。用 iasl 那套「u32 长度 + 5 属性」解不出来 |
| 8 | 逐层解压 | 13 个 blob；其中 `FV@0x11A08A8` → FFS 文件 `AD198BA5-C330-41CD-B097-16488328B798` → GUID_DEFINED 段解出 **21,430,288 字节**，即整片 ACPI 静态表区 |
| 9 | 校验和筛选 ACPI 表 | 30 个校验和正确的表；**唯一一个 DSDT** 在 blob 偏移 `0x3116C` |

- `SC2` 前 `0x23E5000` 字节与 `SC1` **逐字节相同**（故 ACPI 完全一致），`SC2` 只是尾部多了 7.4 MB 其它固件区。
- 全程**只读**原始 BIOS 包，**没有运行 `.exe`**，**没有改动任何固件/驱动**。
- `.exe`（38.3 MB, MZP 壳 + 201 个内嵌 PE）**未使用**——ISO 路径更直接，无需再啃它。

---

## 2. DSDT 基本信息

| 项 | 值 |
|---|---|
| 产物 | `DSDT_X9-15.bin` |
| 签名 | `DSDT` |
| 长度 | **300,544 字节**（`0x49600`） |
| Revision | 2 |
| OEM ID / OEM Table ID | `INTEL` / `SKL`（Insyde 沿用 Intel 参考表的字段，非 Lenovo 字样） |
| 字节求和校验 | **`0x00` → 通过 ✅** |
| 来源 | `$0AN4C00.SC1` → FV@`0x11A08A8` → FFS `AD198BA5-C330-41CD-B097-16488328B798` → LZMA 段解压后 blob 偏移 `0x3116C` |
| MD5 | `c7705f712ef45b4fda70a421d56948fa` |

同一表区里交叉确认存在的表：`FACP`/`FACS`/`HPET`/`WSMT`/`LPIT`/`ECDT`/`DMAR`/`MCFG`/`NHLT`×5/`SPCR`/`UEFI`，
以及 22 个 SSDT（含 **LENOVO / PID0Ss、PID1Ss、ProjSs** 三张联想专有表）和 Intel 的 `PmRef/CpuRef/DptfTb/Cnv_Ss` 等。
`FACP` 等在固件里是「模板」（校验和待启动时回填），DSDT 则是**已定稿**（校验和已为 0）。

---

## 3. `TPAD` 在这台机器上是什么

- 全 DSDT 内 **ASCII `TPAD` 只出现 1 次**，位于 **`0x2F0B`**，上下文：
  ```
  54 50 41 54 08 | 54 50 41 50 08 | 54 50 41 44 08 | 53 54 41 53 08 | 57 52 54 4F 08 | 50 52 53 54 20 | 57 50 52 50
     TPAT , 8        TPAP , 8          TPAD , 8          STAS , 8         WRTO , 8        PRST , 32        WPRP ...
  ```
  即 **8 位 EC 字段**，与 `TPAP/TPAT/TP1U…TPAU` 同一组——与参照机里 `TPAD` 兼作 EC 字段的命名习惯一致。
- **不存在** `5B 82 <PkgLen> 54 50 41 44`（Device(TPAD)）这种节点。
- 本机触控板**设备**名是 **`TPD0`**。

---

## 4. 触控板设备节点：`Device (TPD0)`（DSDT `0x17331`，774 字节）

被 `Scope(\_SB.PC00.I2C5)`（DSDT `0x17320`，pkglen 790）包住 ⇒ 完整路径 **`\_SB.PC00.I2C5.TPD0`**。

原始首部：`5B 82 44 30 54 50 44 30` = `DeviceOp, PkgLength=772, "TPD0"`

内部对象清单（工具自动列出的偏移为 DSDT 内绝对偏移）：

```
0x017339  Name(HID2 ) = Zero                     ← 运行时被 UHMS 写成 HID 描述符寄存器(0x20)
0x01733F  Name(SBFB ) = Buffer[25]               ← I2cSerialBus 资源模板（含 400kHz + 地址占位, ResourceSource "NULL")
0x017361  Name(SBFI ) = Buffer[11]               ← 备用中断描述符
0x017375  CreateWordField (SBFB, 0x10, BADR)     ← I2C 从机地址字段
0x017380  CreateDWordField(SBFB, 0x0C, SPED)     ← I2C 速率字段
0x01738B  CreateDWordField(SBFI, 0x05, INT2)     ← 中断号字段
0x017396  Name(_HRV ) = Zero
0x01739C  Name(ITML ) = Package(4){...}          ← ★ 厂商表（见 §5）
0x017405  Method(UHMS)   0 args, len 240         ← 按 TDVI 匹配 ITML 并回填 BADR/HID2/_HID/SPED
0x0174F5  Method(_INI)   0 args, len 99          ← SRXO(GPDI,1) / INUM(GPDI)→INT2 / SHPO / SGRA / GRXE / SGII / UHMS()
0x017558  Name(_HID ) = "XXXX0000"               ← 运行时被 UHMS 覆盖为实际 _HID
0x017567  Name(_CID ) = "PNP0C50"                ← HID-over-I2C
0x017575  Name(_S0W ) = 0x3
0x01757C  Method(_DSM, 4, Serialized) len 69
0x0175C1  Method(_STA)   0 args, len 46
0x0175EF  Method(_CRS)   0 args, len 72
```

关键方法的语义（AML 已逐字节核对，`84` = ConcatenateResTemplate，二元形式尾随 `NullName` 目标）：

```asl
Method (UHMS, 0) {                       // 按实测厂商 ID 选行
    Store (0, Local0); Store (SizeOf (ITML), Local1)
    While (LLess (Local0, Local1)) {
        Store (DerefOf (Index (ITML, Local0)), Local2)
        Store (DerefOf (Index (Local2, 0)), Local3)      // 第 1 列 = 厂商 ID
        If (TDVI == Local3) {                            // TDVI = GNVS 里的实测 VID
            Store (DerefOf (Index (Local2, 2)), BADR)     // 第 3 列 -> I2C 从机地址   = 0x2C
            Store (DerefOf (Index (Local2, 3)), HID2)     // 第 4 列 -> 描述符寄存器   = 0x20
            Store (DerefOf (Index (Local2, 4)), Local5)   // 第 5 列 -> 速率索引
            Store (DerefOf (Index (Local2, 5)), _HID)     // 第 6 列 -> _HID 字符串
            If (_HID == "SYNA8030") { ... Store ("SYNA802F", _HID) }   // 依 TDFV 版本细分
            Store (TDFV, _HRV)
            If (Local5 == 0) { Store (100000, SPED) }
            If (Local5 == 1) { Store (400000, SPED) }     // 本机表里 4 行全为 1 → 400 kHz
            If (Local5 == 2) { Store (1000000, SPED) }
            Return (One)
        }
        Increment (Local0)
    }
    Return (Zero)
}

Method (_DSM, 4, Serialized) {
    If (Arg0 == HIDG) { Return (HIDD (Arg0, Arg1, Arg2, Arg3, HID2)) }        // HID 描述符寄存器
    If (Arg0 == TP7G) { Return (TP7D (Arg0, Arg1, Arg2, Arg3, SBFB,
                                        G_IN (GPDI, Zero, One, 0x02, Zero, Zero))) }
    Return (Buffer (One) { 0x00 })
}

Method (_CRS, 0) {
    If (TPDM == Zero) {
        Return (ConcatenateResTemplate (I2CM (I2CX, BADR, SPED),
                                        G_IN (GPDI, Zero, One, 0x02, Zero, Zero)))
    }
    Return (ConcatenateResTemplate (I2CM (I2CX, BADR, SPED), SBFI))
}
```

- `I2CM(索引, 地址, 速率)`（DSDT `0x16F71`，**3 参数**）内部是一个 Switch：按索引返回
  `\_SB.PC00.I2C0…I2C5` 的 I2cSerialBus 模板，并把 `地址` 写进 `DAD*`（偏移 `0x10`）、`速率` 写进 `DSP*`（偏移 `0x0C`）。
- 每个 `Scope(\_SB.PC00.I2Cn)` 的 `_INI` 会把 `I2CX` 设成自己的索引 ⇒
  **本机 `I2CX = 5`，触控板挂在 `\_SB.PC00.I2C5` 上**，SBFB 里 `SPED` 默认为 `0x00061A80 = 400000`（400 kHz）。
- `G_IN(引脚描述, 模式, 极性, 共享, 引脚配置, 去抖)`（DSDT `0xAAF7`，**6 参数**）在 `\_SB.GPI0…GPI5`
  中选一个，并就地生成 GpioInt 资源模板：引脚号 = `GNUM(引脚描述)`，写入模板偏移 `0x17`。

---

## 5. ★ 厂商表 `ITML`（DSDT `0x1739C`，原始 `12 43 06 04 …`）

```
Name (ITML, Package(4) {
  Package(6) { 0x04F3, 0x32FE, 0x2C, 0x20, One, "ELAN06FA" },   // 0x04F3 = ELAN 的 VID
  Package(6) { 0x06CB, 0xCFA8, 0x2C, 0x20, One, "SYNA2BA6" },   // 0x06CB = Synaptics
  Package(6) { 0x27C6, 0x01E9, 0x2C, 0x20, One, "GXTP5100" },   // 0x27C6 = Goodix
  Package(6) { 0x0488, 0x1054, 0x2C, 0x20, One, "CIRQ1080" }    // 0x0488 = Cirque
})
```
列含义：`{ 厂商VID(与 TDVI 比对), 保留/版本码, I2C 从机地址, HID 描述符寄存器, 速率索引, _HID 字符串 }`。
**本机 4 行全部是地址 `0x2C` + 寄存器 `0x20` + 速率索引 1(=400 kHz)** ——
也就是说无论装的是 ELAN / Synaptics / Goodix / Cirque 哪一块，这两项都一样。
运行时由 `TDVI`（实际触摸板 VID）决定走哪一行，**不是按序号选**。

---

## 6. 与参照机（ThinkBook 14 G6+ IMH，`Device(TPAD)` @ 参照 DSDT `0x7042A`）逐项对比

| 项目 | 参照机 TB14G6+ `TPAD` | 本机 X9-15 Gen1 `TPD0` | 是否一致 |
|---|---|---|---|
| 设备节点名 | `TPAD` | **`TPD0`** | ✗ 命名不同 |
| 完整路径 | `\_SB.PC00.I2C0.TPAD`（相关） | `\_SB.PC00.I2C5.TPD0` | — |
| **I2C 从机地址** | **0x2C** | **0x2C** | **✅ 一致** |
| **HID 描述符寄存器** | **0x20** | **0x20** | **✅ 一致** |
| I2C 速率 | （表内未体现） | 400 kHz（`SPED` 默认 `0x00061A80`） | — |
| _HID / _CID | `MSFT0001` / `PNP0C50` | `"XXXX0000"`→运行时替换 / `PNP0C50` | CID 一致 |
| **中断 GPIO 引脚** | 硬编码 `GpioInt` 描述符里引脚 **182 (`0xB6`)**、源 `\_SB.GPI0`（在 `Name(SBFG, Buffer[37])` 中） | **无静态引脚**：`_CRS`/`_DSM` 调 `G_IN(GPDI,0,1,2,0,0)` **运行时生成** | ⚠ **本机拿不到常量，见下** |
| 厂商表 | `Name(TPID, Package(5))`，每行 **5** 项 `{序号, 地址, 寄存器, _HID, _CID}`，按序号选（参照机走第 4 行 GXTP5100） | `Name(ITML, Package(4))`，每行 **6** 项 `{VID, 版本码, 地址, 寄存器, 速率索引, _HID}`，**按 VID 匹配** | ✗ 表结构与选取方式不同 |

### 为什么本机「中断引脚」拿不到常量

`GPDI` 是 `Field (GNVS, …)` 里的一个 **32 位字段**（GNVS = `OperationRegion(VS, SystemMemory, …)`，
Field 位于 DSDT `0x27DB`）。DSDT/SSDT 里 `GPDI` 出现 10 次，**全部是读**（`GCOM/GNUM/G_IN/SRXO/SHPO/SGRA/GRXE/SGII/INUM`），
**没有任何一次 `Store` 写它** ⇒ 该值由 BIOS/EC 在启动时填进 GNVS。

`GPDI` 的解码链（DSDT `0xAEBD`–`0xB000` 的辅助方法，已逐字节核对）：
```
GCOM(x) = (x >> 10) & 7        -> GPIO 控制器序号 (0..5 -> \_SB.GPI0..GPI5)
GGRP(x) = (x >>  7) & 7        -> GPIO community/group
GNMB(x) =  x        & 0x7F     -> 组内引脚号
GNUM(x) = GINF(GCOM(x), GGRP(x), 7) + (GNMB(x) << 7)   -> 最终 pad 号（GINF 查 GDSC 社区表）
GADR(x) = SBRG + (GGRP(x) << 16) + GCMP(GCOM(x)) …     -> pad 配置寄存器 MMIO 地址
```
`_CRS` 里传入的其它参数是常量：模式 = 0(Level)、极性 = 1(ActiveLow)、共享 = 0x02、引脚配置 = 0、去抖 = 0。

> 补充排查（均已排除）：本机 DSDT 里全部 26 个 GpioInt 描述符逐个枚举过，
> 只有 USB-C `VGPO`/`GPI0/1/3/4/5` 用途，**没有任何一个涉及触控板，也没有出现引脚 182**；
> 全 21 MB ACPI 表区内也没有第二处 `GpioInt + 触控板` 的组合。
> 因此引脚号确实只在 GNVS 运行时数据里，**无法从 DSDT 静态得到**。

---

## 7. 产物清单（绝对路径）

| 文件 | 说明 |
|---|---|
| `<WORKSPACE>` | **DSDT 本体**，300,544 字节，校验和 0x00 |
| `...\x9bios\deliverables\TPAD_X9-15.bin` | **触控板设备子树** = `Device(TPD0)` 原始 774 字节（DSDT `0x17331`–`0x17637`） |
| `...\x9bios\deliverables\TPAD_X9-15_hexdump.txt` | 带注释的 hex dump：对象清单 + 774 字节原始 hex + `ITML` 定位 + `TPAD` EC 字段区 + **参照机 TPAD/SBFG 对照 hex** |
| `...\x9bios\deliverables\TPAD_EC_field_X9-15.bin` | 本机真正叫 `TPAD` 的那段（EC 字段区，DSDT `0x2EF0`–`0x2F30`，其中 `TPAD` 在 `0x2F0B`，宽度 `0x08`） |
| `...\x9bios\deliverables\ACPI_tables_X9-15\` | 30 个校验和正确的 ACPI 表（含全部 SSDT/NHLT）+ `_index.txt` |
| `...\x9bios\out_sc1\N4C_SC1_blob03_dec.bin` | **21,430,288 字节** 解压后的完整 ACPI 静态表区（DSDT 在其中 `0x3116C`） |
| `...\x9bios\out_sc1\N4C_SC1_blob*.bin` | 从 SC1 解出的 13 个固件 blob |
| `...\x9bios\iso_fat\N4C_SC1.bin` / `N4C_SC2.bin` | 从 ISO 引导镜像 FAT32 里取出的两个固件镜像 |

### 脚本（都在 `...\x9bios\`）

| 脚本 | 作用 |
|---|---|
| `iso_list.py` | ISO9660/Joliet/El Torito 解析 |
| `fat_list.py` | FAT12/16/32 遍历与抽取（`python fat_list.py <img> <base> [outdir]`） |
| `x9_fv.py` | **主力**：FV/FFS/Section 递归 + COMPRESSION/GUID_DEFINED 解压（LZMA-alone / EDK2 / Tiano / deflate），输出树与 blob |
| `acpi_find.py` / `acpi_extract.py` | ACPI 表定位与校验和筛选、按表抽取 |
| `aml_dev.py` | 直接扫 `5B 82` 找 Device、按包含关系嵌套（不会反汇编跑偏） |
| `dump_aml.py` / `x9_report.py` | 区间反汇编清单 + hex dump；生成交付物与对照文件 |
| `find_gpio.py` | GPIO 连接描述符（tag `0x8C`）枚举/解码 |
| `x9_find_tpad.py` | 全镜像搜 `TPAD / GXTP5100 / TPID` 及 `5B 82 … TPAD` |
| `x9_deliverables.py` | 汇总生成 `deliverables\` |

---

## 8. 已排除的路径（避免重复劳动）

1. **`.exe`**：未执行（刷 BIOS 程序，禁止运行），也未用来提取——ISO 路径已完全成功。
2. **ISO9660 目录树**：主卷与 Joliet 卷都是空的，内容全在 El Torito 硬盘镜像里。
3. **明文扫描**：`DSDT`/`APIC` 在 `.iso` 与 `.exe` 里 0 命中；`FACP` 的 7 处全是压缩载荷里的伪命中。
4. **LZMA 头格式**：`u32 解压长度 + 5 字节属性`（iasl 常见写法）在本包上解不出来；
   必须按 **`DataOffset` 从段起点算** + **LZMA-alone 帧**（5 属性 + u64 长度 + 原始流）。
5. **更老的 BIOS 版本**：不需要（1.09 已成功）；也没用 `web-access`/外网 ACPI dump。
6. **`.exe` 的 201 个内嵌 PE / 资源段**：未展开（不需要）。
