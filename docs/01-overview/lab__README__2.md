# 触控板触觉「能力探测 + 分级支持」

> 一句话：**纯用户态、只读、零注入**地判断一台笔记本的触控板属于哪一级触觉能力，并据此选择可用的后端。
> **对任何品牌任何机型都成立** —— 因为它只读描述符声明，不看 vendor ID。

---

## 为什么这是对的形态

「主机能否主动触发触控板震动」不是驱动或 API 层面的问题，而是**设备描述符有没有声明那几条 usage** 的问题。
证据（三条一手规范）：

| 来源 | 结论 |
|---|---|
| **Linux 6.18 `drivers/hid/hid-haptic.c`** | **能力驱动** —— 通篇没有 vendor/product ID 判断；只要描述符里有 `0x0E/0x20` + `0x0E/0x21` + `0x0E/0x10/0x11` 且压力单位是克/牛顿，就自动启用主机触发 |
| **微软《Input Device Haptics Implementation Guide》** | host-initiated 必需 `Manual Trigger (0x0E/0x21, OUTPUT)` + `Waveform/Duration List (FEATURE)`；device-initiated 只允许 `Intensity (0x0E/0x23, FEATURE)` |
| **USB-IF HUT 1.5 §17.1** | `0x0E/0x21` 的官方类型就是 **Output** —— "Ordinal in the WaveformList to trigger immediately" |

**⇒ 所以"探测描述符"就能判定，不需要抓包、拆机或逆向固件。**

---

## ★ 分水岭（最干净的一条判据）

**同一个 usage `0x0E/0x23 (Haptic Intensity)`，落在哪一类报表里，就决定了有没有扳机：**

| 位置 | 含义 | 判定 |
|---|---|---|
| 在 **OUTPUT** 报表里（与 `0x0E/0x21` 同一条 Manual Trigger 报表） | 主机可以"填波形 + 强度"再发出去 | **有扳机（级别 A）** |
| 在**独立的 FEATURE** 报表里 | 只是"用户偏好的强度旋钮" | **只有旋钮（级别 B）** |
| `0x0E` page 完全不出现 | 触觉完全在设备固件内闭环 | **无接口（级别 C）** |

依据：`hid-haptic.c` 的 `fill_effect_buf()` 把 `HID_HP_INTENSITY` 当作 **`manual_trigger_report` 里的字段**来填，然后 `hid_output_report()` 发出去。

---

## 分级与支持策略

| 级别 | 判据 | 后端 | 能实现 |
|---|---|---|---|
| **A · 有扳机** | `0x0E/0x20` + `0x0E/0x21`(OUT) + `0x0E/0x10` + `0x0E/0x11` + 压力带克/牛顿 | **`Windows.Devices.Haptics.InputHapticsManager`**（`TrySendHapticWaveform` / `…ForPlayCount` / `TryStopFeedback`）；Linux 侧为 `FF_HAPTIC` | ★ **任意时机、任意波形、可连续** ⇒「滑动跟随震动」可实现 |
| **B · 只有旋钮** | 有 `0x0E/0x23`（FEATURE），无 `0x0E/0x21` | `HidD_SetFeature` 写强度（0–100） | **强度调节**（对用户仍有价值）；**不能**决定何时震 |
| **C · 无接口** | 没有 `0x0E` page | 无 | 只能做非触觉反馈 |

**⚠️ 级别 B 的天花板是规范级的，不是实现级的** —— 微软原文：
> "This SET_FEATURE report specifies the user's preference for the intensity of the haptic feedback **for button press and release**. **It does NOT apply to the intensity of any host-initiated feedback**, if supported by the device."

---

## 用法

```powershell
# 探测本机（只报触控板类接口）
.\probe-haptic.ps1

# 只探测某个接口
.\probe-haptic.ps1 -Filter gxtp

# 连非触控板接口也打印
.\probe-haptic.ps1 -All
```

**输出内容**：每个接口的 caps、六条判据逐条、旋钮位置（分水岭）、触觉/压力字段明细、主机侧 API 可用性、分级建议。

---

## 安全声明

- 只做：`SetupDiGetClassDevs` 枚举 → `CreateFileW(access=0)` → `HidD_GetPreparsedData` → `HidP_GetCaps` / `HidP_GetValueCaps`
- **不发送任何报文、不写任何 feature、不改设备状态**
- **`access=0 + share=3` 句柄可绕过 PTP 驱动对主集合的独占**（`err=32 → ok`）—— 这是本项目的一个关键方法学收获
- 读的是 hidclass 已解析的 **preparsed data**，所以**在设备被独占时同样可用**

---

## 本机实测结果（ThinkBook 14 G6+ IMH / GXTP5100）

```
接口   : gxtp5100&col02
Caps   : UsagePage=0x000D Usage=0x0005  In=40 Out=0 Feat=737  LinkColl=7
★ 判定 : B · 只有旋钮（可调参数，不能主动触发）

  [1] 0x0E/0x20 Auto Trigger           : ❌
  [2] 0x0E/0x21 Manual Trigger(OUTPUT) : ❌   ← ★ 决定性
  [3] 0x0E/0x10 Waveform List          : ❌
  [4] 0x0E/0x11 Duration List          : ❌
  [5] TipPressure 单位                 : Units=0x0021 (SI Linear, 质量=无) ⇒ 不满足

  0x0E page 出现                       : ✅
  0x0E/0x23 Intensity 存在             : ✅（Feature RID=9，bit=8，cnt=1）
      · 在 OUTPUT 报表 ⇒ 有扳机形态     : ❌
      · 在 FEATURE 报表 ⇒ 只有旋钮       : ✅
  0x0D/0xB0 Button Press Threshold     : ❌

主机侧 API：Windows.Devices.Haptics.InputHapticsManager 在本机不可用
            （需 Windows 11 SDK 10.0.280000.1721+ / 2026-03 运行时）
```

**⇒ 与项目其余逆向结论完全一致**：本机在标准层无触发入口、厂商层 39 条命令无马达入口、固件层触觉闭环在 TF100A 内部。

---

## 实现要点 / 踩过的坑

| 坑 | 说明 |
|---|---|
| **`HidP_*` 返回 NTSTATUS，成功值是 `0x00110000` 而不是 0** | 一开始判成 `rc != 0` 把所有结果都跳过了；`HidP_GetCaps` 成功也会返回 `0x00110000` |
| **`HidP_GetValueCaps` 的长度参数是 `PUSHORT`（2 字节）** | 有些 Python 示例用 `c_ulong`（4 字节）靠小端巧合也能跑；C# 里用 `ref ushort` 才是对的 |
| **`access=0` 句柄** | 主集合被 PTP 驱动独占时，只有 `access=0` 能打开 |
| **只用 ValueCaps，不碰 ButtonCaps** | 触觉相关 usage 全是 value 字段；ButtonCaps 的结构体布局容易出错且用不上 |

## 文件

| 文件 | 说明 |
|---|---|
| `HapticCap.cs` | 探测内核（P/Invoke，无外部依赖） |
| `probe-haptic.ps1` | 运行器 + 分级报告 + 主机侧 API 可用性检查 |
| `README.md` | 本文件 |
