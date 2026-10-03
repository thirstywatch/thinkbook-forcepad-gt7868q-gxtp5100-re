> ⚠️ **本文件（v1）已被 `硬件逆向-逆向方法总谱.md`（v2）取代。**
> v1 的重心偏了：把"ALS 替代角度""扬声器替代震动"这类**换实现**的方案当成了主推。
> v2 只谈**逆向方法本身**。v1 仅作情报库与历史记录保留。

---

# 硬件逆向 · 侧面路线与情报汇总

- 整理时间：2026-09-27
- 本机：Lenovo ThinkBook 14 G6+ IMH（**21LD**）· Core Ultra 7 155H · 主板 LNVNB161216 · BIOS NJCN67WW（12/17/2025）· Win11
- 覆盖两个在研项目：**① 开盖角度传感器逆向**（`lid-probe`）· **② 触控板震动逆向**（`touchpad-lab`）
- 前提：**尚未掌握硬件级逆向技能（不拆机、不焊接、不用逻辑分析仪/JTAG）** —— 本文全部路线按此前提筛选

---

## 零、结论先行

### 0.1 两个项目 × 三种通道 的当前地图

| 通道层级 | 角度项目 | 触控板项目 |
|---|---|---|
| **主机软件接口**（HID / WinRT / ACPI 方法） | 已穷尽 → 只有 0/1 | 已穷尽 → `Col02 out=0`，无主机触发 |
| **EC 层** | ⚠️ **实际从未真正试过**（详见第二章） | 不相关（已确认震动不经 EC） |
| **传感器侧信道** | ★ **有 2 条连续量可用**（ALS / 人体距离） | — |
| **设备固件静态分析** | ⭕ **未做**（EC 固件可从 BIOS 包提取） | 部分已做（TF100A 明文段），**有一处方法论盲区** |
| **执行器** | — | 硬件旁路（唯一确定可行，但需动手） |

### 0.2 一句话

> **角度项目的"死路"结论建立在一个判据错误上** —— 前四轮调查把"EC 通道"等同于"需要 JTAG/SWD"，于是从未尝试。事实上，**这台机器的 EC 有一条主线 Linux 内核已经写好代码、社区已经踩过坑、并且有同型号机器的开发者在用的软件通道**（`VPCR`/`VPCW`）。
>
> **触控板项目的主机侧结论仍然成立**（`Col02 out=0` 是设备描述符级的事实，无法绕），但新增：**一条必须换 OS 才能走的实验路线**、**一处静态分析盲区**、**一份从未读过的原厂一手资料**，以及**一条纯软件的物理反馈通道**（扬声器低频）。

### 0.3 三个突破口（按性价比排序）

| # | 突破口 | 成本 | 能一锤定音的问题 |
|---|---|---|---|
| **1** | **一块磁铁** | ¥0 / 10 秒 | 这台机器的盖子检测是**霍尔开关（二元）**还是**转轴角度传感器** —— 直接决定"到底有没有角度" |
| **2** | **EC 固件静态逆向 + DSDT 反编译** | ¥0 / 纯软件 | EC RAM 里**有没有角度变量**；有的话在哪个字节 |
| **3** | **ALS / 人体距离传感器当"角度替代信号"** | ¥0 | 能不能**今天就做出跟手动画**（不等角度） |

---

## 一、本轮最重要的发现：这台机器的 EC，正有人在啃

这一章是全部内容的引信。之前的调查（`lid-probe` 第十二节、第十四节）判断"要看 EC 内部得用 JTAG/SWD"——那个判断**只对 EC 的物理调试口成立**，对"EC 的软件接口"完全错误。

### 1.1 主线内核里有一段专门点名 2024 年后 ThinkBook 的注释

`drivers/platform/x86/lenovo/ideapad-laptop.c`（Linux 6.15 起）：

```c
/*
 * Some models (e.g., ThinkBook since 2024) have a low tolerance for being
 * polled too frequently. Doing so may break the state machine in the EC,
 * resulting in a hard shutdown.
 * ...
 */
#define IDEAPAD_EC_POLL_MIN_US 150
#define IDEAPAD_EC_POLL_MAX_US 300
```

**这段注释的出处是一个真实事故**（Rong Zhang，2025-05，`Closes: bugzilla.kernel.org/218771`），症状原文：

> `ideapad-laptop sometimes causes some recent (since 2024) Lenovo ThinkBook models shut down when:`
> `- suspending/resuming`
> `- closing/opening the lid`  ← **就是你关心的这个动作**
> `- (dis)connecting a charger`
> `- ... pressing down some Fn keys`

机理：`read_ec_data()` 在两次轮询之间调 `schedule()`，在无就绪任务时**过早返回**，两次轮询间隔太短 → 命令被中止 → 后续"对着空气猛轮询" → **EC 状态机崩 → 硬关机**。

### 1.2 同型号开发者的验证回复（原文）

LKML 上，**Felix Yan** 对该补丁的测试回复：

> *"Tested to work as expected on my **ThinkBook 14 G6+ IMH (Intel model)** with the following:*
> *- Fn+F5/F6 inputs, more responsive than before and no shutdown.*
> *- Sleep via power button and **close the lid** (which is bound to sleep as well); Wake via shaking the mouse and **open lid**. **Both caused unexpected shutdown before** and fixed now."*

**这是你手上这台机器（14 G6+ IMH，Intel）。**

### 1.3 内核里已经写好的通用 EC 读写原语

`ideapad-laptop.c` 的两个 ACPI 方法封装 —— **这就是你 ETW trace 里 `\_SB.PC00.LPCB.EC0.VPC0.VPCR` / `VPCW` 的用户态入口**：

```c
static int eval_vpcr(acpi_handle h, unsigned long cmd, unsigned long *res)  // 读 EC（VPCR）
static int eval_vpcw(acpi_handle h, unsigned long cmd, unsigned long data)  // 写 EC（VPCW）

static int read_ec_data(acpi_handle h, unsigned long cmd, unsigned long *data)
{
    err = eval_vpcw(h, 1, cmd);          // 1 = 发起命令
    while (在 200ms 内) {
        usleep_range(150, 300);          // ★ 安全间隔
        err = eval_vpcr(h, 1, &val);     // 1 = 查状态
        if (val == 0) return eval_vpcr(h, 0, data);   // 0 = 取数据
    }
}
```

**含义**：`(cmd, data)` 是一个完整的 **EC 命令空间**。已知的 `VPCCMD_*` 覆盖：亮度、射频开关、触摸板使能、摄像头、风扇、键盘背光、3D/ODD、传感器读取（`VPCCMD_R_SENSOR`）等。**`read_ec_data` 之外的命令值从未被社区穷举**。

### 1.4 这台机器确实有 EC，而且版本对 OS 可见

Linux hardware probe 对同型号机器的 DMI 转储：

```
Platform Firmware Information
 Vendor: LENOVO   Version: NJCN67WW   Release Date: 12/17/2025   ROM Size: 16 MiB
 Platform Firmware Revision: 2.67
 Embedded Controller Firmware Revision: 2.67     ← EC 固件独立版本号
```

联想中文支持页把 BIOS 和 EC 版本成对公布（例：`BIOS Version: QECN29WW, EC Version: QEEC25WW`）。→ **EC 固件是 BIOS 更新包的一部分，可提取**（见 2.2）。

### 1.5 结论：EC 通道是**开的**，而且是**文档化的**

| 之前判断 | 修正 |
|---|---|
| "要看 EC 内部 RAM 得用 JTAG/SWD" | ❌ 对**调试口**成立；对**命令接口**不成立。`VPCR`/`VPCW` 是软件可调的 |
| "用户态无法调用 ACPI 方法" | ❌ 对 **Windows** 硬性成立；**Linux 侧有 `acpi_call`**（`/proc/acpi/call`，可传整数参数），Windows 侧有联想自家签名的 VPC 驱动 IOCTL（社区已逆向：FanControl / `hejunv/Lenovo-IdeaPad-Z500-Fan-Controller` 就是靠它控风扇） |
| "联想 WMI 大概率是 VPC 的上层包装" | ✅ 方向对，但**不用绕道 WMI** —— VPC 本身可直达 |

---

## 二、角度项目：三条从未走过的软件通道

### 2.1 ★ 通道 A：EC 命令空间扫描 + EC RAM 读取

**目标**：确认 EC RAM 里有没有"角度"这个量，以及它在哪个字节/哪条命令后面。

**做法（全部零硬件）**：

| 步骤 | 工具 | 说明 |
|---|---|---|
| 1 | `iasl -d` 反编译 DSDT + 全部 SSDT | 拿下 `EmbeddedControl` OperationRegion 的**完整 Field 字段表** —— 这是 EC RAM 的"地址簿" |
| 2 | 读 `yogafan` 内核文档方法论 | 主线文档已给出这条套路，且**列了 ThinkBook G6 的 EC 偏移**（见下） |
| 3 | Linux 侧用 `acpi_call` 调 `VPCR`/`VPCW` | 单发读、不写；严格按 150–300 µs 节奏或更慢 |
| 4 | 或 Windows 侧用 `ec-probe`（NBFC 自带）/ `RWEverything` | `ec-probe --dump-registers` 一次把 EC 寄存器打全 |

**已公开的现成锚点**（`Documentation/hwmon/yogafan.rst`，涵盖你这一代）：

| 机型 | EC 偏移 | DSDT 字段 | 宽度 | 倍数 |
|---|---|---|---|---|
| **ThinkBook G6** | **0x06** | `\_SB.PCI0.LPC0.EC0.FAN0` | 8-bit | 100 |
| Legion 7i (Int) | 0xFE/0xFF | `\_SB.PCI0.LPC0.EC0.FANS` / `FA2S` | 16-bit | 1 |
| Yoga / IdeaPad | — | `\_SB.PCI0.LPCB.EC0.FAN0` | 8-bit | 100 |

> 文档里明确写了识别方法论：**DSDT（`iasl`）+ 与 NBFC 配置交叉验证 + 数据宽度分析**。这正是"不用硬件、纯软件拿 EC RAM 语义"的标准做法。

**产出预期（要诚实）**：
- **若 EC RAM 里存在角度字节** → 直接读它，跟手动画的硬件前提就齐了（这是唯一能让角度项目翻盘的路径）
- **若不存在**（只需一个"合盖"位）→ 也把问题彻底关闭，且顺手拿到完整的 EC 状态地图（风扇、温度、电池、传感器）

**安全剂量（必须遵守）**：

| 项 | 值 | 依据 |
|---|---|---|
| 单次命令内的轮询间隔 | **150–300 µs** | 主线内核实测值 |
| 命令与命令之间 | **留足间隔，不做后台轮询** | 高频轮询在 2024+ ThinkBook 上**已记录硬关机** |
| 读/写 | **只读** | 写 EC 风险不成比例 |
| 触发场景 | 不要与挂起/合盖/插拔电源**同时**做 | 这四个场景本身就是崩溃高发点 |

---

### 2.2 ★ 通道 B：EC 固件静态逆向（从 BIOS 更新包提取）

**为什么这条路之前被漏掉**：`lid-probe` 只把 `NJCN67WW_FWUpdate.bin` 当作"找 Insyde 容器/Goodix 字符串"的素材，**没有去找 EC 固件组件**。

**事实**：联想的 BIOS 升级包里**同时含 BIOS 与 EC**（中文社区原话：「由于联想的升级包里面包含 **ec 和 bios** 文件，需要进行截取」）；官方发布说明也是成对公布的（`BIOS Version: QECN29WW, EC Version: QEEC25WW`）。你这台的更新包：`NJCN67WW.exe`（12.2 MB，联想支持页 DEditid=156062）。

**提取链路（纯软件）**：

```
NJCN67WW.exe
  └─ innoextract / 7z / UniExtract2      → 解出内部 .fl1/.fl2/.fd/.bin 镜像
      └─ ifdtool（coreboot，Meteor Lake 需新版）  → 按 flash descriptor 切出 region
          └─ UEFITool / 直接字符串特征         → 定位 EC 固件区（EC 版本号 NJECxxWW 是天然锚点）
              └─ Ghidra                     → 反汇编（EC 多为 ITE IT8xxx，8051 内核；也可能 ARM）
```

**可直接照抄的社区范例**（都不需要硬件）：

| 项目 | 做了什么 | 可借鉴之处 |
|---|---|---|
| `hamishcoleman/thinkpad-ec` | ThinkPad X220/X230 EC 固件的完整逆向方法论 + `dump_datazone` 工具（radare2 项目、内存布局 config、符号表） | **纯静态**：固件分区、键盘矩阵表、函数指针发现 |
| `leecher1337/thinkpad-E130-ec` | Ghidra 工程 + 命令表 + 内存区文档 + `IT8518E-ec-sys` 读写模块 | 8051 EC 的命令/内存文档格式 |
| `Saddytech/Galaxy-Book4-Edge-linux` | **完整逆向路线**：Windows 驱动 Ghidra 逆向 → DSDT 提取 → I2C 协议解码 → 自写驱动（ENE KB9058） | **最贴近你处境的一份完整示范**（同样是"不想碰硬件"的路径） |
| `marcoferr99/msi-ec` | EC 驱动 + `ec_dump` 用法 + 固件版本命名解码 | EC 语义定位的实操文档 |
| mjg59 博客《Extending proprietary PC embedded controller firmware》 | 用 Ghidra 找到寄存器处理函数 → 在未用空间插入新代码 → 改跳转 | **EC 固件可打补丁**的完整案例 |
| CSDN《IT8519 EC固件逆向实战》 | ITE 系 8051 架构、寄存器入口、看门狗反汇编 | 中文入门 |

**关键判断**：**EC 固件是 8051/ARM 的、几十 KB 的东西，反汇编难度远低于"破解 GT7868Q 加密固件"**。而且 EC 固件**不加密**（社区从没遇到 EC 固件加密的）。

---

### 2.3 ★ 通道 C：侧信道 ——"角度替代信号"（性价比最高，今天就能用）

这两条都是**已验证可读的传感器**，只是之前被当作"别的用途"：

| 信号 | 设备 | 已知实测值 | 为什么可以当"角度代理" |
|---|---|---|---|
| **环境光强度** | `LightSensor`（Intel ISH，`HID\VID_8087&PID_0AC2`） | **54.29 lux** 实测可读 | 传感器在**屏幕额头**。合盖过程中，它从"朝环境"逐渐转为"朝键盘"→ **光强连续下降**。而且**变化早于霍尔触发、早于 `_LID`、早于 EC `_Q15`** |
| **人体距离** | 联想自定义传感器（Idea5003，`SENSOR_TYPE_CUSTOM`） | `162`：**2500 mm**（走开）/ 258–603 mm（坐姿） | 同为额头传感器；**合盖时键盘面扑上来 → 距离读数向极小值塌陷**（量程下界需实测，可能饱和） |

**这两个的价值**：

```
目标：「开盖/合盖跟手动画」（Mac Duo 那种）
角度缺失 → 但 ALS 的光强曲线是连续的、时间上超前的

 时间轴 →
 手开始合盖 ──┬───────────────┬────────────┬─────────
              │               │            │
          ALS 开始下降    霍尔/阈值触发   _LID/CS    物理闭合
        （★ 在这里起动画）  （EC._Q15）   （二元）
```

**即：把"跟手"定义从"跟随角度"改成"跟随光线/接近度"，就能在不具备角度传感器的机器上做出连续响应。** 且这两条通道**今天就能测**（现有脚本 + 一个 5 分钟的记录）：

- 测法：前台循环采 `LightSensor` + 自定义传感器 `162/163/164`，同时**慢慢**合盖（**不要合到底** —— 会触发 Modern Standby 让脚本挂起），记录两条曲线的时间关系。
- 判据：ALS 是否在 `_LID` 变化前 200 ms 以上就开始下降；下降是否单调。

---

### 2.4 ★ 一块磁铁：10 秒判定"到底有没有角度传感器"

**这是本轮最便宜的一击。**

物理事实：现代笔记本盖子检测有**三种**实现（不是两种）：

| 实现 | 判据 | 是否会有"角度" |
|---|---|---|
| **霍尔开关** | 屏幕里有小磁铁，机身上的霍尔器件在**阈值处翻转**（典型 3–10 mT，带回差 B_OP/B_RP，2–4 mm 死区） | **没有**，天生二元 |
| 机械行程开关 | 转轴附近按压开关 | **没有** |
| **转轴角度传感器** | 检测转轴转动角度，可区分半开/全开 | **有** |

**实验**：拿一块**小磁铁**（冰箱贴即可，别用强磁）靠近**掌托/转轴附近**（通常在前缘中部或键盘两侧）。

| 现象 | 结论 |
|---|---|
| **屏黑/触发合盖** | 是**霍尔开关** → 物理上就只有一个阈值 → **"角度"在这台机器上根本不存在**，联想用户手册里"detect the angle"是营销措辞 → 角度项目可以**当场结案** |
| **无反应**（换几个位置都不行） | 要么霍尔位置刁钻，要么是**转轴角度传感器** → **EC 通道（2.1/2.2）升级为首要任务** |

> 社区先例：`dev.to` 上有人用一块磁铁贴到笔记本边缘就把屏幕"骗"关了，并拍了视频 —— 说明这个实验对霍尔机型是稳定可复现的。
> **注意**：不要长时间把强磁贴在机器上；不要贴着 NVMe/扬声器位置玩。

**为什么这一击值钱**：它把"开放问题"变成"已结案问题"，成本是一块磁铁。无论结果哪个方向，后面的路线都会立刻收敛。

---

### 2.5 顺带两处可补强（前份报告里的小缺口）

| 缺口 | 说明 |
|---|---|
| **Idea5003 的 Input Report 从未监听** | 之前只读了 4 个 vendor collection 的 **Feature** report（结论：静态）。但 COL01 声明了 `ReportID 0xC1 / 0xC2` 是 **Input** report，**从未被读取过**。只读、单发，风险低（Idea5003 不是指点设备，挂了不影响操作） |
| **`LENOVO_OTHER_METHOD` 的 ID 表会随 BIOS 变化** | 官方更新说明里明确有「**优化 LENOVO_OTHER_METHOD Get/Set 风扇速度**」这类条目 → 说明这套 ID 是活的。之前在 NJCN 早期版本上枚举出的 93 个 ID / 14 个可读，**值得在 NJCN67WW 上重跑一次** |

---

## 三、触控板项目：剩下的侧面

### 3.1 ★ 路线 A：换操作系统做实验（Linux Live USB）—— 把 Windows 上锁死的门打开

Windows 侧做不了的三件事，Linux 侧全部可做，而且**风险更低**：

| Windows 里的墙 | Linux 侧的对应物 |
|---|---|
| `Col02` 被系统独占（`err=32`），**不能写它的 feature report** | Linux 下 `hidraw` 对绑定设备仍可 `HIDIOCSFEATURE`/`HIDIOCGFEATURE` —— **`rid=11/12/13` 那三个语义未解、却已被接受的 feature 写入，可以在这边系统性摸** |
| 拿不到 737 字节的完整 feature 描述符 | `hidraw` 直读 |
| HID 之下没有入口 | **`/dev/i2c-N`**：`i2c-tools` 可对 GT7868Q 的 I2C 从地址发**裸 I2C 事务**（`i2cdetect`/`i2cdump`/`i2ctransfer`）—— 彻底绕开 HID 层 |
| 挂了只能靠"关机+拔电+长按电源 30 秒" | 内核模块可卸载重载、I2C 总线可重新枚举；**Live USB + 外接鼠标**做退路，真机零负担 |

**附带一条一手资料**：`goodix/gtx8_driver_linux`（**汇顶自己的开源 Linux 驱动**，gtx8 正是你这颗芯片的容器格式名）里有 `goodix_ts_tools.c` —— 一个 **"Debug tools" 扩展模块**（`CONFIG_TOUCHSCREEN_GOODIX_GTX8_TOOLS`）。**这份文件至今没被读过。** 厂商自己的调试/测试路径里，出现"马达测试命令"是行业常见做法。

### 3.2 ★ 路线 B：静态分析有一处方法论盲区（BL 调用图 ≠ 全部调用）

项目里有一条关键结论：**「"播放"包装 `0x08008628` 在 600 条边的调用图里无任何调用者」→ 震动是固件内部行为，主机侧无入口。**

这条结论**只对"直接调用（`BL`）"成立**。而同一份固件里明确存在**函数指针调用**：

```asm
0x08008858:  push {r7, lr}
             ldr  r0, [r0, #0x14]     ; 取结构体 +0x14 处的函数指针
             blx  r0                  ; ← 间接调用，BL 图看不见
```

而 `0x08009750`（LRA/TIM3 配置）**恰恰就是把波形回调 `0x0800D6F4` 写进 `+0x14` 的那段代码**。→ **"播放"函数完全可能通过指针被调用，BL 调用图看不见。**

**还剩下三个可查的静态问题（纯离线、零风险）**：

| # | 问题 | 为什么关键 |
|---|---|---|
| 1 | `0x08009750`（LRA 配置）的**调用者集合** | 若调用者能追到命令分发器 → "命令表无一条碰 TIM3" 这条结论需要修正 |
| 2 | 谁**读** `0x20005FEE`？ | `A0-0x0D`（"清/arm"）会 `memcpy` + 写 `0x20005FEE = 1`。**"arm"这个命名意味着有消费者** —— 找到消费者就等于找到隐藏的触发路径 |
| 3 | `0x2000426C`（44B 触觉上下文）的**读写者全表** | A1 类命令大量引用它 → 说明命令空间**确实碰触觉状态**（比"无一条碰马达"更细） |

> **实操提示**（我这次动手时踩到的坑）：capstone 在遇到首个无法解码的字节时会**静默停止**（56 KB 镜像只解出 28 条指令）。必须做**线性扫描重启**（解码中断后偏移 +2 再续）或 `skipdata`。项目里那份"字节级 BL 扫描"是稳的，但任何基于 `md.disasm(whole_image)` 的分析都要检查这个。

### 3.3 ★ 路线 C：规格更新 —— 微软 2026 才开的触觉 API

这是**新增的、之前不存在的**判据：

| 项 | 内容 |
|---|---|
| API | `Windows.Devices.Haptics.InputHapticsManager` |
| 命名空间/版本 | `UniversalApiContract` 19.0；Win11 SDK **10.0.28000.1721（2026-03）**；Align/Collide/Step/Grow 波形需 1839（2026-04） |
| 一行判定 | `InputHapticsManager.IsSupported()` |
| 触发 | `InputHapticsManager.GetForCurrentThread().TrySendHapticWaveform(waveform, 0)` |
| 硬性前提 | 触控板必须暴露 **`SimpleHapticsController` 集合（Page 0x0E / Usage 0x01）**，且**主机触发必须有 Manual Trigger 的 OUTPUT 报表** |

**对本机的意义**：项目已实测 `Col02 OutputReportByteLength = 0` → **输出报表一个都没有 → 主机触发必然不支持**。这条结论不变，但现在的证据是**2026 年最新规范**（而非 2019 年的 HUTRR63），并且可以**用一个 API 调用做最终确认**（`IsSupported()` 返回 false 即闭环，成本 3 行代码）。

**同时要知道反向的事**：**苹果是主机触发的** —— macOS 向 App 开放触觉反馈 API（AppKit `NSHapticFeedbackManager`），Taptic Engine 由主机侧驱动。**"笔记本触控板主机触发震动"是量产机上存在的，只是不在这块模组上。** 这个对照的意义：**做不到不是"没找到方法"，而是"这颗模组的描述符里没写这一项能力"**。

### 3.4 ★ 路线 D：纯软件的物理反馈通道（扬声器低频）

**先说逻辑**：`触控板本体震` 这个需求，在**不碰模组内部**的前提下，还能产生物理振动的可控执行器只剩一个 —— **扬声器**。

| 支撑论据 | 出处 |
|---|---|
| 低频（**<400 Hz**）就是触觉频段 | 微软专利《**Haptic Trackpad Loudspeaker**》（USPTO，2024-11 授权）：触控板同时当扬声器振膜，**<400 Hz 作触觉、400 Hz–10 kHz 作音频** |
| LRA 的谐振频率典型 **150–235 Hz** | 多家 LRA 厂商 datasheet |
| TF100A 固件的 PWM 常量（周期 **999 / 1999**）指向 ~100–200 Hz 量级 | 本项目固件分析 |
| "劫持振动信号 → 缓冲后驱动自己的执行器，不干扰原功能" | `dawidmpunkt/rumble-for-steamdeck`（Steam Deck 触感改造，纯软件嗅探 + 缓冲驱动） |

**可测假设（3 个，全部零风险，今天就能测）**：

1. **扬声器低频 → 掌托/C 面体感震动**：播放 120–200 Hz 正弦（带快速起停包络），手掌放在触控板旁边感受。很多笔记本的扬声器腔体就在掌托下方。
2. **扬声器低频 → 原装 LRA 被"被动激励"**：LRA 是"质量块 + 弹簧"，**不通电也会被外部振动带着振**。若驱动频率接近它的谐振频率，质量块可能被明显带起来，而它**直接贴着触控板**。这是本轮最有想象力、也最不确定的一条。
3. **包络比音调更重要**：短促上升（5–15 ms）+ 快速衰减的 100–200 Hz 爆发，听感上是"咔"，体感上更接近"哒"。微软自己的定义（Intensity / Decay / Sharpness）就是这么分的。

**诚实预期**：这条路的质感**一定不如原装 LRA**，而且"触控板本体震"很可能打折（可能是整机/掌托在震）。但它**零成本、零风险、时机完全可控**，可以在方案③（硬件旁路）之前先跑一版，把"手势 + 节拍"这套逻辑先验证掉 —— 而那套逻辑**在硬件到位后一行都不用改**。

### 3.5 ★ 路线 E：中国专利 —— 钛方的官方技术细节（纯公开渠道）

| 事实 | 数据 |
|---|---|
| 厂家 | 北京钛方科技，**联想创投投资**，国家专精特新"小巨人" |
| 专利量 | **191 件**（另一口径"130 余件申请，发明专利近 60%"） |
| 布局领域 | 传感器、弹性波、**压电传感器**、处理模块、检测装置、传感器模组 |
| 已确认搭载 | 联想小新 Pro13s、**联想已有四款上市笔记本搭载钛方力度感应触控方案** |
| 技术定位 | 弹性波（固体中机械波）→ 深度学习算法 → 识别**力度/位置/模式**；官方明确列出"**触觉反馈**"是能力之一 |

**为什么这是"侧面"**：中国专利**全文公开**，且国产厂商的专利说明书常带**电路框图 + 流程步骤 + 实施例参数**。查"申请人 = 北京钛方科技"的**压感触控/触觉反馈**类专利，有可能直接读到：
- Force IC 与主控（GT7868Q）之间的**接口定义**
- 力度→触觉反馈的**判定流程与阈值**（这正好回答"震动是谁决定的"）
- 是否**存在主机侧接口**

成本：0 元。检索入口：国家知识产权局公开检索 / 智慧芽 / 天眼查专利。

### 3.6 别人已经做成的同类事（方法论可直接抄）

| 项目/报道 | 做了什么 | 对本项目的用法 |
|---|---|---|
| **barryblueice · 基于 ESP32 的三模精确式压感触摸板**（立创开源） | CS40L25 触觉固件（Cirrus 标 NDA 不可公开）**由逆向 Surface Haptic Firmware 得到**：解包 Surface Laptop Studio 驱动包 → 从 SAM 控制器固件与 CS40L25 控制固件里提取 waveform | **"从 OEM 驱动包里逆向触觉固件"** 的标准示范；且他自述"逐参数调优可接近原厂 click 手感" |
| **Steam Controller 触觉 → 立体声扬声器**（Tom's Hardware 报道） | 用 HIDAPI **低层 feature 命令**直接给触控板马达下发 PCM 流，绕开 Steam Input，让马达发出可听声音 | 证明"低层 feature 报表能绕开高层软件直驱马达"这条路径在别的设备上成立 |
| **rumble-for-steamdeck** | usbmon/Wireshark 嗅探振动信号 → 缓冲驱动自己的马达，**不影响原功能** | 方案③的**免焊接替代思路**：不抢线，做旁路缓冲 |
| **微软 Haptic Trackpad Loudspeaker 专利** | 触控板当振膜 | 见 3.4 |
| **联想 X1 Titanium 的 Sensel 控制面板** | 厂商提供"触感反馈：关闭/低/中/高" + 防手掌误触 UI | 说明**触觉强度/开关是厂商侧可配的**；同时反证：Windows 原生只有 `FeedbackEnabled` + `FeedbackIntensity`（= 项目读到的 `rid=9`），**没有主机触发** |

### 3.7 顺带：EC 通道对触控板的两个副产品

| 项 | 说明 |
|---|---|
| `VPCCMD_W_TOUCHPAD` / `R_TOUCHPAD` 存在 | **EC 是触控板使能/供电的一环** → 触控板死掉时，理论上有一条比"拔电池长按电源"更轻的复位路径（**但绝不可当试验品**，红线不变） |
| `README` 里的硬关机记录 | ThinkBook 2024+ **不要对 EC 做高频轮询** —— 这条对触控板项目同样适用（别一边扫 EC 一边做触控板实验） |

---

## 四、情报库（本轮收集，按主题）

### 4.1 EC / 嵌入式控制器

| 名称 | 类型 | 一句话 |
|---|---|---|
| `torvalds/linux` → `drivers/platform/x86/lenovo/ideapad-laptop.c` | 主线代码 | **`VPCR`/`VPCW` 通用 EC 命令读写原语** + ThinkBook 2024 轮询安全间隔 |
| Bug **218771**（bugzilla.kernel.org） | 缺陷报告 | "Lenovo Thinkbook — turning off after **closing lid** or (dis)connecting charger"；含 AMD 版 21LF 完整复现矩阵 |
| `ty2/ideapad-laptop-tb2024g6plus` | 仓库 | **专门为 ThinkBook 2024 G6+ 的 ideapad-laptop 模块**："solves problem with laptop turning off after closing the lid" |
| `ferstar/ideapad-laptop-tb` | 仓库 | DKMS 版；兼容 16+ IMH / **14 G6+ AHP** / 16 G6+ AHP；博客 issue #85 是中文说明 |
| `ferstar/lenovo-wmi-hotkey-utilities` | 仓库/已上游 6.15+ | 联想 WMI 灯控；列出 6 个 ThinkBook 机型；`lenovo-wmi-*` 主线驱动族 |
| `hwmon/yogafan` 内核文档 | 主线文档 | **DSDT→EC OperationRegion 偏移**方法论；**ThinkBook G6@0x06 `FAN0`** |
| `hamishcoleman/thinkpad-ec` | 仓库 | EC 固件逆向方法论 + `dump_datazone`（radare2 工程、内存区 config、符号表） |
| `leecher1337/thinkpad-E130-ec` + `IT8518E-ec-sys` | 仓库 | ITE 8051 EC：Ghidra 工程、命令表、内存区、读写模块 |
| `marcoferr99/msi-ec` | 仓库 | EC 驱动 + `ec_dump` 用法 + 固件版本命名解码 |
| `Saddytech/Galaxy-Book4-Edge-linux` | 仓库 | **"不碰硬件"的完整逆向路线**：Windows 驱动 Ghidra → DSDT → I2C 协议 → 自写驱动 |
| mjg59《Extending proprietary PC embedded controller firmware》 | 博客 | EC 固件可打补丁的完整案例（CR16C、Ghidra、热补丁寄存器处理） |
| `hirschmann/nbfc`（+ `nbfc-linux`） | 工具 | 200+ 机型的 EC 寄存器 XML；自带 **`ec-probe.exe`**（dump/monitor/read/write EC 寄存器） |
| `hejunv/Lenovo-IdeaPad-Z500-Fan-Controller` | 仓库 | **通过联想 VPC 驱动控 EC**（用户态 → 内核驱动 → EC）的实证 |
| `jiarandiana0307/Lenovo-Fan-Control` | 仓库 | 同上，中文详解（联想电脑管家 `WSHardwarePlugin.dll` → VPC 驱动） |
| `Bumblebee-Project/acpi_call` | 工具 | Linux 下 `/proc/acpi/call` **调用任意 ACPI 方法**（可传整数参数）→ 直接调 `VPCR`/`VPCW` |
| Linux `ec_sys` 模块 | 主线模块 | `/sys/kernel/debug/ec/ec0/io` 直读/直写 EC RAM |
| `thinkwiki.org/wiki/Embedded_Controller_Firmware` | 百科 | ThinkPad EC 世代与命名（`TP-1Y` / `1YHT29WW`）—— 理解"BIOS 版本 → EC 版本"对应关系 |
| CSDN《IT8519 EC固件逆向实战》《笔记本EC调试方法全解析》 | 中文教程 | 8051 反汇编、看门狗、`iasl` 反编译 DSDT、`ec_sys` 实操 |
| 联想支持页（BIOS 更新说明） | 官方 | **BIOS/EC 版本成对公布**；更新条目里出现「优化 `LENOVO_OTHER_METHOD` Get/Set 风扇速度」 |

### 4.2 触控板 / 触觉

| 名称 | 类型 | 一句话 |
|---|---|---|
| `goodix/gtx8_driver_linux` | **原厂开源** | 汇顶自己的 gtx8 Linux 驱动，含 **`goodix_ts_tools.c`（调试工具模块）**、`goodix_gtx8_update.c`、`goodix_ts_i2c.c` |
| `fwupd/plugins/goodix-tp` | 上游 | 汇顶员工署名（`xulinkun@goodix.com`）；`com.goodix.goodixtp` 协议 |
| `ty2/goodix-gt7868q-linux-driver` | 仓库 | 本项目同款芯片；`rdesc[607] 0x15→0x25` 描述符修正；已进内核 6.11+ |
| LKML：Goodix GT7868Q `report_fixup` 补丁 | 上游 | ThinkBook 13x Gen4 等机型的 HID 修正 |
| LKML：**`HID: Implement haptic touchpad support`**（v3，2025-08，Chromium OS 团队 Jonathan Denose） | 上游 RFC | **主机控制模式**的完整 HID 设计：设 `WAVEFORM_STOP` 切 host-controlled；**"设备必须支持 manual triggering"** |
| 微软《Input Device Haptics Implementation Guide》 + 《Windows 精确式触摸板集合》 | 规范 | `SimpleHapticsController`（0x0E/0x01）位置要求、波形表、Manual Trigger OUTPUT 报表 |
| 微软《Precision touchpad tuning》 | 规范 | `FeedbackEnabled` / `FeedbackIntensity` / `ClickForceSensitivity` 注册表项 |
| 微软《InputHapticsManager》开发者文档（2026） | 规范/API | **App 侧触发触觉的公开 API**（见 3.3） |
| `barryblueice/ESP32-Haptic-Precision-TouchPad`（立创开源 + GitHub wiki） | 项目 | **逆向 Surface 触觉固件提取波形**；ESP32 + CS40L25 三模压感板 |
| `dawidmpunkt/rumble-for-steamdeck` + `RumbleDeck` | 项目 | 嗅探振动信号 + 缓冲驱动；DRV2605L |
| Tom's Hardware：Steam Controller 触觉变扬声器 | 报道 | HIDAPI 低层 feature 命令直驱马达 |
| 微软专利《Haptic Trackpad Loudspeaker》 | 专利 | **<400 Hz 触觉 / 400 Hz–10 kHz 音频**；触控板当振膜 |
| 钛方科技（`taifangtech.com`）+ 191 件专利 | 厂商 | TF100A 的东家；弹性波力度+触觉；联想投资 |
| 汇顶《Newton Touchpad®》 | 厂商 | 触控+压感二合一（本项目模组的后继方案） |
| 艾为（Awinic）CSDN 技术帖 | 中文技术 | 压感触控板框图/压阻桥原理 |
| CSDN《Windows压力触控板协议解析与实现流程》 | 中文技术 | 描述符 → 波形 → **调试验证清单**（含"用测试工具发 Manual Trigger"） |
| `wayland.freedesktop.org/libinput` 触控板文档 | 上游 | `INPUT_PROP_PRESSUREPAD` 判定条件；`libinput measure touchpad-pressure` 工具 |

### 4.3 硬件工具链（**暂时不需要，仅备案**）

| 工具 | 用途 | 何时才需要 |
|---|---|---|
| `CH341A` + `SOIC8/SOIC16` 夹 + `flashrom` | 直接读/写 EC 或 BIOS 的 SPI 芯片 | **只有在 EC 固件无法从更新包里提取时** |
| `WESCI` / `ITP 2.0` | ITE EC 编程 | 同上（维修向） |
| JTAG / SWD 调试器 | 读 EC **内部 RAM** | 只在"要看运行时变量且软件通道全废"时才需要 |
| saleae / DSLogic 逻辑分析仪 | 抓 eSPI/USB | 已知对本目标无效（`lid-probe` 第十二节） |

### 4.4 可以点名联系的人（本轮最有价值的"人事情报"）

| 人 | 关联 | 为什么值得问 |
|---|---|---|
| **Felix Yan**（`felixonmars`） | **拥有同型号 ThinkBook 14 G6+ IMH (Intel)** | 直接在 EC 补丁上做过真机验证；问他"合盖时 EC 侧能看到什么" |
| **Rong Zhang**（`i@rong.moe`，AOSC） | ① ThinkBook 2024 EC 轮询 bug 的修复者 ② **Linux 上游压感板触觉工作** | **一个人同时踩着你两个项目的技术面**。这是最高优先级联系人 |
| **ty2** | ① `goodix-gt7868q-linux-driver`（你同款芯片）② `ideapad-laptop-tb2024g6plus`（你同型号 EC） | **同一个人，你两个项目的交集**；明显拥有同代 ThinkBook |
| **ferstar** | `ideapad-laptop-tb` + `lenovo-wmi-hotkey-utilities` + 中文博客 | 机型覆盖含 14 G6+ AHP；中文沟通 |
| berrylium0078 / Mingcong Bai / Eric Long / Minh Le / Sicheng Zhu / Jianfei Zhang | 都是 ThinkBook 2024 EC bug 的报告/测试者 | 一群手上就有这类机器的人 |

> 原则不变：**公开发帖/发信使用你自己的账号，需要我起草就说。**

---

## 五、如果只做三件事

| 顺序 | 做什么 | 为什么是它 | 成本 |
|---|---|---|---|
| **1** | **磁铁实验**（2.4） | 10 秒把一个开放问题变成已结案问题；结果直接决定 2.1/2.2 要不要做 | ¥0 |
| **2** | **ALS + 人体距离曲线记录**（2.3） | 不管有没有角度，都能让"跟手动画"**今天**就有连续输入；也是唯一能立刻产出可见成果的 | ¥0 |
| **3** | **DSDT 反编译**（2.1 第 1 步） | 纯离线；一次性拿到 EC RAM 的完整字段表；后续无论走 EC 命令扫描还是 EC 固件逆向，都要它 | ¥0 |

触控板侧只做一件事：**把 3.2 的三个静态问题查掉**（离线、零风险、可能推翻一条结论）。其余（Linux 实验、扬声器实测、专利检索）按兴趣排。

---

## 六、红线更新

**原红线（触控板，全部保留）**：不轮询 `Col04`、不枚举厂商命令空间、只发单发已知安全命令、异常先杀后台任务、触控板是唯一指点设备需备退路、恢复靠"关机+拔电+长按电源 30 秒"、刷机三连 `00 10 / 00 11 / 0E 12` 绝对不碰。

**新增（EC 侧）**：

| # | 红线 | 依据 |
|---|---|---|
| 1 | **禁止对 `VPCR`/`VPCW` 或其他 EC 接口做高频轮询**；命令与命令之间留足间隔 | 主线内核记录：2024+ ThinkBook 高频轮询 → **EC 状态机崩 → 硬关机** |
| 2 | 单次命令内的轮询间隔按 **150–300 µs**（或更慢），不要"抢速度" | 同上 |
| 3 | **只读不写**。EC 写操作风险与收益完全不成比例 | — |
| 4 | **不要与"挂起/合盖/插拔电源"同时进行** EC 操作 | 这四个本身就是崩溃高发场景 |
| 5 | 磁铁实验用**弱磁、短时、逐点试**，不要贴在扬声器/NVMe/电池位置 | — |
| 6 | EC 固件**只提取、只分析，不刷写**（EC 刷坏比触控板难救得多） | — |

---

## 七、本轮没做到 / 没验证的（不夸大）

| 项 | 状态 |
|---|---|
| 本机实时探测（注册表 / 提权 / PnP 枚举） | ❌ 被沙箱拦（`reg.exe` 在黑名单、PowerShell 无回显）→ 全部转为"给出脚本、由你在本机跑" |
| Bugzilla 218771 的完整讨论 | ⚠️ 站点有反爬（Anubis），只拿到首帖与搜索引擎摘要 |
| EC RAM 里是否有角度变量 | ⚠️ **未验证** —— 这正是 2.1/2.2 要回答的 |
| 磁铁能否触发合盖 | ⚠️ **未验证**（一笔就能定案） |
| ALS / 距离传感器是否真的跟随合盖动作 | ⚠️ 未验证（假设有物理依据，需实测曲线） |
| 扬声器能否带动掌托/LRA | ⚠️ 未验证（3 个可测假设） |
| TF100A 间接调用路径 | ⚠️ 未跑（本轮按你的要求停手了；会话目录里留了 `indirect_gap_audit.py`，已修好 capstone 线性扫描问题，**未运行**） |
| 钛方专利全文 | ⚠️ 未检索（只确认了专利量与布局领域） |

---

*一句话总结：**角度项目的"死路"是判据错位造成的假死路 —— EC 有一条软件可调的命令接口，这台机器的同代 EC 正被主线内核和一群同型号用户持续研究；触控板项目的"死路"是真死路，但仍有 3 处没查完的静态角落和 1 条纯软件的物理反馈通道。***
