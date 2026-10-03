# GXTP5100 / GT7868Q 触控板 HID usage 语义权威解读

**设备**：Lenovo ThinkBook 14 G6+ IMH，触控板 Goodix **GXTP5100**（芯片家族 GT7868Q）
**证据基础**：`caps-all.txt` / `caps-all.json`（`HidP_GetValueCaps` + `HidP_GetButtonCaps`，4 个 HID 集合 Col01–Col04）
**一手规范**：
- USB-IF **HID Usage Tables 1.5**（本地下载 PDF，`usb.org/sites/default/files/hut1_5.pdf`，4,452,110 B；正文由本地提取，章节号/UsageID/名称均逐字核对）
- USB-IF **HUTRR111**《Touchpad Button Press Threshold》（Approved，5–0）原文 PDF
- Microsoft《Input Device Haptics Implementation Guide》（2026-04-13 更新）
- Microsoft《Windows Precision Touchpad Collection》
- Microsoft《Precision touchpad tuning》
- Linux 内核 `include/linux/hid.h`（交叉验证用，非规范）

**未触碰设备**：本次全程只读本地文件 + 联网抓取，未发送任何 HID 命令、未运行任何写设备脚本。

---

## 0. 先给结论（TL;DR）

| 问题 | 结论 | 置信度 |
|---|---|---|
| `0x0D/0x55` 是什么 | **Contact Count Maximum** | 官方明确定义 |
| `0x0D/0x59` 是什么 | **Pad Type**（HUT 1.5 官方名；Linux 内核 #define 叫 `HID_DG_BUTTONTYPE`/"Button Type"） | 官方明确定义 |
| `0x0D/0xB0` 存不存在 | **存在**。HUT 1.5 表 16.1 行：`B0 ButtonPressThreshold[78] DV 16.5`；正文定义见 §16.5 | 官方明确定义（含 HUTRR111 原文） |
| 本机有无 `0x0E/0x21` Manual Trigger 的 **OUTPUT** 报 | **没有** | 高（cap 层面统计为 0 个 output） |
| 本机有无 `0x0D/0xB0` | **没有** | 高 |
| 本机有无 `0x0E/0x10` / `0x0E/0x11` | **没有** | 高 |
| 本机 `0x0E/0x23` 是哪种 Intensity | **device-initiated 的 Haptic Intensity**（不是 host-initiated 的 output Intensity） | 高 |

**一句话因果**：主机之所以无法主动触发震动，是因为这块板的 HID 描述符**完全缺失 host-initiated haptics 所需的整条通路**——没有 `0x0E/0x21 Manual Trigger` output report，也没有 `0x0E/0x10 Waveform List` / `0x0E/0x11 Duration List` feature report 来让主机知道有哪些波形可用。本机唯一的 haptics usage 是 `0x0E/0x23 Intensity` 的 feature，它的语义是"用户偏好旋钮"，**不是**触发指令。

---

## 1. 问题 1：完整 usage 对照表

> 说明：`我们声明的值域` 一列取自 caps 的 `lmin..lmax`（注意本机部分字段的 lmin/lmax 是反的，已如实标注）。
> "cap" 一列标注该字段是被 `HidP_GetValueCaps`(V) 还是 `HidP_GetButtonCaps`(B) 枚举出来的。

### 集合 1：`gxtp5100&col01` — Mouse 应用集合（UsagePage 0x0001 / Usage 0x0002）

| 报告类型 | RID | page | usage | 官方名称 | 我们声明的值域 | 含义 | 来源 |
|---|---|---|---|---|---|---|---|
| Input / V | 1 | 0x01 | 0x30 | **X** | −127..127 | 指针 X 位移（相对） | [HUT 1.5 §4 表 4.1（`30 X DV 4.2`）](https://usb.org/sites/default/files/hut1_5.pdf) |
| Input / V | 1 | 0x01 | 0x31 | **Y** | −127..127 | 指针 Y 位移（相对） | 同上 |
| Input / V | 1 | 0x01 | 0x38 | **Wheel** | −127..127 | 滚轮 | [HUT 1.5 §4 表 4.1（`38 Wheel DV 4.3`）](https://usb.org/sites/default/files/hut1_5.pdf) |
| Input / V | 1 | 0x0C | 0x0238 | **AC Pan** | −127..127 | Consumer 页水平平移（本机被复用来当第三轴） | [HUT 1.5 §15.16（`238 ACPan LC 15.16`）](https://usb.org/sites/default/files/hut1_5.pdf) |
| Input / B | 1 | 0x09 | 0x0000..0x0000 | **Button**（usage 范围被解析成退化值，具体按钮号见"不确定点"） | — | 鼠标按键；按 HUT 惯例应为 Button 1 | [HUT 1.5 §12 Button Page (0x09)](https://usb.org/sites/default/files/hut1_5.pdf) |

### 集合 2：`gxtp5100&col02` — Windows Precision Touchpad 顶集合（UsagePage 0x000D / Usage 0x0005 = **Touch Pad**）

**Input 报（RID 4）**——5 个 contact × (Contact ID, X, Y, Pressure)，外加表级 Scan Time / Contact Count：

| 报告类型 | RID | page | usage | 官方名称 | 我们声明的值域 | 含义 | 来源 |
|---|---|---|---|---|---|---|---|
| Input / V | 4 | 0x0D | 0x51 | **Contact Identifier** | 0..15（4 bit） | 接触点 ID（每个 contact 各一个，共 5 个） | [HUT 1.5 §16.6（`51 ContactIdentiﬁer[7] DV 16.6`）](https://usb.org/sites/default/files/hut1_5.pdf) |
| Input / V | 4 | 0x01 | 0x30 | **X** | 0..4149 | contact X 坐标 | HUT 1.5 §4 |
| Input / V | 4 | 0x01 | 0x31 | **Y** | 0..2147 | contact Y 坐标 | HUT 1.5 §4 |
| Input / V | 4 | 0x0D | 0x30 | **Tip Pressure** | 0..2000 | 单指压力 | [HUT 1.5 §16.3.1（`30 TipPressure DV 16.3.1`）](https://usb.org/sites/default/files/hut1_5.pdf) |
| Input / V | 4 | 0x0D | 0x56 | **Scan Time** | 0..65535 | 相对扫描时间，单位 **100 µs**（表级） | [HUT 1.5 §16.5（`56 ScanTime[51] DV 16.5`）](https://usb.org/sites/default/files/hut1_5.pdf) |
| Input / V | 4 | 0x0D | 0x54 | **Contact Count** | 0..127 | 本帧接触点总数（表级） | [HUT 1.5 §16.6（`54 ContactCount[7] DV 16.6`）](https://usb.org/sites/default/files/hut1_5.pdf) |
| Input / B | 4 | 0x0D | 0x0000 | （退化 usage，见"不确定点"） | — | — | — |

**Feature 报**：

| 报告类型 | RID | page | usage | 官方名称 | 我们声明的值域 | 含义 | 来源 |
|---|---|---|---|---|---|---|---|
| Feature / V | 2 | 0x0D | 0x0059 | **Pad Type**（= 微软文档里的 device "button type"） | 0..15（4 bit）；微软定义值 0=Depressible/Click-pad，1=Non-Depressible/Pressure-pad，2=Non-Clickable/Discrete-pad | 触控板是否为可压下式。**本机实测读到 5（未定义值）** | HUT 1.5 §16.5（`59 PadType[51] SF 16.5`）＋ [MS PTP Collection](https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/touchpad-windows-precision-touchpad-collection) |
| Feature / V | 2 | 0x0D | 0x0055 | **Contact Count Maximum** | 0..15（4 bit）；微软要求 3–5 | 最大并发接触点数。**本机实测读到 1** | HUT 1.5 §16.6（`55 ContactCountMaximum[7] SV 16.6`）＋ [MS PTP Collection](https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/touchpad-windows-precision-touchpad-collection) |
| Feature / V | 9 | 0x0E | 0x0023 | **Intensity** | 声明 lmin=**100** / lmax=**1**（反转，异常）；实测读回 0xEE | Haptics 强度。**本机这一条属于 device-initiated 的 Haptic Intensity** | [HUT 1.5 §17.1](https://usb.org/sites/default/files/hut1_5.pdf) ＋ [MS Haptics Guide](https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/input-haptics-implementation-guide) |
| Feature / V | 6 | 0xFF00 | 0x00C5 | **官方表里未找到**（Page 0xFF00 = Vendor-deﬁned，HUT 1.5 表 3.1 明确 `FF00-FFFF Vendor-deﬁned`） | Count=**256** | 256 字节 blob；与微软 PTP "certification status" 的 `Page 0xFF / Usage 0xC5` 256 字节 blob 高度对应 | [HUT 1.5 表 3.1](https://usb.org/sites/default/files/hut1_5.pdf)＋[MS PTP Collection](https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/touchpad-windows-precision-touchpad-collection) |
| Feature / V | 13 | 0xFF00 | 0x00C4 | **官方表里未找到**（vendor-defined） | Count=4 | 厂商自定义 4 字节 | HUT 1.5 表 3.1 |
| Feature / V | 12 | 0xFF00 | 0x00C6 | **官方表里未找到**（vendor-defined） | Count=736 | 厂商自定义 736 字节 | HUT 1.5 表 3.1 |
| Feature / V | 11 | 0xFF00 | 0x00C7 | **官方表里未找到**（vendor-defined） | Count=66 | 厂商自定义 66 字节 | HUT 1.5 表 3.1 |
| Feature / B | 7 | 0x0D | 0x0000 | （退化 usage，见"不确定点"） | — | — | — |

### 集合 3：`gxtp5100&col03` — Device Configuration 顶集合（UsagePage 0x000D / Usage 0x000E = **Device Conﬁguration**）

| 报告类型 | RID | page | usage | 官方名称 | 我们声明的值域 | 含义 | 来源 |
|---|---|---|---|---|---|---|---|
| Feature / V | 3 | 0x0D | 0x0052 | **Device Mode** | 0..10，Count=**2** | 0=以鼠标上报，1=单输入设备（单点触摸/笔），2=多点输入设备（支持 contact identifier + contact count maximum）。Count=2 与 `0x0D/0x53 Device Identiﬁer`（未在 cap 表出现）成对 | HUT 1.5 §16.7（`52 DeviceMode[7] DV 16.7`） |
| Feature / B | 5 | 0x0D | 0x0000 | （退化 usage，见"不确定点"） | — | — | — |

> ⚠️ **命名更正**：`0x0D/0x52` 常被（包括 Linux 内核 `HID_DG_INPUTMODE`）叫做 "Input Mode"，但 **HUT 1.5 表 16.1 的官方名称是 `DeviceMode`**（`UsageName` 列逐字为 `DeviceMode`，UsageType `DV`，小节 16.7）。见 §16.7 正文："The current input mode conﬁguration for a device." 所以官方名 = Device Mode，"input mode" 只是释义性描述。

### 集合 4：`gxtp5100&col04` — 厂商自定义集合（UsagePage 0xFF00 / Usage 0x0001）

HUT 1.5 表 3.1：`FF00-FFFF  Vendor-deﬁned`。集合 4 的 page/usage 全部为 vendor-defined，**官方表里未找到**，本报告不做猜测。

| 报告类型 | RID | page | usage | 官方名称 | 我们声明的值域 | 含义 | 来源 |
|---|---|---|---|---|---|---|---|
| Input / V | 14 | 0xFF00 | 0x0000..0x003E | **官方表里未找到**（vendor-defined 范围） | 0..−1（即 0..0xFF 按无符号） | 厂商自定义 | [HUT 1.5 表 3.1](https://usb.org/sites/default/files/hut1_5.pdf) |
| Input / V | 14 | 0xFF00 | 0x0001 | **官方表里未找到**（vendor-defined） | 0..−1 | 厂商自定义 | 同上 |
| Output / V | 14 | 0xFF00 | 0x0000..0x003E | **官方表里未找到**（vendor-defined） | 0..−1 | 厂商自定义（**注意：这是本设备唯一的 OUTPUT 报，但它不是 Manual Trigger**） | 同上 |
| Output / V | 14 | 0xFF00 | 0x0001 | **官方表里未找到**（vendor-defined） | 0..−1 | 厂商自定义 | 同上 |

### 官方 usage 名一键索引（用于交叉核对）

| page/usage | 官方名称（HUT 1.5 逐字） | 类型 | 小节 |
|---|---|---|---|
| 0x01/0x30 | X | DV | 4.2 |
| 0x01/0x31 | Y | DV | 4.2 |
| 0x01/0x38 | Wheel | DV | 4.3 |
| 0x09/0x01.. | Button 1 (primary/trigger) / Button 2 (secondary) / Button 3 (tertiary) | — | 12 |
| 0x0C/0x0238 | ACPan | LC | 15.16 |
| 0x0D/0x30 | TipPressure | DV | 16.3.1 |
| 0x0D/0x51 | ContactIdentiﬁer | DV | 16.6 |
| 0x0D/0x52 | **DeviceMode** | DV | 16.7 |
| 0x0D/0x54 | ContactCount | DV | 16.6 |
| 0x0D/0x55 | **ContactCountMaximum** | SV | 16.6 |
| 0x0D/0x56 | ScanTime | DV | 16.5 |
| 0x0D/0x59 | **PadType** | SF | 16.5 |
| 0x0D/0xB0 | **ButtonPressThreshold** | DV | 16.5 |
| 0x0E/0x01 | SimpleHapticController | CA/CL | 17.1 |
| 0x0E/0x10 | WaveformList | NAry | 17.1 |
| 0x0E/0x11 | DurationList | NAry | 17.1 |
| 0x0E/0x20 | AutoTrigger | DV | 17.1 |
| 0x0E/0x21 | ManualTrigger | DV | 17.1 |
| 0x0E/0x22 | AutoTriggerAssociatedControl | SV | 17.1 |
| 0x0E/0x23 | Intensity | DV | 17.1 |
| 0x0E/0x24 | RepeatCount | DV | 17.1 |
| 0x0E/0x25 | RetriggerPeriod | DV | 17.1 |
| 0x0E/0x28 | WaveformCutoﬀTime | SV | 17.1 |
| 0xFF00/* | —（vendor-defined） | — | 表 3.1 |

---

## 2. 问题 2：逐条是/否 + 原文依据

### 2.1 本机有没有 `Manual Trigger`（0x0E / 0x21）的 **OUTPUT** 报？

**没有。**

- caps 层面证据：4 个集合的 output 字段统计 —— Col01 `Out=0`、Col02 `Out=0`、Col03 `Out=0`、Col04 `Out=65 bit`（唯一一个 output，但 usage 是 0xFF00 vendor-defined，见上表）。全设备**不存在任何** `page=0x0E` 的 output 字段。
- 规范层面：`ManualTrigger` 的官方类型就是 Output。HUT 1.5 §17.1 原文：
  > "**ManualTrigger** DV **Output**. Ordinal in the WaveformList to trigger immediately. May be accompanied by Intensity, RepeatCount and/or RetriggerPeriod outputs to override feature variants of those controls."
  > —— [HUT 1.5 §17.1](https://usb.org/sites/default/files/hut1_5.pdf)
- 微软侧把它列为 **Mandatory**（host-initiated 场景）：
  > "**Manual Trigger | 0x0E | 0x21 | Mandatory** | Waveform to fire as explicit command from the host"
  > "The host will issue this report when triggering discrete haptic feedback. **This output report must have a dedicated report ID.**"
  > —— [Input Device Haptics Implementation Guide](https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/input-haptics-implementation-guide)

> 结论：**是/否 = 否**（置信度：高）。

### 2.2 本机有没有 `Button Press Threshold`（0x0D / 0xB0）？

**没有。**

- caps 层面证据：Col01–Col04 的 feature 值字段全集为 `{0x0D/0x59, 0x0D/0x55, 0x0E/0x23, 0xFF00/0xC5, 0xFF00/0xC4, 0xFF00/0xC6, 0xFF00/0xC7}`。**没有 0x0D/0xB0**。
- 规范层面（HUT 1.5 表 16.1 逐字行）：
  > "`B0  ButtonPressThreshold[78]  DV  16.5`"（前后行：`A7-AF Reserved`…`B1-FFFF Reserved`）
  > —— HUT 1.5 §16 表 16.1
- 规范层面（HUT 1.5 §16.5 正文逐字）：
  > "**ButtonPress Threshold** DV — The required pressure for a user to apply to a touchpad to report a 'button press'. System-conﬁgurable to suit user-preference. **Default units are grams.** Note: This does not aﬀect any physical buttons in close proximity to the touchpad (e.g. mouse left/right buttons)."
  > —— HUT 1.5 §16.5 Touch Digitizer Usages
- 微软侧：device-initiated 的 force 旋钮，**在同时支持 host-initiated 时是强制的**：
  > "It can choose to support SET_FEATURE reports to allow user customization of its behavior when doing so: The intensity of the haptic feedback / The force required to trigger a button press. **Both of these feature reports are mandatory if the touchpad also supports host-initiated haptic feedback.**"
  > "To support this configuration, the device must define the Button Press Threshold usage (**Page 0x0D, Usage 0xB0**) as a feature report with a dedicated report ID in the Windows Precision Touchpad top-level collection. **It must not be within a SimpleHapticsController logical collection.**"
  > —— [Input Device Haptics Implementation Guide](https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/input-haptics-implementation-guide)

> 结论：**是/否 = 否**（置信度：高）。本机只有 Intensity 这一个 device-initiated 旋钮，没有 force/阈值旋钮。

### 2.3 本机有没有 `Waveform List` / `Duration List`（0x0E/0x10、0x0E/0x11）？

**没有。**

- caps 层面证据：feature 值字段全集中不含任何 `page=0x0E` 的 usage 0x10 / 0x11。
- 规范层面（HUT 1.5 §17.1 逐字）：
  > "**WaveformList** NAry — Collection containing Ordinals that contain the Usages of supported waveforms. … **The WaveformList is mandatory, there is no default deﬁned.**"
  > "**DurationList** NAry — Collection of Ordinals containing the default duration for each haptic waveform. Default units are milliseconds."
  > —— [HUT 1.5 §17.1](https://usb.org/sites/default/files/hut1_5.pdf)
- 微软侧（host-initiated 必需）：
  > "**Waveform List | 0x0E | 0x10 | Mandatory** | Logical collection containing an ordered list of haptic waveforms supported by the device"
  > "**Duration List | 0x0E | 0x11 | Mandatory** | Logical collection containing an ordered list of durations for waveforms in the Waveform List"
  > 且 Waveform Information Feature Report 有三个硬约束：**must have a dedicated report ID**、**must have two child logical collections**（waveform list + duration list）、这两个 collection **must define a usage range on the Ordinal page (0x0A)**。
  > —— [Input Device Haptics Implementation Guide](https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/input-haptics-implementation-guide)

> 结论：**是/否 = 否**（置信度：高）。

### 2.4 按微软规范，device-initiated 设备允许/要求暴露哪些 feature 旋钮？（原文引用）

微软把 haptic touchpad 的 haptics 分成两种模式：

> "**Device-initiated haptic feedback**: The touchpad autonomously triggers haptic feedback when it determines that the user has pressed or released the surface button. This replaces the physical click sensation of a mechanical touchpad. The device can **optionally** accept SET_FEATURE reports from the host to let the user customize the intensity of the feedback and the force required to trigger a button press."
> —— [Windows Precision Touchpad Collection](https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/touchpad-windows-precision-touchpad-collection)

device-initiated 的完整规则（逐条原文）：

| # | 原文 | 出处 |
|---|---|---|
| 1 | "A haptic touchpad is responsible for triggering haptic feedback when it determines that the touchpad's surface button has been pressed or released. It can choose to support SET_FEATURE reports to allow user customization of its behavior when doing so: The intensity of the haptic feedback / The force required to trigger a button press" | MS Haptics Guide §Device-Initiated Haptic Feedback |
| 2 | "**Both of these feature reports are mandatory if the touchpad also supports host-initiated haptic feedback.** Each report must use a distinct report ID, not used with any other usage." | 同上 |
| 3 | "During enumeration, the host will assess the supported logical and physical range from the descriptor and compute the exposed options for the settings UI including the defaults. The host shall issue the SET_FEATURE to communicate the user-specified value to the device; this issuance may occur at any time, but shall occur whenever the setting is changed, a user switch occurs, and when the device is enumerated or resets. Before the SET_FEATURE report has been issued, the device should use a reasonable default of its own choosing (e.g. the middle of its logical range)." | 同上 |
| 4 | **Haptic Intensity 归属要求**："To support this configuration, the device must define a **SimpleHapticsController logical child collection (Page 0x0E, Usage 0x01)** in the Windows Precision Touchpad top-level collection, containing the **Haptic Intensity usage (Page 0x0E, Usage 0x23)** as a feature report with a dedicated report ID. **This child collection must not contain the Auto Trigger (Page 0x0E, Usage 0x20) or Manual Trigger (Page 0x0E, Usage 0x21) usages.** It must be separate from the SimpleHapticsController child collection used for host-initiated haptic feedback (if supported)." | 同上 |
| 5 | **Haptic Intensity 值域**："The logical minimum must be equal to zero, and the logical maximum must be **greater than or equal to four**. The user's preference will be linearly scaled into the logical range, with **zero indicating that no feedback should be triggered for button press and release**." | 同上 |
| 6 | **Button Press Threshold 归属要求**："the device must define the Button Press Threshold usage (**Page 0x0D, Usage 0xB0**) as a feature report with a dedicated report ID in the **Windows Precision Touchpad top-level collection**. **It must not be within a SimpleHapticsController logical collection.**" | 同上 |
| 7 | **Button Press Threshold 值域**："The logical range shall linearly map to the physical range of values, and be evenly spaced and centered around the default value. … The Logical Minimum, Default, and Logical Maximum, will correspond to 3 distinct levels of button press force exposed to a user through Windows settings UI (supporting 'Low', 'Medium', and 'High', respectively). The recommended physical range for Button Press Threshold is to **at least cover the range between 110g and 190g**, corresponding to the minimum and maximum values respectively." | 同上 |
| 8 | **对 host-initiated 的约束**（对比用）："the device must define a SimpleHapticsController logical child collection (Page 0x0E, Usage 0x01) in the Windows Precision Touchpad top-level collection, containing the Haptic Intensity usage (Page 0x0E, Usage 0x23) as a feature report… It must be separate from the SimpleHapticsController child collection used for host-initiated haptic feedback" —— 即 device-initiated 与 host-initiated 必须用**两个互相独立**的 SimpleHapticsController collection | 同上 |

**要点归纳**：device-initiated 场景下，微软**允许**（不强制）暴露两个 feature 旋钮：
1. **Haptic Intensity** = `0x0E/0x23`，放在**自己的** SimpleHapticsController 子集合里（且该子集合内**禁止**出现 `0x0E/0x20`、`0x0E/0x21`）；
2. **Button Press Threshold** = `0x0D/0xB0`，放在 **Touchpad 顶集合**里（**禁止**放进 SimpleHapticsController）。

两者**只有在设备同时支持 host-initiated 时才变成强制**（原文 #2）。而 host-initiated 本身是**可选**的——微软只写了"can support host-initiated haptic feedback"，并没有把它列为 haptic touchpad 的强制项。

---

## 3. 问题 3：`0x0D/0x55` 与 `0x0D/0x59` 分别是什么？

### 结论

| usage | 官方名称（HUT 1.5 逐字） | UsageType | 微软文档里的叫法 | 值域语义 | 置信度 |
|---|---|---|---|---|---|
| **0x0D/0x55** | **ContactCountMaximum** | **SV**（Static Value） | "Contact Count maximum (Page 0x0D, Usage 0x55)" | 最大并发接触点数；微软要求 3–5 | **官方明确定义** |
| **0x0D/0x59** | **PadType** | **SF**（Static Flag） | "button type (Page 0x0D, Usage 0x59)" | 0=Depressible(Click-pad)，1=Non-Depressible(Pressure-pad)，2=Non-Clickable(Discrete-pad) | **官方明确定义** |

### 一手原文

**HUT 1.5 表 16.1（逐字）**：
> "`54 ContactCount[7] DV 16.6` / `55 ContactCountMaximum[7] SV 16.6` / `56 ScanTime[51] DV 16.5` / `57 SurfaceSwitch[51] DF 16.5` / `58 ButtonSwitch[51] DF 16.5` / `59 PadType[51] SF 16.5` / `5A SecondaryBarrelSwitch[18] MC 16.4`"
> —— [HUT 1.5](https://usb.org/sites/default/files/hut1_5.pdf) §16 表 16.1

**HUT 1.5 §16.6 Multi-touch Digitizer Usages（逐字）**：
> "**ContactCountMaximum SV** — Used to report the maximum number of concurrent contacts a digitizer is capable of detecting."

**HUT 1.5 §16.5 Touch Digitizer Usages（逐字）**：
> "**PadType SF** — A touchpad digitizer may be physically depressible (often referred to as a click-pad) or it may not (often referred to as a pressure-pad). This usage allows the device to identify its pad type to the host. **When set, the touchpad is non-depressible (pressure-pad); when clear, the touchpad is depressible (click-pad).**"

**微软对同一 usage 的工程化表述**：
> "The touchpad should report this value via the **Contact Count maximum (Page 0x0D, Usage 0x55)** in the device capabilities feature report."
> "The button implementation type should be specified via the value for **button type (Page 0x0D, Usage 0x59)** in the device capabilities feature report."
> | Button type value | Implementation | → `0` Depressible (Click-pad) / `1` Non-Depressible (Pressure-pad) / `2` Non-Clickable (Discrete-pad) |
> —— [Windows Precision Touchpad Collection](https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/touchpad-windows-precision-touchpad-collection)

### 交叉验证（非规范，仅佐证）

- Linux 内核 `include/linux/hid.h`：`#define HID_DG_CONTACTMAX 0x000d0055`、`#define HID_DG_BUTTONTYPE 0x000d0059`。
  → 内核把 0x59 记作 **ButtonType**（微软文档用词），**HUT 1.5 的规范名是 PadType**，两者同一 usage。
  —— [linux/include/linux/hid.h](https://raw.githubusercontent.com/torvalds/linux/master/include/linux/hid.h)
- ChromiumOS `common/i2c_hid_touchpad.c`：`0x09, 0x59, /* Usage (Pad Type) */`
  —— [chromiumos/platform/ec](https://chromium.googlesource.com/chromiumos/platform/ec.git/+/bb90f093e020401fdb6813ca110b7dbb3ce07dda/common/i2c_hid_touchpad.c)

### 你提示里的那个问题：哪个是哪个？（明确回答）

> "标准 Precision Touchpad 的 'Device Mode / Configuration' feature 常见字段是 Contact Count Maximum、Pad Type 之类，请核实到底哪个是哪个。"

**明确回答**：
- **0x0D/0x55 = Contact Count Maximum**（不是 Pad Type）→ 微软 PTP "Device Capabilities feature report"（设备能力报）里的字段。
- **0x0D/0x59 = Pad Type / button type**（不是 Contact Count Maximum）。
- **注意**：`Device Mode` 是**第三个、完全不同的 usage**——`0x0D/0x52`（HUT 1.5 名 `DeviceMode`），它属于 **Device Conﬁguration (0x0D/0x0E)** 集合，与 0x55/0x59 不是一个东西。本机三者都有声明：`0x0D/0x52` 在 Col03（RID 3 feature），`0x0D/0x55` + `0x0D/0x59` 在 Col02（RID 2 feature）。

### 本机实测值（重要异常）

本机 RID 2 的这两个字段各占 **4 bit**，合起来正好 **1 字节**，实测读回 `0x15`：

| 字段 | 4 bit 值 | 解释 |
|---|---|---|
| 0x0D/0x55 Contact Count Maximum | **1** | 等于 1 —— 低于微软要求的 3–5 |
| 0x0D/0x59 Pad Type | **5** | **未定义值** —— 微软只定义 0/1/2 |

（`hid-probe/col02-writeprobe/writeprobe_result.json` 与 `col02-precise/summary.json` 均记录 RID 2 的读回为 `0215eeee`，即 report ID 2 + data byte `0x15` + 第三个未声明字节 `0xEE`。）

> ⚠️ 关于值域的保留意见：caps 声明 `0x0D/0x59` 和 `0x0D/0x55` 的 `lmin..lmax` 都是 `0..15`（4 bit 无符号满载），但实测值 `5` 落在微软定义域之外、`1` 落在微软 PTP 合理区间之外。这**不影响 usage 语义的判定**（语义由 page/usage 唯一确定），但说明该描述符的这两个字段**可能未按微软 PTP 规范填写**，或该 RID 2 实际承载的是厂商自定义语义而借用了标准 usage 名。此处**我不做进一步猜测**。

---

## 4. 问题 4：`0x0D/0xB0` 在官方 HID Usage Tables 里到底存不存在？

### 结论：**存在，且是官方明确定义的 usage。**

**置信度：官方明确定义（最高级别）。** 依据有两层，都是 USB-IF 一手文档：

**第一层 —— HUT 1.5 表 16.1 表行（逐字）**：
> `A6 TransducerIndexSelector[75] DV 16.3.1` / `A7-AF Reserved` / **`B0 ButtonPressThreshold[78] DV 16.5`** / `B1-FFFF Reserved`
> —— HUT 1.5 §16 表 16.1: Digitizer Page

其中 `[78]` 是 HUT 1.5 的参考文献编号，对应：
> "[78] HUTRR111, TouchpadButtonPressThreshold, 2022, https://usb.org/sites/default/files/hutrr111-touchpadbuttonpressthreshold_0.pdf"
> —— HUT 1.5 参考文献列表

**第二层 —— HUT 1.5 §16.5 正文定义（逐字）**：
> "**ButtonPress Threshold** DV — The required pressure for a user to apply to a touchpad to report a 'button press'. System-conﬁgurable to suit user-preference. **Default units are grams.** Note: This does not aﬀect any physical buttons in close proximity to the touchpad (e.g. mouse left/right buttons)."

**第三层 —— HUTRR111 原始请求文档（Approved）逐字**：
> Request #: HUTRR111
> Title: **Touchpad Button Press Threshold**
> Spec Release: 1.3 — Requester: Matthew Williams — Company: **Microsoft**
> Pages Affected: **Digitizer (0x0D)**
> Current Status: **Approved** — Voting Result: **5-0** — Voting: 23rd Nov 2022 – 30th Nov 2022
> Required Voter: Intel / ELAN / Synaptics
>
> Summary: "Add a new Digitizer Usage to allow system-configurable touchpad button-press activation pressure."
>
> Scenario: "Configurable touchpad button-press threshold permits greater customization of [the tou]ch experience and supports accessibility scenarios … and those with limited finger-strength can lower the required activation force. Conversely, users who have difficulty performing subtle gestures can increase the required activation force. This dynamic customization allows the same device to adjust to multiple users."
>
> Proposal: "Add Digitizer Usage to allow system-configurable touchpad button-press activation pressure threshold.
> **Add to Table 16.1: Digitizer Page** — `Usage Id 0xB0` / `Usage Name Button Press Threshold` / `Usage Type DV`
> **Add to Table 16.5 Touch Digitizer Usages** — `Button Press Threshold` / `DV` / 'The required pressure for a user to apply to a touchpad to report a "button press". System-configurable to suit user-preference. **Default units are grams.** Note: This does not affect any physical buttons in close proximity to the touchpad (e.g. mouse left/right buttons).'"
> —— [HUTRR111 原文 PDF](https://www.usb.org/sites/default/files/hutrr111-touchpadbuttonpressthreshold_0.pdf)

### 关于你在 LKML RFC 里看到的说法

Rong Zhang 的 RFC 描述与你看到的**完全正确**，且微软规范措辞一致：
> "pressurepads with device-initiated haptic feedback can support SET_FEATURE reports to allow users to customize the intensity of the haptic feedback (**usage page 0x0e Haptics, usage 0x23 Intensity**) and/or the force required to trigger a button press (**usage page 0x0d Digitizers, usage 0xb0 Button Press Threshold**)."
> —— [LKML RFC, Rong Zhang, 2026-06-16](https://lkml.iu.edu/hypermail/linux/kernel/2606.2/01413.html)

**准确措辞对照表**（避免不同文档的用词混淆）：

| 来源 | 措辞 | page/usage |
|---|---|---|
| HUT 1.5 表 16.1（UsageName 列） | `ButtonPressThreshold`（无空格） | 0x0D / 0xB0 |
| HUT 1.5 §16.5 正文标题 | `ButtonPress Threshold` | 0x0D / 0xB0 |
| HUTRR111 标题 | `Touchpad Button Press Threshold` | 0x0D / 0xB0 |
| MS Haptics Guide | `Button Press Threshold (Page 0x0D, Usage 0xB0)` | 0x0D / 0xB0 |
| Windows 注册表（用户可见） | `ClickForceSensitivity` | 映射到 0xB0 |

**附带确认**：微软《Precision touchpad tuning》明确把它与用户设置对应起来：
> "**Click sensitivity** — This setting specifies the relative sensitivity of the touchpad's haptic click detection, if supported. … **This is the user-facing setting for the 'Button Press Threshold' feature report.** | `ClickForceSensitivity` | DWORD | Percent | 0-100 | 50 | **Windows 11, build 26027+**"
> —— [Precision touchpad tuning](https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/touchpad-tuning-guidelines)

（注：RFC 里把第二个旋钮也写成 `ClickForceSensitivity`，那是 RFC 作者的一处笔误——按微软文档，`ClickForceSensitivity` 对应 **Button Press Threshold (0xB0)**，而 `FeedbackIntensity` 对应 **Haptic Intensity (0x0E/0x23)**。同一页面原文："> **Intensity** … This is the user-facing setting for the 'Haptic Intensity' feature report. | `FeedbackIntensity` | DWORD | Percent | 0-100 | 50 | Windows 11"）

---

## 5. 这对"主机能否触发震动"意味着什么

### 5.1 目标拆解

你要的是：**纯软件**、**通用到所有同款压感触控板**、让**主机主动**触发震动。

按微软规范，主机主动触发 = **host-initiated haptic feedback**，它的最小可用通路**必须**包含两样东西：

```
① Feature: Waveform Information Report   ← 主机问"你有哪些波形、各多长"
   └─ 0x0E/0x01 SimpleHapticController (Logical)
        ├─ 0x0E/0x10 Waveform List   (0x0A Ordinal 范围 → 波形 usage)
        └─ 0x0E/0x11 Duration List   (0x0A Ordinal 范围 → 毫秒)
② Output: Manual Trigger Report           ← 主机说"现在放第 N 号波形"
   └─ 0x0E/0x01 SimpleHapticController (Logical)
        ├─ 0x0E/0x21 Manual Trigger      (波形 ordinal, 必填)
        ├─ 0x0E/0x23 Intensity           (必填)
        └─ 0x0E/0x24/0x25/0x28 (可选, 三个必须同进同退)
```

### 5.2 本机缺了什么（逐条对照）

| 通路要素 | 需求 | 本机状态 | 缺口 |
|---|---|---|---|
| 主机知道有哪些波形 | Feature `0x0E/0x10 Waveform List` | **无** | ❌ 缺 |
| 主机知道波形时长 | Feature `0x0E/0x11 Duration List` | **无** | ❌ 缺 |
| 主机下发"播放" | Output `0x0E/0x21 Manual Trigger` | **无**（且 Col02 `Out=0`，整个集合没有任何 output） | ❌ **致命** |
| 主机指定强度 | Output `0x0E/0x23 Intensity` | 只有 **Feature** 版本（RID 9） | ❌ 有 feature、无 output |
| 波形信息报的容器 | `0x0E/0x01 SimpleHapticController` Logical Collection | cap 层面看不到（无法从 caps 确认） | ⚠️ 不确定 |

**导致主机无法触发震动的，是这一条：`0x0E/0x21 Manual Trigger` 的 OUTPUT 报不存在。**

这是唯一"主机 → 设备"的震动指令通道。它在 HUT 1.5 里的官方 UsageType 就是 `Output`（§17.1：`ManualTrigger … DV Output. Ordinal in the WaveformList to trigger immediately.`），在微软规范里是 `Mandatory`（"Waveform to fire as explicit command from the host"）。

**本机唯一的 haptics usage（`0x0E/0x23` Intensity, RID 9 feature）语义是"设备自主触发时用多大劲"的用户偏好旋钮**，不是触发指令。HUT 1.5 §17.1 原文：
> "**Intensity** DV Feature or Output. Percentage of maximum intensity to apply to the waveform. **If declared as a feature, applies to all waveforms.** If declared as an output, applies to the Waveform ordinal specified by a ManualTrigger in the same output report."

本机是 **feature 形态** → 属于"applies to all waveforms"（即 device-initiated 触发时统一生效的强度档位）。微软规范更直白：
> "This SET_FEATURE report specifies the user's preference for the intensity of the haptic feedback for button press and release. **It does NOT apply to the intensity of any host-initiated feedback**, if supported by the device."

### 5.3 为什么"主机侧写 RID 9"不可能让它震

即便你在主机侧把 RID 9 的 Intensity 写到最大，那也只是告诉设备"用户偏好这个强度"。设备**仍然只在它自己判定 press/release 时**才震动。缺的那条 Output 报（Manual Trigger）决定了**主机在协议上根本没有"现在震动"这句话可说**。

另外两条实测观察佐证了这条路径的死路：
1. `col02-writeprobe/writeprobe_result.json`：RID 2 的"改动写入"返回 `effective: false`（写进去但读回不变）；RID 9 写入 `ok: true` 但读回是 `0xEE`（无效值）。
2. `col02-precise/summary.json`：**所有** feature report（RID 2/6/7/9/11/12/13）读回的头部都是 `06fc28fe8440cb9a870dbe573cb67009…`（RID 6 的内容）或 `eeee…`，说明 `GET_FEATURE` 在这台设备上返回的不是真实 feature 数据。

这两点与 LKML RFC 的独立观察**完全吻合**：
> "However, getting the feature report returns garbage data (probably from the last input report in the buffer), which makes some sense as **the implementation guide only requires SET_FEATURE support**."
> —— [LKML RFC, Rong Zhang](https://lkml.iu.edu/hypermail/linux/kernel/2606.2/01413.html)

也就是说：**GET_FEATURE 读不到不代表设备坏了**，因为微软对 device-initiated 旋钮只要求支持 SET_FEATURE。但这也意味着 **RID 9 只能写、不能验证，且与"触发"无关**。

### 5.4 那么，"纯软件让主机主动触发"还有路吗？

按官方规范，**有且只有**三条路（按通用性排序）：

1. **要求设备侧新增 host-initiated haptics 描述符**（唯一完全符合微软规范、可通用的路）
   在触控板顶集合下增加一个独立的 `0x0E/0x01 SimpleHapticsController` 子集合，包含：
   - feature 报（独立 RID）：`0x0E/0x10 Waveform List` + `0x0E/0x11 Duration List`，两者用 `0x0A Ordinal` usage 范围；
   - output 报（独立 RID）：`0x0E/0x21 Manual Trigger`（必填）+ `0x0E/0x23 Intensity`（必填）；
   - 同时按规范 #2，因为加了 host-initiated，**必须同时补上 `0x0D/0xB0 Button Press Threshold`**（且 `0x0E/0x23` 的两个 collection 必须彼此分离：device-initiated 那个不得含 `0x20`/`0x21`）。
   → **这需要改固件/描述符，与你"不改固件"的约束冲突**。所以严格说：**在纯软件层面，主机主动触发震动对这块板是不可能的**；它是"设备描述符缺 usage"级别的限制，不是驱动/API 层面的限制。

2. **走厂商私有通道**（可能可行，但**不通用**）
   本机 Col04 有一个 vendor-defined（`0xFF00`）的 **Output 报 RID 14，65 bit**。理论上厂商可能在这里留了"强制震动"的私有命令。但：
   - 该 usage 在**官方表里未找到**（`FF00-FFFF` 就是 Vendor-deﬁned 区），没有可依据的语义；
   - 要逆向出命令格式才能用，且**只对这一款固件有效**，违背"通用到所有同款笔记本"的目标；
   - 本次任务明确要求不触碰设备，我**没有**做任何探测。
   → 作为"可能性"保留，不作为方案。

3. **依赖 device-initiated 的既有行为**（不是"主机主动触发"）
   让 Windows 把 `FeedbackIntensity`（映射到 RID 9）设在非 0 值，用户按压触控板时设备自己会震。这是**设备自主触发**，主机只是改了"力度旋钮"，**不是主机主动触发**。如果你的最终目标可以放宽成"让震动以指定强度生效"，这条路可行；如果必须是"主机在任意时刻主动命令它震"，这条路不满足。

### 5.5 一句话回答你的核心疑问

> "缺了哪几条 usage 才导致主机无法触发？"

缺的是 **host-initiated haptics 的整条指令通路**，按重要性排序：

1. **`0x0E/0x21 Manual Trigger`（OUTPUT）** —— 决定性缺口。没有它，主机**没有任何可下发的震动指令**。
2. **`0x0E/0x10 Waveform List`（FEATURE）** —— 主机无法得知可用波形与 ordinal。
3. **`0x0E/0x11 Duration List`（FEATURE）** —— 主机无法得知波形时长（Duration List 的 usage 范围必须与 Waveform List 完全一致）。
4. **`0x0E/0x23 Intensity` 的 OUTPUT 形态** —— 本机只有 feature 形态；output 形态才能在 Manual Trigger 同一 output 报里逐次覆盖强度。
5. （可选）`0x0E/0x24 Repeat Count`、`0x0E/0x25 Retrigger Period`、`0x0E/0x28 Waveform Cutoff Time` —— 三个必须同进同退。
6. （连带）因为要加 host-initiated，按微软规范还**必须**同时补 `0x0D/0xB0 Button Press Threshold`。

**本机在 1–3 上全缺，因此主机主动触发在 HID 语义层面直接不可能**，与驱动实现、API 调用、权限都无关。

---

## 6. 不确定点（如实标注，不填空）

| # | 不确定项 | 说明 | 影响 |
|---|---|---|---|
| 1 | **caps 里部分字段是退化的乱码** | 例如 Col02 的 `RID=0 page=0 usage=0x0022..0x000D Cnt=0`、`RID=71 page=71 usage=0x0000..0x0000 Cnt=13`；Col01 的 button `usage=0x0000..0x0000`。这更像是探测脚本在 `HidP_GetButtonCaps` 上的缓冲区/结构体问题，不是设备真的声明了这些 usage | 报告中已把这些行单独标注为"退化 usage"，未据此下任何语义结论 |
| 2 | **本机是否真的存在 `0x0E/0x01 SimpleHapticsController` collection** | 从 `HidP_GetValueCaps`/`GetButtonCaps` 的字段列表**无法确定集合归属**；且 `desc_gxtp5100&co.bin` 是 **preparsed data** 而非原始报告描述符，`hid_devices.json` 里 `desc` 为 `null`（原始描述符当时没抓到），因此我**没有**描述符字节可解析 | 因此我**不能**断言 RID 9 的 Intensity 位于 SimpleHapticsController 里。可以确定的是：**它是 feature、不是 output**，这已足以支撑"不是主机触发通道"的结论 |
| 3 | **RID 2 的 Contact Count Maximum=1 / Pad Type=5 异常** | 与微软 PTP 要求（Contact Count 3–5、Pad Type 0/1/2）不符；也可能是该 RID 借用标准 usage 名承载厂商语义 | 不影响 usage 语义判定；但如果你要依赖这两个值做逻辑判断，需谨慎 |
| 4 | **caps 里 `0x0D/0x59` 与 `0x0D/0x55` 的 `lmin..lmax` 都报 0..15** | 未体现微软要求的语义化取值 | 同上 |
| 5 | **本机 `0x0E/0x23` 声明 lmin=100 / lmax=1（反转）** | 微软要求 logical minimum = 0、logical maximum ≥ 4，本机反向 | 可能是 `HidP_GetValueCaps` 字段解读问题，也可能描述符确实异常。我只如实报告 cap 里的数值 |
| 6 | **`0xFF00` 系列的 0xC4/0xC5/0xC6/0xC7 语义** | 官方表里**未找到**（vendor-defined 区）。0xC5 的 256 字节与微软 PTP certification blob（`Page 0xFF / Usage 0xC5`）高度对应，但**page 不同**（本机 0xFF00 vs 微软写 0xFF） | 只作"高度对应"的观察，不作定义 |
| 7 | **未验证固件是否真的不支持私有触发** | 任务硬要求"绝对不要触碰设备"，我未做任何写/探测 | §5.4 路线 2 只作为可能性列出，未验证 |

---

## 7. 来源清单（全部可点）

**官方规范（一手）**
1. USB-IF, *HID Usage Tables 1.5* — <https://usb.org/sites/default/files/hut1_5.pdf>（本地提取正文；§4 表 4.1、§12、§15.16、§16 表 16.1、§16.5、§16.6、§16.7、§17 表 17.1、§17.1、表 3.1、参考文献 [78]）
2. USB-IF, *HUTRR111 — Touchpad Button Press Threshold*（Approved 5-0, 2022-11-30）— <https://www.usb.org/sites/default/files/hutrr111-touchpadbuttonpressthreshold_0.pdf>
3. USB-IF, *HUTRR83 — Touchpad*（0x0D/0x55、0x59、0x56、0x60 的来源，HUT 1.5 参考文献 [51]）— <https://www.usb.org/sites/default/files/hutrr83_-_new_digitizer_usages_for_touchpads_0.pdf>
4. Microsoft, *Input Device Haptics Implementation Guide* — <https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/input-haptics-implementation-guide>
5. Microsoft, *Windows Precision Touchpad Collection* — <https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/touchpad-windows-precision-touchpad-collection>
6. Microsoft, *Precision touchpad tuning* — <https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/touchpad-tuning-guidelines>

**交叉验证（非规范）**

7. Linux 内核 `include/linux/hid.h`（`HID_DG_CONTACTMAX` / `HID_DG_BUTTONTYPE` / `HID_HP_*`）— <https://raw.githubusercontent.com/torvalds/linux/master/include/linux/hid.h>
8. ChromiumOS `common/i2c_hid_touchpad.c`（`0x09, 0x59, /* Usage (Pad Type) */`）— <https://chromium.googlesource.com/chromiumos/platform/ec.git/+/bb90f093e020401fdb6813ca110b7dbb3ce07dda/common/i2c_hid_touchpad.c>

**本机证据文件**

9. `caps-all.txt` / `caps-all.json` — `<WORKSPACE>`
10. `col02-precise\summary.json`（feature 读回全为 `06fc28fe…` 或 `eeee…`）
11. `col02-writeprobe\writeprobe_result.json`（RID 2 写入 `effective: false`）
12. `desc_gxtp5100&co.bin`（580 B，头部 ASCII `HidP KDR` → **preparsed data**，非原始报告描述符）

**社区讨论（仅作现象佐证）**

13. LKML, *[RFC] Adding device-initiated haptic feedback knobs for pressurepads*（Rong Zhang, 2026-06-16）— <https://lkml.iu.edu/hypermail/linux/kernel/2606.2/01413.html>
14. LKML, Dmitry Torokhov 回复 — <https://lkml.iu.edu/hypermail/linux/kernel/2606.2/01668.html>
