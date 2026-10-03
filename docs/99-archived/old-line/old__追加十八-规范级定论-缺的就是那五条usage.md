# 追加十八 —— 规范级定论：缺的就是那五条 usage（含微软原文）

> 日期：2026-09-28 · 全部来自一手规范（USB-IF HUT 1.5 / HUTRR111 / 微软 Input Device Haptics Implementation Guide / Precision Touchpad Tuning）
> 完整报告：`<LAB>\GXTP5100-HID-usage-report.md`（4 张对照表 + 全部可点来源）

---

## §0 一句话

> **这不是驱动或 API 层面的限制，而是「HID 描述符缺 usage」级别的限制。**
> **在纯软件、不改固件的约束下，主机主动触发震动对这块板 —— **在 HID 协议语义上不可能**。**
> **缺的决定性一条是 `0x0E/0x21 Manual Trigger`（必须是 **OUTPUT** 报表）：没有它，主机在协议上**根本没有"现在震动"这句话可说**。**

---

## §1 悬置项的官方答案（HUT 1.5 一手）

| usage | 官方名 | 出处 | 含义 |
|---|---|---|---|
| **`0x0D/0x55`** | **ContactCountMaximum** | HUT 1.5 §16.6，表中第 `55` 行 `SV` | "maximum number of concurrent contacts a digitizer is capable of detecting" |
| **`0x0D/0x59`** | **PadType** | HUT 1.5 §16.5，表中第 `59` 行 `SF` | ★ **"When set, the touchpad is non-depressible (pressure-pad); when clear, depressible (click-pad)"** |
| **`0x0D/0x52`** | **DeviceMode** | HUT 1.5 §16.7 | 第三个**不同**的 usage（Linux 内核里叫 `HID_DG_INPUTMODE`） |
| **`0x0D/0xB0`** | **ButtonPressThreshold** | ★ **HUT 1.5 表 16.1 逐字行：`B0 ButtonPressThreshold[78] DV 16.5`**；参考文献 `[78] HUTRR111, TouchpadButtonPressThreshold, 2022` | 见 §1.2 |

> ⚠️ 注意：Linux 内核把 `0x59` 记作 `HID_DG_BUTTONTYPE`，而 **HUT 1.5 的规范名是 `PadType`** —— 同一个 usage，两个名字。

### 1.2 `0x0D/0xB0` 的官方定义（HUTRR111 原文）

**HUTRR111《TouchpadButtonPressThreshold》**（2022，Approved 5-0，微软 Matthew Williams 提，Pages Affected: Digitizer `0x0D`）：

> "The required pressure for a user to apply to a touchpad to report a 'button press'. System-configurable to suit user-preference. **Default units are grams.**"

**⇒ 这个 usage 确实存在（不是 RFC 作者的臆造）。但 **本机没有它**（caps 里不存在）。**

---

## §2 ★ 两个子代理在一处冲突，我的裁定

`RID 2` 应答 = `02 15`，含两个 4 bit 字段（`0x59 PadType` + `0x55 ContactCountMaximum`）。**两个子代理给出了相反的位序：**

| | 低 4 位 | 高 4 位 | 结果 |
|---|---|---|---|
| 子代理 B（二进制解读） | `5` = **ContactCountMax** | `1` = **PadType** | **两者都合规**（微软要求 CountMax 3–5；PadType=1 = 非按压式压感板）✓ |
| 子代理 A（usage 语义） | `5` = PadType | `1` = CountMax | **两者都不合规**（CountMax=1 < 3；PadType=5 不在微软定义的 0/1/2）✗ |

**⇒ 我倾向 **B**，理由是决定性的：**
1. **本机 Col02 里有微软 PTP 认证 blob（PTPHQA = Precision Touchpad Hardware Quality Assurance）** ⇒ **这是一台通过了微软精密触控板认证的设备**，不可能带着两处规范违规出厂
2. B 的读法下两个字段**都合规**，且 `PadType=1 = 非按压式压感板` **与物理事实完全吻合**
3. 项目已独立确认"本机是压感板 + device-initiated 触觉"

**⚠️ 但 A 的依据是 caps 的声明顺序（`0x59` 在 `0x55` 之前），这也不能忽略 —— 且本机描述符**确有已知不规范处**（第 607 字节 `0x15` 应为 `0x25`，正落在 `rid=9` 的 Logical Maximum 上）。**
**⇒ 要彻底定案，需要**原始报告描述符**（`I2C 0x2c:0x0021`，项目 `vendor/wiki` 记录过已读到过）。这是唯一还缺的一块拼图。**

---

## §3 ★★★ 决定性原文：`rid=9` 那条路被**规范原文**否掉

我们唯一的触觉旋钮是 `0x0E/0x23`（RID 9，**feature**）。微软规范原文：

> "This SET_FEATURE report specifies the user's preference for the intensity of the haptic feedback **for button press and release**. **It does NOT apply to the intensity of any host-initiated feedback**, if supported by the device."

**⇒ 这不只是被我们的实验否掉（`追加十五`），而是被**规范原文**否掉：**
**`rid=9` 按定义只管"按下/抬起"那条设备自决的路径，与主机发起的反馈无关。**

**⇒ 而且微软对 device-initiated 设备的规定是：**
- **允许（不强制）** 暴露两个旋钮：`0x0E/0x23` Haptic Intensity（放在 `0x0E/0x01 SimpleHapticsController` **子集合**内，该集合内**禁止**出现 `0x20/0x21`）、`0x0D/0xB0` Button Press Threshold（放在**触控板顶集合**，**禁止**放进 SimpleHapticsController）
- 原文：**"Both of these feature reports are mandatory if the touchpad also supports host-initiated haptic feedback."** ⇒ **只有加了 host-initiated，这两个才变强制**

---

## §4 ⇒ 缺的到底是什么（按决定性排序）

| # | 缺的 usage | 官方类型 | 官方要求 | 我们 |
|---|---|---|---|---|
| **1** | ★ **`0x0E/0x21 Manual Trigger`** | **OUTPUT** | **Mandatory** | ❌（**Col02 `Out=0`**；全设备唯一的 output 是 Col04 的 vendor `0xFF00` RID14） |
| 2 | `0x0E/0x10 Waveform List` | FEATURE | Mandatory | ❌ |
| 3 | `0x0E/0x11 Duration List` | FEATURE | Mandatory | ❌ |
| 4 | `0x0E/0x23 Intensity` 的 **OUTPUT** 形态 | OUTPUT | （支持 host-initiated 时的形态） | ❌（我们只有 feature 形态 = "对所有波形生效的偏好旋钮"） |
| 5 | `0x0D/0xB0 Button Press Threshold` | FEATURE | 加 host-initiated 后变强制 | ❌ |

**★ 第 1 条是最硬的**：HUT 1.5 §17.1 里 `0x0E/0x21` 的官方类型就是 **`Output`**，定义原文 = **"Ordinal in the WaveformList to trigger immediately"**；微软列为 Mandatory："Waveform to fire as explicit command from the host"。
**⇒ 没有它，主机连"现在震动"这句话都没有语法可说。**

---

## §5 两处互证 + 一处纠正

| 项 | 内容 |
|---|---|
| **互证 1** | LKML RFC 作者 Rong Zhang 的设备描述符**与本机 RID 9 结构完全一致**（`0x0E/0x01` Logical → `0x0E/0x23` → `0x85 0x09` RID 9 → Feature），且他确认 Windows 设置里能看到 "Touchpad feedback → Intensity" ⇒ **本机 `rid=9` 就是 device-initiated 的 Haptic Intensity，能调档、不能触发** |
| **互证 2** | RFC 原文解释了我们"读 feature 拿到垃圾/`0xEE`"的现象：**"getting the feature report returns garbage data … which makes some sense as the implementation guide only requires SET_FEATURE support"** ⇒ **读不到 ≠ 坏了**（与 `追加十七` §2/§3 一致） |
| **一处纠正** | RFC 里把第二个旋钮写成 `ClickForceSensitivity` 是**作者笔误**。按微软《Precision touchpad tuning》原文：`ClickForceSensitivity` ↔ **Button Press Threshold (`0xB0`)**；`FeedbackIntensity` ↔ **Haptic Intensity (`0x0E/0x23`)** |

---

## §6 诚实标注的不确定点

| 项 | 状态 |
|---|---|
| 本机**是否有** `0x0E/0x01 SimpleHapticsController` 集合 | **无法从 caps 确认** —— `desc_gxtp5100&co.bin` 是 preparsed data（头部 `HidP KDR`），`hid_devices.json` 的原始描述符为 `null`。**只能确定 RID 9 是 feature 而非 output**，这已足够支撑"它不是主机触发通道" |
| caps 里若干退化乱码行（如 Col02 `RID=71 page=71 Cnt=13`） | 判为探测脚本缓冲区问题，**未据此下结论** |
| `0xFF00` 的 `0xC4/C5/C6/C7` | **官方表里未找到**（FF00–FFFF 即 Vendor-defined 区）。`0xC5` 的 256 B 与微软 PTP certification blob 高度对应，但 page 不同（`0xFF00` vs `0xFF`），**仅作观察** |
| Col04 厂商通道（`0xFF00` RID14，65 B 双向） | 未探测（硬要求不碰设备）；作为"可能但不通用"列出 |

---

## §7 最终判定

> **在纯软件、不改固件的约束下：**
> **主机主动触发这块板的震动，在 HID 协议语义上不可能。**
> **唯一符合微软规范、且能通用的路，是设备侧新增 host-initiated 描述符 —— 而那等于改固件/描述符，与"不改固件"的约束冲突。**

**⇒ 因此"纯软件 + 通用 + 震动反馈"这个组合，对 GXTP5100 这一支的最终形态只能是：**
1. **能力探测**（读描述符判断 `0x0E/0x21` + `0x0E/0x10/0x11` 是否存在）
2. **支持的机型**（如 Surface Laptop 8）⇒ 走 `InputHapticsManager`，**任意时机、任意波形、可连续**
3. **不支持的机型**（如本机）⇒ 降级为**强度调节**（`rid=9`，规范允许）+ 把"为什么做不到"讲清楚
