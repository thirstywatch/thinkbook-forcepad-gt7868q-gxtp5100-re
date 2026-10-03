# GXTP5100 触控板触觉改造 · 现状总览（信息汇总）

> ⚠️ **本文已被取代** —— 内容截止 2026-09-30 23:21，未含 ROUND70/71。
> **请改读 `00-★交接文档-GXTP5100.md`**（唯一权威入口，覆盖到 ROUND71）。
> 本文仅作历史存档保留。

> 生成日期：**2026-09-30**
> 目的：把两条在研线、全部已确认事实、已作废结论、当前卡点与可选路径**一次性汇总**，供后续会话直接接手。
> 状态标记：✅ 已确认 · ❌ 已作废 · ⚠️ 未验证/存疑 · 🔒 红线

---

## 〇、30 秒速览

| 项 | 内容 |
|---|---|
| **目标** | ThinkBook 14 G6+ IMH（21LD）上，**纯软件**让压感触控板滑动时产生震动反馈（不改造硬件） |
| **硬件** | 汇顶 **GXTP5100**（`VID_27C6 / PID_01E9`）+ 钛方 **TF100A** 压力前端 + 艾为 **AW86927FCR**（丝印 `CA4F`）LRA 驱动 |
| **总线** | **I²C**（不是 USB）· 挂在 `Intel Serial IO I2C Host Controller - 7E78` |
| **一句话现状** | ① 主机侧通路在 **Windows 上被 `hidi2c.sys` 硬阻断**；② 我们逆向一个月的那个 BIN **根本不是固件，是 UEFI 胶囊**；③ **Linux 侧通路完全开放，尚未验证** |
| **当前最该做的判定** | Linux live USB 验证（§六 · 路线 A），或 SPB 客户端内核驱动（§六 · 路线 B1） |

---

## 一、两条在研线（★ 动手前必须先读它们的文档）

### 线 1 · `touchpad-lab`（触控板震动/触觉）

```
位置: <LAB>\touchpad-lab\
规模: 67 个文件
状态权威: 00-★交接文档（先读这一份）.md
主索引:   00-触控板结论总表.md
```

**核心结论（来自该线）**：

| 判定 | 状态 | 依据 |
|---|---|---|
| 主机侧 HID 通路**全封死** | ✅ | `Col02 out=0`，无 Manual Trigger OUTPUT 报表 |
| Col04 已真机判否 | ✅ | 无第二份容器 |
| 触觉判定与驱动**都在模组内部** | ✅ | 模组含 2 颗主控 + 1 颗专用驱动 IC（`CA4F` = AW86927） |
| 只有 **TF100A 的固件是明文** | ✅ | 其余为加扰 |
| 唯一可行 = **实体接管 `HDP`/`HDN` 焊盘直驱 LRA** | ✅ | 主机侧无路可走时的硬件方案 |
| `tpcfgsid*.cfg` 是**明文逗号分隔 `0xNN` 寄存器表** | ✅ | 内含 **AW86927 的 I²C 从地址 `0x5A`** + 18 个 u16 振动强度包络表 |

### 线 2 · `goodix-tool`（固件逆向/官方工具）

```
位置: <WORKSPACE>
规模: 95 个脚本 + 6 份 MD 报告 + cfg/ 明文样本
本轮新增: ROUND61-67_UEFI_CAPSULE_TRUTH.md
```

---

## 二、硬件事实（已确认 ✅）

| 项 | 值 | 来源 |
|---|---|---|
| 触控板型号 | Goodix **GXTP5100** / GT7868Q | HID 枚举 |
| USB/HID ID | `VID_27C6` `PID_01E9` | `hid.enumerate()` |
| ACPI 设备名 | `GXTP5100`（`ACPI\GXTP5100\1`） | PnP |
| **总线类型** | **I²C**（`bus_type=3`） | hid.enumerate |
| 所在控制器 | `Intel(R) Serial IO I2C Host Controller - **7E78**` | 设备父子链 |
| 控制器 PCI | `VEN_8086&DEV_7E78&SUBSYS_383017AA&REV_20` · `BUS0/DEV1F/FUNC?` · `0&A8` | PnP |
| 控制器驱动 | `oem19.inf`，Intel **30.100.2405.44** | Win32_PnPSignedDriver |
| 平台 | Meteor Lake（MTL-H） | `7E78` 推断 |
| BIOS | `NJCN67WW` | Win32_BIOS |
| 序列号 | `<DEVICE-SERIAL>` | Win32_BIOS |
| 压力前端 | 钛方 TF100A | touchpad-lab |
| LRA 驱动 IC | 艾为 AW86927FCR（丝印 `CA4F`），I²C 从地址 **`0x5A`** | touchpad-lab + cfg 明文 |

### HID 接口划分（4 个）

| 接口 | Usage Page | 用途 | 驱动 |
|---|---|---|---|
| `COL01` | `0x0001` | Mouse | `msmouse.inf` |
| `COL02` | `0x000D` | Touchpad | `input.inf` |
| `COL03` | `0x000D` | Microsoft Input Config | `mtconfig.inf` |
| **`COL04`** | **`0xFF00`** | **Vendor-Defined** ← 官方协议通道 | `input.inf` |

父设备 `ACPI\GXTP5100\1` 由 **`hidi2c.inf`（Microsoft，10.0.26100.8972）** 驱动。

---

## 三、★★★ 本轮最大反转：`TB14P_GT7868Q_...BIN` 是 **UEFI 胶囊**

### 物证链（三重，本机）

```
① C:\Windows\System32\DriverStore\FileRepository\
       goodixtouchpad.inf_amd64_dd57a59bc9759d61\
           TB14P_GT7868Q_14030522_20240202.BIN   161,628 B   Feb 2 2024
           GoodixTouchpad.inf                      1,212 B
           GoodixTouchpad.cat                     11,888 B   (Goodix 签名)

② C:\Windows\Firmware\
           TB14P_GT7868Q_14030522_20240202.BIN   ← 同 inode 硬链接 (link=2)

③ UEFI 设备树:
       OK  Goodix Update UEFI   UEFI\RES_{B6AE105A-BA93-4FC8-AA28-E63903FFEDDE}\0
             DriverProvider = Goodix
             DriverVersion  = 0.0.2.8
             DriverInfPath  = oem87.inf
```

### INF 决定性行

```ini
[Version]
Class=Firmware                                      ; ← 不是 HIDClass
ClassGuid={f2e7dd72-6468-4e36-b6f1-6488f42c1b52}    ; FU 设备类
DriverVer=02/02/2024,0.0.2.8

[Firmware.NTamd64]
%FirmwareDesc% = Firmware_Install,UEFI\RES_{b6ae105a-ba93-4fc8-aa28-e63903ffedde}

[Firmware_AddReg]
HKR,,FirmwareVersion,%REG_DWORD%,0x14030522          ; 文件名里那串
HKR,,FirmwareFilename,,TB14P_GT7868Q_14030522_20240202.BIN

[DestinationDirs]
DefaultDestDir = %DIRID_WINDOWS%,Firmware            ; → C:\Windows\Firmware
```

### 数据流

```
goodixtouchpad.inf (Class=Firmware, Goodix)
   → C:\Windows\Firmware\*.BIN   (胶囊落地)
   → Windows 交给 UEFI ESRT (UEFI\RES_{b6ae105a-…})
   → 重启进入 UEFI，BIOS 读 RES 资源
   → BIOS 通过 I²C 写入 GT7868Q 触控板
```

### 由此得出的四条结论

| # | 结论 |
|---|---|
| 1 | **高熵区（`0x1400`–`0x18FFF`）不是加密载荷，是胶囊载荷。** UEFI 规范允许压缩/原样 |
| 2 | **不存在"我们的密钥"这个问题。「找解密密钥」从头就不成立** |
| 3 | Windows **不解析**它，直接交给 BIOS；**只有 BIOS 需要理解它** |
| 4 | 该 BIN **不能**喂 `gdix_hid_firmware_update`（工具吃的是 HID 固件，非 FU 胶囊） |

### ⚠️ 重要：哪些结论**不**受影响

| 旧结论 | 状态 |
|---|---|
| `tpfw_86272_PNOR_G1_7863.bin` 通过官方校验（长度/校验和/PID/12 子固件全对） | ✅ **仍然成立** |
| 官方容器格式（子固件表 8 B/条，`addr(2B BE)<<8 + type + len(4B BE)`） | ✅ 成立 |
| `#define CFG_FLASH_ADDR 0x19000` 与静态逆向数值一致 | ✅ 成立 |
| ROUND61 校验 15 个候选、只有 `tpfw` 通过 | ✅ 成立（**为什么**更清楚了：两个物种） |
| 「全片 XOR 加扰」被推翻 | ✅ 成立 |
| K 泄漏链作废 | ✅ 成立 |

---

## 四、Windows 侧硬阻断（实测 🔒）

```python
COL04: VID=27C6 PID=01E9 UP=FF00  bus_type=3 (I²C)
open_path()                    → 成功 ✅
GET_FEATURE(0x0e, 65/64/10/8)  → OSError: read error   (全部失败) ❌
SET_FEATURE([0e 20 00 00 05 01 96 F8 00 03])
                               → 返回 -1                ❌
```

### 根因（两层）

**第一层 · 协议层**
I²C-HID 是**寄存器寻址协议**，设备固件只认 ACPI 声明的这几个寄存器：

| 寄存器 | 默认地址 | 用途 |
|---|---|---|
| `wReportDescriptorRegister` | 0x21 | Report Descriptor |
| `wCommandRegister` | 0x22 | SetPower(`08 00`) / RESET(`01 00`) |
| `wDataRegister` | 0x23 | 数据传输 |
| `wInputRegister` | 0x24 | 输入报告 |
| `wOutputRegister` | 0x25 | 输出报告 |

我们发的 `0x0e 0x20 ...` 是 **Goodix 私有封装（`_I2C_DIRECT_RW`）**，超出声明范围 → 被拒。

**第二层 · 驱动层**
`hidi2c.sys` 作为 KMDF HID 迷你端口，**按 ACPI 声明范围严格转发**，超出即拒。

### 驱动栈现状

```
ACPI\GXTP5100\1    → hidi2c.inf    (Microsoft 10.0.26100.8972)  ← 拦截点
HID\GXTP5100&COL01 → msmouse.inf   (Microsoft 10.0.26100.1150)
HID\GXTP5100&COL02 → input.inf     (Microsoft 10.0.26100.9444)
HID\GXTP5100&COL03 → mtconfig.inf  (Microsoft 10.0.26100.1150)
HID\GXTP5100&COL04 → input.inf     (Microsoft 10.0.26100.9444)

运行中: hidi2c  Running  C:\Windows\system32\drivers\hidi2c.sys
IsAdmin: False  ⚠️
```

**注意**：DriverStore 里有 Goodix 自己的包 `goodixtouchpad.inf_amd64_…`，但它**只提供 Firmware 类设备**，不服务 HID 接口。5 个 HID 接口全绑 Microsoft 驱动 —— 这是设计，不是配置错误。

---

## 五、已作废 / 已进入死路的结论（❌ 勿重试）

| # | 结论 | 为什么错 |
|---|---|---|
| 1 | 「固件加密已破」 | **判据错误**。那个 1024 B 表 `K` 本身就是固件内部数据表（`raw` 里 0x400 步长重复 **2645** 处）。`plain[i] = raw[i] ^ K[i%1024]` 在 K 副本处必然输出 0 —— 所有"零串/低熵"都是**自消自演的假象** |
| 2 | 「高熵区是加密主固件，需要密钥」 | 是**胶囊载荷**，无需密钥（§三） |
| 3 | 「抓 USB trace 看官方工具怎么发命令」 | 触控板走 **I²C**（`bus_type=3`），**不经过 USB 总线**，USBPcap/Wireshark 物理上抓不到 |
| 4 | 「下载联想 Zero Touch Driver」 | 那是 **Lenovo Intelligent Sensing**（VL53L3/L7 ToF 存在感应传感器），与触控板无关。**论坛误传** |
| 5 | 「把该 BIN 喂给 `gdixupdate`」 | 工具/容器不匹配（HID 固件 vs UEFI 胶囊） |
| 6 | `K_gt7868q.bin` / `GT7868Q_plain.bin` / `GT7868Q_scramble_key.bin` | 上述判据错误的产物，作废 |
| 7 | `goodix-fw-tool.exe` | 实为 **Dell DUP Framework**（Native x86，`CLR=0`，非 .NET），内嵌 4 个 PE，**零固件格式逻辑**，死路 |
| 8 | 「单个字节写 `0x1800` 是低风险」 | **错**。`0x1800` 是**逻辑偏移**，写入走**页擦除粒度（1 KB）**。且 `0x3200` 命令实际写 **27 字节**不是 1 字节 |

---

## 六、可行路径（重新排序）

### 路线 A · Linux 侧 ★★★★ 最现实

**依据**：`github.com/ty2/goodix-gt7868q-linux-driver`
目标机 **ThinkBook 16+ 2024 IMH**（同代同芯片）。其 quirks 文件已含：

```
MatchVendor=0x27C6
MatchProduct=0x01E9      ← 就是本机触控板
```

**机理**：Linux 的 `i2c-hid` **完整透传** hidraw（任意 `HIDIOCSFEATURE` 可用），而 Windows 的 `hidi2c.sys` 会拦截校验。

**成本**：1–2 小时（live USB，不碰硬盘） · **风险：零**
**产出**：官方工具 `gdixupdate -p` 可读版本；可自由读写参数区

### 路线 B1 · SPB Target 客户端内核驱动 ★★★ 正统做法

**依据**：微软文档明示

> *"The I2C Controller Driver exposes a **Serial Peripheral Bus (SPB) IOCTL interface** to perform read and write operations."*

**机理**：**绕开 `hidi2c.sys`，直接作为 SPB 客户端对触控板发 I²C 读写。**

```
        hidi2c.sys            ← 拦截点（绕过它）
             │
     ┌───────┴───────┐
     │  Resource Hub │       ← 资源中心（改道）
     └───────┬───────┘
             │  ★ 旁路入口
     Intel Serial IO I2C Controller (oem19.inf 30.100.2405.44)
             │
        I²C → GT7868Q
```

**关键 API**：

| API | 作用 |
|---|---|
| `SpbTargetGetConnectionParameters` | 从 ACPI 取目标连接参数（Connection ID） |
| `SpbTargetConnect` / `SpbTargetOpen` | 打开到触控板的 I²C 通道 |
| `SpbRequestCreate` + `SpbRequestWrite` | 发起任意 I²C 传输 ← **核心** |

**先例**：Dell DUP / 联想 Vantage 的固件工具即用此机制。

**成本**：3–5 天（内核驱动 + 签名/测试模式） · **风险：中**（与 hidi2c 争用总线，需错峰）
**前置需要**：① 管理员 dump DSDT 拿 Connection ID ② WDK + VS 环境

### 路线 B3 · 普通 HID 过滤驱动 ❌ 无效

挂在 `hidi2c` **之上**，只能看 HID 层。而我们的私有命令**正是在 HID 层被拒的**，过滤驱动连转发机会都没有。**排除。**

### 路线 B2 · 换绑 COL04 父设备 ⚠️ 高风险

自写 HID miniport 替换 `hidi2c` → 必须**完整实现替代品**，写不完则**触控板彻底失效**。`MouseLikeTouchPad_I2C` 有完整换绑步骤可参考（README 第 5–7 步），但那个驱动只解析标准 HID 报文，**不碰私有寄存器**。
**风险：高**，不推荐首选。

### 路线 C · 硬件直驱 ★★★ 已封死后的唯一硬件方案

实体接管 `HDP`/`HDN` 焊盘直接驱动 LRA。**不依赖固件**。沿用 `touchpad-lab` 完整文档。
**成本**：拆机 · **风险：高**

---

## 七、🔒 红线（不可触碰）

| # | 红线 | 原因 |
|---|---|---|
| 1 | **禁批量轮询 `Col04`** | 会导致设备无响应 |
| 2 | **≤ 2 往返/秒** | 同上 |
| 3 | 🔴 **红线是四条，不是“三连”**：`00 10` / `00 11` / **`0E 12`（★ 真正写 flash）** / **`0E 13`（重启）** 绝不碰（旧文档漏了 `0E 13`） | 官方源码已确认 = ISP 刷写路径，**风险从“未知”升级为“已确认危险”** |
| 4 | 修改 ACPI 表 | 破坏性，需管理员，**只读 dump 可以，写入绝对禁止** |
| 5 | `HidD_GetInputReport` 连续调用 | 会丢报文且**部分设备会变得无响应** → 持续取报文必须用 `ReadFile`/`IRP_MJ_READ` |

---

## 八、关键数据速查

### 官方 HID 协议命令（Goodix `gdix_hid_firmware_update`）

| 命令 | 字节 | 含义 |
|---|---|---|
| `_I2C_DIRECT_RW` | `0x20` | 直接读写（我们需要的） |
| `_I2C_INDIRECT_READ` | `0x21` | 间接读 |
| Write 封装 | `[0E 20 00 00 05 00 addrH addrL lenH lenL]` | 写操作 |
| Read 封装 | `[0E 20 00 00 05 01 addrH addrL lenH lenL]` | 读操作 |
| 取回 | `GetReport(0x0e)` → `[.. .. .. pkgidx datalen data…]` | |

### 参数区布局（ROUND47-59 逆向 + 官方源码印证）

| 偏移 | 长度 | 含义 |
|---|---|---|
| `0x0444` | 1 B | 标定/属性字节 |
| **`0x1800`** | **27 B** | **★ 触觉参数区** |
| `0x2000` | 1092 B | 配置块 A |
| `0x2444` | 1 B | 标定/属性字节 |
| `0x2C00` | 1092 B | 配置块 B |
| `0x3044` | 1 B | 标定/属性字节 |
| **`0x3800`** | **8 B** | **★ 触觉参数区** |

### 官方地址常量

```c
#define CFG_FLASH_ADDR  0x19000    // 与我们静态推的 0x08019000 一致
#define CFG_START_ADDR  0x96F8     // 明文 cfg 写入点，读 3B 得 cfg 版本
#define CMD_ADDR        0x4160
#define VER_ADDR        0x4014     // 读 32B，末 2B 为校验和
#define BL_STATE_ADDR   0x5095     // 等 0xDD
#define FLASH_RESULT_ADDR 0x5096   // 等 0xAA
#define FLASH_BUFFER_ADDR 0xC000
#define RAM_BUFFER_SIZE 4096
```

### 官方 cfg 握手（明文本通路）

```
读 0x96F8 拿旧版本
  → 写 cmd 0x80
  → 等 CMD_ADDR == 0x82
  → 明文写 cfg 到 0x96F8
  → 写 cmd 0x83
  → 等 CMD_ADDR == 0x7F (或 0x7E 00 07)
  → 写 cmd 0x7D 结束
  → 读 0x96F8 复核
```

### `update flag` 枚举

`0x00` NO_NEED_UPDATE · `0x01` NEED_UPDATE_FW · `0x02` NEED_UPDATE_CONFIG · `0x10` NEED_UPDATE_CONFIG_WITH_ISP · `0x80` NEED_UPDATE_HID_SUBSYSTEM

### 明文样本

| 文件 | 大小 | 说明 |
|---|---|---|
| `tpfw_86272_PNOR_G1_7863.bin` | 86,272 B | **唯一通过官方校验的真实固件**（PID `7863`） |
| `tpcfgsid0_Xiaomi7867_20240307.cfg.txt` | 6,509 B | 明文寄存器表（含 **AW86927 从地址 `0x5A`**） |
| `tpcfgsid2_20230407.cfg.txt` | 2,760 B | 同上 |
| `tpcfgsid3_LaiBao7986P_20220701.cfg.txt` | 9,329 B | 同上 |

---

## 九、文件与脚本索引

### 报告（`fw-touchpad\goodix-tool\`）

| 文件 | 内容 |
|---|---|
| `ROUND61-67_UEFI_CAPSULE_TRUTH.md` | ★ **本轮核心**：UEFI 胶囊真相 + Windows 阻断取证 |
| `ROUND60_OFFICIAL_SOURCE_SOLUTION.md` | 官方源码解法（格式/协议/命令） |
| `ROUND47-59_FLASH_OFFSET_SEMANTICS_REPORT.md` | `0x1800`/`0x3800` 语义 + 写风险 |
| `ROUND24_USB_AND_PARTITION_REPORT.md` | USB 与分区 |
| `ROUND23_COMMAND_ENTRY_REPORT.md` | 命令入口 |
| `ROUND22_CALLER_TRACE_REPORT.md` | 调用者追踪 |

### 本轮新增脚本

| 脚本 | 用途 |
|---|---|
| `round61_official_validator.py` | 复刻官方 `GetDataFromFile()` 批量校验 |
| `round62_hid_enum.py` | 枚举 HID，定位 COL04 |
| `round64_readback.py` | 官方协议只读回读（Windows 下被阻断） |
| `round65_diag.py` | Feature-Report 通路诊断 |
| `round66_driverstack.py` | 驱动栈取证 |
| `round67_uefi_fu.py` | UEFI FU 设备状态 |
| `round68_acpi_probe.py` | ACPI + I²C 控制器取证 |

### 环境

```
隔离 venv: <HOME>\.workbuddy\binaries\python\envs\default
已装:      hidapi 0.15.0
capstone:  <HOME>\miniconda3\python.exe (5.0.7)
官方源码:  <HOME>\AppData\Local\Temp\gdix_fw
```

---

## 十、待办与下一步

| 优先级 | 动作 | 前置 | 成本 |
|---|---|---|---|
| ★★★★★ | **决策：Linux live USB（路线 A）还是 SPB 驱动（路线 B1）** | 无 | — |
| ★★★★☆ | 管理员权限 dump DSDT，拿 `GXTP5100` 的 **Connection ID** | 管理员 + 只读脚本 | 低 |
| ★★★★☆ | Linux 下 `gdixupdate -p` 读固件版本，与本机胶囊版本比对 | 路线 A | 低 |
| ★★★☆☆ | Linux 下回读 `0x1800`(27B) / `0x3800`(8B) | 路线 A | 低 |
| ★★★☆☆ | 确认是否有 **WDK + Visual Studio** 环境 | 询问 | 低 |
| ★★☆☆☆ | 评估路线 C 拆机可行性 | 无 | 高 |

### 阻塞项

- ⚠️ **无管理员权限**（`IsAdmin: False`）→ DSDT dump、驱动安装均受阻
- ⚠️ 路线 B1 需要 **WDK 环境**（未确认是否存在）

---

## 十一、安全记录（本轮）

- ✅ 全程**未发任何写命令**
- ✅ **未触碰** `00 10` / `00 11` / `0E 12`
- ✅ `GET_FEATURE` 尝试为**纯只读**，被 Windows 拒绝，**无副作用**
- ✅ **未修改**任何驱动绑定、INF、注册表、ACPI
- ✅ 唯一"写"动作 = pip 安装 hidapi 到**隔离 venv**

---

## 附：一句话给未来的自己

> **别再找密钥了 —— 那个 BIN 是 UEFI 胶囊，不是加密固件。**
> **别在 Windows 上硬碰 `hidi2c.sys` —— 要么走 Linux（2 小时），要么写 SPB 客户端驱动（3-5 天）。**
> **动手前先读 `touchpad-lab/00-★交接文档（先读这一份）.md`。**
