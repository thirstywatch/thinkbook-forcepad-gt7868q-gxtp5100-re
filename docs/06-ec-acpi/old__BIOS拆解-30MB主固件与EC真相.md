# BIOS 拆到底了：19 MB 外壳 → 30.88 MB 主固件 → 447 个模块

> 日期：2026-09-27　机型：ThinkBook 14 G6+ IMH（21LD）
> 物料：`NJCN67WW.exe`（12,790,536 B，2025-12-17）→ `isflash.bin`（19,205,640 B）

---

## 一、结论速览

| 问题 | 答案 |
|---|---|
| `isflash.bin` 是什么 | **不是裸 SPI 镜像**，是个 **EFI 应用外壳**（PE32+，Subsystem=10，FileAlignment=0x20，ImageBase=0）。真内容全在 `.reloc` 节（19,181,568 B，占 99.9%） |
| `.reloc` 里是什么 | Insyde 的 **`$_IFLASH_*` 容器**：`$_IFLASH_DRV_IMG`（外层，铺满整个 payload）→ 内含 `$_IFLASH_BIOSIMG`、`$_IFLASH_INI_IMG`、`$_IFLASH_BIOSCER`、PFAT 证书 |
| BIOS 镜像在哪 | `$_IFLASH_BIOSIMG` 声明 16 MiB（`0x01000000`），实体在 **payload+0x1E1170**（文件偏移 `0x1E69D0`），窗口 16 MiB |
| 主固件怎么装的 | 16 MiB 里 `bios16+0x2F8000` 那个 5.26 MB 的卷里，有个 **LZMA 压缩的嵌套 FV**（GUID `EE4E5898-…`，段长 `0x4F1C9F`） |
| **解压结果** | **5,184,647 → 30,883,968 字节**（与 LZMA 头声明 `0x1D74080` 完全一致）= 一个完整 FFS2 卷 |
| 解压后规模 | **447 个文件 / 389 个有名字 / 1660 个段** |
| 触控板驱动 | ✅ **`GoodixTpDxe`**（`F540704A-50B5-4BB6-93A8-377EA20F1030`，0xBDCE） |
| 触控板 ACPI | ✅ DSDT 里 **`_HID = "GXTP5100"`，`_CID = "PNP0C50"`** |
| 触控板芯片 | **Goodix GT7863 / GT7868Q**（驱动里 `GTPGetBasicProperties7863` / `…7868Q`） |
| 触控板固件载荷 | ❌ **不在 BIOS 里**，走 FMP capsule（`FmpDxeY750` / `FmpUpdateDxe` / `EsrtFmpDxe`） |
| EC 驱动 | ✅ **`CompalEcDxeDrv`**（0x2D96）+ **`CompalEcSmmDrv`**（0x708A）——ODM 是 **仁宝 Compal** |
| EC 固件 | ❌ **不在本包**，走 **`EcCapsuleDxe`**（capsule 单独投递） |
| 角度 / Hall / Hinge | ❌ 固件里**零命中**（`Hinge` / `LidAngle` / `LID_ANGLE` / `Hall` 全是 0） |
| 其他 | 触控板三供应商共存：Goodix + **Synaptics**（`SynaReflash`）+ **Cirque**（`FmpDxeY750` 的 PDB 路径） |

---

## 二、为什么这一步重要：我推翻了自己的一条结论

之前我写过 **"联想 BIOS 里没有 Goodix 代码 —— 在正确物料上依然成立"**。

**这条是错的。** 错的原因很具体：

- 之前搜的是 `isflash.bin` 的**压缩态**原始字节，字符串被 LZMA 压掉了；
- 主固件是 **5.18 MB → 30.88 MB（5.95:1）** 的压缩体，`Goodix` 这种长串根本不可能在压缩流里按明文出现。

解压之后：**`Goodix` 出现 12 次，全部落在 `GoodixTpDxe` 这个 48.6 KB 的完整驱动里。**

> 教训：**在对固件做字符串取证之前，必须先确认物料是不是压缩的。** 熵分析是最便宜的判据（主卷 0x500000–0x900000 区间熵 7.95，一眼就是压缩段）。

---

## 三、三层结构逐层拆解

### 第 1 层：`isflash.bin` 是 EFI 应用外壳

```
00000000  4D 5A ...                          "MZ"
000000C8  50 45 00 00 64 86 04 00 F0 00 22 20 "PE\0\0"  x86-64  4 节  OptHdr=0xF0
000000E0  0B 02 ...                          PE32+
```

节表：

| 节 | 文件偏移 | 大小 | 说明 |
|---|---|---|---|
| `.text` | 0x280 | 0x5240 | 小代码桩 |
| （无名节，名字全 0） | 0x54C0 | 0x2C0 | 全 0，占位 |
| `.xdata` | 0x5780 | 0xE0 | |
| **`.reloc`** | **0x5860** | **0x124B000（19,181,568）** | **全部内容** |

`Subsystem=10` = `IMAGE_SUBSYSTEM_EFI_APPLICATION`；`FileAlignment=0x20`、`ImageBase=0` —— 典型"外壳 PE"，不可执行，只是打包格式。

> ⚠️ 一开始我按"找 Intel Flash Descriptor"的思路走（找 `5AA5F00F`），**0 命中**——因为这里根本不是 SPI 转储，而是 Insyde 的容器。**判断容器类型的成本远低于沿着错误假设深挖。**

### 第 2 层：`$_IFLASH_*` 容器

`.reloc` 开头就是容器头：

```
payload+0x00  00 00 00 00 44 00 00 00 F0 A2 F8 A2 00 A3 08 A3 ...   ← 偏移表
payload+0x60  24 5F 49 46 4C 41 53 48 5F 44 52 56 5F 49 4D 47       "$_IFLASH_DRV_IMG"
payload+0x70  88 AF 24 01  88 AF 24 01  4D 5A ...                   长度 / 长度 / 嵌套 MZ
```

找到的全部标签（`$_` + 16 字节定长）：

| 标签 | payload 偏移 | 含义 |
|---|---|---|
| `$_IFLASH_DRV_IMG` | 0x60 | 最外层，`0x124AF88` 正好铺到 payload 末尾 |
| `$_IFLASH_BIOSIMG` | 0x1E1158 | **声明 16 MiB BIOS 镜像** |
| `$_IFLASH_BIOSIMG` | 0xBB0040 | 镜像内的副本（模块名目录：`__ACBP__` / `__KEYM__` / `_FIT_`） |
| `$_IFLASH_BIOSIMG` | 0xFB0040 | 再一份（与上一份**相隔正好 4 MiB，逐字节相同**） |
| `$_IFLASH_INI_IMG` | 0x11E1178 | **内嵌的 platform.ini**（与包外那份**不同**，大 ~500 B） |
| `$_IFLASH_BIOSCER` | 0x11F0298 | BIOS 签名证书 |
| `$_PFAT_CER_IMG__` | 0x11F03B8 | PFAT 证书 |
| `$_PFAT_HDR_IMG__` | 0x12243D8 | PFAT 头 |

读写格式（实测）：`[16 B 标签][DWORD][DWORD][载荷]`；`$_IFLASH_BIOSIMG` 的第二个 DWORD = 载荷长度（`0x01000000`），第一个 = 长度 + 8。

`[MULTI_FD]` 的语义也解出来了（`platform.ini` 自带文档）：
```
FD#XX=ID,[型号名],[BIOS 文件],[ME 文件],[INI 文件]
FD#01=ID,ILVR4,isflash.bin      ← 14 寸（本机）
FD#02=ID,ILVR6,tttt.bin         ← 16 寸，本包未附带
```

### 第 3 层：主固件是 LZMA 压缩的嵌套卷

16 MiB 镜像里第一层卷从 `bios16+0x41000` 开始（都是 4 KiB 对齐）。到 `bios16+0x2F8000`：

```
F FV_IMAGE    20BC8AC9-94D1-4208-AB28-5D673FD73486 sz=0x4F1CB7
  SEC GUID_DEF size=0x4F1C9F guid=EE4E5898-3914-4259-9D6E-DC7BD79403CF  doff=0x18  attr=0x1
                                                                        ↑ LZMA
```

压缩流（`payload+0x4D9220`）：LZMA 头 `5D | 00 00 00 01 | 80 40 D7 01 00 00 00 00`
→ props 0x5D、字典 16 MiB、**解压后 0x1D74080 = 30,883,968 B**。Python `lzma FORMAT_ALONE` 一次成功，长度分毫不差。

解压出来的就是**一整个 FFS2 卷**（`78E58C8C-3D8A-1C4F-9935-896185C32DD3`，`FvLength=0x1D74000`），第一个文件是众所周知的 **PEI APRIORI**（`FC510EE7-FFDC-11D4-BD41-0080C73C8881`）——这直接证明解析正确。

---

## 四、触控板：`GoodixTpDxe` 全解

这是本次对**触控板项目**最大的收获。驱动来源写在自己的代码路径里：

```
c:\minnowboard\Build\Vlv2TbltDevicePkg\RELEASE_VS2015x86\X64\Vlv2TbltDevicePkg\GtpUpdate\GtpUpdate\DEBUG\AutoG…
c:\minnowboard\edk2-platforms\Vlv2TbltDevicePkg\GtpUpdate\GoodixTouchpadFMPImpl.c
```

→ 从 **Intel MinnowBoard 的 `Vlv2TbltDevicePkg`** 移植（该包在 `edk2-platforms` 开源），核心文件 **`GoodixTouchpadFMPImpl.c`**。

### 4.1 芯片族与固件分体

```
GTPGetBasicProperties7863 run.      ← GT7863
GTPGetBasicProperties7868Q run.     ← GT7868Q（本机）
Get IC version 0x%x.  Get fw pid/vid  Get sensorID  Get cfgVer
```
固件分成两套**独立比对版本、独立刷写**的子系统：
```
image tp fw:%d.                      ← TP
image tf fw:%d.                      ← TF
<GTPCheckTFUpdate> get tf fw version failed   tf fw fw need update,file ver…
```

### 4.2 走 FMP（固件管理协议），从 EFI Capsule 取包

```
start install FMP protocol.        InitializePrivateData InstallProtocolInterface
FmpGetImage / FmpGetImageInfo / FmpGetPackageInfo / FmpSetImage / FmpCheckImage
Start to check bios pack EFI_CAPSULE_HEADER or not!      Bios add EFI_CAPSULE_HEADER!
FmpSetImage OsCapsuleHeaderSize:%d, BinaryImageOffset: %d
```

包格式（字符串即规格）：
```
Firmware package protocol: V%u
Fimware PID:%x%x%x%x        Fimware VID:%02X%02X%02X%02x
Firmware chip type:%02X     Firmware size:%u     Firmware subsystem num:%u
Subsystem type:%02X   Subsystem size:%u   Subsystem flash_addr:%08X
```

### 4.3 刷写流程与寄存器

```
enter pass through mode → start updating → erase flash → write flash
→ reload subFW → reset ic
```
关键寄存器：`0x0300`（update-mode 标志）、`0x0100`（写命令）、`0xB68A`（`GtTransmissionWrite`）、`0x2194`（4 字节读）。
`Read back 0x%x(0x%x) != 0xAA` —— 写完回读校验字节 **0xAA**（这也解释了我在固件镜像里到处看到 `AA` 的原因，是**擦除态魔数**，不是巧合）。

### 4.4 两条 HID 通道

```
hid.wCommandRegister  hid.wDataRegister  hid.wOutputRegister
hid.wMaxOutputLength  hid.wMaxInputLength  hid.wVendorID  hid.wProductID
GTPHIDWrite / GTPHIDRead / GTPI2CWriteAndRead
```
驱动**从触控板自己读 HID 描述符**来得知 command / data / output 寄存器地址。

> **对"主机为什么触发不了震动"的直接意义**：这台板子的触控板有自己的固件 + 自己的力/触觉子系统（TF），主机侧只有 HID 报文和一条 **vendor 命令通道**（Command/Data 寄存器 + pass-through 模式）。标准 HID Manual Trigger 不存在的现象，与"触觉由板内固件自治"是自洽的。**要触发，得走 vendor 通道**，而 vendor 通道的入口就在这个驱动里。

### 4.5 DSDT 一侧

`_HID = "GXTP5100"`，`_CID = "PNP0C50"`（标准 HID-over-I2C），带中断号与 I²C 资源。

---

## 五、EC：真相与下一步

固件里 EC 相关全部命中：

| 模块 | GUID | 大小 |
|---|---|---|
| **`CompalEcDxeDrv`** | 39C28A86-9097-48DA-B424-6C13E3D391FA | 0x2D96 |
| **`CompalEcSmmDrv`** | 39C28A86-9197-481A-B424-6C13E3D391FA | 0x708A |
| **`EcCapsuleDxe`** | C26B2DBB-83B2-4AF2-BBD7-D4558036DE11 | 0xD14A |
| `CompalEepromDxe` / `CompalEepromSmm` | C937B8BF-… / 0C8823D5-… | 0x130A / — |
| `CompalGlobalNvsDxe` | 03D56EEC-E196-4815-B91A-C4885A839043 | 0x872 |
| `CompalThermalDxe` / `CompalThermalToolSmi` | 076FBF50-… / DEEA4A6A-… | 0x9AE / — |

**要点：**
1. **ODM = 仁宝（Compal）**，不是 Quanta/Wistron。
2. `CompalEcDxeDrv` / `CompalEcSmmDrv` **几乎没有任何字符串**（纯代码）—— 说明 EC 命令协议要靠**反汇编**才拿得到。好在它们很小（11 KB / 28 KB），是 x86-64 PE，成本可控。
3. `EcCapsuleDxe` 里有一张 **8 字节标签目录**：`_AUTOPAD`、`_TBT_IMG`、`_ISH_IMG`、`$_MICROCODE_IMG`、`_IOM_IMG`、`_MGPHY__`、`_ME_IMG_`，函数 `FindCpHeader` / `H2OCpTrigger`。
   → **EC 固件走 capsule 投递，不内嵌在 BIOS 包里。** 这与 `platform.ini` 的 `[Region] EC=0` / `[UpdateEC] Flag=0` 完全一致，互相印证。

**所以"EC 固件在哪"的答案变了**：不在 BIOS 包，不在 BIOS 镜像，而是由 **Lenovo 的独立 EC capsule**（或 BIOS 运行时由 `EcCapsuleDxe` 接收）提供。

---

## 六、角度项目：一个明确的反向结论

在 30.88 MB 解压后的完整固件（447 个模块）里：

| 关键字 | 命中 |
|---|---|
| `Hinge` / `hinge` | **0** |
| `LidAngle` / `lid angle` / `LID_ANGLE` | **0** |
| `Hall` | **0** |
| `EmbeddedController` | **0** |
| `ECFW` / `EC_FW` / `EcFw` | **0** |

→ **BIOS 侧不存在任何"开盖角度"的处理逻辑。** 这把我之前的判断收紧了一步：角度信息（如果有）完全在 **EC 内部**，BIOS 只是通过 `LIDF` 之类的位读一个"开/合"布尔量。**要继续角度项目，只有两条路：拿到 EC 固件，或直接问 EC 要数据。** 前者现在要靠 `EcCapsuleDxe` + Lenovo 的 EC 包，后者要靠反汇编 `CompalEcDxeDrv` 拿到命令协议。

---

## 七、本次修正记录（自查，3 条）

| # | 错误 | 影响 | 修正 |
|---|---|---|---|
| 1 | **"联想 BIOS 没有 Goodix 代码"** | 差点让触控板项目放弃最有价值的一块物料 | 物料是压缩的；解压后 `Goodix` ×12，`GoodixTpDxe` 是完整驱动 |
| 2 | **LZMA GUID 打错 2 字节**（Data4 `9D 6E` 写成 `D6 9E`） | 首次搜索 0 命中，一度误判"没有压缩段" | 改正后立刻命中主卷 |
| 3 | **FFS 文件头字段错位 1 字节**（`IntegrityCheck` 是 2 字节，Type 应在 +18） | type/size/state 全错，解析在第二个文件就崩 | 修正后 447 个文件一次全解 |

另有 2 处小修正：`ITE` 在 DSDT 里的 6 次命中全是**假阳性**（来自 `WR**ITE**_OPCODE`、`**ITE**M`）；`AA` 是擦除态魔数而非数据。

---

## 八、可执行动作（按性价比排序）

| 优先 | 动作 | 为什么 |
|---|---|---|
| ★★★ | **反汇编 `CompalEcDxeDrv` / `CompalEcSmmDrv`** | 直接产出 **EC 命令协议**（端口 / 寄存器 / 命令码）。这是角度项目下一步最省力的一条 |
| ★★★ | **反汇编 `GoodixTpDxe` 里的 `GoodixTouchPadUpdate` / `GTPHIDWrite`** | 拿到触控板 **vendor 命令通道**的确切寄存器与报文格式 —— 触觉触发的前提 |
| ★★ | **找 Lenovo 的 Goodix 触控板固件 capsule** | 拿到 TP / **TF（力/触觉）子系统**固件本体 |
| ★★ | 拉 **`ty2/goodix-gt7868q-linux-driver`** | 社区已有 **GT7868Q** 的 Linux 驱动（含 report descriptor fixup），可直接对照 HID 报文 |
| ★ | 重找 NJCN68WW 下载链接做**差分**（本次 URL 404） | 68 版说明里有 `[Embedded Controller] Keyboard - Modify Copilot key function`，差分能定位 EC 交互改动 |
| ★ | 复原 Windows 安全设置 | **当前 VBS=0 / HVCI=0 / 驱动黑名单=0 仍是关闭态**，实验做完了，该复原 |

---

## 九、产物清单

目录：`bios/out/`

| 文件 | 内容 |
|---|---|
| `模块清单-389.txt` | 389 个具名模块（类型 / GUID / 大小 / 名字） + 无名字的大文件 |
| `固件树-447文件.txt` | 完整 FV/FFS/段 树 |
| `GoodixTpDxe.bin` | 触控板驱动（48.6 KB） |
| `CompalEcDxeDrv.bin` / `CompalEcSmmDrv.bin` | **EC 驱动**（下一步反汇编目标） |
| `EcCapsuleDxe.bin` | EC capsule 处理 |
| `FmpDxeY750.bin` / `FmpUpdateDxe.bin` | FMP 框架 |
| `SynaReflash.bin` | Synaptics 触控板刷写（说明本机触控板是多供应商） |
| `CompalEepromDxe.bin` / `CompalThermalDxe.bin` / `CompalGlobalNvsDxe.bin` | 仁宝 OEM 模块 |
| `DSDT-528KB.bin` | **BIOS 内的 DSDT**（528,582 B，含 GXTP5100 设备节点） |

中间产物：`bios/extract/payload_reloc.bin`（19.18 MB）、`bios16.bin`（16 MiB）、**`fw_decompressed.bin`（30.88 MB，主固件）**
工具：`uefi_scan.py`、`ffs_scan.py`、`fw_names.py`（本目录，可复用）
