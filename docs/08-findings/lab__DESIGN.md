# ThinkBook 14+ 触控板「全局边缘手势」设计方案

> **【参考 · 设计方案，未随本轮更新】** 项目当前权威状态：`PREFLIGHT-STATE.md`。
> 本文是 PC 侧手势方案的**设计稿**（对应 `PREFLIGHT-STATE.md` §5 的「后置工作」），仍可作实现参考。

> **目标机器**：Lenovo ThinkBook 14 G6+ IMH（机型码 21LD）· Windows 11 25H2（26200.9445）
> **触控板**：Goodix **GXTP5100**（VID `0x27C6` / PID `0x01E9`）· I2C-HID · Windows 精确式触控板 · 压力感应 + LRA 触觉
> **版本**：v1（待评审）· 全部结论均在本机实测得出，证据见附录

---

## 0. 结论速览

| 问题 | 结论 |
|---|---|
| 要不要逆向？ | **手势功能不需要**。联想自己也是用户态 Raw Input 读触控板，我已在本机跑通同款探针，能实时拿到每根手指的 X/Y/压力。 |
| 能做成华为那样全局单指吗？ | **能，且不用驱动**。用 `ClipCursor` 在边缘手势期间把光标"焊死"，绕开"单指滑动必移光标"这个唯一冲突点。系统与联想都没这么做。 |
| 震动反馈？ | **标准 API 是死路**（触控板没有 Manual Trigger 输出报文，且该 HID 集合被系统独占）；**唯一活路是逆向厂商通道 Col04**，实测该通道用户态可读写。 |
| 工作量 | MVP 一个会话内可跑起来；完善 2~3 轮；震动逆向独立立项，成功率估 30~50%。 |
| 需要装什么 | **不需要**。用系统自带 .NET Framework 4.8 + `csc.exe` 编译成单文件 exe。 |

---

## 1. 目标与非目标

### 目标
1. 单指在触控板**左边缘上下滑 → 调屏幕亮度**，**右边缘上下滑 → 调音量**，**任何应用下都生效**（不再限定全屏）。
2. 滑动时**光标不能乱跑**（这是华为体验的核心，也是本方案的技术重点）。
3. 有跟随的进度条 OSD，手感可调（步进粒度、灵敏度、加速曲线）。
4. 常驻托盘、可随时暂停、开机自启、参数写在配置文件里方便调。

### 非目标（本期不做）
- 不做内核驱动、不修改联想任何文件、不替换系统驱动。
- 不追求"和华为一模一样"的震动反馈（见 §2.5，需要先立项逆向）。
- 不实现触控屏手势（本机无触摸屏）。

---

## 2. 侦查结论（本机实测）

### 2.1 触控板能力（读 HID 报告描述符得到，非推测）

触控板共 4 个 HID 集合：

| 集合 | 顶层 Usage | 作用 |
|---|---|---|
| Col01 | `0x01/0x02` | 鼠标兼容接口 |
| **Col02** | `0x0D/0x05` | **Windows 精确式触控板（手势数据来源）** |
| Col03 | — | Microsoft Input Configuration Device（配置用） |
| **Col04** | `0xFF00/0x01` | **Goodix 厂商自定义通道（震动的唯一入口）** |

**Col02 的输入报文（Report ID 4，40 字节）**：

| 字段 | Usage | 位宽 | 取值范围 |
|---|---|---|---|
| 接触数 Contact Count | `0x0D/0x54` | 8 | 0–127 |
| 扫描时间 Scan Time | `0x0D/0x56` | 16 | 0–65535 |
| 触点 ID（每个触点） | `0x0D/0x51` | 4 | 0–15 |
| X（每个触点） | `0x01/0x30` | 16 | **0–4149** |
| Y（每个触点） | `0x01/0x31` | 16 | **0–2147** |
| **压力 Tip Pressure（每个触点）** | `0x0D/0x30` | 16 | **0–2000** |
| 触点按下状态 | `0x0D/0x42` Tip Switch | 按钮位 | 0/1 |

触点用 5 个 link collection 承载，即**最多 5 指**，每个触点有独立 ID / X / Y / 压力。
另有 Feature 报文：`Contact Count Maximum`(rid=2)、触觉强度 `0x0E/0x23`(**rid=9**)。

> X 量程 4149、Y 量程 2147（比值 1.93）。边缘带按 X 的百分比划，不依赖物理尺寸。

### 2.2 为什么重装系统时触控板不能用（回答那个疑问）

触控板不是 USB 即插即用，而是 **I2C-HID**，设备栈是：

```
ACPI\GXTP5100  →  hidi2c（微软内置的 I2C-HID 传输）
      ↑ 挂在 I2C/SPB 控制器下
ACPI\LTCN0001  →  TcnPeripheral（oem14.inf「Sunia SPB Peripheral Driver」，第三方驱动）
ACPI\INTC1083  →  iaLPSS2_GPIO2_MTL（oem18.inf，Intel Serial IO）
```

**I2C-HID 设备必须总线驱动先加载，触控板才会被枚举。** WePE 和 Windows 安装界面都是 WinPE 环境，里面没有这些 OEM 驱动 → I2C 控制器起不来 → 触控板在系统视角里**根本不存在**。所以"装了驱动才能用"是**必然的因果**，不是巧合。

> 实用副产品：以后重装系统若想在安装界面用鼠标，需要把 Intel Serial IO + Sunia SPB 驱动用 `DISM /Add-Driver` 注入 `boot.wim`。
> 与本项目无关——本项目全部工作在正常系统的用户态。

### 2.3 联想原功能是怎么实现的（以及为什么被限死在全屏）

组件：Vantage 的 `SmartInteractAddin` → `GestureInner.dll`（内部工程名 `SmartGesture`）+ `OSDControl.exe`（OSD）+ `SmartInteractAddin.dll`（发按键）。

机制（从导入符号与字符串直接读出）：

| 环节 | 实现方式 |
|---|---|
| 取触控板数据 | `RegisterRawInputDevices` / `GetRawInputData` / `HidP_GetUsageValue` —— **用户态 Raw Input** |
| 全屏门槛 | `CommonUIHelper::IsFullScreenActive` + `IsProcessMatch`，日志串 `"Air Gesture: Not full screen or process not match"` |
| 调亮度 | `root\wmi` → `WmiMonitorBrightnessMethods.WmiSetBrightness`（异步线程 `ThreadSetBrightness`） |
| 调音量 | `SendInput` + `KEYBDINPUT`（VK_VOLUME_*） |
| 弹 OSD | 拉起 `OSDControl.exe` |

**全屏限制的根因**：这个手势是"单指在边缘上下滑"，而桌面上单指滑动就是**移动光标**，必然打架。全屏看视频时鼠标指针本来隐藏，联想索性不处理，只在全屏放行。
华为能让它全局生效，技术上说通的路径只有一条：**驱动层把"边缘起手的触点"的位移对系统屏蔽掉**。这就是两家体验差异的全部根源，也是本方案 §4.4 要解决的问题。

### 2.4 用户态到底能拿到什么（三个实测实验）

| 实验 | 结果 | 含义 |
|---|---|---|
| Raw Input 注册 `0x0D/0x05` + 解析 | ✅ 实时收到 5 触点 X/Y/压力/接触数 | **手势数据源成立**，与联想同路径 |
| `CreateFile` 打开 **Col02**（触控板集合） | ❌ `ERROR_SHARING_VIOLATION`(32) | 该集合被系统触控板栈**独占**，我们无法直接读写它的 Feature/Output 报文 |
| `CreateFile` 打开 **Col04**（厂商通道） | ✅ **READ 与 READ\|WRITE 都成功** | **震动逆向的通道存在且可写** |

> 关键点：Raw Input 是"旁路监听"，**不需要打开设备**，所以系统独占 Col02 完全不影响我们读手势数据。

### 2.5 震动反馈判定（逐条对照微软 Haptic Touchpad 规范）

| 规范要求 | 本机情况 |
|---|---|
| 触控板集合内应有 `Simple Haptic Controller` 子集合（`0x0E/0x01`） | ✅ 有（link collection 6），内含 `Haptic Intensity`（`0x0E/0x23`，Report ID 9） |
| 设备自主反馈（按下/抬起时震动） | ✅ 有（**实测**：Col02 写 `rid=9` → 50 变轻 / 100 消失 / 10 恢复，用户体感验证）<br>⚠️ 注册表里的 `FeedbackIntensity=100` / `ClickForceSensitivity=50` **不能**当"系统在用它"的证据：同键内 `ClickForceSensitivity` 对应的报表本机根本不存在（见 `STATUS.md` §16.3），说明该键是**无差别的默认值转储**，不是能力清单 |
| 主机发起反馈需要 **Manual Trigger 输出报文**（`0x0E/0x21`） | ❌ **没有**——Col02 的 `OutputReportByteLength = 0` |
| 主机发起反馈需要可写的触控板集合 | ❌ Col02 被系统独占，用户态无法写 |

**权威依据（三份公开材料交叉确认，2026-06 补充）：**

- 微软 [Input Device Haptics Implementation Guide](https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/input-haptics-implementation-guide)：主机发起触觉**必须**提供 `Manual Trigger`（`0x0E/0x21`）输出报文；设备自主触觉只提供 `Haptic Intensity`（`0x0E/0x23`）这类 SET_FEATURE 旋钮。
- USB-IF **HUTRR63**（Haptics Page 增补）：同类设备的 HID 触觉协议定义。
- Google ChromeOS 团队 upstream 系列 [`[PATCH v2 00/11] HID: Implement haptic touchpad support`](https://patchew.org/linux/20250804-support-forcepads-v2-0-138ca980261d@google.com/) + LKML [`[RFC] Adding device-initiated haptic feedback knobs for pressurepads`](https://lkml.iu.edu/hypermail/linux/kernel/2606.2/01413.html)：明确定义两种模式——**device-controlled**（设备按力度阈值自主触发按下/抬起反馈）与 **host-controlled**（主机/用户态主动触发效果）。进入 host-controlled 需设备同时提供 `Auto Trigger`(`0x0E/0x20`)、`Waveform List`/`Duration List`(`0x0E/0x10`/`0x11`)、`Manual Trigger`(`0x0E/0x21`)。

**本机逐项比对：**

| 能力 | 本机 | 依据 |
|---|---|---|
| `Simple Haptic Controller` 子集合（`0x0E/0x01`） | ✅ 有 | link collection 6 |
| 强度旋钮 `Haptic Intensity`（`0x0E/0x23`） | ✅ **Report ID 9**；⚠️ **原厂描述符是坏的**——实测解析出的逻辑范围是 `[100, 1]`（**上下限颠倒**，见 `poc/hid-dump.txt:38`），**本意应为 0–100** | 该字节正是 Linux 社区必须修的**描述符第 607 字节**（`0x15`→`0x25`，ty2 驱动 `local-overrides.quirks`）；LKML RFC 作者贴出的描述符与本机逐字段一致。**这很可能就是 Windows 设置里不显示触觉强度控件的原因** |
| 设备自主反馈（按下/抬起震动） | ✅ 有 | 有 Intensity 旋钮即属此模式 |
| `Auto Trigger`(`0x0E/0x20`) / `Waveform List`(`0x0E/0x10`) / `Duration List`(`0x0E/0x11`) | ❌ 全无 | Feature 能力表里只有 rid=2 与 rid=9 |
| `Manual Trigger`(`0x0E/0x21`) 输出报文 | ❌ 无 | Col02 `OutputReportByteLength = 0`（整块板子没有任何输出报文） |
| 用户态可写该集合以发 SET_FEATURE | ❌ | Col02 `CreateFile` → `ERROR_SHARING_VIOLATION` |

**结论（三重确认，可定性）：**
1. 本机触控板是**纯设备自主触觉 + 一个强度旋钮**，**不实现主机发起触觉协议**。即：**任何应用程序都无法让这块板子按指令震动**——不是驱动问题、不是 Windows 限制，而是设备端固件没有实现该协议面。
2. 反过来说：**即使把华为的实现原样搬过来，也震不起来**——缺的是设备端能力，不是软件。
3. 强度旋钮本身我们也调不了：写它需要对 Col02 发 SET_FEATURE，而该集合被系统独占（只能通过 Windows 设置的「触控板反馈 → 强度」滑块）。
4. **唯一剩下的可能性**是 Goodix 厂商通道 **Col04**（Report ID 14、64 字节 IN/OUT、usage page `0xFF00`，实测可读写）里存在未公开的震动命令。这是真·逆向，**成功率已从初估 30–50% 下调至 15–25%**，证伪条件见 §6 Phase 3。

**关于"厂商通道里找命令"这条路的证据评估（2026-06 补充）：**
- 支持面：同族板子的厂商集合**确实是活的**（Linux 补丁记录华为/荣耀那块会以 1 Hz 上报心跳）；本机马达确实存在（社区实测点击有"力回馈"、Windows 设置里有「触控板反馈 → 强度」）；产线测试与固件升级通常也需要能驱动马达。
- 反对面：已知用途是**遥测/状态上报**而非命令通道；若固件真具备完整触觉能力，厂商最省事的做法是直接声明标准报文（华为那块板就是这么做的），没理由只在私有通道开后门。
- **已排除的线索**：社区项目 [`ty2/goodix-gt7868q-linux-driver`](https://github.com/ty2/goodix-gt7868q-linux-driver)（GT7868Q = `01E8`）核心源码仅 1663 字节，本质是给 `hid-multitouch` 加描述符 fixup，**不含厂商协议实现**。附带信息：上游 [`HID: multitouch: Add report_fixup for Goodix GT7868Q`](https://lists.openwall.net/linux-kernel/2024/08/19/1403) 称该芯片是 "**a haptic touchpad** used on Lenovo **ThinkBook 13x Gen 4**"——又一台"联想 + Goodix 触觉板"。

### 2.6 同族硬件证据：华为 MateBook X Pro 的触控板也是 Goodix

FreeBSD 社区在 MateBook X Pro 2023 上的一手 dmesg：

```
iichid0: <GXTP7863:00 27C6:01E0 I2C HID device> at addr 0x15 on iicbus14
hmt0: <GXTP7863:00 27C6:01E0 TouchPad>
hmt0: 5 contacts, Report range [0:0] - [3684:2338]
iichid1: <GXTP738X:00 27C6:0114 I2C HID device>   ← 触摸屏，同为 Goodix
```

Linux 内核 `drivers/hid/hid-ids.h` 里两者是**相邻同族条目**：

```c
#define I2C_VENDOR_ID_GOODIX      0x27c6
#define I2C_DEVICE_ID_GOODIX_01E0 0x01e0   /* 华为 MateBook X Pro 2023 / 荣耀 MagicBook = GXTP7863 */
#define I2C_DEVICE_ID_GOODIX_01E8 0x01e8
#define I2C_DEVICE_ID_GOODIX_01E9 0x01e9   /* 本机 ThinkBook 14+ = GXTP5100 */
```

**三条推论：**

1. 两块板子**同厂（Goodix）、同总线（Intel I2C 上的 I2C-HID）、同驱动类**（Linux 都归入 `MT_CLS_WIN_8_FORCE_MULTI_INPUT_NSMU`），PID 相邻 → 厂商命令通道**很可能是同一协议族**。
2. 那批 Linux 补丁顺带证明：这类板子的**厂商集合是"活"通道**——会周期性上报心跳/遥测（Linux 通用驱动甚至把 1Hz 心跳误读成无限 `KEY_BRIGHTNESSUP` 连发）。本机 Col04 是否也发心跳，可用只读实验验证（§6 Phase 3.1 步骤 0）。
3. 因此"研读华为实现"的价值从"看别人怎么写"升级为"**可能拿到同一芯片族的真实命令序列**"——这是震动逆向里性价比最高的一条路。

#### 2024 款的查证结果（重要）

华为 2023 与 2024 两代 MateBook X Pro **用的是同一块触控板**，两个独立一手来源：

- Deepin 的 libinput quirks 文件 `50-system-huawei.quirks`：
  `[Huawei MateBook X Pro 2024 Touchpad (27C6:01E0)]` + `MatchName=*GXTP7863*` + `ModelPressurePad=1`
- Linux Mint 论坛 2024 款用户（DMI 机型码 `VGHH-XX`，与拆解报告的 `VGHH-32` 一致）：
  `[Huawei MateBook X Pro 2024 Touchpad] MatchName=GXTP7863* ModelPressurePad=1`

| | 华为 X Pro 2023 / 2024 | 本机 ThinkBook 14+ 2024 |
|---|---|---|
| 厂商 / 型号 | Goodix **GXTP7863** | Goodix **GXTP5100** |
| VID:PID | **27C6:01E0** | **27C6:01E9** |
| 类型 | 压力触控板 + LRA（`ModelPressurePad=1`） | 压力触控板 + LRA |
| 拆解要点（2024 款） | **电涡流压感 + X 轴线性马达**（马达镭雕 `R0B3`），官方称"8 种创新手势" | — |
| 系统 | **WIN11 HOME**（Windows 实现可分析） | WIN11 |

**结论**：2024 款没有换芯片，仍是与 2023 相同的 GXTP7863——与本机是"**同族兄弟**"，不是"同一块板"。所以华为实现的参考价值是"同族协议 + 同族能力边界"，而非"可直接移植"。
**但这次查证有一个额外收获**：它把我引到了这套板子类的权威公开资料（§2.7），从而把震动问题彻底定性了（§2.5）。

#### 华为的实现层级：官方文档已直接给出答案（关键）

华为官方支持页《[华为笔记本电脑如何使用压力触控板](https://consumer.huawei.com/cn/support/content/zh-cn15908056/)》（适用 Windows 10/11，机型含 X Pro 2022/2023/2024 全系）：

> 「计算机支持全新压力触控板功能，结合创新手势，可以实现窗口最小化、关闭窗口、快速截屏、录屏，**调节亮度、音量**，调节视频快进/后退、打开通知中心等功能。」
> **「此功能集成在华为电脑管家，使用时请保持华为电脑管家为运行状态。」**
> **「此功能要求华为电脑管家版本在 13.0.2.300 及以上。」**

设置入口与项目（《[如何设置压力触控板属性](https://consumer.huawei.com/cn/support/content/zh-cn15866077/)》）：**华为电脑管家 → 我的设备 → 压力触控板**

| 分组 | 内容 |
|---|---|
| 触控板设置 | 按压灵敏度、**振感强度（低/中/高）** |
| 指关节手势 | 截屏、录屏 开关 |
| **边缘手势** | **调节亮度、调节音量**、视频快进快退、最小化窗口、关闭窗口（均可开关） |
| 多指手势 | 打开通知中心、鼠标右键 |

**这三条事实直接改写了我们的判断：**

1. **华为的边缘手势是"用户态应用功能"，不是固件魔法、也不是驱动层功能**——否则不需要"保持电脑管家运行"、也不会随管家版本号（13.0.2.300+）解锁。
   → 说明**本方案的技术路线（用户态 Raw Input + 用户态光标处理）与华为是同构的**，我们不是在造一个"比人家低一档"的东西。
   → 也说明 §6 Phase 3.1 那句"若华为是驱动层屏蔽光标，则纯用户态做不到"的担忧**基本可以排除**。
2. **华为的震动是"设备自主触觉的强度可调"（低/中/高）**，与我们从描述符测到的 `Haptic Intensity`（Report ID 9）是同一个旋钮；滑动过程中的逐格震动则大概率来自**他们那块板子支持主机发起触觉**（本机不支持，见 §2.5）——这正好落在 Phase 3 的证伪条件上。
3. 既然实现层级已确认，**Phase 3.1 的"下载华为驱动包/电脑管家"不再是必要动作**（见 §6 Phase 3.1 更新）。

### 2.7 公开资料索引（这套硬件的一手材料）

| 材料 | 用途 |
|---|---|
| [微软 Input Device Haptics Implementation Guide](https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/input-haptics-implementation-guide) | 触觉协议权威规范（Auto/Manual Trigger、波形表、强度旋钮） |
| [微软 Touchpad Implementation Guide](https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/touchpad-devices) | 精确式触控板要求（本机 Col02 描述符即按此实现） |
| USB-IF HUTRR63（Haptics Page 增补） | HID 触觉用法的官方定义 |
| [`[PATCH v2 00/11] HID: Implement haptic touchpad support`](https://patchew.org/linux/20250804-support-forcepads-v2-0-138ca980261d@google.com/)（Google ChromeOS 团队） | 公开实现，定义 device-controlled / host-controlled 两种模式与切换条件 |
| [LKML RFC: device-initiated haptic feedback knobs for pressurepads](https://lkml.iu.edu/hypermail/linux/kernel/2606.2/01413.html) | 给出强度旋钮的真实描述符（Report ID 9 / 0–100），与本机逐字段一致 |
| Linux `drivers/hid/hid-ids.h` Goodix 段 | 同族 PID 对照（01E0 华为 / 01E8 / 01E9 本机 / 01F0） |
| libinput `50-system-huawei.quirks`、`quirks: add pressure pad quirk for Lenovo ThinkBook 14 G7+ ASP` | 两家压力触控板的识别参数（`ModelPressurePad`、掌压阈值、触摸尺寸范围） |

### 2.8 能力对照表：华为 FreeTouch 功能 → 本机可行性

以华为官方文档列出的功能集为基准（§2.6），逐项评估本机能否实现：

| 华为的功能 | 本机 | 依据 / 实现手段 |
|---|---|---|
| 左边缘上下滑 → 调**亮度** | ✅ 能 | Raw Input 读触点 + Dxva2/WMI 写亮度 |
| 右边缘上下滑 → 调**音量** | ✅ 能 | Raw Input + Core Audio 标量音量 |
| **全局生效**（不限全屏、不限应用） | ✅ 能，且优于联想 | `ClipCursor` 锁光标（§4.4）；联想只在全屏放行 |
| 边缘手势：视频**快进/快退** | ✅ 能 | 发媒体键（VK_MEDIA_NEXT/PREV_TRACK） |
| 边缘手势：**最小化窗口** | ✅ 能 | 对前台窗口 `ShowWindow(SW_MINIMIZE)` |
| 边缘手势：**关闭窗口** | ✅ 能 | 向前台窗口发 `WM_CLOSE` |
| 每个手势可**单独开关** | ✅ 能 | 配置文件 |
| **滑动过程中的逐格震动反馈** | ❌ **不能** | 本机固件无 `Manual Trigger`(`0x0E/0x21`) 输出报文，不实现主机发起触觉（§2.5）——**硬件能力缺失，软件无法弥补** |
| 振感强度（低/中/高） | ⚠️ 仅系统设置可调 | 旋钮存在（Report ID 9 / 0–100），但 Col02 被系统独占，程序写不进去 |
| 按压灵敏度（触发力度阈值） | ❌ 不能 | 本机未暴露 `Button Press Threshold`(`0x0D/0xB0`) feature report |
| 指关节双击 → 截屏 / 录屏 | ⚠️ 勉强 | 本机输入报文**没有触摸尺寸字段**，无法可靠区分指关节与指尖，只能靠压力特征猜，误判率高 |
| 多指手势（通知中心 / 右键） | — | Windows 自带，与本项目无关 |

**一句话总结**：**华为那套"全局边缘滑动调节亮度/音量"的核心功能，本机完全能做，而且能做得比联想更接近华为**（联想锁全屏，我们不需要）；唯一复制不了的是**滑动时的震动反馈**，那是你这块板子固件不支持主机发起触觉所致，与软件实现无关（§2.5）。

**本机相对华为的额外优势**（因为是我们自己写的，参数全开放）：步进粒度与加速曲线可调、左右边缘可互换/可换绑、可加应用黑白名单、OSD 样式自定。

**唯一待实测验证的环节**：`ClipCursor` 锁光标在真实使用中的手感与失效场景（前台全屏程序抢占剪辑区）。这在 Phase 1 MVP 里验证，并预留了位移补偿作为二级防御（§4.4）。

### 2.9 官方文档对 Col01~Col04 的定位（查证结果，2026-09-13）

微软《Touchpad Implementation Guide》系列文档明确规定精确式触控板各集合的职责，与本机实测逐一对应：

| 集合 | 本机实测 | 官方定义 | 与震动的关系 |
|---|---|---|---|
| Col01 | HID-compliant mouse（`0x01/0x02`） | 鼠标集合：设备可选以鼠标模式上报输入 | 无 |
| Col02 | **精确式触控板集合**（`0x0D/0x05`） | 主集合；触觉强度旋钮（`0x0E/0x23`）按规范亦挂在此集合内 | 强度旋钮所在；**无主机发起触觉** |
| Col03 | `0x0D/0x0E`，仅一条 Feature：`0x0D/0x52` log[0,10] | **配置集合（Configuration Collection）**：Input Mode（`0x0D/0x52`：0=鼠标集合、3=精确式触控板集合）+ Selective Reporting（`0x0D/0x57` surface switch / `0x0D/0x58` button switch） | 无 |
| Col04 | 厂商自定义（`0xFF00/0x01`）、Report ID 14、65 字节 IN/OUT | **固件与厂商配置更新集合（可选）**：原文 *"provide a vendor-specific top-level collection for performing device firmware and vendor configuration updates… could provide an output report for transferring the firmware payload from the host to the device"* | **这才是厂商命令通道**；但规范定位是固件/配置传输，**不保证存在触觉命令** |

**两点结论与一处更正：**

1. Col04 确实是"厂商命令通道"——我们的假设得到官方文档支持；要找隐藏的震动命令，只能在这条通道里找。
2. **更正此前的风险判断**：本机固件虽由 UEFI ESRT 投递，但 Col04 的规范用途**本身就是传输固件载荷**，因此"盲写 Col04 可能触发固件更新流程"的风险**真实存在**，此前"风险已排除"的说法作废。→ 任何写入测试都必须先用固件逆向确定命令格式，绝不盲试。
3. Col03 的用途已被官方文档解释清楚，与触觉无关，该支线关闭。

---

## 3. 总体架构

```
                    ┌──────────────────────────────────────────┐
                    │  Goodix GXTP5100 触控板 (I2C-HID)         │
                    └───────────────┬──────────────────────────┘
                                    │ HID 报文（报告描述符驱动解析）
        ┌───────────────────────────┴───────────────────────────┐
        │  ① 采集层  HidSource                                   │
        │  隐藏窗口 + RegisterRawInputDevices(RIDEV_INPUTSINK)    │
        │  WM_INPUT → GetRawInputData → HidP_GetUsageValue       │
        │  产出：TouchFrame{ contacts[], count, scanTime }        │
        └───────────────────────────┬───────────────────────────┘
                                    ▼
        ┌───────────────────────────────────────────────────────┐
        │  ② 手势状态机  GestureEngine                           │
        │  Idle → Armed → Active → Cooldown                     │
        │  边缘带判定 / 压力门限 / 位移积分 / 步进发射            │
        │  产出：StepEvent{ axis: Brightness|Volume, delta: ±1 }  │
        └───────┬───────────────────────────────┬───────────────┘
                │ 手势开始/结束                  │ 步进事件
                ▼                               ▼
   ┌────────────────────────┐    ┌──────────────────────────────┐
   │ ③ 光标锁 CursorLock    │    │ ④ 执行器 Actuators           │
   │ ClipCursor(2px 矩形)   │    │ 亮度：Dxva2 → 失败回退 WMI   │
   │ 闭环校验 GetCursorPos   │    │ 音量：Core Audio 标量音量     │
   │ 失效则启用位移补偿      │    │ （本地目标值 + 异步合并写入） │
   └────────────────────────┘    └──────────────┬───────────────┘
                                                ▼
                                 ┌──────────────────────────────┐
                                 │ ⑤ OSD 分层窗口（自绘进度条）  │
                                 └──────────────────────────────┘
        ┌───────────────────────────────────────────────────────┐
        │ ⑥ 宿主：托盘图标 / 配置(JSON) / 单实例 / 开机自启 / 日志│
        └───────────────────────────────────────────────────────┘
```

**模块职责**

| 模块 | 职责 | 关键点 |
|---|---|---|
| ① HidSource | 拿原始报文并解析成触点数组 | 隐藏窗口必须用 `RIDEV_INPUTSINK` 才能后台收报文；解析必须按 `(usagePage, usageId)` 建键 |
| ② GestureEngine | 判定"边缘单指上下滑"并产出步进 | 纯状态机、无副作用，方便单测与调参 |
| ③ CursorLock | 手势期间冻结光标 | 本方案的灵魂，见 §4.4 |
| ④ Actuators | 真正改亮度/音量 | 亮度接口慢，必须异步合并 |
| ⑤ OSD | 视觉反馈 | 分层窗口，不抢焦点 |
| ⑥ Host | 进程外壳 | 托盘、配置、自启、异常兜底 |

---

## 4. 关键算法

### 4.1 手势状态机

```
                 ┌──────────────────────────────────────────┐
                 ▼                                          │
  ┌────────┐  触点落下，X 在边缘带内，压力>门限  ┌────────┐    │
  │  Idle  │ ────────────────────────────────▶ │ Armed  │    │
  └────────┘                                   └───┬────┘    │
       ▲                                           │ |ΔY|>启动阈值
       │ 抬起/超时/条件破坏                         ▼          │
       │                                      ┌─────────┐    │
       └──────────────────────────────────────│ Active  │────┘
                                              └─────────┘  条件破坏
```

- **Idle**：`ContactCount == 0`。
- **Armed**（待命）：恰好 1 个触点在边缘带内落下，压力 > 门限（默认 150/2000，用于排除手掌/搭手），记录 `startX/startY/t0`。此时**还不锁光标**，避免误锁。
- **Active**（激活）：同一触点 `|ΔY| > 启动阈值`（默认 40 单位）→ 立刻锁光标，开始按位移发射步进。
- **Cooldown**：手指抬起后 250ms 内不接受新手势，防止连击。

**Active 期间的条件破坏（立即退出并解锁）**：
- 触点数变为 ≥2（用户其实想滚动/多指操作）；
- 触点横向移出边缘带（`|X - startX| > 带宽`，说明用户想正常用光标）；
- 压力掉到门限以下且位移停滞（手指搭在上面）；
- 超过 8 秒无位移（超时保护）。

### 4.2 边缘带与防误触

- **左边缘带**：`X < 0.14 × 4149 ≈ 580` → 亮度
- **右边缘带**：`X > 4149 - 580 ≈ 3569` → 音量
- 带内还必须满足 `startY` 距上下边界留 80 单位余量，避免误判。
- 带宽、门限、启动阈值全部写进配置，方便按手感微调。
- **防误触要点**：手掌搁在边缘打字时，压力通常低且触点数 >1；用"压力门限 + 恰好 1 触点 + 起始 Y 余量"三重条件过滤。

### 4.3 位移 → 步进映射

```
ΔY 累计（向外 +，向内 -，方向可配）
每累计 STEP_UNITS（默认 90 单位 ≈ 全高的 4%）→ 发射 1 个步进
    步进量：亮度 4% / 音量 3%（可配）
    加速：滑动速度 > 1500 单位/秒 时，步进量 ×2（高速快调，可关）
```

- 用 **Y 位移积分**而不是"步进计数"，手感连续；
- 步进发射用**余数保留**（`accumulator % STEP_UNITS`），避免快速滑动丢步；
- 方向反转时余数清零（避免"回拉一下才生效"的粘滞感）。

### 4.4 光标锁 CursorLock（本方案核心技术）

**问题**：单指滑动必然移动光标，纯用户态无法让系统忽略它。

**主方案：`ClipCursor` 冻结**
```
手势 Armed→Active 的瞬间：
    GetCursorPos(&p)                       // 记录当前光标位置
    RECT r = { p.x, p.y, p.x+1, p.y+1 }    // 1~2 像素的牢笼
    ClipCursor(&r)                         // 光标物理上无法移动
手指离开 / 条件破坏：
    ClipCursor(NULL)                       // 立即解锁
```
- 光标不是"补偿回来"，而是**根本动不了**，理论零抖动；
- `ClipCursor` 不要求窗口在前台，后台常驻进程即可生效；
- 手势结束后光标停在原位，**不需要恢复动作**。

**保险丝（二级防御）**：前台全屏程序/游戏可能自己调用 `ClipCursor` 覆盖我们的锁。因此 Active 期间以 ~30Hz 闭环采样 `GetCursorPos`：
- 若光标位移超过 3px，判定锁失效 → 启用**位移补偿**（按触点 Δ 用 `SendInput` 反向抵消），并记录日志；
- 解锁后仍持续校验 200ms，确认已放开。

**崩溃兜底**（必须做，否则可能把用户光标焊死在 1 像素里）：
1. 进程启动时先无条件 `ClipCursor(NULL)` 清一次残留；
2. `try/finally` + `AppDomain.UnhandledException` + 控制台关闭事件统一释放；
3. 独立看门狗：若主线程 500ms 未心跳，强制 `ClipCursor(NULL)` 并退出。

**已知边界**：以管理员权限运行的前台程序可以覆盖剪辑区；多显示器下按当前光标所在显示器的**物理像素**计算（进程需声明 Per-Monitor DPI Aware）。

### 4.5 执行器

**亮度**
1. 首选 `Dxva2.dll!SetMonitorBrightness`（快，通常 <5ms），启动时自检：读当前值→写入→回读，确认真的生效；
2. 自检失败则回退 **WMI** `root\wmi → WmiMonitorBrightnessMethods.WmiSetBrightness`（联想用的就是它，本机必然可用，但单次 50~200ms）；
3. 无论走哪条，**维护本地目标值**，把连续步进**合并**成一次写入（节流 60~80ms），避免快速滑动时排队卡顿。

> 注：WMI 写入必须在 MTA 线程；`System.Management` 在 .NET Framework 里开箱可用。

**音量**
- 首选 **Core Audio** `IAudioEndpointVolume::SetMasterVolumeLevelScalar`：精确、无系统 OSD 干扰、可读回；
- 回退 `SendInput` 发 `VK_VOLUME_UP/DOWN`（会带出 Windows 自己的音量 OSD，与我们自绘的 OSD 冲突，故仅作回退）；
- 同样维护本地目标值 + 节流。

### 4.6 OSD

- 自绘分层窗口（`WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE`），**不抢焦点、不进任务栏**；
- 内容：图标（☀/🔊）+ 进度条 + 百分比；
- 位置：默认屏幕底部居中（可配到触控板同侧）；
- 行为：出现即显示，最后一次步进后 800ms 淡出；连续调节期间不重置透明度（避免闪烁）；
- 不复活联想 `OSDControl.exe`（命令行未公开，且会把 OSD 行为绑死在联想实现上）。

---

## 5. 与联想原功能的共存

联想只在"全屏 + 白名单进程"下响应，我们是全场景响应，**在全屏看视频时会双方各调一格 = 跳两格**。

两种处理，配置里可选，默认 (B)：
- **(A) 全屏让位**：检测到前台全屏且是联想的白名单场景时，我们暂停，交给联想；
- **(B) 全局接管**（默认）：我们始终生效，用户在 Vantage 里把「手势」开关关掉即可。文档里会写清这一步。

> 我们**不修改**联想的任何文件，只做运行时判断。

---

## 6. 分期计划

### Phase 1 — MVP（目标：一个会话内可跑起来）

| # | 内容 | 验收标准 |
|---|---|---|
| 1 | HidSource：隐藏窗口 + Raw Input + 描述符驱动解析（含 Tip Switch） | 日志能打印每一帧的触点数/坐标/压力 |
| 2 | GestureEngine：Idle/Armed/Active/Cooldown + 左右边缘 + 位移积分 | 在左右边缘各滑一次，日志出现正确的亮度/音量步进序列 |
| 3 | CursorLock：ClipCursor 冻结 + 释放 + 崩溃兜底 | 滑动全程光标**肉眼不可动**；强杀进程后光标正常 |
| 4 | Actuators：音量走 Core Audio；亮度先 WMI（稳妥），带本地目标值 + 节流 | 滑动可连续调节，无卡顿、无跳变 |
| 5 | OSD 进度条 | 滑动时出现，抬手后淡出 |
| 6 | 托盘：暂停/退出；配置 JSON | 可热重载参数 |
| 7 | 打包：`csc` 编译单文件 exe + 使用说明 | 双击即用，无需安装 |

**MVP 明确不做**：3/4 指模式、白名单、多显示器亮度、HDR、开机自启（Phase 2 补）。

### Phase 2 — 完善
- 加速度曲线与步进粒度调参界面；3 指/4 指模式；左右互换与方向反转；
- 应用白/黑名单（游戏内禁用）、全屏检测、与联想互斥的自动检测；
- 开机自启、单实例、日志轮转、面板/外接屏亮度、HDR 兼容；
- 光标锁失效时的补偿模式实测调优；功耗与采集率优化。

### Phase 3 — 震动（独立立项，先 go/no-go）

| 步骤 | 内容 | 安全约束 |
|---|---|---|
| 0 | **只读观察** Col04：静置/触摸/点击时设备是否自发上报 | 只读，绝不写 |
| 1 | 找资料：Goodix 公开文档、Linux `hid-multitouch` 的 Goodix quirk、LKML 关于压感触控板触觉的 RFC、Deepin/Ubuntu 社区里 GXTP5100 的记录 | — |
| 2 | 用"已知安全"的查询类命令验证通道语义（如读固件版本） | 单字节试探，逐次记录 |
| 3 | 小步试探震动/波形命令；每次只改一个字节并记录状态 | 先准备好回滚：禁用/重新启用设备 → 重启 → 重装 Goodix 驱动 |
| 4 | 若成功：接入"每一步一震"，再尝试按滑动速度调频率/强度 | — |

**go/no-go 门槛**：Phase 3 步骤 2 结束时若仍无法确定通道语义（命令头/长度/校验），即判失败并退出，改用 OSD 视觉反馈。

**先验判断与证伪条件（2026-06 更新）**
- 已证伪的部分：本机固件**没有**实现主机发起触觉的标准协议面（§2.5），所以"用标准 HID 报文触发震动"这条路不必再试。
- 剩下只有厂商通道一条路，且成功率下调至 **15–25%**。

### Phase 3 结论：已关闭（只读实测，2026-09-13）

对 Col04 做**只读**监听（`VendorListen.cs`：`CreateFile(GENERIC_READ)` + 重叠 `ReadFile`，绝不写入），同时用 Raw Input 记录触控板接触数变化做时间对齐：

| 观测 | 结果 |
|---|---|
| 静置 30 秒 | **0** 条厂商报文（同时产生 30 次 1 秒读超时，证明读取通道本身工作正常） |
| 主动交互（40 次接触数变化，含 1~4 指、按压、边缘滑动） | **0** 条厂商报文 |
| 全程 | 无心跳、无事件、无任何自发上报 |

**第二次复核（全集合覆盖，同日 01:03）**：改为同时只读监听 **Col01~Col04 全部四个集合** 重跑（约 71 秒、1246 条触点轨迹、含 1~4 指与多次按压，峰值压力 713/2000）。结果：

- **Col04 依然是 0 条报文**（空闲 4 次心跳全部 reports=0）；
- **Col03 打开成功但 `inLen=0`** —— 纯 Feature 集合（featLen=3，即 PTP 的 Device Mode 配置报文），**结构上不可能发输入报文**；
- **Col01 `err=5`（ACCESS_DENIED）**、**Col02 `err=32`（被系统独占）** —— 两者无法监听，但前者是标准鼠标接口、后者是触控板本体，都不构成"隐藏的厂商通道"。

结论不变，且覆盖面已完整。

### Phase 3 重开：两个新发现（2026-09-13）

**新发现 1：触控板固件就在本机，而且是可逆向的 ARM Cortex-M 镜像**

- 文件：`C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN`（**161,628 字节**）；`TB14P` = ThinkBook 14+（本机机型），芯片名 **GT7868Q**
- 由 `GoodixTouchpad.inf`（`Class=Firmware`）通过 **UEFI ESRT** 刷写（`UEFI\RES_{b6ae105a-ba93-4fc8-aa28-e63903ffedde}`）；本机 ESRT 条目 `FirmwareVersion=0x14030522`、`FirmwareStatus=0`（已生效）
- 文件偏移 **105204** 起有连续 49 项 Thumb 向量表，地址全为 `0x0800xxxx` → **ARM Cortex-M / STM32 系 Flash 基址**，**镜像未加密**
- **推论 A（已作废，见 §2.9）**：本机固件更新由 UEFI ESRT 投递，但微软规范把 Col04 这类厂商集合定义为**固件与厂商配置更新集合**，其规范用途之一就是传输固件载荷 → **盲写仍可能导致触控板进入固件更新流程**，风险未排除。
- **推论 B（坏消息）**：按 6 种 HID 描述符特征搜索，**固件里找不到 PTP 集合（`05 0D 09 05 A1 01`）与 Haptics 集合（`05 0E 09 01`）的明文**；2 字节模式（`09 21`/`09 20`/`09 10`）命中数与随机概率相当。描述符可能运行时生成或编码存放
- 本机可用工具：Python 3.14.6 + numpy；**capstone 缺失、无网络** → 暂时无法反汇编

**新发现 2：可能存在"侧门"写入通道（待功能验证）**

- 用 **Col03（mtconfig）句柄** 调 `HidD_SetFeature` 写 `report ID 9`（Haptic Intensity，本属 Col02）→ 返回 **True**
- **对照实验**：写不存在的 `report ID 0x55 / 0x99` **也返回 True** → HID 栈不校验报文 ID，**返回值本身不构成证据**
- 唯一验证方式 = **功能验证**：把强度写 0，看点击震动是否消失（已执行写入，等待验证）
- **若侧门成立** → 我们获得 Col02 功能报文的写入通道（含厂商报文 `0xC4~0xC7`），这是"找到并发出震动命令"的必要前提，成功率重新上调
- **若侧门不成立** → 写入通道彻底关闭，只剩改固件（有签名，实际不可行）→ 震动支线终结

#### 已排除清单（逐条实测，2026-09-13）

| 路径 | 结论 | 证据 |
|---|---|---|
| 标准 HID 主机发起触觉 | ❌ 设备端不支持 | 无 Manual Trigger 输出报文、`OutputReportByteLength=0`、无 Auto Trigger/波形表 |
| 直接写 Col02 功能报文 | ❌ 被系统独占 | `CreateFile` → `ERROR_SHARING_VIOLATION(32)` |
| 侧门写入（Col03 句柄 → rid 9） | ❌ **不成立** | ① 对不存在的报文 ID（0x55/0x99）同样返回 True；② A/B 功能测试（强度 0/100 每 6 秒交替、用户全程按压）震动始终存在 → 数据未到达设备 |
| 只读监听 Col01~Col04 找事件/遥测 | ❌ 全静默 | 空闲 0 报文；71 秒 1~4 指按压滑动期间 0 报文；Col03 为纯 Feature 集合（inLen=0） |
| 华为实现参考 | ❌ 无可迁移内容 | 官方文档证实其功能在电脑管家（用户态）；其板子（GXTP7863）大概率支持标准主机发起协议 |
| Linux / 上游实现 | ❌ 不适用 | HID 树 `for-6.18/haptic` 只实现标准 HUTRR63 协议，不支持本机这种"仅强度旋钮"的设备 |
| 联想自研模块 | ❌ 无厂商命令通道 | `TouchpadModule.dll` = 触控板识别/开关修复（HID 描述符解析 + SwitchTouchPad）；`module_touchpad_devices.dll` = 诊断测试（点击/精度/压力） |
| 固件里找明文描述符 | ❌ 不存在 | 4~7 字节严格特征（`05 0D 09 05 A1 01` 等）**全部 0 命中**；先前"厂商页 `06 00 FF`"6 处命中经上下文 dump 确认是 **Thumb-2 代码**（`BD F8 06 00` / `FF E7` / `70 47` / `9F ED` 浮点指令） |
| 改固件 | ❌ 有签名 | 走 UEFI ESRT 刷写，签名校验；无非对称密钥无法伪造 |

**唯一剩余路径**：反汇编固件（需 capstone）找到 LRA 触发路径 → 经 **Col04**（已确认可读写）发送命令。

- **综合成功率 ≈ 20~25%** = P(生产固件里存在隐藏触发路径) ≈ 40% × P(能在无符号的 Thumb-2 代码里定位到) ≈ 55%
- 工作量：数小时至数天；风险：低（分析阶段全程只读，且 Col04 已确认不是 DFU 通道）

**结论与影响：**

1. Col04 **不是**事件/遥测通道——与华为/荣耀同族板子**相反**（那块板的厂商集合会以 1 Hz 上报心跳）。它最可能是**命令-响应通道**，且很可能与**固件升级/产线测试**有关：本机装有 Goodix 的 `goodixtouchpad.inf`（**Firmware 类**驱动，oem87.inf），固件更新需要一条这样的双向 64 字节通道。
2. 因此若震动命令存在，只能在一个**未知协议、且可能与 DFU 共用**的通道上盲试——**风险高于此前评估**：错误的操作码可能让触控板进入固件升级模式。
3. **综合判定：本机实现"应用触发震动"的概率 < 10%，且下行风险不可接受 → 终止该支线，不再试探写入。**
4. **替代方案**：OSD 脉冲 + 短促提示音，提供"这一格生效了"的反馈（无物理震动）。此外用户仍可在 Windows 设置里手动调整点击反馈强度（唯一可用的触觉参数）。

**原计划的下载路径（已作废，保留备查）**：本会话文件沙箱拿不到 TLS 凭证（`curl` / `Invoke-WebRequest` 对所有 HTTPS 站点报 `SEC_E_NO_CREDENTIALS`）。

### Phase 3.1 华为参考实现研读（新增，与步骤 0 并行）

**为什么要做**：华为那块板是 Goodix 同族（§2.6），他们的"边缘滑动调音量/亮度 + 震动反馈"是**同一芯片族上的已知可用实现**，能回答我们最想知道的两个问题：

| 问题 | 为什么关键 | 去哪里找答案 |
|---|---|---|
| **Q1 单指边缘滑动时，他们怎么让光标不乱跑？** | 若答案是"内核 HID 过滤驱动"，说明纯用户态确实做不到，我们的 `ClipCursor` 方案就是正解；**若答案落在用户态（甚至就是 ClipCursor，或 PTP 的 Selective Reporting 特性报文），我们可以直接照抄思路** | 各 INF 的 `UpperFilters`/`LowerFilters`；电脑管家 EXE/DLL 的导入表是否含 `ClipCursor` / `SetCursorPos` / `HidD_SetFeature` / `RegisterRawInputDevices` |
| **Q2 震动指令长什么样？** | 同族芯片的厂商命令有迁移可能，比盲试成功率高得多 | 电脑管家/驱动中对 usage page `0xFF00` / `0xFF01` 的 Feature/Output 报文写入；命令常量表 |

**要拿到的文件**：① MateBook X Pro 2023 触控板驱动包；② 华为电脑管家（PC Manager）安装包。

**拿到后的分析清单**（全部只读）：
1. 解包，列出所有 INF → 找触控板设备的过滤器驱动、Goodix 驱动版本与日期（判断与本机固件是否同代）；
2. 对 Huawei 自研的 `.sys/.dll/.exe` 抽字符串与导入表，检索：`ClipCursor`、`SetCursorPos`、`RegisterRawInputDevices`、`HidD_SetFeature`、`HidD_SetOutputReport`、`IOCTL_HID_SET_*`、`0xFF00`、`0xFF01`、`Manual Trigger`、`WmiSetBrightness`、`VK_VOLUME`、`SendInput`；
3. 找配置/参数文件（JSON/XML/INI）里的手势阈值与震动节奏；
4. 结论仅用于"学思路、学命令格式"——**不复制、不安装、不分发华为的任何二进制**。

**结论（2026-06 更新）：本节已被官方文档回答，下载分析不再是必要动作。**

- 华为官方文档确认边缘手势**集成在电脑管家（用户态）**（§2.6），因此"光标屏蔽在哪一层"这个核心疑问的答案已经拿到：**至少功能主体在用户态**，不存在"华为用内核驱动做了我们做不到的事"这一障碍。我们的 `ClipCursor` 路线与华为同构。
- 于是原先计划的"拆包华为驱动/电脑管家"降级为**可选**：只有在你想确认"他们在用户态具体用什么手法处理光标"时才需要做。真要验证，最低成本的做法是对电脑管家主程序做**导入表扫描**（找 `ClipCursor` / `SetCursorPos` / `HidD_SetFeature` / `HidD_SetOutputReport` / `RegisterRawInputDevices`），而不是全量逆向。
- 震动那一路（Q2）**优先级下调到最后**：本机固件缺少主机发起触觉的协议面（§2.5），即使华为是用厂商命令实现的，搬过来也未必能被本机固件接受。
- **下一步真正有意义的动作**：Phase 3 步骤 0 —— 对 Col04 做**只读**观察，确认这条厂商通道是不是活通道。这是零风险、不需要任何外部文件、能自主完成的实验。

**原计划的下载路径（已降级为可选，保留备查）**：本会话文件沙箱拿不到 TLS 凭证（`curl` / `Invoke-WebRequest` 对所有 HTTPS 站点报 `SEC_E_NO_CREDENTIALS`），如需取得文件只能 (a) 用 CDP 驱动你的浏览器下载，或 (b) 你手动下载后给我路径。

---

## 7. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| `ClipCursor` 被前台程序覆盖 | 光标锁失效，光标乱跑 | 30Hz 闭环检测，超过 3px 自动切到位移补偿模式 |
| 进程崩溃时残留光标锁 | 光标被焊死在小矩形内 | 启动清残留 + 全异常路径释放 + 独立看门狗 |
| 与联想功能重复触发 | 一次滑两格 | §5 两种策略，默认全局接管并提示关闭 Vantage 开关 |
| WMI 亮度延迟大 | 手感发黏、快速滑动丢步 | 本地目标值 + 异步合并写入 + 节流；优先 Dxva2 |
| 边缘手势误触发（打字/搭手） | 亮度音量自己乱跳 | 压力门限 + 单触点 + Y 余量 + 启动阈值四重过滤，参数可调 |
| 游戏/全屏程序行为异常 | 误调音量、光标锁打架 | 可配置黑名单；检测前台全屏可暂停 |
| 压力值漂移/个体差异 | 门限失效 | 用"压力差分 + 门限"而非绝对阈值；门限可调 |
| 震动逆向失败或写坏固件 | 触控板异常 | Phase 3 独立立项；只读先行；准备恢复预案；失败即止损 |

---

## 8. 验证方法

| 项目 | 方法 | 目标值 |
|---|---|---|
| 采集率 | 用 `ScanTime` 差值统计 | 记录实测（PTP 典型 100–140Hz） |
| 端到端延迟 | 触点事件时间戳 → OSD 更新，日志打点 | < 30ms |
| 光标稳定性 | Active 期间 30Hz 采样 `GetCursorPos`，统计最大偏移 | ≤ 2px |
| 误触发率 | 日常使用 1 小时，统计非意图触发 | 0 次 |
| 步进准确性 | 滑动固定距离，统计步数 | 与设定值误差 ≤ 1 步 |
| 崩溃安全 | 任务管理器强杀 / 抛异常，检查光标 | 光标始终正常 |

---

## 9. 配置项（`config.json`）

```jsonc
{
  "edge": {
    "bandWidthRatio": 0.14,      // 边缘带宽度（占 X 量程比例）
    "topBottomMargin": 80,       // 距上下边界的余量（设备单位）
    "minPressure": 150,          // 压力门限（0-2000）
    "startThreshold": 40,        // 启动位移阈值（设备单位）
    "stepUnits": 90              // 每多少位移发一个步进
  },
  "map": {
    "leftEdge": "brightness",    // 左边缘 → 亮度
    "rightEdge": "volume",       // 右边缘 → 音量
    "invertDirection": false     // 是否反转上下方向
  },
  "actuator": {
    "brightnessMode": "auto",    // auto | dxva2 | wmi
    "brightnessStepPercent": 4,
    "volumeStepPercent": 3,
    "throttleMs": 70,
    "fastSlideMultiplier": 2
  },
  "osd": { "enable": true, "position": "bottom-center", "hideDelayMs": 800 },
  "cursor": { "lockMode": "clip", "verifyHz": 30, "compensateOnFailure": true },
  "coexist": { "mode": "takeover" }   // takeover | yield-in-fullscreen
}
```

---

## 10. 构建与运行

**主路线（推荐，零安装）**：C# / .NET Framework 4.8，用系统自带 `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe` 编译成单文件 exe。
- 优点：目标机不需要装任何运行时；产物小（几百 KB）；WinForms/WMI/COM 全部开箱可用。
- 约束：编译器是 C# 5（不能用字符串插值、`?.`、表达式体成员等新语法），代码风格需相应收敛。

**备选路线**：装 .NET SDK（`winget install Microsoft.DotNet.SDK.8`）→ 现代 C# + `dotnet publish` 单文件。代码结构不变，仅语法与打包方式不同。**需要你点头才装。**

> 本机现状：无 SDK；已有 .NET Framework 4.8.09221 + csc.exe；另有 .NET 6/8/9/10 运行时。

---

## 11. 附录：已完成的侦查工具与实验记录

全部位于 `<LAB>\touchpad-lab\poc\`：

| 文件 | 作用 |
|---|---|
| `RawTouchProbe.cs` | 用户态 Raw Input 探针：注册 `0x0D/0x05`，解析触点 X/Y/压力/接触数。**已实测跑通** |
| `run-probe.ps1` | 长时间采集脚本，输出 `probe-log.txt` |
| `HidDump.cs` | 枚举所有 HID 集合的 usage 能力，用于发现触觉特征与报文结构 |
| `HidOpenTest.cs` | 测试各集合能否被用户态打开（得出 Col02 独占 / Col04 可读写） |
| `hid-dump.txt` / `hid-open.txt` | 上述工具的实测输出存档 |

**已证实的事实（可复核）**：
1. 触控板 4 个 HID 集合的 usage、报文长度、各字段取值范围（§2.1）。
2. Raw Input 能实时读到多点报文（探针输出可见逐帧触点数据）。
3. Col02 `CreateFile` → `ERROR_SHARING_VIOLATION`；Col04 `CreateFile(READ|WRITE)` → OK。
4. 触觉走微软规范：有 `Simple Haptic Controller` + `Haptic Intensity`(rid=9)，但**无 Manual Trigger 输出报文**。
5. 联想实现路径：用户态 Raw Input + `IsFullScreenActive` 门槛 + WMI 亮度 + SendInput 音量 + 外部 OSD 进程。
6. 华为 MateBook X Pro 2023 的触控板是 **Goodix GXTP7863（27C6:01E0）**，与本机 GXTP5100（27C6:01E9）同厂同族，Linux 内核同表同驱动类（§2.6）。
7. 该族触控板的厂商集合是活通道（会周期性上报心跳/遥测），本机 Col04 是否为活通道待只读实验确认。

**环境限制记录**：本会话沙箱内 `curl` / `Invoke-WebRequest` 访问任何 HTTPS 站点均失败于 `schannel: SEC_E_NO_CREDENTIALS`，故所有外部文件需经浏览器或用户手动取得。

---

## 12. 待你确认的三个点

1. **文档是否 OK**，以及 MVP 范围是否符合预期（§6 Phase 1）。
2. **构建路线**：走零安装的 .NET Framework 4.8，还是装 .NET SDK 用现代 C#？（默认前者）
3. **震动**：Phase 3 是否现在就并行启动"只读观察"（安全、零风险，可以先摸清 Col04 通道），还是等手势部分做完再说？
