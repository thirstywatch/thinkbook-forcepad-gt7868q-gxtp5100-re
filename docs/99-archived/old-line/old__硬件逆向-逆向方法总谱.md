# 逆向方法总谱 · 不碰硬件的可行路径

- 版本：v2（2026-09-27）—— 按喆的口径重写：**只谈"怎么把东西逆向出来"，不谈"换个东西实现"**
- 本机：Lenovo ThinkBook 14 G6+ IMH（**21LD**）· Core Ultra 7 155H · 主板 LNVNB161216 · BIOS NJCN67WW
- 覆盖：**① 开盖角度传感器逆向**（`lid-probe`）· **② 触控板震动逆向**（`touchpad-lab`）
- 前提：**不拆机、不焊接、不用逻辑分析仪/JTAG** —— 全部方法按此前提筛选
- v1 的"ALS 替代角度""扬声器替代震动"已剔除（那是换实现，不是逆向）；磁铁实验、专利、维修资料保留 —— 它们是**识别/取证**手段

---

## 一、方法论地图：六类、32 种

> 状态标记：✅ 已做 · 🟡 部分做过 · ⭕ **全新、未做过**

### 第 I 类 · 资料侧（完全不接触设备）

| # | 方法 | 做法 | 能拿到什么 | 状态 |
|---|---|---|---|---|
| 1 | **OEM 更新包取证** | innoextract / 7z / UniExtract2 解 Lenovo/Dell/HP 的 BIOS·EC·触控板更新包 → ifdtool 切 flash region → UEFITool 定位 | **EC 固件**、GT7868Q 容器、刷写器程序 | 🟡 触控板已解；**EC 固件从未提取** |
| 2 | **原厂开源驱动** | 读汇顶自己的 `goodix/gtx8_driver_linux`（含 `goodix_ts_tools.c` 调试模块）、`fwupd/plugins/goodix-tp`、上溯的 `goodix_gtx8.c` | **官方命令/寄存器定义**、容器格式、调试路径 | ⭕ **未读** |
| 3 | **上游考古** | LKML / linux-input / bugzilla / GitHub issue 全文检索目标芯片与机型 | 别人已经问过的答案、踩过的坑、未公开的行为描述 | 🟡 触控板做过；**EC 侧本轮机型未做** |
| 4 | **★ 维修资料：原理图 + Boardview + HMM + FRU** | 按主板板号搜 `Schematic` / `Boardview`（OpenBoardView 打开），查服务手册与备件目录 | **主板连接关系、EC 引脚去向、片间连线**；备件号可反证器件是否存在 | ⭕ **全新**（见 3.6 / 4.6） |
| 5 | **专利与厂商资料** | 国家知识产权局公开检索（申请人=北京钛方科技，191 件）；汇顶/微软专利 | 电路框图、接口定义、判定流程、阈值 | ⭕ 未做 |
| 6 | **★ 同类机器实测数据库** | `linux-hardware.org` 按机型查 probe（DMI、设备树、驱动、BIOS/EC 版本） | **同型号别人机器上的真实配置**，可交叉验证假设 | ⭕ 全新 |
| 7 | 认证/白皮书/招聘 JD | FCC、厂商白皮书、招聘技能栈 | 弱情报，仅备用 | ⭕ |

### 第 II 类 · 固件侧（拿到镜像之后）

| # | 方法 | 做法 | 能拿到什么 | 状态 |
|---|---|---|---|---|
| 8 | 容器脱壳与分区 | 熵分析、结构对齐、官方解析器比对 | 载荷边界、子镜像落位地址 | ✅ 触控板做得很完整 |
| 9 | 架构识别 → 向量表 → ISR | 向量表扫描 + 缺失检测 | 中断服务程序入口 → 反查外设驱动 | ✅ |
| 10 | 反汇编 + 调用图 | Ghidra / capstone / radare2 | 函数边界、可达性 | ✅ |
| 11 | **★ 间接调用图补全** | 扫 `blx rN`、`ldr rX,[rY,#imm]` + `blx`、写回调指针的代码点 | **BL 图看不见的调用路径** | ⭕ **未做**（见 5.2） |
| 12 | **★ 版本差分（diff）** | 同机型相邻两版 EC/触控板固件逐函数 diff | **改动定位**：更新说明里提过的功能改动，直接落在函数级 | ⭕ 未做 |
| 13 | **★ 同族/跨机型横向取证** | LVFS 与各 OEM 搜集同芯片不同机型固件包，对比 | 补齐缺失代码段（如 TF100A 的 USART1 ISR 尾段）；发现未被禁用的命令 | 🟡 手里已有 Dell Hellcat 刷写器 + LVFS GT7936L |
| 14 | 表驱动分发器识别 | 跳转表/switch 表扫描 | 命令空间枚举 | ✅（0x80/0xA0/0xA1 + 39 条子命令） |
| 15 | 字符串/日志/错误码挖掘 | 全量字符串 + printf 表 | 版本、编译时间、内部命名 | ✅ |

### 第 III 类 · 协议侧

| # | 方法 | 做法 | 能拿到什么 | 状态 |
|---|---|---|---|---|
| 16 | 边界求解 + 单发决定性实验 | 静态解出合法空间 → 真机发一帧看应答 | 可达性判定 | ✅ A0/A1 已做 |
| 17 | **★ 未探索的协议族：`0x80` 类** | 项目解出"类只有 3 个：`0x80`（疑数据写入）/`0xA0`/`0xA1`"，但只对 A0/A1 做了边界与语义 | **`0x80` 是空白区**（产线写数据类） | ⭕ |
| 18 | **★ 回复路径重定向假设** | TF100A 的 `0xA2` 帧构造是"写帧头 → 填数据 → **操作 GPIOA bit3**"，是**另一条物理线**，不是 HID 通道 | **"没收到 A2"≠"TF100A 没响应"** —— H1 的判否逻辑需要修正 | ⭕（见 5.1） |
| 19 | 剂量–响应 | 二分找安全边界 | 安全操作区间 | ✅（90 次安全 / 683 次冻结） |
| 20 | 受控对照实验 A/B/C/D | 只改一个变量 | 排除"值在变≠相关" | ✅ 已建立为规范 |

### 第 IV 类 · 动态侧（设备在跑的时候）

| # | 方法 | 做法 | 能拿到什么 | 状态 |
|---|---|---|---|---|
| 21 | **★ 厂商工具插桩 / record & replay** | DLL 注入 / API hook 挂到厂商工具（联想电脑管家、Vantage、Dell 刷写器、Windows 触控板设置 UI）上，记录它发出的**每一条 HID/IOCTL/文件读写** | **厂商自己认可的命令序列** —— 比枚举命令空间安全一个数量级，且可能含测试/马达命令 | ⭕ **性价比最高** |
| 22 | **★ OEM 内核驱动 IOCTL 逆向** | 反汇编 `AcpiVpc.sys`(VPC2004) / `LnvMSRIO.sys`，找 IOCTL 号，从用户态直接 DeviceIoControl | **用户态直达 EC**（Windows 上绕过"没有 ACPI 调用入口"的限制） | ⭕ 社区已证可行（FanControl / `hejunv/Lenovo-IdeaPad-Z500-Fan-Controller` 就这么控风扇） |
| 23 | **★ HID 过滤驱动** | upper filter 看**解析后报文**；**lower filter 看传输层原始交互**；在 `IOCTL_HID_READ_REPORT` 的 completion routine 里取样 | **包括被上层丢弃的报文**；Windows 自己发的 feature 写入 | ⭕ **全新**（见 4.2） |
| 24 | **★ ACPI 命名空间主动调用** | Linux `acpi_call`（`/proc/acpi/call`）直接调 `VPCR`/`VPCW`/`_Qxx`/任意自定义方法 | **EC 命令空间与事件空间的直接入口** | ⭕ **角度项目的钥匙** |
| 25 | **★ ACPI SSDT Override** | Linux 加载自定义 SSDT 覆盖 `_LID` 等方法（可加日志、可改返回） | 运行时观测/干预 ACPI 层行为 | ⭕ |
| 26 | ETW / xperf 扩大覆盖 | ACPI + HIDCLASS + SPB-HIDI2C + Sensors + USBXHCI，多 provider 同时抓 | 调用序列与毫秒级时序 | 🟡 角度项目做过 ACPI；**触控板侧没做** |
| 27 | **★ 裸 I2C 访问** | Linux `/dev/i2c-N` + `i2c-tools`（`i2cdetect`/`i2cdump`/`i2ctransfer`）对 GT7868Q 从地址发裸事务 | **绕开 HID 层**，直接触达芯片 | ⭕（Windows 无对应物） |
| 28 | 设备访问层降级链 | feature report → raw HID → transport → bus，逐层下探 | 每下一层多得一份信息，多一份风险 | 🟡 到 transport 为止 |

### 第 V 类 · 环境侧（换平台/换机器）

| # | 方法 | 做法 | 能拿到什么 | 状态 |
|---|---|---|---|---|
| 29 | **★ 换 OS** | Linux Live USB + 外接鼠标做退路 | 打开 Windows 上被独占/不存在的一整层（见 4.8） | ⭕ |
| 30 | 换实验台 | 同型号料板（触控板模组 ¥100 上下）/ 二手同款机 | 把破坏性试错挪出真机 | 🟡 已列入计划 |
| 31 | 对照机 | 第二台同型号机器，做 A/B 差分 | 区分"普遍行为"与"本机个例" | ⭕ |

### 第 VI 类 · 情报侧（问人）

| # | 对象 | 为什么是他 |
|---|---|---|
| 32 | 见第七章名单 | **Rong Zhang 一人同时踩着你两个项目的技术面**（ThinkBook 2024 EC bug 修复者 + Linux 上游压感板触觉）；**ty2 一人写了同款芯片驱动 + 同型号 EC 模块**；**Felix Yan 手上有你这台机器** |

---

## 二、本轮最重要的结构性发现：EC 通道一直是开着的

角度项目前四轮得出"任何软件手段都拿不到角度"，**这个结论建立在一个判据错误上**：

> 把"EC 通道"等同于"需要 JTAG/SWD" → 于是从未尝试。
> 事实上，**EC 有两条纯软件通道**：① ACPI 方法 `VPCR`/`VPCW`（正是你 ETW 里刷屏的那两个）② 老式的 `0x62/0x66` EC 端口。JTAG/SWD 只是**第三条**（看运行时 RAM），而它本不必是第一选择。

### 2.1 证据一：主线内核已经有现成的代码

`drivers/platform/x86/lenovo/ideapad-laptop.c`：

```c
static int eval_vpcr(acpi_handle h, unsigned long cmd, unsigned long *res)   // 读 EC
static int eval_vpcw(acpi_handle h, unsigned long cmd, unsigned long data)   // 写 EC

static int read_ec_data(acpi_handle h, unsigned long cmd, unsigned long *data)
{
    err = eval_vpcw(h, 1, cmd);            // 发起命令
    while (未超时) {
        usleep_range(150, 300);            // ★ 安全间隔，实测值
        err = eval_vpcr(h, 1, &val);       // 查状态
        if (val == 0) return eval_vpcr(h, 0, data);   // 取数据
    }
}
```

`(cmd, data)` 就是一个 **EC 命令空间**。已知常量覆盖亮度、射频、触摸板使能、摄像头、风扇、键盘背光、**传感器读取**（`VPCCMD_R_SENSOR`）等；**清单之外的命令值从未被穷举**。

### 2.2 证据二：这台机器的 EC bug 有真实事故记录，且报的就是"合盖"

`bugzilla.kernel.org/218771` — 《Lenovo Thinkbook — turning off after **closing lid** or (dis)connecting charger》。修复补丁（Rong Zhang，2025-05）措辞：

> *"Some models (e.g., **ThinkBook since 2024**) have a low tolerance for being polled too frequently. Doing so may break the state machine in the EC, resulting in a **hard shutdown**."*

**Felix Yan 的验证回复原文**：

> *"Tested to work as expected on my **ThinkBook 14 G6+ IMH (Intel model)** … Sleep via power button and **close the lid** … **Both caused unexpected shutdown before** and fixed now."*

### 2.3 证据三：EC 是这个平台的"一等公民"，而且被主线文档化

| 证据 | 内容 |
|---|---|
| DMI 转储（同型号机器） | `Platform Firmware Revision: 2.67` · **`Embedded Controller Firmware Revision: 2.67`** |
| 联想官方发布 | BIOS 与 EC **成对公布**（例：`BIOS Version: QECN29WW, EC Version: QEEC25WW`）→ EC 固件在更新包里 |
| 主线 `hwmon/yogafan` 文档 | 直接列出 **ThinkBook G6 → EC 偏移 `0x06` → DSDT 字段 `\_SB.PCI0.LPC0.EC0.FAN0`**；并写明方法论：**`iasl` 反编译 DSDT → EmbeddedControl OperationRegion → 与 NBFC 配置交叉验证 → 数据宽度分析** |
| 联想官方更新说明 | 出现「优化 **`LENOVO_OTHER_METHOD` Get/Set 风扇速度**」→ 这套 EC 参数 ID 是活的、会随版本变 |

**结论：EC 是本文最值得投的一条线，而且它要的不是硬件技能，是 25 年前就有的 ACPI 知识。**

---

## 三、角度项目：把 **ACPI 命名空间** 当作逆向对象

前四轮把 ACPI 当成"只能读 `_LID` 的 0/1"。实际上 **ACPI 命名空间本身就是一个可枚举、可调用、可反编译的逆向面**。以下 7 条，只有第 1 条的前半段做过。

### 3.1 ★ DSDT / SSDT 全量反编译 → EC RAM 的"地址簿"

| 项 | 内容 |
|---|---|
| 做法 | `iasl -d DSDT.dat` + 全部 SSDT；搜 `OperationRegion (…, EmbeddedControl, …)` 与 `Field (…, ByteAcc, …)` |
| 拿到什么 | **EC RAM 每一个字节的字段名与位宽**（风扇/温度/电池/lid/传感器/未知字段全在一张表里） |
| 为什么是第一步 | 无论后面走"EC 命令扫描"还是"EC 固件逆向"，这张表都是坐标系 |
| 附带产出 | `\_SB.PC00.LPCB.EC0.VPC0.VPCR/VPCW` 的定义、所有 `_Qxx` 的实现、所有厂商自定义方法 |
| 关键点 | **看 Field 表里有没有"角度"语义的字段**（`ANGLE`/`HINGE`/`DEG`/`ROT`/`LIDANG`），或有长度 >1 bit 的 lid 相关字段 |
| 状态 | ⭕ 未做（前四轮只做了 ETW 追踪，没反编译） |

### 3.2 ★ `_Qxx` 方法枚举 —— ACPI 规范内的合法扩展点

| 项 | 内容 |
|---|---|
| 做法 | EC 设备下的 `_Q00`–`_QFF` 是"EC 向主机上报事件"的标准方法名。从 DSDT 里读出**哪些存在**，再逐个用 `acpi_call` 调用观察副作用 |
| 为什么合法 | 这是 ACPI 规范定义的入口，不是"猜"；且**调用只读方法**比写 EC 安全得多 |
| 拿到什么 | **EC 会向主机报哪几类事件** —— 如果存在"角度变化"这类事件，必然有一个 `_Qxx`；同时把 `_Qxx` 与它读写的 EC RAM 字节对应起来（→ **EC RAM 语义地图的最快来源**） |
| 已知锚点 | 你的 trace 里出现过 `EC0._Q04`、`EC0._Q15`（lid）、`EC0._Q3B` —— **已经确认这三个存在**，但**从未枚举全集** |
| 状态 | ⭕ |

### 3.3 ★ `VPCR`/`VPCW` 命令空间扫描

| 项 | 内容 |
|---|---|
| 做法 | Linux：`acpi_call` 直接调 `\_SB.PC00.LPCB.EC0.VPC0.VPCW 1 <cmd>` → 轮询 `VPCR 1` → `VPCR 0` 取值。Windows：反汇编 VPC 驱动拿 IOCTL（见 4.2/22），或 `RWEverything` / NBFC 自带 `ec-probe --dump-registers` |
| 拿到什么 | 每个 `cmd` 对应的值。**若某个 cmd 的返回值随盖子角度连续变化 → 角度就在这里** |
| 与 3.1 的关系 | `_Qxx` 与 Field 表告诉你"哪些 cmd/字节有意义"，扫描负责验证。**先读表、再扫描，不要盲扫** |
| 状态 | ⭕ |

### 3.4 ★ EC 固件提取 → 反汇编 →（关键）**版本差分**

| 步骤 | 做法 | 产出 |
|---|---|---|
| a. 提取 | `NJCN67WW.exe` → innoextract/7z → ifdtool 切 region → UEFITool/字符串特征（EC 版本号 `NJECxxWW` 是天然锚点） | EC 固件镜像 |
| b. 反汇编 | Ghidra。EC 多为 **ITE IT8xxx（8051 内核）**，也可能是 ARM | 代码 |
| c. 定位 | 找 lid 相关的 I2C/GPIO 读取、阈值比较、`_Qxx` 处理 | **"到底有没有角度运算"的最终答案** |
| **d. ★ 版本差分** | 下载**相邻两版 BIOS/EC**（如 NJCN63WW 与 NJCN67WW），逐函数 diff | 更新说明里写过的改动（电源/lid/传感器）**直接定位到函数**，省掉大量盲搜 |

> **这条是本项目唯一能把"有没有角度"从"推测"变成"确证"的路径**，而且全程不碰硬件。
> 参考范例（都不需要硬件）：`hamishcoleman/thinkpad-ec`（EC 固件逆向方法论 + `dump_datazone`）、`leecher1337/thinkpad-E130-ec`（Ghidra 工程 + 命令表 + 内存区文档）、`Saddytech/Galaxy-Book4-Edge-linux`（**Windows 驱动 Ghidra → DSDT → I2C 协议解码**的完整示范）、mjg59《Extending proprietary PC embedded controller firmware》。

### 3.5 磁铁探针：**机理识别**（不是"换实现"）

用一个**弱磁铁**靠近掌托/转轴附近：

| 现象 | 逆向结论 |
|---|---|
| 屏黑 / 触发合盖 | **确定是霍尔开关** → 天生二元 → **"角度"在硬件层就不存在**，用户手册里 "detect the angle" 是营销措辞 → 3.1–3.4 降级为"取值地图"用途 |
| 无反应 | ⚠️ **推不出任何结论**（2026-09-27 修正，原写"可能是转轴角度传感器"是**过度推断**）。至少四种原因：磁铁太弱（冰箱贴通常不够）、**位置不对**、**极性反**（霍尔开关对极性敏感）、传感器在屏幕侧而你在机身侧试 |

> **⚠️ 方法论纠正（实测踩过）**：**"吸得住"找的是磁铁，"触发息屏"找的才是传感器。**
> 霍尔传感器是硅芯片，**不会被磁铁吸**。所以"手感最磁的地方"必然是磁铁（扬声器磁铁、锁扣磁铁、铁质加强片），**与传感器位置无关**。
> ⇒ 找传感器**只能靠"哪里让它触发"**，不能靠"哪里吸得住"。
> ⇒ 正确的扫描姿势：**强钕磁铁** + **两个面都试** + 每点**停 2–3 秒**（EC 有去抖）+ 扫**屏幕顶部摄像头一带**与**触控板周围**（两种镜像布置都要试）。
>
> **更省事的替代**：查该机型的 **HMM（硬件维护手册）**的 LCD 模组爆炸图与拆装视频 —— 里面有独立的 `Sensor board` + `Sensor board cable` 这类 FRU，能直接看出传感器板在哪一侧。

先做这个，能省掉后面一半工作。社区先例：有人用一块磁铁贴笔记本边缘就把屏幕骗关了，并有视频。

### 3.6 ★ Boardview / 原理图：**不拆机看走线**

这是本轮新开的资料侧渠道。维修圈公开分发联想 ThinkBook 各代主板的**原理图 PDF + Boardview CAD**（`OpenBoardView` 打开）：

| 已见的 ThinkBook 资料 | 板号 |
|---|---|
| ThinkBook 15p Gen2 | NM-E021 Rev 1.0 |
| ThinkBook 14p Gen3 | NM-E561 Rev 1.0 |
| ThinkBook 16p Gen3 | NM-E661 Rev 1.0 |
| ThinkBook 14 G2 ARE | LA-K061P |

**用法（针对角度项目）**：
1. 按本机板号找 21LD 的原理图/boardview（本机 DMI 板名是 `LNVNB161216`，需另找 LCFC 板号 `NM-xxxx`，可在维修站/论坛按"ThinkBook 14 G6+ IMH boardview"检索）
2. 找到 EC（IT8xxx）的引脚表 → 看 lid 检测接在哪
   - **只有一根 GPIO** → 霍尔开关 → 天生二元
   - **接在 I2C/SMBus 上、且有独立器件** → 可能是**角度传感器**（→ 那个器件查 datasheet 就知道了）
3. 顺带确认 `EC0` 的全部外设挂载（风扇、温度、电池、传感器），与 3.1 的 Field 表互相印证

**成本 ¥0，信息量可能超过若干轮实机实验。**

### 3.7 Idea5003 的 **Input Report**（从未被读过）

前份报告只读了 4 个 vendor collection 的 **Feature** report（结论：静态）。但 COL01 声明了 `ReportID 0xC1` / `0xC2` 是 **Input** report —— **从未被监听**。

- 做法：阻塞 `ReadFile`（不是 `HidD_GetInputReport`，见第八章红线）监听 COL01/COL02/COL03/COL04，同时改变物理状态
- 注意：用 **`ReadFile` 流式读取**（`IRP_MJ_READ`），**不要用 `HidD_GetInputReport` 轮询**
- 风险：低（Idea5003 不是指点设备，打挂不影响操作）

### 3.8 一张图看清角度项目的路径

```
                     ┌─ 3.5 磁铁探针 ──→ 霍尔开关？→ 项目结案（角度不存在）
   物理机理 ─────────┤
                     └─ 或是角度传感器 ─┐
                                        │
                     ┌──────────────────┴─────────────────┐
   软件取值 ─────────┤ 3.1 DSDT Field 表  → 3.2 _Qxx  → 3.3 VPCR/VPCW 扫描
                     │            │                            │
                     │            └──── 3.7 Idea5003 Input ────┤
                     └────────────────────────────────────────┘
                                        │
                    ┌───────────────────┴────────────────────┐
   固件取证 ────────┤ 3.4 提取 EC 固件 → 反汇编 → 版本 diff    │
                    └────────────────────────────────────────┘
```

---

## 四、触控板项目：把 **厂商工具** 和 **兄弟产品** 当作逆向对象

### 4.1 ★★ 厂商工具插桩 / record & replay（本轮最高性价比）

**核心思路**：不要自己猜命令序列 —— **让厂商工具去发，你只负责记录**。

| 项 | 内容 |
|---|---|
| 为什么 | 项目两次打挂都源于"用户态自己构造厂商帧"。而**厂商工具发的一定是合法序列**，且可能包含我们不知道的调试/马达命令 |
| 对象 | ① 联想电脑管家 / Lenovo Vantage（触控板设置、硬件诊断）② **Windows 自带"设置 → 蓝牙和设备 → 触控板"面板**（它会写 `rid=9` Intensity，路径已知）③ Dell 触控板刷写器（`poc/pkg/` 里已有 `DellTouchpadUpdate_Hellcat_v0.2.2.100.exe`）④ Goodix 若有 PC 侧工具 |
| 做法 | a. **API hook / DLL 注入**：记录 `CreateFile`→`DeviceIoControl`/`WriteFile` 的 (device, report id, bytes)（前份资料里就有同类实证：LenovoECExtractor 用 DLL 注入劫持 `CryptDecrypt`；`WSHardwarePlugin.dll` 被 IDA 反编译出风扇控制代码）<br>b. **HID 层抓取**：用 4.2 的 lower filter 或 USBPcap（若是 USB 路径）记录实际报文<br>c. **回放**：把录到的序列原样重放，验证可复现 |
| 拿到什么 | **完整的、厂商认证的命令序列**，以及"Windows 设置面板到底对 Col02/Col04 做了什么" |
| 价值 | 把一个"不能安全枚举的空间"变成"已知安全序列的集合" —— **这是绕开红线的正路** |
| 状态 | ⭕ 未做 |

### 4.2 ★ HID 过滤驱动：看见"被丢弃的报文"

Windows HID 栈自底向上：`Hidi2c`（传输）→ `HidClass`（解析）→ `Mouclass/Kbdclass` → 应用。过滤驱动可插在两个位置：

| 位置 | 看得见什么 |
|---|---|
| **lower filter**（`Hidi2c` 与 `HidClass` 之间） | **传输层原始交互** —— 最接近总线的观测点 |
| **upper filter**（`HidClass` 之上） | 解析后的 HID 报文（跨所有设备） |

**对本项目的决定性价值**：

> 项目判定 H1（"GT7868Q 会不会把 `A1` 转发给 TF100A"）为**否**，依据是"发 `A1` 后没收到 `0xA2` 应答"。
> **但这个判据本身有漏洞**（见 4.3）。而 **lower filter 能回答的是**：设备**到底有没有往上送过任何报文** —— 包括因为 `InputReportByteLength` 不匹配、或被上层丢弃的那些。

| 实现要点 | 内容 |
|---|---|
| 拦截点 | `IOCTL_HID_READ_REPORT` 的 completion routine（`WdfRequestSetCompletionRoutine`），可以取样、改写、或另路回传用户态 |
| 回传方式 | inverted call（长挂 IOCTL）或共享内存环形缓冲 |
| 风险 | 中（内核驱动、需签名或测试模式）。**但它是"只观察"，不改变设备行为** |
| 替代品 | 先用内置 `xperf`：`xperf -start ... -on "Microsoft-Windows-Input-HIDClass:0x4:0x5"` → `xperf -a hid`，过滤 `HIDCLASS_Read` / `HIDCLASS_GetReport` 看流量与频率 —— **零安装**先摸底 |

### 4.3 ★ 两处需要修正的旧结论

**（1）H1 的判否逻辑站不住**

TF100A 明文固件里的"设备→主机上报模式"是：**写 `0xA2` 帧头 → 填数据 → 操作 `GPIOA` 第 3 位**。

→ `0xA2` 应答**走的是片间物理线（GPIOA）**，**不是 HID 通道**。
→ 要让主机看到 `0xA2`，**必须由 GT7868Q 主动把片间收到的东西转成 Col04 IN 报文**。GT7868Q 转不转，是**它**的事（而它的固件在加密段）。
→ **所以"发 A1 后没收到 A2"不能推出"TF100A 没处理这条命令"，只能推出"GT7868Q 没有把它转出来（或转了但格式不被 hid 层接受）"。**

**新的可查方向**：GT7868Q 的加密段里有没有"片间报文转发"的逻辑 —— 这属于 4.5 的横向取证范畴（找同族固件的可比段），或 4.2 的观测（看有没有异常长度的 INPUT 报文）。

**（2）BL 调用图看不见函数指针**

旧结论「"播放"包装 `0x08008628` 无任何调用者 ⇒ 震动是固件内部行为、主机侧无入口」—— **只对直接调用（`BL`）成立**。同一份固件里存在间接调用器：

```asm
0x08008858:  push {r7, lr}
             ldr  r0, [r0, #0x14]      ; 取结构体 +0x14 处的函数指针
             blx  r0                   ; ← BL 图看不见
```

而 `0x08009750`（TIM3/LRA 配置）**恰恰就是把波形回调写进 `+0x14` 的那段代码**。

**三个待查（纯离线）**：

| # | 问题 | 为什么关键 |
|---|---|---|
| a | `0x08009750` 的**调用者集合** | 若可追到命令分发器 → "命令表无一条碰 TIM3" 需要修正 |
| b | **谁读 `0x20005FEE`？** | `A0-0x0D`（"清/arm"）会写它 = 1。"arm"意味着**有消费者**；找到消费者 = 找到隐藏触发路径 |
| c | `0x2000426C`（44B 触觉上下文）读写者全表 | A1 类命令大量引用它 → 命令空间**确实碰触觉状态** |

### 4.4 ★ 未探索的协议族与未读的一手资料

| 项 | 内容 |
|---|---|
| **`0x80` 类** | 项目已解出"类只有 3 个：`0x80`（疑**数据写入**）/`0xA0`/`0xA1`"，但只对 A0/A1 做了边界与语义。**`0x80` 整类空白**（写类通常在产线工具里使用） |
| **`goodix_ts_tools.c`** | 汇顶**自己的** Linux 驱动 `goodix/gtx8_driver_linux` 里的调试工具模块（`CONFIG_TOUCHSCREEN_GOODIX_GTX8_TOOLS`）。厂商自带的调试路径里出现寄存器读写/自检命令是行业惯例。**从未读过** |
| **`goodix_cfg_bin.c` / `goodix_ts_i2c.c`** | 同一仓库，**官方定义的寄存器/配置空间与帧格式** —— 可与项目逆向出的 `0x20` 内存窗口相互印证 |
| 主线 `goodix_gtx8.c`（2026-02 上游化） | Normandy/Yellowstone 系的 regmap 16-bit 寄存器映射，可确认 GTX8 家族**地址空间是直接可寻址的** |

### 4.5 ★ 同族横向取证：补齐缺失的那段

项目的"未定项"里有一条：**缺失的固件尾段（含 USART1 中断服务程序 = 片间帧格式）**。

正确解法不是去撬芯片，而是**再找几份同族容器**：

| 来源 | 说明 |
|---|---|
| LVFS（Linux Vendor Firmware Service） | 汇顶的固件包公开分发（项目已拿到一份 `GT7936L_16753412`） |
| 各 OEM 官网 / Windows Update Catalog | 同芯片不同机型的触控板更新包 |
| Dell 刷写器（已在手） | `DellTouchpadUpdate_Hellcat_v0.2.2.100.exe` |
| 其他联想机型 | ThinkBook 13x Gen4、14 G7+、16+ IMH 等 |

**两次收益**：① 补齐代码段 → 拿到片间帧格式 ② **对比不同机型固件，找"某机型启用而本机型禁用"的命令**（尤其是触觉相关）。

### 4.6 ★ Boardview：查 **GT7868Q ↔ TF100A 的片间连线**

项目里"片间物理链路（推测 UART，未验证）"一直是未定项。既然模组只是 I2C-HID + 一颗 LRA，**片间大概率就是一路 UART 或 I2C**。

用 3.6 的同一套维修资料，查触控板模组（或主板 FPC 连接器）的走线：

| 查到什么 | 意义 |
|---|---|
| `USART1`/`I2C1` 哪几个 pad 引出来、接到哪 | **确认片间链路性质** → 若能在 4.1/4.2 里定位到对应报文，H1 就有了旁证 |
| 是否有测试点（TEST/TXD/RXD） | 说明模组出厂时留了**产线调试口** → 与 `0x80` 类命令的用途互相印证 |
| `HDP`/`HDN` 焊盘位置 | 与项目已有的背面照片互证（方案③的接线点） |

### 4.7 专利：钛方的官方设计细节

| 项 | 数据 |
|---|---|
| 厂家 | 北京钛方科技（TF100A 的东家），**联想创投投资**，专精特新"小巨人" |
| 专利量 | **191 件**（另一口径"130 余件申请，发明专利近 60%"） |
| 布局领域 | 传感器、弹性波、**压电传感器**、处理模块、检测装置、传感器模组 |
| 官方描述 | 弹性波 → 深度学习 → **力度/位置/模式识别**；明确列出"**触觉反馈**"是能力之一 |
| 搭载机型 | 联想小新 Pro13s，**联想共四款上市笔记本** |

**检索目标**：申请人=北京钛方科技，关键词「压感触控 触觉反馈 / 力度 振动 / Force IC 接口」。
**期望拿到**：Force IC 与主控的**接口定义**、力度→触觉的**判定流程与阈值**（正好回答"震动是谁决定的"）、**是否存在主机侧接口**。
中国专利全文公开，国产厂商说明书常附**电路框图 + 实施例参数**。成本 ¥0。

### 4.8 换 OS：Windows 上做不到的三件逆向动作

| Windows 里的墙 | Linux 侧对应物 | 用途 |
|---|---|---|
| `Col02` 被系统独占（`err=32`），**写不了它的 feature** | `hidraw` 仍可 `HIDIOCSFEATURE`/`HIDIOCGFEATURE` | 系统摸 `rid=11/12/13` 那三个"已被接受但语义未解"的 feature |
| 拿不到完整描述符 | `hidraw` 直读 737 字节 | 逐字段核对 `0x0E/0x01`、`Manual Trigger`、`Intensity` 的真实存在性 |
| HID 之下没有入口 | **`/dev/i2c-N`** 裸 I2C 事务 | 彻底绕开 HID 层 |
| 挂了只能"关机+拔电+长按 30 秒" | 模块可卸载重载、总线可重枚举 | **Live USB + 外接鼠标 = 零负担退路** |

---

## 五、已试过 / 已排除（避免重复劳动）

### 5.1 触控板：确认封死的（不必再试）

| 路线 | 结论 | 一句话依据 |
|---|---|---|
| HID 主机触发 | ❌ | `Col02 OutputReportByteLength = 0`；微软规范要求 **Manual Trigger 的 OUTPUT 报表** |
| 改点击阈值 / 改配置 | ❌ | 写入被丢弃；阈值与波形是 MCU 侧编译期常量 |
| 改固件 | ❌ 单程门 | 容器加密 + 无自助刷回 |
| 解密容器 | ❌ 做不到 | 无密钥、无 IV、无已知明文对 |
| 找其它执行器 | ❌ | 模组内只有一颗 LRA |
| 抄 Surface/EC 方案 | ❌ | Surface 触控板挂在 SSAM（=EC）后面；本机直连 Intel I2C 控制器 |
| 抓 eSPI 拿 EC 数据 | ❌ 架构无效 | `lid-probe` 第十二节已判 |

### 5.2 前份报告里三处需要修正的

| # | 旧表述 | 修正 |
|---|---|---|
| 1 | 「发 `A1` 无 `0xA2` ⇒ GT7868Q 不转发」（H1 = 否） | **判据不成立**：`0xA2` 经 GPIOA bit3 上报（片间线），转不转是 GT7868Q 的事（见 4.3） |
| 2 | 「"播放"函数无调用者 ⇒ 主机侧无入口」 | **只对 BL 成立**；固件存在函数指针调用器 `0x08008858`（见 4.3） |
| 3 | 「要看 EC 内部得用 JTAG/SWD」 | **只对"看运行时 RAM"成立**；EC 的命令接口是软件可调的（见第二章） |
| 4 | **`lid-probe` N1：「BIOS 镜像 `NJCN67WW_FWUpdate.bin`（4.34 MB，Intel FPT）全镜像 0 个 Goodix/GXTP/TB14P/7868、0 个固件 GUID ⇒ 联想 BIOS 里没有 Goodix 代码 ⇒ 从平台固件取容器解析器是死路」** | **物料认错了**。该文件头部 offset 0x10 是 **`$FPT`**（Flash Partition Table），同目录配 `FWUpdLcl64.exe` + `FLASH_me.BAT`（`… -F NJCN67WW_FWUpdate.bin -forcereset -allowsv`）⇒ **它是 Intel CSME（ME）固件，不是 BIOS**。ME 固件里当然没有 Goodix 代码。**→ 这条结论必须在真 BIOS 上重做**（`<HOME>\Downloads\NJCN67WW.exe`，12.79 MB，**从未解包**）。定性：**需复核**，不是"已推翻" |

> **顺带盘出的物料（本条修正的来源）**：`C:\Drivers\Flash\` 下有两份 ME payload（NJCN67WW 4,343,352 B / NJCN61WW 4,339,256 B）；
> Downloads 下另有 **两个 Dell 托管的汇顶触控板固件更新工具**（`9FP2Y` 0.2.1.3 / `XTDR1` 0.2.2.100）——
> **4.1 的"厂商工具插桩"对象已经在手，不用再找**。

### 5.3 实操踩坑记录（工具层）

| 坑 | 说明 |
|---|---|
| **capstone 遇到首个无法解码的字节会静默停止** | 我这次动手时 56 KB 镜像只解出 **28 条**指令。必须做**线性扫描重启**（解码中断后偏移 +2 再续）或 `skipdata`。项目里那份"字节级 BL 扫描"是稳的，但任何基于 `md.disasm(整个镜像)` 的分析都要先验这个 |
| `HidD_GetInputReport` 连续调用 → 设备无响应 | **微软官方文档明说**（见第八章红线） |

---

## 六、情报源清单

### 6.1 EC / 嵌入式控制器

| 名称 | 类型 | 一句话 |
|---|---|---|
| `linux/drivers/platform/x86/lenovo/ideapad-laptop.c` | 主线代码 | **`VPCR`/`VPCW` 通用 EC 读写原语** + ThinkBook 2024 轮询安全间隔 |
| Bug **218771** | 缺陷报告 | 「turning off after **closing lid** or (dis)connecting charger」，含 AMD 版 21LF 复现矩阵 |
| `ty2/ideapad-laptop-tb2024g6plus` | 仓库 | 专为 **ThinkBook 2024 G6+**："solves problem with laptop turning off after closing the lid" |
| `ferstar/ideapad-laptop-tb`（+ 博客 issue #85） | 仓库 | DKMS 版；兼容 16+ IMH / **14 G6+ AHP** / 16 G6+ AHP |
| `ferstar/lenovo-wmi-hotkey-utilities` | 仓库（已上游 6.15+） | 联想 WMI 灯控；列 6 个 ThinkBook 机型 |
| `Documentation/hwmon/yogafan.rst` | 主线文档 | **DSDT→EC OperationRegion 偏移方法论**；**ThinkBook G6@0x06 `FAN0`** |
| `hamishcoleman/thinkpad-ec` | 仓库 | EC 固件逆向方法论 + `dump_datazone`（radare2 工程、内存 config、符号表） |
| `leecher1337/thinkpad-E130-ec` + `IT8518E-ec-sys` | 仓库 | ITE 8051 EC：Ghidra 工程、命令表、内存区、读写模块 |
| `marcoferr99/msi-ec` | 仓库 | EC 驱动 + `ec_dump` 用法 + 固件版本命名解码 |
| `Saddytech/Galaxy-Book4-Edge-linux` | 仓库 | **"不碰硬件"的完整路线**：Windows 驱动 Ghidra → DSDT → I2C 协议 → 自写驱动 |
| mjg59《Extending proprietary PC embedded controller firmware》 | 博客 | EC 固件可打补丁的完整案例 |
| `hirschmann/nbfc` + `nbfc-linux` | 工具 | 200+ 机型 EC 寄存器 XML；自带 **`ec-probe.exe`** |
| `hejunv/Lenovo-IdeaPad-Z500-Fan-Controller` · `jiarandiana0307/Lenovo-Fan-Control` | 仓库 | **通过联想 VPC 驱动用户态直达 EC** 的实证（含中文详解） |
| `Bumblebee-Project/acpi_call` | 工具 | `/proc/acpi/call` **调用任意 ACPI 方法** |
| Linux `ec_sys` 模块 | 主线模块 | `/sys/kernel/debug/ec/ec0/io` 直读 EC RAM |
| `thinkwiki.org/wiki/Embedded_Controller_Firmware` | 百科 | ThinkPad EC 世代与"BIOS 版本 → EC 版本"命名 |
| CSDN《IT8519 EC固件逆向实战》《笔记本EC调试方法全解析》 | 中文教程 | 8051 反汇编、`iasl` 反编译 DSDT、`ec_sys` 实操 |
| 联想支持页更新说明 | 官方 | BIOS/EC 版本成对；「优化 `LENOVO_OTHER_METHOD` Get/Set 风扇速度」 |

### 6.2 触控板 / 触觉

| 名称 | 类型 | 一句话 |
|---|---|---|
| `goodix/gtx8_driver_linux` | **原厂开源** | 含 **`goodix_ts_tools.c` 调试模块**、`goodix_cfg_bin.c`、`goodix_ts_i2c.c` |
| `fwupd/plugins/goodix-tp` | 上游 | 汇顶员工署名；`com.goodix.goodixtp` |
| `ty2/goodix-gt7868q-linux-driver` | 仓库 | 同款芯片；`rdesc[607] 0x15→0x25`；已进内核 6.11+ |
| LKML《HID: Implement haptic touchpad support》(v3) | 上游 RFC | **host-controlled 模式**的完整设计；"设备必须支持 manual triggering" |
| 微软《Input Device Haptics Implementation Guide》/《精确式触摸板集合》/《Precision touchpad tuning》 | 规范 | `SimpleHapticsController`(0x0E/0x01)、波形表、Manual Trigger OUTPUT、`FeedbackIntensity` |
| 微软《InputHapticsManager》(2026-03 API) | 规范/API | App 侧触觉触发；**`IsSupported()` 一行定生死** |
| `barryblueice/ESP32-Haptic-Precision-TouchPad` | 项目 | **逆向 Surface 触觉固件提取波形**（从 OEM 驱动包里取证的标准示范） |
| `dawidmpunkt/rumble-for-steamdeck` + `RumbleDeck` | 项目 | 嗅探振动信号 + 缓冲驱动 |
| Tom's Hardware：Steam Controller 触觉变扬声器 | 报道 | HIDAPI 低层 feature 命令直驱马达 |
| 钛方科技（191 件专利） | 厂商+专利 | TF100A 东家 |
| `wayland.freedesktop.org/libinput` | 上游 | `INPUT_PROP_PRESSUREPAD` 判定条件；`libinput measure touchpad-pressure` |
| CSDN《Windows压力触控板协议解析与实现流程》 | 中文技术 | 描述符 → 波形 → 调试验证清单 |

### 6.3 维修资料侧（新开）

| 项 | 说明 |
|---|---|
| Boardview / Schematic 站 | `bios-fix.com`、`indiafix.in`、`eletronicabr.com`、`thetechstall.com` 等按板号分发 `NM-xxxx` / `LA-xxxx` 的原理图 PDF 与 `.tvw/.bv/.brd` CAD |
| 查看器 | **OpenBoardView**（免费、跨平台）、All-in-One BoardViewer、FlexBV |
| 检索姿势 | `"<板号>" + schematic / boardview`；或 `"ThinkBook 14 G6+" boardview` |

### 6.4 可点名的人

| 人 | 关联 | 为什么值得问 |
|---|---|---|
| **Rong Zhang**（`i@rong.moe`） | ① ThinkBook 2024 EC 轮询 bug 修复者 ② **Linux 上游压感板触觉工作** | **一人同时踩着你两个项目的技术面** —— 最高优先级 |
| **ty2** | ① `goodix-gt7868q-linux-driver`（同款芯片）② `ideapad-laptop-tb2024g6plus`（同型号 EC） | 你两个项目的交集，且明显拥有同代 ThinkBook |
| **Felix Yan**（`felixonmars`） | **拥有同型号 ThinkBook 14 G6+ IMH (Intel)** | 在 EC 补丁上做过真机验证 |
| **ferstar** | `ideapad-laptop-tb` + `lenovo-wmi-hotkey-utilities` + 中文博客 | 中文沟通无障碍 |
| berrylium0078 · Mingcong Bai · Eric Long · Minh Le · Sicheng Zhu · Jianfei Zhang | 同为 ThinkBook 2024 EC bug 报告/测试者 | 一群人手上就有这类机器 |

> 原则：**公开发帖/发信使用你自己的账号**；需要我起草就说。

---

## 七、如果只做五件事（按性价比排序）

| 顺序 | 做什么 | 属于哪一类 | 为什么是它 | 成本 | 需要技能 |
|---|---|---|---|---|---|
| **1** | **磁铁探针**（3.5） | III 机理识别 | 10 秒把开放问题变已结案；结果决定后面要不要做 | ¥0 | 无 |
| **2** | **DSDT/SSDT 反编译取 Field 表**（3.1）+ **`_Qxx` 枚举**（3.2） | IV 动态侧 | 纯离线；拿到 EC RAM 完整地址簿与事件清单 | ¥0 | `iasl`（一条命令） |
| **3** | **找 21LD 的 boardview 看 lid 走线**（3.6） | I 资料侧 | 判霍尔 vs 角度传感器，与磁铁实验互相印证 | ¥0 | 会看原理图（可现学） |
| **4** | **厂商工具插桩 record & replay**（4.1） | IV 动态侧 | 把"不可安全枚举"变成"已知安全序列"；触控板侧最高性价比 | ¥0 | API hook 基础 |
| **5** | **静态补全三个盲区**（4.3 a/b/c） | II 固件侧 | 纯离线、零风险，可能推翻一条既有结论 | ¥0 | capstone/Ghidra 基础 |

**次优先**：EC 固件提取 + 版本 diff（3.4，工作量最大但最确定）· boardview 查片间连线（4.6）· 读 `goodix_ts_tools.c`（4.4）· 钛方专利（4.7）

**如果只做一件**：**第 1 件**。它最便宜，而且无论结果朝哪个方向，都会立刻把路线收敛。

---

## 八、红线

**原有（触控板，全部保留）**：不轮询 `Col04`；不枚举厂商命令空间；只发单发已知安全命令；异常先杀后台任务；触控板是唯一指点设备需备退路；恢复靠"关机+拔电+长按电源 30 秒"；刷机三连 `00 10 / 00 11 / 0E 12` 绝对不碰。

**新增：**

| # | 红线 | 依据 |
|---|---|---|
| 1 | **禁止用 `HidD_GetInputReport` / `IOCTL_HID_GET_INPUT_REPORT` 连续取报文**；要持续取就用 **`ReadFile`/`IRP_MJ_READ`** | **微软官方文档**：*"If an application attempts to use HidD_GetInputReport to continuously obtain input reports, the reports can be lost. In addition, **some devices don't support HidD_GetInputReport and become unresponsive** if this routine is used."* ← **这正是触控板两次打挂的官方机理** |
| 2 | **禁止对 `VPCR`/`VPCW` 或其他 EC 接口高频轮询**；命令之间留足间隔，单命令内轮询按 **150–300 µs** 或更慢 | 主线内核记录：2024+ ThinkBook 高频轮询 → **EC 状态机崩 → 硬关机** |
| 3 | EC **只读不写** | 风险收益不成比例 |
| 4 | 不要与"挂起/合盖/插拔电源"同时做 EC 操作 | 这四个本身就是崩溃高发场景 |
| 5 | 磁铁实验用**弱磁、短时、逐点试**，避开扬声器/NVMe/电池 | — |
| 6 | EC 固件**只提取、只分析，不刷写**；Boardview/原理图**只看、不动主板** | — |
| 7 | 内核驱动（过滤器/IOCTL 客户端）**先在离机环境编译与测试**；不装未知来源驱动 | 内核态出错不像用户态那样好收场 |

---

## 九、本轮没做到的（不夸大）

| 项 | 状态 |
|---|---|
| 本机实时探测（注册表/PnP/提权） | ❌ 被沙箱拦（`reg.exe` 黑名单、PowerShell 无回显）→ 全部转为"给脚本、你在本机跑" |
| Bugzilla 218771 完整讨论 | ⚠️ 站点反爬（Anubis），只拿到首帖与摘要 |
| EC 里有没有角度 | ⚠️ 未验证 —— 正是 3.1–3.4 要回答的 |
| 21LD 的 boardview 是否已流出 | ⚠️ 未检索（同代 `NM-xxxx` 资料已确认大量存在） |
| `0x80` 类、`goodix_ts_tools.c`、钛方专利 | ⚠️ 未读/未检 |
| TF100A 三个静态盲区 | ⚠️ 未跑（按你的要求停手；会话目录留了 `indirect_gap_audit.py`，已修好 capstone 线性扫描问题，**未运行**） |

---

*一句话：**角度项目的"死路"是判据错位造成的假死路 —— ACPI 命名空间（`_LID` 之外还有 `_Qxx`/`VPCR`/`VPCW`/Field 表）和 EC 固件这两块从未被当作逆向对象；触控板项目的"死路"是真死路，但仍有 4 处没查完的角落（`0x80` 类、回复路径、间接调用、同族固件），以及一条全新且安全的动态侧路线（插桩厂商工具）。***
