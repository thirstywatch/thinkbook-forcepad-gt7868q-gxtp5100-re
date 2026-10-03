# 2026-10-03 · 蓝莓**新**项目实证 + 本机总线定案 + 同构 forcepad 挖掘清单

> 触发：喆提出「目标就是**纯软件在主机端**让触控板滑动震动」，并指出
> ① 想从**其它同构 forcepad 的固件**里挖更多信息；② `github.com/barryblueice` 是重要参考。
> 本文所有代码/寄存器/枚举结果**均为本轮实际下载或实际执行所得**，标注了出处行号。
> 与既有文档冲突处**已标红更正**，不覆盖旧结论。

---

## 〇、本轮三句话

| # | 结论 |
|---|---|
| 1 | 蓝莓**最新项目**（2026-10-02 更新，本项目从未看过）= `ESP32-Haptic-Precision-TouchPad`，靶机 **Surface Laptop Studio 1964**。它给出**第二个源码级实证**：触觉 IC 与触控 IC 挂在**同一条 I²C** 上。 |
| 2 | ★ **本机总线定案**：触控板 = **I²C HID**（`hidi2c`，**不是 SPI**），挂在 **`\_SB.PC00.I2C0`**，从地址 **`0x2C`**（**不是**本项目一直写的「1」），400 kHz；控制器 = `PCI\VEN_8086&DEV_7E78`（Intel Serial IO I2C Host Controller - 7E78，已启动）。 |
| 3 | ⚠️ **期望校准**：蓝莓**自己也没做出来**连续触觉 —— 他的 TODO 里 `[ ] 触觉反馈和强度控制（后续可能支持）` **至今未勾**。他做到的是「按一下震一下 + 分档强度」。"滑动震动"在业界参考实现里**同样没有现成答案**。 |

---

## 一、蓝莓新项目实证（`barryblueice/ESP32-Haptic-Precision-TouchPad`）

### 1.1 项目身份

| 项 | 值 | 出处 |
|---|---|---|
| 名称 | ESP32-Haptic-Precision-TouchPad | GitHub API `/users/barryblueice/repos` |
| 最近推送 | **2026-10-02** | 同上 |
| 靶机 | **Surface Laptop Studio 1964**（Synaptics 触控板 + 触觉引擎） | `README_CN.md` L9 |
| 硬件 | ESP32-S3 三模（USB / 2.4G / BLE），自绘 PCB（oshwhub） | `README_CN.md` |
| 定位 | 「基本是前代项目（小米那台）的扩展增强版」 | `README_CN.md` L19-22 |
| 附带 | `mcu-drivers/` 内含**完整 Cirrus CS40L25 驱动 + 固件镜像**（`cs40l25_fw_img.c` 204 KB、`cs40l25_cal_fw_img.c` 55 KB） | 文件树 |

### 1.2 ★★★ 硬件拓扑（源码级证据，可直接抄的模板）

`Main/main/I2C/I2C_handle.h`：

```c
#define TP_I2C_PORT         I2C_NUM_0
#define TP_I2C_SDA          36
#define TP_I2C_SCL          35
#define I2C_FREQ_HZ         400000
#define TP_I2C_ADDR         0x2C     /* ← 触控 IC */
#define HAPTIC_MOTOR_ADDR   0x43     /* ← 触觉 IC（CS40L25） */
#define SUB_I2C_PORT        I2C_NUM_1   /* 第二条总线：只放电源器件 */
#define SUB_I2C_SDA         17
#define SUB_I2C_SCL         18
#define MP28167_ADDR        0x60
#define BQ24195_ADDR        0x6B
#define MAX17048_ADDR       0x36
```

`Main/main/I2C/TP/i2c_cmd.c` → `tp_i2c_init()`：**同一个 `bus_handle` 上注册两个 device**

```c
ESP_ERROR_CHECK(i2c_new_master_bus(&bus_cfg, &bus_handle));
i2c_master_bus_add_device(bus_handle, &dev_cfg,               &dev_handle);                 // 0x2C 触控
i2c_master_bus_add_device(bus_handle, &dev_haptic_motor_cfg,  &dev_haptic_motor_handle);    // 0x43 触觉
```

`Main/main/I2C/SUB_DEV/surface_haptic_hw.c`：

```c
#define MP28167_TARGET_VREF_RAW 1256U      // 0.8 mV/LSB ⇒ VOUT ≈ 13.003 V
CHECK_ESP(gpio_set_level(GPIO_HAPTIC_BUCK_BOOST_EN, EN_ON));   // GPIO14 先使能外置 buck-boost
/* 再经 I2C 把 MP28167(0x60) 的 VREF 调到 1256，才去 identify 触觉 IC */
```

`Main/main/GPIO/GPIO_handle.h`：

```c
#define GPIO_HAPTIC_BUCK_BOOST_EN   GPIO_NUM_14
#define GPIO_HAPTIC_FUNC_FOR_TP_EN  GPIO_NUM_33   /* 与触控 IC 共用 */
#define GPIO_HAPTIC_ALERT_N         GPIO_NUM_37
```

`surface_haptic_hw.c` 原注释：
> `Do not reset GPIO33: it is shared with the working touch controller.`

**⇒ 三条可迁移事实**

| # | 事实 | 对本机的意义 |
|---|---|---|
| **A** | **触觉 IC 与触控 IC 同一条 I²C**（`0x2C` + `0x43`），这是**第二个独立实证**（第一个是小米那台 `0x2C` + `0x50`） | ★★★ 「模组把触觉 IC 挂在对外的 I²C 排线上」是这类模组的**通行做法** ⇒ **本机 `0x5A` 也落在 `\_SB.PC00.I2C0` 上的先验概率大幅上升** |
| **B** | **触觉 IC 的电源轨平时是关的**：要 GPIO 使能 + I²C 编程到 13 V | ★ **本轮新增的、此前项目从未考虑过的一项**：即使我们能寻址到 AW86927，它的 **BOOST/供电可能没人开**。这不影响「能不能读 CHIPID」（数字核另有常供电），但**直接影响「读到了为什么不振」的排查方向** |
| **C** | 触觉 IC 的 RESET 与触控 IC **共用一根 GPIO** | 本机 TF100A↔GT7868Q 之间已知有「PA3 门铃」这种共用/握手机制，BOM 上是否同引脚未知（**待核**） |

### 1.3 ★★ 期望校准：他做到什么、没做到什么

`README_CN.md` 的 TODO 原文照抄：

```
### 压感与触觉
- [x] 压感调整原理破解
  - [x] CS40L25 SDK适配
  - [x] ROM模式下触发振动
  - [x] 特定waveform固件优化触觉反馈 (实验性)
- [x] 压感支持
  - [x] 单击敏感度 (实验性)
  - [x] 触觉点击和强度调整 (实验性)
  - [ ] 触觉反馈和强度控制 (后续可能支持)      ← ★★★ 至今未勾
```

他自述的一句关键话：

> ~~由于 CS40L25 的固件问题, 按下的振动反馈比较奇怪。~~
> **手感问题已基本解决，是 firmware 解包和 SAM 控制逻辑不正确导致。**

| 结论 | 说明 |
|---|---|
| 「按一下震一下」→ **已实现**（ROM 模式 / RAM 波形，两级强度） | 对应我们要的"点击/滑过时震一下"的**基础能力** |
| 「连续触觉反馈 / 强度控制」→ **参考实现也未实现** | ⇒ 若目标是"滑动过程中持续反馈"，**没有现成答案可抄**；若目标是"滑动时逐次脉冲"，则**他已经证明了可行性** |
| 手感问题的根因是 **firmware 解包 + SAM（算法模块）控制逻辑** | ⇒ 与我们本机"cfg / 固件配置体 / 波形区"那条线**同源**：手感不好 ≠ 驱动不对，而是**参数/波形不对** |

### 1.4 触发路径与波形参数（可与 AW86927 逐项对照）

`Main/main/I2C/SUB_DEV/surface_haptic_settings` / `Hacking/cs40l25_haptic_strength_test.c`：

| 项 | 值 |
|---|---|
| 波形总数 | `SURFACE_VIBEGEN_WAVE_COUNT = 28` |
| 点击按下 / 抬起 | `SURFACE_CLICK_PRESS_WAVE = 3` / `SURFACE_CLICK_RELEASE_WAVE = 4` |
| 触发两种模式 | `mbox1_full_wave`（duration=0，整条播完） vs `mbox2_cutoff_Nms`（48/64/80/96 ms 截断） |
| **ROM 模式触发** | `bsp_dut_trigger_haptic(BSP_DUT_TRIGGER_HAPTIC_POWER_ON, 0)` → 即"BHM 上电脉冲" |
| 完整启动序列 | `enable_vamp(true)` → `reset` → ROM 试震 → `boot(false)` → `power_up()` → `update_haptic_config(0)` → `enable_haptic_processing(true)` |
| 身份校验 | `read_reg(CS40L25_SW_RESET_DEVID_REG)`，比对 `CS40L25_DEVID` / `CS40L25B_DEVID` |

★ **`Hacking/` 目录里有`i2c_addr_scanner.c`** —— 他**扫模组 I²C 总线找从设备**用的就是这段（`i2c_master_probe` 遍历 0x03–0x7E）。
⇒ **这就是"怎么知道触觉 IC 在哪个地址"的标准做法**，也是本机那条"零成本判据"的现成模板。

### 1.5 顺带白拿：HID-over-I²C 描述符寄存器全解（本机对照模板）

`Hacking/README.md` 给出 Synaptics 触控板的 **Microsoft HID I2C Descriptor（寄存器 `0x0020`）** 原始 23 字节：

```
1E 00 | 00 01 | 65 03 | 21 00 | 24 00 | 40 00 | 25 00 | 17 00 | 22 00 | 23 00 | CB 06 | 43 CE | 08 | 01
```

逐字段解析（标准 HID-over-I²C 结构）：

| 偏移 | 字段 | 值 | 含义 |
|---|---|---|---|
| 0x00 | `wHIDDescLength` | 0x001E | 30 字节 |
| 0x02 | `bcdVersion` | 0x0100 | 1.00 |
| 0x04 | `wReportDescLength` | 0x0365 | 869 字节 |
| 0x06 | `wReportDescRegister` | **0x0021** | ★ 报告描述符所在寄存器 |
| 0x08 | `wInputRegister` | 0x0024 | 输入报文寄存器 |
| 0x0A | `wMaxInputLength` | 0x0040 | 64 B |
| 0x0C | `wOutputRegister` | 0x0025 | 输出报文寄存器 |
| 0x0E | `wMaxOutputLength` | 0x0017 | 23 B |
| 0x10 | `wCommandRegister` | **0x0022** | ★ 他写 magic 用的就是这个 |
| 0x12 | `wDataRegister` | **0x0023** | 数据寄存器 |
| 0x14 | `wVendorID` | **0x06CB** | **Synaptics** |
| 0x16 | `wProductID` | 0xCE43 | |
| 0x18 | `wVersionID` | 0x08 | |

**⇒ 本机 DSDT 给的描述符寄存器 = `0x20`**（见 §二，`TPID` 里 `GXTP5100` 项第 3 个字段），
与 Synaptics 用 `0x21` 不同 —— 这正好解释了「读描述符要读 0x20」这条本机约定**不是猜的**，
而是**厂商在 ACPI `_CRS` 里声明**的。

另：他切换 PTP/鼠标模式用的「magic 包」= 往**命令寄存器 `0x22`** 写
`[0x00,0x3F, 0x03, 0x0F, 0x23,0x00, 0x04,0x00, 0x0F, 0x01|0x00]`（`crostouchpad4-synaptics` 出处）。
⇒ 与本机「Goodix 私有封装 `0x05/0x00` + `0x33/0x0N`」是**同一层语义、不同厂商语法**。

---

## 二、本机总线定案（本轮新事实，逐条可复核）

### 2.1 原始命令与输出

```bash
# 注意：Git Bash 会把 /xxx 当路径吃掉，必须加 MSYS_NO_PATHCONV=1
MSYS_NO_PATHCONV=1 pnputil /enum-devices
```

| # | 事实 | 出处 |
|---|---|---|
| 1 | `ACPI\GXTP5100\1` = **「I2C HID 设备」**，类 `HIDClass`，驱动 **`hidi2c.inf`**，状态**已启动** | `pnputil` 输出 |
| 2 | `ACPI\MSFT0001\1` = 「I2C HID 设备」，`hidi2c.inf`，状态**已断开连接**（DSDT `_HID` 的默认返回串，未选中/未启用的一份枚举残留） | 同上 |
| 3 | `Device (TPAD)` 位于 **`Scope (_SB.PC00.I2C0)`** 内 | `DSDT_本机_21LD.dsl:87375-87377` |
| 4 | `_CRS` = `ConcatenateResTemplate (IICB (ADR0, "\\_SB.PC00.I2C0"), SBFG)`；`ADR0 = DerefOf(TPID[选中项][One])` | `:87646` / `:87655` |
| 5 | `TPID` 中 `GXTP5100` 项 = **`(0x04, 0x2C, 0x20)`** ⇒ **I²C 从地址 `0x2C`、描述符寄存器 `0x20`** | `:87413-87420` |
| 6 | `IICB` 模板速度字段 `80 1A 06 00`（LE）= `0x00061A80` = **400 000 Hz** | `:7265` |
| 7 | 控制器 = `PCI\VEN_8086&DEV_7E78` → **「Intel(R) Serial IO I2C Host Controller - 7E78」**，状态**已启动** | `pnputil` |
| 8 | `\_SB.PC00.I2C0` 的 `_ADR` = **`0x00150000`** ⇒ **PCI 00:15.0**（与 7E78 位置一致） | `DSDT:10810` |

### 2.2 🔴 对项目口径的两处更正

| 旧口径（须改） | 更正后 | 依据 |
|---|---|---|
| 「触控板从地址 = **`1`**（ACPI `_ADR` 权威）」 | ❌ **错**。I²C 子设备的地址权威在 **`_CRS`**，= **`0x2C`**；`Name (_ADR, One)` 是 DSDT 模板遗留（ACPI 对 I²C 子设备本就要求地址由 `_CRS` 描述） | §2.1 #4 #5 |
| 「链上是 `spi_hid` **还是** `hidi2c` —— 未定」 | ✅ **定案：`hidi2c`（I²C，非 SPI）** | §2.1 #1 |

**⇒ 需同步修改**：《全书》§1.3.4 表里「触控板从地址 `1`」、§11.1 符号表、`00-统一口径速查` 里的
`1 = GT7868Q 的 I²C 从地址`。

### 2.3 ★★ 这一更正顺手解开了 `0x2C` 的重名混淆

```
0x2C  ── 在【主机总线 \_SB.PC00.I2C0】上  =  GT7868Q（触控 IC，本机实测 _CRS 权威）
0x2C  ── 在【GT7868Q 片内 I²C1】上        =  TF100A（压力 MCU，逐指令实测"只做从机 0x2C"）
```

**两条不同总线上的同号从设备，不是矛盾。** ⇒ §11.1 的"符号消歧表"该给 `0x2C` 补上「哪条总线」限定。

### 2.4 三方对照（本机不是异类）

| | 触控 IC | 触觉 IC | 同一条 I²C？ | 证据强度 |
|---|---|---|---|---|
| 蓝莓·小米 Book Pro 2022 | Goodix **GT7863 @0x2C** | 马达 **@0x50** | ✅ | 源码（`goodix_i2c_motor_hack.c`）+ 同一对 `PIN_SDA/SCL` |
| 蓝莓·Surface LSS 1964 | Synaptics **@0x2C** | Cirrus **CS40L25 @0x43** | ✅ | 源码（`tp_i2c_init()` 同一 `bus_handle`） |
| **本机 ThinkBook 14 G6+** | Goodx **GT7868Q @0x2C** | 艾为 **AW86927 @0x5A/0x5B** | **❓ 待测** | 本机 `_CRS` 权威（触控侧）；触觉侧**仍无任何证据** |

> ⇒ **先验被抬高了两次，但本机那一格仍然是空的。** 这正是下一节要做的事。

---

## 三、★ 同构 forcepad 挖掘清单（按性价比排序）

> 「同构」= **汇顶触控 + 第三方压力 IC + 第三方触觉 IC** 的三厂分装结构。

| # | 目标 | 为什么值得挖 | 位置 / 线索 | 具体要找什么 | 状态 |
|---|---|---|---|---|---|
| **1** | **ThinkPad X9-14 / X9-15 Gen 1** | ★ **最同构**：同为联想 + **Goodix GXTP5100** 家族 + **官方宣称为触觉压感板**（PID `0x01EA`/`0x01EB`，与本机 `0x01E9` 同族）。若它有触觉，**要么有主机侧驱动、要么有第二颗 IC** —— 两者都是我们要的答案 | Lenovo 支持站按机型 `21QA/21QB`（X9-14）、X9-15 搜「触控板 / Mouse, Touchpad, Keyboard and Pen」，重点看**固件更新包**与**非 inbox 驱动** | ① 包内有没有**第二个芯片**的 I²C/SPB 驱动；② 有没有声明**触觉 usage** 的描述符补丁；③ 有没有 AW86927 类寄存器序列 | ⏳ **最高优先，本轮未取到包** |
| **2** | 小米 Book Pro 14/16 **2022**（TM2119） | 蓝莓的靶机，架构已实证；**芯海 CSF70001 + RichTap 马达** | 小米驱动自助下载（按型号 TM2119）；DSDT 补丁已下（`fw-dl/`） | 触控板固件里**触觉相关区**；芯海驱动的**寄存器协议** | ⏳ 固件待下 |
| **3** | 小米 Book Pro 14 **2026** | 官方稿：采用**艾为「Haptic+Force SoC」** ⇒ 与本机 AW86927 同一器件谱系 | 小米官网 / 艾为案例页 | **AW86927 在笔记本里的典型接线与初始化** | ⏳ |
| **4** | **Dell Hellcat**（`tpupdate_7868q`） | **同 PID 段的 GT7868Q 官方更新工程**，本地已有 | `gdix-tool/hellcat/`（PE，固件在 `.data`/`.rsrc`） | `.data` 里 93 KB 加密段是否含 **cfg/波形**；`subFwType` 枚举 | ⏳ 本地 |
| **5** | ThinkBook 16+ 2024 IMH / 16 G7+ IAH（**同 PID `27c6:01e9`**）+ `ty2/goodix-gt7868q-linux-driver` | **同 PID = 同一颗触控 IC**，社区驱动已入 Linux 6.12 | GitHub `ty2/…`、AUR `goodix-gt7868q-dkms` | 描述符 `byte 605/607` 重复的处理方式；有没有触觉相关 quirk | ⏳ |
| **6** | 阿里云无影笔记本（**NDT 压力 + 艾为**） | 钛方=NdT，同一压力器件谱系 | 无公开包 | 同 1 | ❌ 找不到包 |
| **7** | Fairphone 5 **downstream** kernel `aw86927.c` | 主线版**不含 F0 标定 / RTP / CONT**，downstream 有 | Fairphone kernel 源 | **RTP / CONT 模式的完整寄存器序列**（= 可能不需要传波形就能震） | ⏳ |
| **8** | Surface Touchpad Haptic 2.9.139（蓝莓用的那份） | 已被人挖穿的**样本对照** | 他仓库 / 本机可能已有 | 容器结构 vs 我们载荷 A 的**同构性判断** | ⏳ |
| **9** | 蓝莓新项目全量 `cs40l25_*` | 官方 SDK 级代码（含固件镜像） | 本轮已下 9 个文件，`Main/main/I2C/SUB_DEV/mcu-drivers/` 还有 ~40 个 | **触觉 IC 的完整初始化/KPI**，作为 AW86927 的"应该长什么样"的对照 | ✅ 部分已下 |

### 统一四条判据（在任何一个包里只看这四件事）

| # | 判据 | 为什么 |
|---|---|---|
| **a** | 触控板总线上**第二个从设备的驱动/地址** | 直接回答"触觉 IC 是主机可见还是被触控 IC 私有" |
| **b** | 触觉 IC 的**初始化序列 + 波形数据** | 回答"怎么让它震" |
| **c** | 触觉 IC 的**供电 / BOOST 由谁使能**（见 §1.2 事实 B） | 回答"读得到为什么不振" |
| **d** | 有没有**主机侧触发**（HID 触觉 usage / 厂商命令 / 独立驱动） | 回答"主机能不能触发" |

---

## 四、纯软件路的**真实形状**（把"纯软件"这个词拆开）

```
目标：主机端纯软件 ⇒ 触控板滑动时震
                      │
        ┌─────────────┴─────────────┐
        │                           │
   ① 能不能"发出去"             ② 能不能"到得了"
   （主机→触发源）              （触发源→执行器）
        │                           │
   Col02 Out=0  ❌              GT7868Q 转发？ 无证据
   Col04 厂商命令 ✅ 能发        TF100A 出？   定案"不驱动 LRA"
   → 但无任何 handler 直达输出    主机 I²C 直达  ❓ ← 唯一未结清的一格
     （§11.5「39 个 handler 里只有 0xA0/0x0D00 能启动检测引擎」）
```

### 4.1 Windows 侧（喆的主力系统）

| 路线 | 可行性 | 卡点 |
|---|---|---|
| 标准 HID 触觉 usage | ❌ | `Col02 OutputReportByteLength = 0`（已闭合） |
| Col04 厂商命令直达输出 | ❌ | 39 个 handler 逐一实测：**没有任何一个能直达输出例程** |
| **SPB 客户端驱动直连 `0x5A`** | ⚠️ **理论可行，但有硬卡点**（见下） | Windows 的 SPB 客户端只能连 **ACPI `_CRS` 已声明的连接**（本机 = `I2C0@0x2C`）。**`0x5A` 未被声明 ⇒ 拿不到 connection ID。** 要绕只有两条：**(i) 打 DSDT 补一个 `0x5A` 节点**；**(ii) 直接 MMIO 打 Intel 控制器寄存器**（= `RwDrv.sys` 那条被黑名单+HVCI 拦的路） |
| 驱动签名 | ⚠️ | KMDF 自签需开测试签名 ⇒ 与 Secure Boot 冲突。可参考小米那台的 **`I2CDriver.sys`（`spbi2cdevice.cat`，微软签名）** 证明"厂商自己就这么干"，但**我们没有它的签名** |

⇒ **结论：Windows 侧的"纯软件"其实不便宜。** 除非发现第二颗从设备的驱动是 inbox 的。

### 4.2 Linux 侧

| 项 | 状态 |
|---|---|
| `i2c-dev` 是否允许访问**任意**从地址？ | ✅ **允许**，不需要 ACPI 声明 |
| 要不要驱动签名？ | ❌ 不要 |
| AW86927 有没有主线驱动？ | ✅ 有（`drivers/input/misc/aw86927.c`，854 行，2025-10 合入） |
| 寄存器位宽（决定 `i2cget` 用法） | `regmap: reg_bits=8, val_bits=8, max_register=0x80` ⇒ **`i2cget -y N 0x5a 0x57` 直接可用** |
| 触发 | 写 `0x09` bit0（GO）即可，波形可先用驱动自带的正弦表 |

> ⇒ **本目标的"纯软件"，实际上等价于"Linux 侧"。**
> Windows 唯一现实的路是"补 ACPI 节点 + 自己签驱动"，那是**另一个量级的工程量**。

---

## 五、下一步（就一件事，且本轮已把已知的坑填掉）

> ### 🎯 用修好的 `linux/probe2.sh` 跑一次：**先解绑 `i2c_hid`，再只扫 `\_SB.PC00.I2C0`**。

### 5.1 🔴 旧 `linux/probe.sh` 的致命顺序问题（**这就是为什么这条判据一直没做出来**）

旧脚本 `[6]` 的动作是：**在 `i2c_hid` 还绑着 `0x2C` 的情况下**，
对**全部**适配器用 `i2cdetect -y -r -a` 全地址扫描。

而项目自己的方法学保留写着两条：
- 「扫之前**须先解绑 `i2c_hid`**」（2026-09 记下，至今未执行）
- 「触控板那条总线 `i2cdetect` **崩内核**」

⇒ **两条对得上：「崩内核」极可能就是"没解绑就扫"造成的。**
⇒ 这条"零成本判据"被自己的工具顺序卡了两周。

### 5.2 修好的做法（`linux/probe2.sh`，本轮新写）

| 步骤 | 动作 | 为什么 |
|---|---|---|
| 0 | 按 **ACPI 路径 `\_SB_.PC00.I2C0`** + 客户端 `i2c-N-002c` **双判据**定位总线 | 不再"扫全部" |
| 1 | **先解绑** `i2c_hid_acpi` / `i2c_hid_of` 在 `i2c-N-002c` 上的绑定 | ★ 关键修复 |
| 2 | **只扫 0x5A–0x5B 两个点**（`i2cdetect -y -r N 0x5a 0x5b`） | 最小扰动，先拿判据 |
| 3 | 定点读身份：`i2cget N 0x5a 0x57` / `0x58` ⇒ 期望 `0x92` / `0x70` | AW86927 唯一身份判据 |
| 4 | 若无应答，再扫 `0x03–0x77` 全表（**只读 `-r`，不用 `-a`**） | 找"第二个从设备在哪" |
| 5 | 收尾**恢复绑定** | 不留状态 |

### 5.3 二元判据

| 结果 | 含义 | 下一步 |
|---|---|---|
| 扫到 `0x5A`/`0x5B` 且 `0x57=0x92, 0x58=0x70` | ★★★ **AW86927 就在主机总线上** ⇒ 「隔着 GT7868Q」这个问题**根本不存在**；Linux 侧照抄 §4.2 就能震 | 写 Linux 侧 input→i2c 的小程序，做"滑动即震"原型 |
| 扫到其它**非 0x2C** 的从地址 | 触觉 IC 可能用别号（`AD` 脚决定 `0x5A`/`0x5B`，也可能被改成别的）；把全表留档 | 逐个读 `0x57/0x58` 指纹 |
| **一个都没有**（除 0x2C） | 触觉 IC 确实在 GT7868Q 的私有总线上 | 只剩"硬件接管"或"改固件"，回到 §三/§四 的硬件判据 |

---

## 六、纪律（第 55–58 条）

55. ★★★ **"参考项目的**最新**项目"要单独查一次。**
    项目此前只查过蓝莓的两份 wiki 和前代 `ESP32-Precision-TouchPad`，
    **完全没看到 2026-10-02 才推送的 `ESP32-Haptic-Precision-TouchPad`** ——
    而它恰好是**同构度最高**的一份（同一个 `0x2C` + 一颗独立触觉 IC）。
    ⇒ **跨项目找同一作者的历史产物**这条（第 46 条）要补一半：**也要找他的"现在"。**

56. ★★★ **"上层 API 拿到的地址"要先问"ACPI 声明的地址"是什么。**
    本项目长期把 `_ADR = One` 当成"触控板 I²C 从地址 = 1"，
    而 I²C 子设备的地址**权威在 `_CRS`**（= `0x2C`）。
    ⇒ **ACPI 里同一个设备有多个"地址类"字段时，先确定哪个是规范的。**

57. ★★ **"扫描没找到"之前，先问"扫描时的占用状态对不对"。**
    旧 `probe.sh` 在 `i2c_hid` 绑定状态下全地址扫描 ⇒ 与"崩内核"记录自洽。
    ⇒ **工具的顺序（先解绑、后扫描）本身就是方法学的一部分。**

58. ★★★ **"参考实现做到了什么"要和"我们要什么"对齐后再下判断。**
    蓝莓 `[ ] 触觉反馈和强度控制` 至今未勾 ⇒
    **"滑动持续反馈"没有现成答案**；**"滑动逐次脉冲"则有可行性证明**。
    ⇒ **先确认目标属于哪一种，再决定要不要继续挖波形固件。**

---

## 附：本轮实际产物

| 文件 | 内容 |
|---|---|
| `probe/bb_repos.json` | 蓝莓 50 个仓库的 API 快照 |
| `probe/ESP32-Haptic-Precision-TouchPad.tree.json` | 新项目 199 个 blob 的完整文件树 |
| `probe/bh/*.c` / `*.h` / `*.md` | 实际下载的源码：`README_CN.md`、`Hacking/README.md`、`i2c_addr_scanner.c`、`cs40l25_rom_test.c`、`cs40l25_haptic_strength_test.c`、`I2C_handle.h`、`GPIO_handle.h`、`i2c_cmd.c`、`sub_i2c_init.c`、`surface_haptic_hw.c` |
| `probe/ghget.py` | GitHub contents API 下载器（raw.githubusercontent 走代理常 502，用 API 稳） |
| `probe/pnp.txt` | 本机 `pnputil /enum-devices` 全量快照 |
| `linux/probe2.sh` | ★ **解绑优先版**只读探测脚本（本轮新写） |
