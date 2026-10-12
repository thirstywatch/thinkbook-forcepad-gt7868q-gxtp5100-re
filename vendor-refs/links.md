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
| **★★ `nwkyz/goodhaptic`** | `https://github.com/nwkyz/goodhaptic` | ★★★★ **本项目迄今找到的唯一一个"host 侧触觉控制真正跑通"的开源实现**（Linux，C + GTK4 + systemd daemon，GPL-3.0，2026-07 建）。<br>目标 **Goodix GXTP5100，HID `27C6:01E7`**（ThinkBook 16 G8+ IPD）—— 与本机 `27C6:01E9` **同族不同代次**。<br>★ 给出 `0x09 = Haptics(0x0E/0x23) Intensity 0–100` 的**可用实现**（本机同 usage 确实存在，已实测）<br>★ 独立复现"只写不可读"（`HIDIOCGFEATURE` 对 0x08/0x09 无效）<br>★ 独立印证"写入易失"（其"开机恢复"= daemon 每次开机重写，非写 flash）<br>★ 独立把 Report `0x0D`(0xC4) 标为"固件命令写入入口"、`0x0E` 标为"Vendor 双向通道"<br>⚠️ **它也没有解决"主机主动触发"** —— 全部是 SetFeature 偏好旋钮，无触发命令<br>→ 本项目对照文档：`docs/08-findings/2026-10-08-外部项目评估-goodhaptic独立交叉验证.md` |
| **★★★ `glutamatt/sensel-touchpad-linux`** | `https://github.com/glutamatt/sensel-touchpad-linux` | ★★★★ **与 goodhaptic 并列的第二个"host 侧触觉偏好可调"开源实现**（Linux，纯 Python 3 stdlib，MIT）。目标 **Sensel 触觉板**（vendor `2C2F`，ThinkPad X1 Carbon Gen 12 / P1），**不同厂商**。<br>★ 暴露的旋钮结构与本项目**同构**：**「Haptic enabled ON/OFF 主开关」+「Haptic intensity 0–100%」** —— 与 `0x09`（0=静音 / 100=最强）几乎一一对应<br>★ 协议走 **HID Report ID `0x09`**（厂商自定义管道）：`[cmd_hi, cmd_lo, size]` 读 / 写寄存器 + `[ACK, reg, len, data…, checksum]` 回<br>★ **"无已知 commit-to-flash 寄存器"** ⇒ 用 udev rule + boot service + systemd-sleep hook **反复重放配置**（**与 goodhaptic 的 daemon 策略、本项目 B12 完全同构**）<br>⚠️ **也没有 host-initiated 触发**；它的"intensity"是偏好旋钮<br>→ ★ 第三个独立样本，进一步确认**"强度/开关是 device-initiated 偏好，触发不是" 是全行业现象** |
| **`codgician/elan-haptune`** | `https://github.com/codgician/elan-haptune` | ELAN 触觉板调参（Rust，0★，新）。同构思路的另一厂商样本，可作"旋钮命名"旁证 |
| **`larixer/zenbook-touchpad-i2c`** | `https://github.com/larixer/zenbook-touchpad-i2c` | ★ ASUS ZenBook **FTE1001** I2C-HID 协议逆向（MIT，2016）。**方法论同构**：卸载驱动 → `i2c-dev` 用户态直读 → 解 Windows 驱动命令序列。<br>★ 其描述符里 **vendor Feature Report `0x0D/0xC5`、`0x0C/0xC6`、`0x0B/0xC7`** 与本项目 Col02 **完全同名同页**（`0xFF00/0xC5`、`0xC6`、`0xC7`）⇒ **汇顶系 vendor 报告 ID 分配是跨代/跨厂商的行业惯例**，强化 B13"vendor 通道是家族/行业级"的判定<br>★ 它的 `05 00 3D 03 …` = **SET_REPORT(Feature, RID 13)**，与本项目 `0x0D` 用法同型 |
| **`waynehuang2022/fwupd_forcepad`** | `https://github.com/waynehuang2022/fwupd_forcepad` | fwupd **forcepad 插件**草稿（C，2022，3 commit，0★，已停更）。与已登记的 `fwupd/goodix-tp` 同源方向，价值低于后者 |
| **`ty2/goodix-gt7868q-linux-driver`** | `https://github.com/ty2/goodix-gt7868q-linux-driver` | ★★ **本项目早已引用的那个 GT7868Q 驱动**（92★，2024-05 建，**2025-08 仍在更新**）<br>⇒ 本次检索确认其**就是** `ca4f-hunt/gt7868q-driver/` 的公开上游（见 §5 第 1 行）<br>★ 其 `local-overrides.quirks` 注明已适配 **2025 ThinkBook 16 G7+ IAH** ⇒ 同族机型持续有人维护 |
| **`thirstywatch/thinkbook-forcepad-gt7868q-gxtp5100-re`** | `https://github.com/thirstywatch/thinkbook-forcepad-gt7868q-gxtp5100-re` | ⚠️ **这就是本项目自己的公开档案仓库**（描述逐字为"ThinkBook ForcePad 触觉逆向档案：汇顶 GT7868Q / GXTP5100 触控板主机控制追踪"）<br>建库 `2026-10-03`，末次推送 `2026-10-05`，Apache-2.0，语言标 `ASL`<br>⇒ 检索时命中自己 ⇒ **未发现任何第三方项目引用/复现本项目**（0 fork / 0 issue / 1 star）|

> **2026-10-08 再检索结论**：GitHub 上与本项目**同题材**的独立项目总数仍是**极小**。
> 真正实现"host 侧触觉控制"的仅 **2 个**：`nwkyz/goodhaptic`（Goodix）与 `glutamatt/sensel-touchpad-linux`（Sensel）。
> **两者策略完全一致**：写一个 0–100 的 intensity feature report + 开机重放补偿易失；
> **两者都未实现 host-initiated 触发**，且都明确声明"无已知落盘寄存器"。
> ⇒ 本项目"**只暴露强度/阈值偏好、不暴露触发指令**"的结论，**第三方样本从 2 个升到 4 个**（+Newton +Sensel）。

### 4b. ★★★★★ 第四轮补充：`barryblueice/ESP32-Haptic-Precision-TouchPad`（**唯一实现 host-initiated 触发**）

| 项目 | 链接 | 价值 |
|---|---|---|
| **★★★★★ `barryblueice/ESP32-Haptic-Precision-TouchPad`** | `https://github.com/barryblueice/ESP32-Haptic-Precision-TouchPad` | **本项目迄今找到的唯一个"主机主动触发 + 强度/阈值全可调"的完整实现**（ESP32-S3 + **Surface Laptop Studio 1964 的 Synaptics 触控板**，2026-04/08 活跃）。<br>⇒ **它是"外围替代"路数**：把整块触控板拆下来接到自己的 MCU 上，**绕开原厂 host 通道**，直接对触控板板的 I²C 从设备发命令。<br>★ 关键：haptic engine = **`CS40L25`（Cirrus）** —— **本项目 `vendor-refs` 早已登记的同构器件**（见 §1 第 33 行、§5 的 `surface_fw/cs40l25_*_fw_img.c`）<br>★ `Hacking/` 目录里有 **3 份 CS40L25 触觉测试源码**（本项目的直接参照）：<br>　· `cs40l25_rom_test.c` — ROM/BHM 模式按固定间隔发 `BSP_DUT_TRIGGER_HAPTIC_POWER_ON`（**最简单的"主机触发"**）<br>　· `cs40l25_surface_fw_test.c` — 上 RAM 固件后**依次触发 waveform 1..4**（`update_haptic_config(0)` → `enable_haptic_processing(true)` → `trigger_haptic(waveform, 50ms)`）<br>　· `cs40l25_haptic_strength_test.c` — ★★ **压感阈值 + 触发 + 换波形**（commit 原文：`压感阈值与触发支持，更换触发对应的waveform`）<br>★★ 它揭示的触发机制：**「MBOX1 全长波形」vs「MBOX2 超时截断」** 两种触发路径（`duration_ms = 0` = 跑完整波形；`= 20/48/64/80/96ms` = 到点截断）—— 这正是**"主机决定波形 + 主机决定时长"**，即本项目最想要的 `Manual Trigger` 语义<br>★ 它还补了一段**汇顶无关但同构**的知识：Synaptics RMI4 的 **"Magic Package"**（`00 3f 03 0f 23 00 04 00 0f 01`）用于 Mouse Mode ↔ PTP Mode 切换（出处 `coolstar/crostouchpad4-synaptics` 的 `rmi.c`）<br>⚠️ **代价**：它的做法需要**物理替换触控板 + 自研 MCU 板**，且**明确警告"用错型号会导致驱动失效或短路永久损坏"** ⇒ **本项目不可照搬**（我们的目标是"原装板、原厂通道、主机侧软控制"）<br>→ ★ **但它的触发常量（波形编号 1–4、时长 50ms、MBOX1/MBOX2 区分）是本项目逆向 `0x0D`/`0x0E` 通道时最有价值的量纲参照** |

> **★ 四轮检索总账**：GitHub 上与本项目同题材的独立项目 = **5 个**（本项目 / Newton / goodhaptic / sensel-touchpad-linux / ESP32-Haptic）。
> **其中 4 个**（前三 + 本项目）**全都只能调"强度/阈值偏好"，无一实现 host-initiated 触发**；
> **唯一实现触发的第 5 个**（ESP32-Haptic）**是靠"换掉原厂主机通道、自己当主机"达成的** ——
> ⇒ **"原装板 + 原厂通道 + 主机主动触发"仍是无人做到的空缺**，本项目若做到即为**首个**。

---

## 4c. 2026-10-10 第五轮（广撒网）新增条目

> 完整筛查见 `docs/08-findings/2026-10-10-GitHub广撒网-硬件逆向与I2C与固件改写工具筛查.md`
> （19 组关键词；筛出 8 个"有用"，其余 90% 与本案无关）

**★★★ 必读（方法论文本模板 / 直接工具）**

| 项目 | 链接 | 价值 |
|---|---|---|
| `schlarpc/elgato-cam-link-4k-firmware-re` | `https://github.com/schlarpc/elgato-cam-link-4k-firmware-re` | ★★★★★ **本案要产出东西的完整孪生范例**：vendor HID 协议 + SPI flash 布局 + 固件格式 + 更新路径 + **自研刷写工具** + 安全分析。同作者 `schlarpc/shure-mv7-firmware-re` 亦为 "vendor HID 控制台 + 固件更新协议" 同型 |
| `airbus-seclab/cpu_rec` | `https://github.com/airbus-seclab/cpu_rec` | ★★★★★ **从任意二进制识别 CPU 指令集** ⇒ 可直接用于**独立验证 C3 结论（GT7868Q = 8051/Turbo51）** |
| `goodix-fp-linux-dev/goodix-fp-dump` | `https://github.com/goodix-fp-linux-dev/goodix-fp-dump` | ★★★★★ **同厂商（Goodix）主机↔IC 私有协议全套 + 固件 dump** ⇒ 可对照本案 `0x0E 20` 组包方式。配套 `goodix-fp-linux-dev/goodix-firmware`（厂商固件样本库） |
| `DatanoiseTV/practical-reverse-engineering` | `https://github.com/DatanoiseTV/practical-reverse-engineering` | ★★★★ 实用逆向手册，**含 8051 固件章节**（本案芯片正是 8051） |
| `microsoft/hidtools` | `https://github.com/microsoft/hidtools` | ★★★★ **微软官方 HID 工具**（Windows）；本案大量用 `HidP_GetValueCaps`/`HidD_SetFeature`，此为权威高层参考 |
| `quarkslab/binbloom` | `https://github.com/quarkslab/binbloom` | ★★★★ 裸二进制固件分析（本案加扰固件适用） |
| `REhints/efiXplorer` | `https://github.com/REhints/efiXplorer` | ★★★ UEFI 固件分析/逆向的 **IDA 插件与 loader**（本案 UEFI 胶囊分析可深入） |
| `FrameworkComputer/EmbeddedController` | `https://github.com/FrameworkComputer/EmbeddedController` | ★★★ **业界唯一完整开源笔记本 EC 固件** ⇒ 本案 4MB EC 反汇编的唯一可对照源码 |

**★★ 触控板固件改写（直接同题材）**

| 项目 | 链接 | 价值 |
|---|---|---|
| `ayufan-rock64/pinebook-pro-keyboard-updater` | `https://github.com/ayufan-rock64/pinebook-pro-keyboard-updater` | ★★★ **主机侧给触控板刷固件**的完整实现 |
| `cirque-corp/chromeos_cirque_fw_update` | `https://github.com/cirque-corp/chromeos_cirque_fw_update` | ★★★ **厂商（Cirque）自己写的**触控板固件更新器 ⇒ "落盘序列"的官方答案所在处 |
| `rahlquist/elan-touchpad-diagnostics` | `https://github.com/rahlquist/elan-touchpad-diagnostics` | ★★★ 竞品 ELAN 触控板"**固件能力边界**"分析（Lenovo Yoga Pro 9） |
| `radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion` | `https://github.com/radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion` | ★★★ **给消费设备固件加功能**的完整案例 |
| `h2o64/goodix-parcel-patcher` | `https://github.com/h2o64/goodix-parcel-patcher` | ★★ **改 Goodix 二进制 blob** 的直接案例 |
| `mgottschlag/focaltech-tools` | `https://github.com/mgottschlag/focaltech-tools` | ★★ 竞品 FocalTech 触控板逆向工具 |
| `anarsoul/pbtp_fw_writer` · `coolstar/crostouchpad4-synaptics` | 见仓库 | ★★ 前者为同类刷写器；**后者是 `Hacking/README.md` 里 RMI4 "Magic Package" 的出处** |

**★★ I2C / 硬件协议工具（⚠️ 仅在"转向物理介入"时启用，本案当前路线不需要）**

`geo-tp/ESP32-Bit-Pirate`（5962★，全协议 Web CLI）· `hydrabus/hydrafw`（452★）· `tigard-tools/tigard`（882★）· `nofeletru/UsbAsp-flash`（1395★）· `bigbigmdm/IMSProg`（701★）· `osresearch/spispy`（416★，**SPI flash 仿真+监视**）

**索引级**：`hexsecs/awesome-embedded-security`（64★）· `koutto/hardware-hacking`（620★）· `f3nter/HardBreak`（493★）· `voidstarsec/hw-hacking-lab`（265★）

**HID 库**：`libusb/hidapi`（2283★）· `signal11/hidapi`（2537★）· `todbot/hidapitester`（383★，**现成的"某 RID 能否读写"排查器**）· `mikeobrien/HidLibrary`（630★）

**⚠️ 本轮确认的"无现成工具"缺口**：`8051 disassembler` 全 GitHub 只有 1 个（5★，很弱）⇒ **本案 8051 逆向基本无现成工具可用**。

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

---

## §X 真实 Goodix gtx8 `cfg` 包样本（2026-10-05 第九轮，**只登记出处，二进制不入库**）

> 用途：读取官方 `goodix_cfg_bin` 结构（`pkg_const_info` + `pkg_reg_info`）与**寄存器映射**；
> 已用官方解析器读通 **5 份**（全部 `ic_type='Berlin'`、`hw_pid='9916*'`、`cfg_type=0x01`、`pkg_num=1`）。
> **关键结果**：这 5 份里 `x_res_offset` / `y_res_offset` / `trigger_offset` **全部为 0** ⇒ 厂商不填这三个字段。
> **寄存器映射**（5 份一致）：`cfg_send_flag=0x4034 · version_base=0x4014 · pid=0x4022 · vid=0x402A ·
> sensor_id=0x402F · cfg_addr=0x96F8 · esd=0x4166 · command=0x4160 · coor=gesture=fw_request=0x4180 · proximity=0x4182`
> —— 其中 **`0x96F8` / `0x4160` / `0x4014` 与本机 GT7868Q 的官方常量逐位一致**（第四条独立来源，且跨代）。

| 仓库 | 路径 | 文件长 |
|---|---|---:|
| `xiaomi-mediatek-devs/android_kernel_xiaomi_mt6877`（另见 crdroid / various forks） | `firmware/goodix_cfg_group_m16_TM.bin.ihex` | 1421（Intel HEX 文本） |
| 同上 | `firmware/goodix_cfg_group_m16_GVO.bin.ihex` | 1421（Intel HEX 文本） |
| `rahulsnair/proprietary_vendor_motorola_cybert_bak`（另见 Motorola-MT6897-Devs 同名仓库） | `proprietary/vendor/firmware/goodix_cfg_group.bin` | 1729（**Git LFS**） |
| `JoseMCC0705/vendor_motorola_dubai` | `proprietary/vendor/firmware/csot_goodix_cfg_group.bin` | 1701 |
| `yuanxing109/android_vendor_xiaomi_manet` | `proprietary/odm/firmware/goodix_cfg_group_manet.bin` | 1601 |

**取回方式（沙箱内 `raw.githubusercontent.com` 不通，`api.github.com` 通）**
- 普通文本文件（`.ihex`）：`GET https://api.github.com/repos/<owner>/<repo>/contents/<path>` → 取返回 JSON 的 `content`（base64）→ 解码；Intel HEX 再按 `:LLAAAATT…` 还原二进制。
- **LFS 文件**：`contents` 只返回 `version https://git-lfs.github.com/spec/v1 / oid sha256:… / size N` 指针；
  改走 **`https://media.githubusercontent.com/media/<owner>/<repo>/HEAD/<path>`** 可拿到真实字节。
- 解析脚本：`tools/firmware/lab__r10_2_api_fetch.py`。

---

## §XI 同一批 cfg 包的第二用途：**「已知答案」样本**（2026-10-05 第十二轮）

> 用途：既然"再找一台 GT7868Q"要不到**描述符**，就改用**答案已知**的样本 ——
> 这 3 份裸 `.bin` 各代表一块**公开可查分辨率的手机面板**，于是可以直接检验
> "**Goodix cfg 里到底有没有 X/Y 坐标量程、值是不是'点数'**"。
> **结果（见 `docs/08-findings/2026-10-05-触控板底层联动链-完整定案.md` §三十）**：
> 三块板各自在自己的 cfg 数据里命中**真实分辨率**（moto cybert 1220×2712 · moto dubai-CSOT 1080×2400 · xiaomi manet 1440×3200），
> 且 dubai 与 manet 在 `cfg数据+0xA0` 处**逐字段对齐**（X/Y 随板变、`140/30/40/60/80` 五个常量跨板全等）。
> ⇒ **"X/Y 是相邻一对 u16、值是坐标点数"这条语义拿到跨代独立证据**。

| 本轮回溯用到的 3 份（**同一批、二进制仍不入库**） | 对应真实面板 | 在 cfg 数据中的位置 |
|---|---|---|
| `rahulsnair/proprietary_vendor_motorola_cybert_bak` → `goodix_cfg_group.bin` | moto cybert **1220 × 2712** | `+0xB8`（1 次） |
| `JoseMCC0705/vendor_motorola_dubai` → `csot_goodix_cfg_group.bin` | moto dubai（CSOT）**1080 × 2400** | `+0xA0`、`+0xB8`（2 次） |
| `yuanxing109/android_vendor_xiaomi_manet` → `goodix_cfg_group_manet.bin` | xiaomi manet **1440 × 3200** | `+0xA0`、`+0xB8`（2 次） |

> ⚠️ **同一批数据给出的警告**：手机侧是 **u16LE**、本机 GT7868Q 侧是 **u16BE**，且 cybert 那一段**多插入 3 字节**
> ⇒ **跨代/跨机型"按偏移直比"仍会产假字段**，不要把手机侧的相对偏移直接搬到本机。
