# 追加二十 —— 「汇顶有没有带扳机的固件」：能力驱动判据 + 六路搜索全部 0 命中

> 日期：2026-09-28 · 一手来源：Linux 6.18 `hid-haptic.c` 源码 + 本机实测 caps + 固件/BIOS 字节级搜索

---

## §0 一句话

> **手头能查的六路（本机实测 / Goodix 官方 UEFI 驱动 / 整份 16 MB BIOS / 30 MB 解压体 / GT7868Q 容器 / Goodix 官方 fwupd 源码），没有任何一处含 host-initiated（带扳机）触觉描述符。**
> **★ 但更重要的认知是：Linux 上游是「能力驱动」的 —— 没有 vendor ID 白名单。「有没有扳机」只取决于描述符里那几条 usage，不取决于汇顶是否"批准"。**

---

## §1 ★★★ 关键源码：`hid-haptic.c` 是**能力驱动**，不是白名单

`drivers/hid/hid-haptic.c`（Linux 6.18，已入 mainline）的启用判据：

```c
int hid_haptic_input_configured(struct hid_device *hdev,
                                struct hid_haptic_device *haptic,
                                struct hid_input *hi)
{
    if (hi->application != HID_DG_TOUCHPAD)   return -1;
    if (!haptic->auto_trigger_report || !haptic->manual_trigger_report)
        return 0;                              // ← 缺任一 ⇒ 不启用触觉
    __set_bit(INPUT_PROP_PRESSUREPAD, hi->input->propbit);
    return hid_haptic_init(hdev, haptic, hi->input) ? 1 : 0;
}
```

而那两个 report 是这样被发现的（**纯按 usage，无任何 ID 判断**）：
```c
if (usage->hid == HID_HP_AUTOTRIGGER)    haptic->auto_trigger_report   = field->report;
if (usage->hid == HID_HP_MANUALTRIGGER)  haptic->manual_trigger_report = field->report;   // 0x0E/0x21
```
再加上一条硬要求：
```c
bool hid_haptic_check_pressure_unit(...)
{   if (field->unit == HID_UNIT_GRAM || field->unit == HID_UNIT_NEWTON) { ... return true; }
    return false; }
```

> ## **⇒ 任何设备，只要描述符里有 `0x0E/0x20` + `0x0E/0x21` + `0x0E/0x10/0x11`，且压力带克/牛顿单位，Linux 就会自动把它变成"主机可触发"。**
> **⇒ 所以"汇顶有没有带扳机的固件"= "有没有汇顶芯片的描述符里声明了这几条 usage"。**

---

## §2 ★★★ 最干净的分水岭：同一个 usage，放 **OUTPUT** 还是 **FEATURE**

`fill_effect_buf()` 揭示了"有扳机"设备的形态：

```c
static void fill_effect_buf(...)
{
    struct hid_report *rep = haptic->manual_trigger_report;   // ★ 填的是「Manual Trigger 报表」
    ...
        switch (usage->hid) {
        case HID_HP_INTENSITY:      value = ...effect->intensity...; break;   // ★ 0x0E/0x23 在这里！
        case HID_HP_REPEATCOUNT:    ...
        case HID_HP_RETRIGGERPERIOD:...
        case HID_HP_MANUALTRIGGER:  value = waveform_ordinal;   break;
        }
    hid_output_report(rep, buf);    // ★ 作为 OUTPUT 报表发出去
}
```

> ## **★ 也就是说：在有扳机的设备上，`0x0E/0x23 Intensity` 是「Manual Trigger 那条 OUTPUT 报表里的一个字段」。**
> ## **而在我们本机，`0x0E/0x23` 是一条**独立的 FEATURE 报表**（RID 9）。**
> **⇒ 同一个 usage、两种位置 —— 这就是"有无扳机"的分水岭，一眼可辨。**

---

## §3 「有扳机」的完整判据清单（六条）

| # | 需要什么 | 官方类型 | 我们本机 |
|---|---|---|---|
| 1 | `0x0E/0x20` **Auto Trigger** | FEATURE | ❌ |
| 2 | `0x0E/0x21` **Manual Trigger** | **OUTPUT** | ❌（`Col02 Out=0`） |
| 3 | `0x0E/0x10` **Waveform List** | FEATURE | ❌ |
| 4 | `0x0E/0x11` **Duration List** | FEATURE | ❌ |
| 5 | `ABS_MT_PRESSURE` 带**克/牛顿**单位 | — | ❌（`0x0D/0x30`，0..2000，**无单位**） |
| 6 | （可选）`0x0D/0xB0` Button Press Threshold | FEATURE | ❌ |
| — | `0x0E/0x23` Intensity | **应放在 #2 那条 OUTPUT 里** | ⚠️ 有，但在**独立 FEATURE** 里 |

**⇒ 六条缺六条（第 7 行的位置也是错的形态）。**

---

## §4 六路搜索：全部 0 命中

字节级搜索（4~8 字节模式，偶然期望 <0.01，故 0 命中**有统计意义**）：

| 搜索目标 | `05 0E 09 01 A1 02` | `05 0E 09 21` | `05 0E 09 23` | `09 21 75 08 95 01 91 02` |
|---|---|---|---|---|
| **`GoodixTpDxe.bin`**（**Goodix 自己的 UEFI 驱动**，48,590 B） | 0 | 0 | 0 | 0 |
| **完整 BIOS `bios16.bin`**（16,777,216 B） | 0 | 0 | 0 | 0 |
| **BIOS 解压体 `fw_decompressed.bin`**（30,883,968 B） | 0 | 0 | 0 | 0 |
| **`touchpad_GT7868Q_fw.bin`**（161,628 B） | 0 | 0 | 0 | 0 |
| `CompalEcSmmDrv.bin` / `EcCapsuleDxe.bin`（EC 驱动） | 0 | 0 | 0 | 0 |

**再叠加三条独立证据：**
| 来源 | 结论 |
|---|---|
| **本机实测 caps**（`HidP_GetValueCaps`，`access=0` 句柄） | `0x0E` page 下**只有 `0x23`**；无 `0x21`/`0x10`/`0x11` |
| **GT7863**（华为 MateBook，同族 GT7） | 项目已确认描述符里**同样没有 `0x0E/0x21`** |
| **Goodix 官方 `fwupd/plugins/goodix-tp`**（GTX8/BRLB 两族源码） | **零触觉命令**，只有固件更新 + 内存读写 |

**⇒ 六路 + 三条旁证 = 没有任何一份汇顶相关的固件/驱动含带扳机的描述符。**

---

## §5 诚实的局限（不能把"搜不到"说成"一定没有"）

| 局限 | 说明 |
|---|---|
| **GT7868Q 的 97 KB 加密区** | 已判定"不是代码"（熵 7.998），**搜不了**。若描述符模板藏在里面，本次搜索看不见 |
| **描述符可能是运行期构造的** | 很多 MCU 用代码拼 HID 描述符，而非放静态数组 ⇒ 字节搜索会漏 |
| **搜索范围** | 只覆盖了本机机型（TB14+ 21LD）的 BIOS/固件。**别的汇顶机型没查** |
| **Goodix 的其它家族** | 只看了 GTX8/BRLB（fwupd 里的两族）。**若汇顶有第三族支持 HUTRR63，本报告看不出来** |

---

## §6 ⇒ 由此得到的可执行结论

**① 想"造"一个带扳机的汇顶设备，技术上只需在设备描述符里补 §3 的六条 —— 门槛不高（微软规范 + HUTRR63 都公开）。**
**② 但那是设备侧的事，与"纯软件"约束冲突。**
**③ 想"找"一个现成带扳机的汇顶机型，可查的权威名单目前都没有：**
| 名单 | 触控板条目 |
|---|---|
| 微软 `InputHapticsManager` [Supported Device Database](https://microsoft.design/wp-content/uploads/2026/06/Supported-Device-Database.pdf)（2026-06） | **只有 Surface Laptop 8 / 8 for Business** |
| Linux `INPUT_PROP_HAPTIC_TOUCHPAD` | 上游刚合入（6.18），**未见汇顶设备报告** |

**④ ★ 最可靠的"探测器"其实是一句话：`0x0E/0x23` 在 OUTPUT 还是 FEATURE。**
- **OUTPUT**（在 Manual Trigger 报表里）⇒ **有扳机**
- **FEATURE**（独立一条）⇒ **没扳机**（本机是这种）
**⇒ 这个判据可以在**任何一台机器**上、用**用户态只读**（`HidP_GetValueCaps`）在几秒内做出来** —— 这正是"能力探测层"该做的事。
