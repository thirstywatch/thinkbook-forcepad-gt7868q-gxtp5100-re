# 第三方参考 · 出处链接

> **本目录不再存放任何第三方文件**（163 份第三方 wiki / 源码已在开源整理时移除）。
> 原因：**许可无法逐项确认**。所有需要的材料请按下面的链接自行获取。
> 本仓库中引用的第三方**结论**（如 AW86927 寄存器表、引脚定义）已写入 `method/` 与 `docs/`，属本项目自己的分析表述，不含第三方原文。

---

## 1. 官方固件 / 驱动（厂商渠道）

| 材料 | 获取渠道 | 说明 |
|---|---|---|
| **ThinkBook 14 G6+ IMH 触控板固件** | 联想官方支持 `https://pcsupport.lenovo.com/` → 输入机型 `21LD` → Driver & Software → **Touchpad Firmware** | 得到 `TB14P_GT7868Q_14030522_20240202.BIN`（161,628 B）。<br>**本机副本**：`C:\Windows\Firmware\*.BIN`（Windows 更新下来后在此） |
| **BIOS/EC 更新包** | 同上 → BIOS Update | 用于解出 `GoodixTpDxe` / `EcCapsuleDxe`。本机 BIOS `NJCN67WW` |
| **汇顶官方工具**（含 cfg 样本） | Goodix 官方 / 随联想驱动包分发 | `GoodixTouchpadTool.exe`、`tpcfgsid*.cfg` |
| **汇顶固件（LVFS 镜像）** | `https://fwupd.org/` · `https://github.com/linuxhw/firmware` | ★ **对照样本** `GT7936L_16753412.bin`（BERLIN 族真明文，用于"是不是代码"的四类反例标定） |
| **汇顶开源驱动/更新工具源码** | `https://github.com/goodix` | ★ 三个仓库：<br>`gdix_hid_firmware_update`（含 **`gt7868q/`** 与 **`gtx2/`** 两层）<br>`gtx8_driver_linux`<br>`fwupdate_for_berlin_linux` |
| **Surface 触觉固件**（对照用） | `https://support.microsoft.com/` · Surface 驱动包 | `SurfaceTouchpadHaptic_*_fw_img_v2.bin`、`CS40L25` 系列 |

> ### ★ 拿源码时务必连 `gtx2/` 一起拿
> 本项目曾漏掉 `gtx2/` 那一层，导致**一直拿不到官方命令表**。补上后一次就拿到了。

---

## 2. 芯片数据手册

| 芯片 | 渠道 |
|---|---|
| **AW86927FCR**（艾为触觉驱动） | 艾为电子官方 `https://www.awinic.com/`；公开镜像：TI E2E 社区附件 `AW86927FCR.PDF` |
| **AW86927 Linux 主线驱动 + 设备树绑定** | patchew.org（Fairphone 上游补丁组）· kernel.org 源码树 `drivers/input/misc/aw86927*` |
| **GT7868Q / GXTP5100** | 汇顶官方（多为 NDA）；公开可得信息来自上面三个开源仓库 |
| **TF100A**（钛方） | 钛方官方（未公开）；本项目按 STM32F1 类（Cortex-M3）兼容分析 |
| **CS40L25**（Cirrus，同构对照） | Cirrus Logic 官方 + Linux 主线源码 |
| **HMM 硬件维护手册**（本机 21LD） | 联想官方支持 → 文档 → Hardware Maintenance Manual |

---

## 3. 规范

| 规范 | 链接 |
|---|---|
| **HID Usage Tables (HUT) 1.5** | `https://usb.org/document-library/hid-usage-tables-15` |
| **HID over I²C** | `https://learn.microsoft.com/windows-hardware/drivers/hid/hid-over-i2c` |
| **Windows Precision Touchpad** | `https://learn.microsoft.com/windows-hardware/design/component-guidelines/touchpad-windows-precision-touchpad` |
| **★ Haptics implementation guide** | `https://learn.microsoft.com/windows-hardware/design/component-guidelines/input-haptics-implementation-guide` |
| **SPB（Simple Peripheral Bus）** | `https://learn.microsoft.com/windows-hardware/drivers/spb/` |
| **ACPI 规范** | `https://uefi.org/specifications` |
| **UEFI Firmware Update (capsule)** | `https://uefi.org/specifications` |

---

## 4. 同构项目 / 社区参考

| 项目 | 链接 | 价值 |
|---|---|---|
| **barryblueice / ESP32-Haptic-Precision-TouchPad** | `https://github.com/barryblueice/ESP32-Haptic-Precision-TouchPad` | ★ **标准 HID 触觉接口**的落地实现 + 两个 wiki（ESP32-PTP / haptic）。<br>⚠️ 它证明了"标准接口怎么做"，**没有**证明原装板可被主机触发 |
| **ESR / Blueberry GT7863 驱动实证** | 上述仓库的 `gt7863` 分支 | 同厂商芯片的第三方驱动实现 |
| **Linux `hid-multitouch` / `i2c-hid`** | kernel.org | 主机侧驱动行为 |
| **fwupd / LVFS** | `https://fwupd.org/` | 固件包公开分发渠道 |
| **PawnIO** | `https://github.com/ZenithDevs/PawnIO` | 签名内核驱动（SMBus / EC / MMIO） |
| **RWEverything** | `https://rweverything.com/` | ⚠️ 专有免费软件，**不可再分发** |
| **ACPICA iasl** | `https://acpica.org/downloads` | AML 反编译 |

---

## 5. ★ 明确未入库的第三方源码（2026-10-03 终审补齐）

> 终审时发现：本机另有 **93 份 C/H/CPP 第三方源码**散落在 5 个工区。
> 按"第三方源码不入库"的一致原则（与开头 163 份 wiki 的处理相同），**不拷贝，只列出处**。
> 它们支撑的**结论**已全部写进 `docs/00-软件逆向全书…md` 与 `method/`。

| 本机目录 | 是什么 | 出处 / 许可 | 它支撑了本项目哪条结论 |
|---|---|---|---|
| `ca4f-hunt/gt7868q-driver/` | Goodix GT7868Q Linux 驱动（GPL，Terry Wong 2024） | 公开仓库；作者自述在 **ThinkBook 16+ 2024 IMH** 上测试 | ★ **§19.30.1 推翻「描述符主机改不了」这条定案** 的关键证据（`report_fixup` 针对本机 PID `0x01E9`）|
| `ca4f-hunt/gdix/goodix_advance_touch_platform/` | 汇顶 HID over I²C 平台层 | 汇顶 SDK（NDA 风险） | §19.32.6 汇顶官方固件更新工程的**身份**（一手字符串）|
| `ca4f-hunt/gdix/gtx8_driver_linux/` · `gt9xx_driver_android/` · `fwupdate_for_berlin_linux/` | 汇顶 gtx8/gt9xx 开源驱动 + Berlin 刷机工具 | `https://github.com/goodix` | cfg 格式、刷机流程、官方校验和算法 |
| `touchpad-lab/poc/gdix-hid-fw/` | `gt7868q` + `berlin_a` 固件更新工程源码 | 汇顶内部工程（**含 PDB 路径泄漏，见 §19.24.3**） | ★ §19.19.1–19.19.4 **官方命令表**与 `SetBasicProperties()`；§19.24.1 `CfgImage::load` |
| `touchpad-lab/poc/gdix-official-missing/` | **`gtx2/` 那一层**（补上后才拿到官方命令表） | 同上 | ★ §19.19.2 官方命令表原文；§19.19.3 flash 命令真格式 |
| `touchpad-lab/poc/gtx8-official/` | gtx8 官方源码（`goodix_cfg_bin.c/h`） | 同上 | cfg 二进制打包格式 |
| `surface-vs-mine/blueice-gt7863/` | 蓝莓 GT7863 驱动（`goodix_i2c.c` 等） | barryblueice 项目 | §19.32.3 / §19.33.7 同构方案实证 |
| `surface-vs-mine/aw86927/` · `demo/` | AW86927 Linux 驱动 + 回放 demo | 艾为 / 开源社区 | §19.15.3 / §19.16.3 TRIG 边沿→波形映射 |
| `surface_fw/cs40l25_*_fw_img.c` | Cirrus CS40L25 **固件镜像**（C 数组形式） | Cirrus Logic，属厂商固件二进制 | 同构对照：主机侧波形库下发 |
| `probe/bh/` · `probe/barry-haptic/Hacking/` | 蓝莓项目的 HID 描述符 hack / 强度测试 | barryblueice 项目 | §19.26.10「标准 HID 触觉接口」的可行性边界 |
| `probe/pio/PawnIO__src__*/` | PawnIO **内核驱动源码** | `https://github.com/ZenithDevs/PawnIO` | §19.33.6 PawnIO 原语清单（决定 W2 路线是否成立）|
| `touchpad-lab/pawnio/` | PawnIO 已签名模块（`.p`，RSA-4096） | 同上，**签名二进制** | §19.33.13 W2 定案；§19.33.17 签名者黑名单实锤 |
| `touchpad-lab/rwe/` | RWEverything（`Rw.exe` + `RwDrv.sys`） | `https://rweverything.com/` **专有、不可再分发** | §4.2.4 SMBus 强结论；§19.37 PCI 配置空间实测 |

> **`touchpad-lab/driver-patch/`（本项目自己写的 UEFI DSDT 补丁）已入库** → `tools/bios/`
> **`fw-touchpad/goodix-tool/spb-client/`（本项目自己写的 SPB 客户端草稿）已入库** → `tools/bios/`

---

## 6. 本项目对这些材料的使用方式

| 用法 | 说明 |
|---|---|
| **引用结论，不复制原文** | 如 AW86927 的引脚定义、寄存器地址，已用本项目自己的表格重写在 `method/09-memory-map.md` |
| **给出获取方式，不打包文件** | 见 `reproduce/DATA-INVENTORY.md` |
| **第三方源码不入仓库** | 包括 GPL 的 Linux 驱动源码 —— 需要者请按链接自行获取 |

> ⚠️ **如果你要二次分发本仓库内容，请先确认上面每项的许可。**
