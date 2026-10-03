# 追加十九 —— 蓝莓的触控板怎么和主机沟通 · 主机有没有"发送震动"的指令

> 日期：2026-09-28 · 全部来自他的源码与描述符（程序化搜索，见下）
> 问题：① 蓝莓的触控板怎么和主机沟通？② 主机有发送震动的指令吗？

---

## §0 一句话

> ## **主机没有"发送震动"的指令 —— 一条都没有。**
> **他 869 字节的 HID 描述符里，`0x0E`（Haptics）usage page 出现 **0 次**。**
> **主机能做的只有"调参数"（强度、力度阈值、手势映射）；"何时震"完全由他的 ESP32 固件决定。**

---

## §1 描述符程序化搜索结果（决定性证据）

拉取 `Hacking/README.md` 里的 HID Descriptor，剥成字节后逐项检索（869 字节）：

| 检索项 | 含义 | 出现次数 |
|---|---|---|
| **`05 0E`** | **Usage Page = Haptics** | **0** |
| **`09 21` / `0B 21`** | **Manual Trigger** | **0** |
| **`09 23` / `0B 23`** | **Haptics Intensity** | **0** |
| **`09 10` / `0B 10`** | **Waveform List** | **0** |
| **`09 11` / `0B 11`** | **Duration List** | **0** |
| **`09 B0` / `0B B0`** | **Button Press Threshold** | **0** |
| `91 02`（Output 项） | — | **2** —— 都在 `06 00 FF`（0xFF00 vendor collection）里：**RID `0x09` 与 `0x0A`，各 20 字节** |
| `05 0D`（Digitizers） | — | 14 |
| `09 C5` | = 我们本机也有那个 256 B 认证页 | 1（RID 7） |

全部 Report ID：`02 · 03 · 08 · 0D · 07 · 04 · 06 · 09 · 0A · 0B · 0C · 0F · 0E · 22 · 23 · 24 · 25`

**⇒ 结论：他的设备**根本不向主机声明任何触觉能力** —— 连 `Intensity` 都没有。**

---

## §2 双向沟通通道清单

### 设备 → 主机
| 通道 | 内容 |
|---|---|
| **PTP 多点触控报表**（RID 3） | 坐标/压力/触点数（标准精密触控板） |
| **鼠标报表**（RID 2） | 兼容模式 |
| ★ **`aux_output.c` 的 aux 辅助输出** | **他自己的手势实现方式**：设备端识别手势 → **直接向主机发**鼠标按键/滚轮（RID 2）、消费者控制（RID 7，媒体键 `0xe2`/`0xcd`/`0xb6`…）、键盘（RID 8，含 `AUX_KNUCKLE_SCREENSHOT` = Win+PrintScreen） |
| vendor input 报表 | RID `0x0B` / `0x0C`（各 61 字节） |

> **★ 方向要点**：`aux_output.c` 是**设备→主机**的。**他是"设备端做手势识别 + 直接发快捷键"，不是"主机发指令让它做事"。**

### 主机 → 设备
| 通道 | 内容 |
|---|---|
| **vendor feature 报表** | RID `0x22`(1 B) · `0x23`(15 B) · `0x24`(12 B) · `0x25`(1 B) · `0x0E`(1 B) · `0x0F`(3 B) · RID 8（`0x55`/`0x59`）· RID `0x0D`（`0x0D/0x60`） |
| **2.4G 无线扩展** | `rstp_protocol.c` / `wireless_extension.h` |
| **vendor OUTPUT** | RID `0x09` / `0x0A`（各 20 B，0xFF00 集合） |

**★ 关键代码注释（`device_config.h`）**：
```c
esp_err_t device_config_set_legacy(unsigned offset, uint8_t value, bool persist);
/* Bits 0/1 select intensity/press level; apply a combined Windows update once. */
esp_err_t device_config_set_controls(uint8_t mask, uint8_t intensity, uint8_t level, bool persist);
```
**⇒ "apply a combined Windows update" —— 主机会通过一条 vendor 报文**同时下发「强度」和「力度阈值」**两块偏好设置。**

**配套设置层（`surface_haptic_settings.c`）**：
```c
uint8_t ptp_haptic_click_intensity_get(void);              // 0..100，默认 63
esp_err_t ptp_haptic_click_intensity_set(uint8_t, bool);
esp_err_t ptp_haptic_click_intensity_set_report(const uint8_t *data, size_t length, bool persist)
{   if (length != 1) return ESP_ERR_INVALID_ARG;
    return ptp_haptic_click_intensity_set(data[0], persist); }   // ★ 1 字节 feature
// value == 0 ⇒ cs40l25_surface_cancel_click()
```
**力度阈值层（`hid_msg.c`）**：
```c
uint8_t ptp_button_press_threshold = 0x02;                 // 值域被 clamp 到 1..3
void ptp_button_press_threshold_set(uint8_t, bool persist);// 存 NVS: "btn_press_th"
```

**⇒ 所以主机能发的是「偏好设置」：强度 0–100、力度阈值 1–3、手势动作映射、旋转、X/Y 范围等 —— 全是配置，没有"执行"。**

---

## §3 震动是怎么发生的（100% 在设备端）

```
压力过阈值  →  surface_runtime_button(r, down, setting, now)
                    ├─ surface_haptic_resolve(setting, &pair)   // 强度 → 波形索引对
                    └─ surface_haptic_play_event(pair, release)
                          └─ bsp_dut_apply_haptic_mapping(...) + bsp_dut_trigger_haptic(wave, 0)

手势        →  surface_runtime_gesture(r, point, now)          // ★ 区分 point / edge
                    └─ SURFACE_GESTURE_POINT_WAVE / _EDGE_WAVE → 同样走 bsp_dut_trigger_haptic()
```

**⇒ 主机全程不参与触发。主机的角色只是"改 `setting` 那个数字"。**

---

## §4 ★★ 与我们本机的对比（这一栏最关键）

| | **蓝莓的设备**（自制 ESP32 + Surface + CS40L25） | **我们本机**（GXTP5100 + TF100A） |
|---|---|---|
| 主机能写的触觉参数 | **强度 0–100 ＋ 力度阈值 1–3**（都用 vendor feature） | **只有强度**（`0x0E/0x23`，标准 feature） |
| 主机能触发震动吗 | ❌ **不能**（`0x0E` page 零出现） | ❌ **不能**（无 `0x0E/0x21`，`Out=0`） |
| 谁决定"何时震" | **他的 ESP32 固件**（压力阈值 + 手势） | **原厂 TF100A 固件**（局部反射） |
| 能不能加"手势震动" | ✅ 能（`SURFACE_GESTURE_POINT_WAVE` / `_EDGE_WAVE`） | ❌ 不能（39 条命令全覆盖无马达入口） |
| 256 B 认证页 | 有（RID 7，`0xFF00/0xC5`） | 有（RID 6，同 usage） |

> ## **★★ 他有一个我们本机没有的旋钮：力度阈值（1–3）。**

**⇒ 按微软规范，`0x0D/0xB0 Button Press Threshold` 是 device-initiated 设备的**可选第二个旋钮**（"加 host-initiated 后变强制"）。**
**⇒ 蓝莓的设备**有**这个能力（虽然是 vendor 形态）；**我们本机没有**（`0x0D/0xB0` 在 caps 里不存在）。**
**⇒ 也就是说：「把阈值调到最低 ⇒ 接触就震」这个思路，在他的硬件上理论上更可行；而在我们这块板上，连这个旋钮都没有。**

---

## §5 结论

> **① 蓝莓的触控板与主机的沟通 = 标准 HID（PTP 输入 + 鼠标/消费者/键盘 aux 输出 + 一组 vendor feature 配置通道）。**
> **② 主机**没有**任何"发送震动"的指令 —— 描述符里 Haptics page 零出现，唯一两个 OUTPUT 是 0xFF00 vendor 集合（20 字节，且 `aux_output.c` 的 id 只用 2/7/8，说明那两个用于无线扩展/配置，不是触觉）。**
> **③ 他让触控板震动的唯一途径是「自己写设备固件」：手势/压力在设备端判定 → 直接驱动 CS40L25。主机只负责改"强度"和"力度阈值"两个数字。**
> **④ 因此他那句"连 MCU 自己摸协议完事"的完整含义是：**"把设备侧换成我能编程的，然后触觉就成了我的固件问题"** —— 主机侧的协议从来不是答案，**主机侧本来就没有那句话**。**
