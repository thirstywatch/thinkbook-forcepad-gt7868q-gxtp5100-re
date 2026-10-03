# 追加十六 —— 生态定论：主机触发触觉需要设备声明什么（微软官方 API + Linux 6.18 上游 + macOS + 蓝莓）

> 日期：2026-09-28 · 全部来自**一手来源**（微软官方文档、Linux 内核补丁系列、Apple 私有 API 实作、蓝莓开源代码）
> 目的：回答「纯软件让触控板按我们的时机震动」在业界到底怎么做，以及**我们这台差在哪几条**

---

## §0 一句话

> **「主机按自己的时机触发触控板震动」在 2026 年已经是**官方支持的能力**：**
> **Windows 有 [`Windows.Devices.Haptics.InputHapticsManager`](https://learn.microsoft.com/en-us/windows/apps/develop/input/haptics)（Win11 SDK 10.0.28000.1721+，2026-03），Linux 6.18 有 [`hid-haptic.c`](https://patchew.org/linux/20250818-support-forcepads-v3-0-e4f9ab0add84@google.com/)（Google/ChromiumOS 提交，已合入主线）。**
> **但它们全部要求「设备在 HID 描述符里声明了触发能力」。**
> **我们这台 GXTP5100 只声明了一个 `0x0E/0x23` Intensity（FEATURE）—— 五条必需项里缺四条。**
> **⇒ 结论不是"技术上做不到"，而是"**这台设备的描述符没有开这个口**"，而且描述符在设备固件里，软件改不了。**

---

## §1 生态全景：四条路线，一个共同前提

| 平台 / 项目 | 主机触发机制 | 前提 | 纯软件可行？ |
|---|---|---|---|
| ★ **Windows 官方 API** | `InputHapticsManager.TrySendHapticWaveform()` / `TrySendHapticWaveformForPlayCount()` / `TryStopFeedback()` | 设备须在**官方支持列表**（[Supported Device Database](https://microsoft.design/wp-content/uploads/2026/06/Supported-Device-Database.pdf)）；目前**只有 Surface Laptop 8 / 8 for Business**（外加鼠标与笔） | ✅ 可行，但**设备必须被支持** |
| ★ **Linux 6.18 上游** | 内核 `hid-haptic.c`：把设备的 `auto trigger waveform` 置为 `WAVEFORM_STOP` ⇒ 进入 **host-controlled mode** ⇒ 用户态用 **Force Feedback 协议 + 新 `FF_HAPTIC` effect** 请求波形 | 设备须暴露 **simple haptic controller** 集合 + waveform usage + **manual trigger** + `auto trigger waveform`；且 `ABS_MT_PRESSURE` 须以**牛顿/克**报告 | ✅ 可行，同样要求设备声明 |
| **macOS（Apple Force Touch）** | 私有框架 `MultitouchSupport.framework`：`MTActuatorCreateFromDeviceID` / `MTActuatorOpen` / **`MTActuatorActuate`** / `MTActuatorClose` | Apple 全系 Force Touch 触控板都支持（无需公开声明） | ✅ **最成功**：[mactic](https://github.com/MatMercer/mactic) 能播敲门 / 心跳 / SOS / 鼓点 / 倒计时 |
| **Steam Deck / Valve** | HID output report + FF（`drivers/hid/hid-steam`） | 设备声明 | ✅ |
| **蓝莓的自制设备**（Surface + CS40L25 + ESP32） | ❌ **主机侧不能触发**，只能写强度 | — | ❌（但他的**手势震动**在他的**设备固件**里：`SURFACE_GESTURE_POINT_WAVE` / `EDGE_WAVE`） |
| **我们这台（GXTP5100 / GT7868Q + TF100A）** | ❌ | 只有 `0x0E/0x23` Intensity（FEATURE） | ❌（§3 逐条对照） |

---

## §2 微软的官方答案（2026 年）

**API**：`Windows.Devices.Haptics.InputHapticsManager`
- 最低 OS：**Windows 11, SDK 10.0.28000.1721（2026-03）**；波形 Align/Collide/Step/Grow 需 **10.0.28000.1839（2026-04）**
- API 契约：`UniversalApiContract` 19.0
- 用法：
  ```csharp
  bool apiPresent = ApiInformation.IsTypePresent("Windows.Devices.Haptics.InputHapticsManager");
  bool supported  = apiPresent && InputHapticsManager.IsSupported();
  var mgr = InputHapticsManager.GetForCurrentThread();   // ⚠️ 必须在 UI 线程 / 拥有输入焦点的线程
  bool sent = mgr.TrySendHapticWaveform(KnownSimpleHapticsControllerWaveforms.Align, 0);
  mgr.TryStopFeedback();
  ```
- 加强版：`TrySendHapticWaveformForPlayCount(waveform, fallback, intensity /*0.0–1.0*/, playCount, delay)`
- **官方支持设备（全是 2026 年的新东西）**：**Touchpad：Surface Laptop 8 / Surface Laptop 8 for Business**；Mouse：Logitech MX Master 4；Pen：ASUS Pen 3.0 / Surface Slim Pen 2 / MSI Pen 2

**⇒ 读法**：微软把"主机触发触控板触觉"做成了**官方能力**，而且是**白名单模式** —— **设备必须声明，且要进官方支持列表**。
**⇒ 我们这台不在列表里，而且从描述符看它连声明都没声明（§3）。**

---

## §3 ★★ 决定性对照：Linux 上游的五条要求 vs 我们这台

Linux 6.18 的 `hid-haptic.c`（[补丁系列 v3](https://patchew.org/linux/20250818-support-forcepads-v3-0-e4f9ab0add84@google.com/)，已由 Benjamin Tissoires 合入 `for-6.18/haptic`）定义了设备要支持"主机控制"必须满足的条件。逐条对我们这台：

| # | 上游要求 | 我们这台 | 证据 |
|---|---|---|---|
| **1** | 暴露 **"simple haptic controller" 逻辑集合** | ✅ **有** | `HidP_GetCaps`：Col02 `UsagePage=0x000D Usage=0x0005`，其中含 `0x05 0x0E / 0x09 0x01` 集合（Rong Zhang 贴的描述符与我们一致） |
| **2** | 支持波形 usage（`WAVEFORM_PRESS` / `RELEASE` / `STOP` / `CLICK` 等） | ❌ **没有** | Col02 的 Feature 值字段只有 7 个，**page `0x0E` 下只有 `0x23`(Intensity)，没有任何 waveform usage** |
| **3** | 支持 **`auto trigger waveform`** 字段（默认 `WAVEFORM_PRESS`；置 `WAVEFORM_STOP` 即交出控制权） | ❌ **没有** | 同上，描述符里无此 usage |
| **4** | **必须支持 manual triggering**（手动触发；若支持强度，intensity 应放进 **manual trigger 的 OUTPUT 报表**） | ❌ **没有** | **`Col02 OutputReportByteLength = 0`（零个输出报表）**；而我们的 Intensity 是 **FEATURE**（RID 9），形态与"manual trigger OUTPUT 报表里的 intensity"完全不同 |
| **5** | `ABS_MT_PRESSURE` 以**牛顿或克**报告（含物理单位/指数/上下限） | ❌ **不满足** | 我们的压力是 `0x0D/0x30`，值域 **0..2000**，**无物理单位**（只能算"原始域"，且实测阈值 141/149 才对应点击） |

**⇒ 五条里只满足第 1 条（集合的"壳"存在），后四条全缺。**
**⇒ 所以这台设备在上游定义里属于**最小的 device-controlled 形态** —— 一个只暴露了 Intensity 的 simple haptic controller。**

**⇒ 而且第 4 条最致命**：上游明确说，支持主机触发的设备会把 intensity 放进 **manual trigger 的 OUTPUT 报表**；而我们的 intensity 是 **FEATURE** —— **这两种形态一眼就能区分"能不能被主机触发"。**

---

## §4 「厂商驱动如何」——两条合规路径都已存在，但都要求设备声明

| 路径 | 谁在用 | 我们的位置 |
|---|---|---|
| **Windows `InputHapticsManager`** | 微软官方（2026-03 起）；官方列表：Surface Laptop 8 系 | 不在列表；描述符也不支持 |
| **Linux `hid-haptic.c` + FF_HAPTIC** | Linux 6.18 主线；Google ChromiumOS 团队推动 | 五条缺四条 |
| **macOS `MTActuator`** | Apple 全系 Force Touch；开源实作 mactic | — |

**⇒ ⇒ 关键：三条路径**没有一条**是在"设备未声明"的情况下工作的。**
**⇒ 这回答了你问的"厂商的驱动如何"：厂商（微软/Apple/Valve）的做法都是「在设备侧定义接口，在主机侧提供 API」，从未试图绕过设备侧。**

---

## §5 蓝莓 vs 我们：为什么他能"完事"

| | 蓝莓 | 我们 |
|---|---|---|
| 谁决定"何时震" | **他自己的 ESP32 固件**（`surface_runtime_gesture` → `bsp_dut_trigger_haptic`） | 原厂 TF100A 固件（局部反射，压力过阈值才震） |
| 他能加"手势震动"吗 | ✅ 能 —— 他写固件 | ❌ 不能 |
| 主机能调什么 | 只有那个 0-100 的强度设置 | 只有那个 0-100 的强度设置（一样） |
| 他的波形从哪来 | 逆向 Surface 固件得到 **78 条波形表** + 强度→波形索引映射（`surface_haptic_policy.c`） | — |

**⇒ 他的"逆向"产出是「能让他自己那套硬件跑起来的东西」（固件 + 波形表 + 描述符），不是"一份命令表"。**
**⇒ 他的"完事"建立在「他掌控设备侧」之上。我们受"设备固件固定"这个约束，所以他的路径对我们不可移植。**

---

## §6 ⇒ 最终判定（纯软件 + 通用）

| 问题 | 答案 |
|---|---|
| "纯软件让触控板按我们的时机震"在业界有成功案例吗？ | **有，而且不少**：macOS（mactic）、Windows（InputHapticsManager）、Linux（FF_HAPTIC）、Steam Deck |
| 它们的共同前提是什么？ | **设备在 HID 描述符里声明了触发能力**（waveform usage / manual trigger / auto trigger waveform / OUTPUT 报表） |
| 我们这台满足吗？ | ❌ **五条缺四条**；`out=0`、无 waveform、无 auto trigger、无 manual trigger、无物理单位压力 |
| 能靠软件补吗？ | ❌ **描述符在设备固件里**；且 39 条厂商命令全覆盖证明没有马达入口；改固件需碰 `0xA0/0x0500`+`0x0100`（红线，且只对同批次有效） |
| 那"通用"能交付什么？ | ★ **能力探测 + 分级支持**：用 `InputHapticsManager.IsSupported()` / 描述符探测判断机型是否支持 → 支持就走官方 API（如 Surface Laptop 8），不支持就优雅降级。**这是对所有同款机型都成立、且可发布的形态。** |

---

## §7 出处（一手）

| 内容 | 链接 |
|---|---|
| 微软：在 Windows 应用中实现触觉反馈（API + 支持设备列表） | <https://learn.microsoft.com/en-us/windows/apps/develop/input/haptics> |
| 微软：输入设备触觉实现指南（device-initiated vs host-initiated） | <https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/input-haptics-implementation-guide> |
| 微软：触控板调优指南 | <https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/touchpad-tuning-guidelines> |
| Linux 上游补丁系列 v3（11 个补丁，已合入 6.18） | <https://patchew.org/linux/20250818-support-forcepads-v3-0-e4f9ab0add84@google.com/> |
| Linux RFC：给压感板加 device-initiated 旋钮（Rong Zhang，同款描述符） | <https://lkml.iu.edu/hypermail/linux/kernel/2606.2/01413.html> |
| USB-IF HUTRR63（Haptics page redline） | <https://www.usb.org/sites/default/files/hutrr63b_-_haptics_page_redline_0.pdf> |
| mactic（macOS 纯软件触觉工具） | <https://github.com/MatMercer/mactic> |
| 蓝莓项目 | <https://github.com/barryblueice/ESP32-Haptic-Precision-TouchPad> |
