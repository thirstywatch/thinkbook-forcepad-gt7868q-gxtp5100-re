# 追加十七 —— 三项纠正 · 厂商驱动扫描的结构性结论

> 日期：2026-09-28 · 子代理（纯离线二进制解读）+ 厂商 Windows 驱动 INF 实扒
> 本文更正项目两处推理，并关闭一个长期挂账项。

---

## §1 ★★ 重大纠正：那个 256 字节"高熵数据"就是**微软规范里公开的样例 blob**

**子代理结论（可复现：`fw-touchpad/hid-probe/_verify_ptphqa.py`）**：

> **`col02_feature_256B.bin` 与微软 PTP 规范公开的默认 `PTPHQA` 样例 blob 逐字节 256/256 相同**
> （开头 `fc 28 fe 84 40 cb 9a 87 0d be 57 3c b6 70 09 88 07 97 2d …`）

**⇒ 所谓"高熵随机数据 / 判为签名或密钥类"（`00-触控板结论总表.md` 等多处）**实际是公开常量**，零信息量。**

**⇒ 这关闭了一个长期挂账项**：
| 旧记录 | 更正 |
|---|---|
| "`Col02` feature 那 256 字节页的语义未解（判为签名/密钥类，无法验证）"（`追加十四` §5 残余） | **已解：微软 PTPHQA 默认样例 blob，公开常量** |

**⇒ 同时解释了 `追加十六` 里"vendor feature 面可能有戏"的期待：`0xFF00/0xC5`（256 B）那一页**没有**厂商私有内容。**

---

## §2 ★ 纠正：`col02_feature_rid9_full.bin` 其实是 **RID 6** 的应答，不是 RID 9

子代理逐字节证据：

| 文件 | 首字节 | 判定 |
|---|---|---|
| `col02_feature_rid2_full.bin`（737 B） | `02` | **RID 2** 应答（`02 15`）**＋ 735 × `00` 未初始化填充** |
| `col02_feature_rid9_full.bin`（737 B） | **`06`** | ★ **RID 6** 应答（`06` + 256 B PTPHQA blob）**＋ 480 × `00`** —— **不是 RID 9** |
| `col02_feature_256B.bin`（256 B） | — | = `rid9_full[1:257]`，唯一位于 offset 1 的连续子串 |
| `col02_feat_rid2.bin` / `feat_rid9.bin`（各 8 B） | `02` | **md5 完全相同** ⇒ 都是 RID 2 的应答 |

**⇒ 而且：** 同目录既有的受控扫描 `col02-precise/summary.json` 显示 **RID 6 / 7 / 9 / 11 / 12 / 13 的 257 B 应答 md5 两两相同**（头部 `06 FC 28 FE 84 40 CB 9A`），未声明的 RID 读取直接失败。

**⇒ 结论（含推测标注）**：
- **观察事实**：这 6 个 RID 的 `GET_FEATURE` 返回**同一份缓存的 RID 6 认证报表**；未声明 RID 则失败（说明驱动按描述符校验了 RID）。
- **推测（理由：六者逐字节相同 + 尾部保持缓冲初值 + LKML 独立旁证）**：这些 feature 的 `GET_FEATURE` **未路由到设备寄存器**。
- **★ 旁证**：Linux LKML 的 RFC 里，作者在**他自己的压感板**上报告了同一现象 ——「GET feature returns garbage data… the guide only requires SET_FEATURE support」。

**⇒ ⇒ 所以 `0xFF00/0xC4`(4 B) / `0xC6`(736 B) / `0xC7`(66 B) 这三个 vendor feature 的真值，用 `GET_FEATURE` **拿不到**；只能靠 I2C/驱动层抓包。**

---

## §3 ★ 纠正：`col02-writeprobe` 的"读回不变 ⇒ 写入无效"推理**不成立**

- 既然 `GET_FEATURE` 返回的是缓存 blob、与写入无关，那么**"读回不变"完全不能用来判断写入是否生效**。
- **⇒ 正确做法**：写 `SET_FEATURE` RID 9 后用**手感 / 录音 / 加速度计**验证。
- **⚠️ 但这不影响 `追加十五` 的实验**：那次读的是 **Col04 的 `0x20` 设备内存**（`0x4000`/`0x5B80`），不是 feature 回读 ⇒ **"写 intensity 对这两个窗口零影响"的结论仍然成立**。
- **⇒ 也不影响 `WHY-NOT-VIBRATE` §3 的结论**：那个盲测用的是**体感**（正确方法），结论"力度变、不产生震动"依然有效。

---

## §4 顺带确证：RID 2 的位序（被微软规范唯一确定）

`RID 2` 应答 = `02 15`：
- 低 4 位 = **Contact Count Max = 5**
- 高 4 位 = **Button Type = 1 = 非按压式压感板（pressure-pad）**
- 依据：反解会让 Button Type = 5，而**规范只允许 0/1/2** ⇒ 位序被规范唯一确定
- **⇒ 与"设备自决触觉（device-initiated）"这个前提完全吻合**

**⇒ 并再次确认：`0x0D/0xB0 Button Press Threshold`（第二个规范旋钮）**本机不存在**。**

---

## §5 ★ 厂商 Windows 驱动实扒结果（Goodix 官方 INF）

从一台土耳其厂商服务器扒下真实的 Goodix 触控驱动包，解码 `oem3.inf`（2,039 B）：

```ini
[Version]
Signature="$WINDOWS NT$"
Class = HIDClass
ClassGuid = {745a17a0-74d3-11d0-b6fe-00a0c90f57da}
Provider=%ManufacturerName%                 ; ⇒ "Shenzhen Huiding Technology Co.,Ltd."（= 汇顶科技）
CatalogFile=GoodixTouchDriver.cat
DriverVer = 08/31/2023,4.7.2.49211

[Standard.NTamd64.6.1]
%GoodixTouchDriver.DeviceDesc%=GoodixTouchDriver_Device, ACPI\GDIX1002

[GoodixTouchDriver_Device.NT.HW]
AddReg = GoodixTouchDriver_Reg_Parameters.AddReg

[GoodixTouchDriver_Reg_Parameters.AddReg]
HKR,, "UpperFilters",0x00010000,"mshidkmdf"          ; ★ 微软自带的 HID KMDF shim
HKR,, "EnhancePowerManagementEnabled",0x00010001,1

[GoodixTouchDriver_Service_Inst]
ServiceType = 1          ; SERVICE_KERNEL_DRIVER
StartType   = 3          ; SERVICE_DEMAND_START
ServiceBinary = %12%\GoodixTouchDriver.sys
LoadOrderGroup = Extended Base
```

## ⇒ 结构性结论：**厂商驱动里不会有"触发震动"，因为那不是驱动的职责**

| 观察 | 含义 |
|---|---|
| `Class = HIDClass` + **`UpperFilters = mshidkmdf`** | 厂商驱动只是**挂在微软 HID 栈上的一个壳**，把设备报给系统 |
| 注册表参数只有 `EnhancePowerManagementEnabled` | **没有**任何触觉/力度/波形参数 |
| `ServiceBinary = GoodixTouchDriver.sys` | 内核驱动，负责传输与电源 |
| 没有任何 usage / 命令 / 触觉字段 | **触觉不在这一层** |

**⇒ 与 §6 的四条独立证据完全一致。**

---

## §6 ⇒ 对"厂商驱动如何做到触觉"的最终回答

| 厂商 / 平台 | 触觉实现方式 | 主机能否触发 | 驱动里有什么 |
|---|---|---|---|
| **Goodix（GT7/GTX8 家族）** | 交给**设备固件**（device-initiated） | ❌ | 官方开源 `fwupd/plugins/goodix-tp`：**只有固件更新 + 内存读写，零触觉命令**；Windows 驱动：**HIDClass 壳 + 电源管理** |
| **Microsoft** | `InputHapticsManager` API + **设备白名单** | ✅ **但仅限白名单设备**（2026 年列表里触控板只有 **Surface Laptop 8**） | 系统级，非厂商驱动 |
| **Apple** | 私有 `MTActuator*` API | ✅（全系 Force Touch） | 系统私有框架 |
| **Valve** | HID output report + FF | ✅ | `hid-steam` |
| **Linux 上游** | `hid-haptic.c`：`auto trigger waveform` 置 `WAVEFORM_STOP` 切 host-controlled | ✅ **需设备满足五条**（我们缺四条） | `for-6.18/haptic` |

> ## **⇒ 触觉的实现位置只有两个：① 设备固件（自决）；② 设备声明 host-controlled 协议面。**
> ## **厂商驱动从来不"创造"触觉能力 —— 它只做传输、电源、以及把设备能力报给系统。**

**⇒ 所以"把 GT7 系列的厂商驱动扒下来看"这条线，**已经到头了**：
- Goodix 官方源码（GTX8/BRLB 两族）→ **零触觉命令**（`VIB-REOPENED.md` §18.5 L690 早已记录）
- Goodix Windows 驱动 INF → **HIDClass 壳 + 电源管理**（本文 §5）
- GT7863（华为同族）描述符 → **同样没有 `0x0E/0x21`**（`WHY-NOT-VIBRATE.md` L127）
- ty2 / mainline 的 GT7868Q patch → **只做描述符第 607 字节 fixup**（而那正是 `rid=9` Intensity 的量程项，`STATUS.md` L451）**

---

## §7 残余（诚实）

| 项 | 状态 |
|---|---|
| `0xFF00/0xC4`(4 B) / `0xC6`(736 B) / `0xC7`(66 B) 的真值 | **`GET_FEATURE` 拿不到**（返回缓存 blob）⇒ 只能 I2C/驱动层抓包 |
| `Col04`（RID 14，65 B 双向）里的厂商命令 | 39 条 TF100A 命令已全覆盖（无马达入口）；**GT7868Q 侧的命令**仍未知 |
| 华为电脑管家导入表扫描 | `PREFLIGHT-STATE.md` §6.10.2 第 2 项，**仍未做**（项目主动降级为可选） |
| 另有 1 个子代理（HID usage 官方语义）**仍在运行** | 会补 `0x0D/0x55`·`0x59` 的官方定义 |
