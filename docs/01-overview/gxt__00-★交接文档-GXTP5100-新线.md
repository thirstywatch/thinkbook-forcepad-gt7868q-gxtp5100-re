> # ⚠️⚠️ 读本文前必看：本文有三处结论**已被推翻**
>
> 本文是 **goodix-tool（新线）** 的交接文档。它的**绝大部分事实仍然有效**（硬件表、SPB 机制、驱动产物、文件索引），
> 但**核心推进方向（并列 SPB 客户端）已被证伪**。全文以此为准：
>
> | # | 本文的说法 | 现状 | 依据 |
> |---|---|---|---|
> | **1** ★★★ | §二/§二.2「`hidi2c.sys` 只是这条总线的**一个客户端**，不是独占者」⇒ 可以**并列**再挂一个 SPB 客户端 | ❌ **同一个外设的连接只能一家持有**。微软官方原文：*"Only one driver can hold an open logical connection to an SPB-connected peripheral device at a time."* ⇒ **并列客户端这条路不通** | 全书 §3.2.5；`2026-10-01-SPB客户端驱动架构判定与蓝莓对比.md` |
> | **2** ★★★ | §七 决策 3「Linux 的 `i2c-hid` **完整透传** hidraw」 | ❌ **不成立**。`ty2/goodix-gt7868q-linux-driver` **全仓库只有 1,663 字节**，内容是 `hid-multitouch` 的 report descriptor 修补（`rdesc[607]: 0x15 → 0x25`），**不碰寄存器、不做总线透传**；且本项目实测 **Linux 下触控板根本不工作**（指针不动） | 全书 §3.3.1b |
> | **3** ★★ | §十 红线「刷机**三连** `00 10`/`00 11`/`0E 12`」 | ⚠️ **是四条**，且 `0E 12` = **真正写 flash**、`0E 13` = 重启，两者不同 | 官方源码 `ROUND60` §4.1 |
>
> ## ★ 另外三处需要修正的表述
>
> | # | 本文的说法 | 应改为 |
> |---|---|---|
> | 4 | §四「**AW86927 地址 `0x5A`**（来自 cfg 明文）」 | ⚠️ **推理方式已撤回**（配对率/字节语义/频次三重检验不成立）。`0x5A` 这个值本身在业界一手资料里是对的，但**不能引用 cfg 作为依据**；且本项目实测 **PCH SMBus 上 `0x5A`/`0x5B` 均无应答** |
> | 5 | §一「`tpcfgsid0.cfg` 里有 **18 个 u16 振动强度包络表**」 | ⚠️ **降级为"待定系数表"** —— 值域 93–111（±10%）过窄、末两项 29/29 断崖，更像**多通道增益/校准系数**。且 `tpcfgsid*.cfg` 是**带元信息头的人可读导出格式**（首字节是 `PCB`/`LaiBao` 标签），**不是可直接下发的 cfg 载荷** |
> | 6 | §七 决策 2「要不要先问 UMP45」 | ❌ 该项**已关闭**：UMP45 的"正确"后来**被项目方撤回**，且其方向与本机**不同代**，不适用 |
>
> ## ★ 仍然完全有效、值得先读的部分
>
> - §三 **Sunia `TcnPeripheral` 取证** —— 这是本机**唯一有价值的 SPB 客户端证据**
>   （但它证明的是"**第三方可以拥有一个 ACPI 节点的函数驱动**"，**不证明**"可以在别人已占的连接上再开一条"）
> - §四 **硬件与总线事实表**（除 `0x5A` 的依据外全部有效）
> - §五 **SPB 两种东西别用错**（控制器驱动 vs 客户端驱动）+ **应用层不能直接发 SPB IOCTL**
> - §五.3 **上层 HID 过滤器是逻辑死路**
> - §六 **驱动产物清单**与安全设计
> - §八 **已知不确定点**（第 2 项「`\Device\0000008a` 每次枚举变」已确认为真问题）
> - §九 **文件索引**
>
> ---
>
> ## 🔒 红线（**已更新为四条**）
>
> ```
> 00 10  switch to patch   ← 绝不碰
> 00 11  start update      ← 绝不碰
> 0E 12  load flash        ← ★ 真正写 flash，绝不碰
> 0E 13  restart           ← 绝不碰
> ```
>
> 另：禁批量轮询 `Col04` · 单次事务 ≤ 32 B 间隔 ≥ 500 ms · 未获明确同意不动 `bcdedit` ·
> 不删 `.workbuddy` / `touchpad-lab` · 本驱动保持只读
>
> ---
# 00-★交接文档（先读这一份）· GXTP5100 触觉改造

> **最后更新：2026-10-01 00:10**
> **覆盖：ROUND61 ~ ROUND71 全部成果**
> 这份文档是**唯一权威入口**。读完它你应该能完全接手。
> 历史细节见同目录各 `ROUND*_*.md`，但**以本文件为准**。

---

## 〇、30 秒速览

| 项 | 内容 |
|---|---|
| **目标** | ThinkBook 14 G6+ IMH（21LD）上，**纯软件**让触控板产生震动反馈。**不拆机、不焊接、不用外接马达** |
| **硬件** | 汇顶 GXTP5100 / GT7868Q + 钛方 TF100A（压力）+ **艾为 AW86927FCR（震动驱动）** —— 后者**机器里本来就有** |
| **总线** | **I²C**（`bus_type=3`），挂 `Intel Serial IO I2C Host Controller - 7E78` |
| **一句话现状** | 已经认识到 Windows 不是铁板一块 —— I²C 控制器允许**并列客户端**，我们用官方 SPB 机制绕开 `hidi2c`。**驱动已编译成功**（`GdixSpbProbe.sys`），**尚未加载** |
| **当前卡点** | 加载需要 `bcdedit /set testsigning on`（改 BCD）→ **等用户拍板** |
| **建议并行** | 先把问题发给群里 UMP45，他有同方向经验，可能省下摸索时间 |

---

## 一、我们要做什么（先校正认知）

**不是"加装震动"，是"解锁本来就有的震动"。**

```
第一层（硬件，已有，不动）：触控 IC → AW86927 → LRA 马达
第二层（主机侧，★堵点在这）：Windows 通过 hidi2c.sys 只让读 HID 报表
第三层（应用层）：你的手滑动时触发
```

`tpcfgsid0.cfg`（官方**明文**配置）里有 **18 个 u16 振动强度包络表**。
> **厂商不会为不存在的硬件写 18 组振动波形。**
> ⇒ 硬件极大概率存在且已连接 ⇒ **纯软件路线是正确的，外接马达反而是降级方案。**

---

## 二、★ 最重要的认知：我们攻破了什么

### 2.1 之前以为的死局

```
用户态 → hidapi → hidi2c.sys → I²C
              ↑ 被拒：GET_FEATURE → OSError: read error
```

当时的结论是"Windows 上没有旁路"。**这个结论错了** —— 因为它默认"只有一条路"。

### 2.2 实际的路（两条并列）

```
                    ┌─────────────────────────────────┐
                    │  Intel Serial IO I2C 7E78       │
                    └───────────────┬─────────────────┘
                                    │
              ┌─────────────────────┴─────────────────────┐
              │                                           │
     ┌────────▼─────────┐                     ┌───────────▼──────────┐
     │  路径 A：HID 栈   │                     │  路径 B：SPB 客户端   │
     │  hidi2c.sys      │  ← 堵死              │  （我们写的）         │  ← 通
     │  用户态可触达     │                      │  内核态，公用一条总线 │
     └──────────────────┘                     └──────────────────────┘
```

**`hidi2c.sys` 只是这条总线的"一个客户端"，不是独占者。**

### 2.3 攻破的三件事

| # | 攻破内容 | 具体值 | 为什么必要 |
|---|---|---|---|
| **1** | SPB Connection ID | `{F0E20F09-D97A-49A9-8046-BB6E22E6BB2E}` | 定位目标连接的钥匙 |
| **2** | **本机实证**有第三方 SPB 客户端在跑 | **Sunia `TcnPeripheral`**（见 §三） | 从"理论可行"→"本机已验证" |
| **3** | 工具链 + 驱动编译 | `GdixSpbProbe.sys` 9,728 B | 从"纸上方案"→"可执行产物" |

### 2.4 ★ 一句话总结

> **认识到「I²C 控制器不是 `hidi2c` 独占的，它可以有并列客户端」—— 这是整个项目的转折点。**
>
> UMP45 说的"i2c 明明很简单"，指的就是：微软已经把 SPB 框架写好了，难的**不是 I²C 协议**，而是**知道有这条路**。

---

## 三、★★ 本机实证：Sunia 的 SPB 客户端驱动（最有价值的一份证据）

在 ACPI 设备树里发现的**现成模板**：

```
### ACPI\LTCN0001\1  [Sunia SPB Peripheral Driver - LTCN0001]
    Device_BiosDeviceName  = \_SB.PC00.I2C2.TCON
    Device_Class           = System              ← ★ 不是 HIDClass
    Device_Service         = TcnPeripheral       ← 第三方自写内核服务
    Device_Stack           = \Driver\TcnPeripheral | \Driver\ACPI
                             ↑ ★ 完全没有 hidi2c
    Device_Parent          = PCI\VEN_8086&DEV_7E7A  ← 同族 Serial IO I2C 控制器
    Device_DriverProvider  = Sunia Electronics
    Device_ProblemCode     = 0                    ← ★ 正常运行
```

**意义**：第三方 SPB 客户端驱动在这批 I²C 控制器上**已经运行着**。
这不再是推论，是本机事实。**我们的 INF 就该长成它这个形状。**

---

## 四、硬件与总线事实表

| 项 | 值 |
|---|---|
| 触控板型号 | Goodix **GXTP5100 / GT7868Q** |
| HID ID | `VID_27C6 / PID_01E9` |
| ACPI 节点 | `ACPI\GXTP5100\1`，BIOS 路径 `\_SB.PC00.I2C0.TPAD` |
| **总线类型** | **I²C（`bus_type=3`）** ← 一切方案的基础 |
| I²C 控制器 | `PCI\VEN_8086&DEV_7E78&SUBSYS_383017AA&REV_20\3&11583659&0&A8` |
| 控制器驱动 | `oem19.inf`，Intel `30.100.2405.44` |
| **Device_Address** | **1**（ACPI `_ADR`，权威） |
| SPB 连接速度 | **400 kHz**（I²C Fast Mode） |
| DataBitLength | 10 bits（I²C-HID 标准） |
| 中断控制器 | `ACPI\INTC1083\2&DABA3FF&0`（GPIO `\_SB.GPI0`） |
| 触控板驱动栈 | `\Driver\mshidkmdf \| \Driver\hidi2c \| \Driver\ACPI` |
| UpperFilters | `mshidkmdf` |
| **AW86927 地址** | **`0x5A`**（来自 cfg 明文） |
| 平台 / BIOS | Meteor Lake / `NJCN67WW` / SN `<DEVICE-SERIAL>` |

### ★ 注意地址的两个层级（易混）

| 地址 | 是什么 |
|---|---|
| `1` | **ACPI 声明的 I²C-HID 设备地址**（主机 ↔ 触控 IC） |
| `0x5A` | **AW86927 在触控 IC 内部的从地址**（触控 IC ↔ 震动芯片） |

**不是同一个东西**，也说明"主机侧可能只能到触控 IC 那一格"。

---

## 五、★ 关键技术认知（ROUND71 纠正的核心错误）

这段务必读 —— 是第一版驱动写错、修正后才编译过的。

### 5.1 SPB 有两种东西，别用错

| | 控制器驱动 | **客户端驱动（我们要的）** |
|---|---|---|
| 头文件 | `km\spb\1.1\spbcx.h` | **`shared\spb.h`** |
| API | `SpbTargetConnect` / `SpbRequestWrite` | **`IOCTL_SPB_EXECUTE_SEQUENCE`** |
| 适用 | SoC 厂商写 I²C 主控 | **第三方读写某个从设备** |

**陷阱**：`spbcx.h` 里有诱人的 `SpbTargetXxx` 函数名，但它们都要一个 `SPBTARGET` 句柄 ——
那**只有控制器驱动**能在 `EvtSpbTargetConnect` 回调里拿到。独立第三方用不了。
（`CTL_CODE(FILE_DEVICE_CONTROLLER, 0x602, METHOD_BUFFERED, FILE_ANY_ACCESS)`）

### 5.2 ★ 应用层不能直接发 SPB IOCTL

> **`IOCTL_SPB_*` 只允许内核态驱动发送。**

⇒ **必然是三层架构**（这也印证了我们的设计是对的）：

```
gdix_read.exe ──自定义IOCTL──> GdixSpbProbe.sys ──IOCTL_SPB_EXECUTE_SEQUENCE──> I²C ──> GT7868Q
   (用户态)                      (KMDF内核)                                     (硬件)
```

### 5.3 为什么上层 HID 过滤器不可能（反模式）

被 `hidi2c` 拒绝的请求**根本不会下传到过滤层**。挂载 `mshidkmdf` 之上是逻辑死路。

---

## 六、当前产物（已编译验证）

目录：`fw-touchpad\goodix-tool\spb-client\`

| 文件 | 大小 | 状态 |
|---|---|---|
| **`build\x64\Debug\GdixSpbProbe.sys`** | **9,728 B** | ✅ PE32+，`subsystem=1 (Native)`，x64，**唯一导入 `ntoskrnl.exe`** |
| `build\x64\Debug\gdix_read.exe` | 145,408 B | ✅ 用户态测试工具 |
| `GdixSpbProbe.c` | 16,950 B | ✅ 零 error |
| `GdixSpbProbe.inf` | 3,049 B | ✅ `Class=System` |
| `GdixSpbProbe.vcxproj` | — | 参考用（实际用 build.cmd） |
| `build.cmd` | — | ✅ **一键重建** |
| `README_INSTALL.md` | — | ✅ 部署 + 回滚步骤 |

### 驱动安全设计（勿放松）

- `Class = System`（**不是 HIDClass**）→ 不抢 `hidi2c` 的 PnP 匹配
- **只读**：地址白名单 `0x96F8 / 0x4014 / 0x1800 / 0x3800`，越界 → `STATUS_ACCESS_DENIED`
- **硬编码节流**：单次 ≤ 32 B，间隔 ≥ 500 ms（用户态再 sleep 300 ms）
- 符号链接 `\DosDevices\GdixSpbProbe`
- **尚未加载，未动任何系统配置**

---

## 七、下一步 · 三个决策点

### 决策 1：要不要开启测试签名（**你在 Linux 上不需要，Windows 必须**）

```cmd
bcdedit /set testsigning on    ← 改 BCD，需重启
```

- ✅ 可完全回滚：`bcdedit /set testsigning off`
- ⚠️ 桌面右下角会出现"测试模式"水印
- ⚠️ Secure Boot 开着时可能还要额外处理
- **🔒 我不会擅自执行 —— 等你明确同意**

### 决策 2：要不要先问 UMP45

群里的 UMP45 主动提到过：*"i2c 明明很简单的"*、*"网上那些 2b 全跑 ps2"*、*"还有就是我的开源项目"*。

**建议问这三个**（他自己提到过开源项目，这是最高优先级）：

1. **> 你的开源项目在哪？**（他主动提的，最省事）
2. **> 我这边 GT7868Q 走 SPB 客户端，Connection ID 已拿到。你当时是 SPB 客户端还是别的？hidi2c 那关怎么过的？**
3. **> 驱动签名怎么解决？测试模式还是正式证书？**

**第 3 问最省时间** —— 签名这道坎我们迟早要过，有现成经验能省好几天。

### 决策 3：Linux 验证线（已搁置，可随时重启）

`ty2/goodix-gt7868q-linux-driver` + libinput quirks，`MatchVendor=0x27C6 / MatchProduct=0x01E9`
（与本硬件**精确匹配**）。社区已在同款 GXTP5100 上跑通（Launchpad bug #2093390）。
Linux 的 `i2c-hid` **完整透传** hidraw，不像 Windows 拦截。
**如果用户不想改 BCD，这条路是零风险的替代验证手段。**

---

## 八、已知不确定点（跑起来才知道）

| # | 问题 | 影响 | 应对 |
|---|---|---|---|
| **1** ★ | `_I2C_DIRECT_RW`（`0e 20 ...`）是 **HID 层封装**，裸 I²C 可能**不需要** | 读到全 `0x00`/`0xFF` 或报错 | 改一处组包代码重编译，非结构性 |
| 2 | 目标设备名 `\Device\0000008a` 每次枚举可能变 | `WdfIoTargetOpen` 失败 | 改成按接口名/父设备动态获取 |
| 3 | 能否与 `hidi2c` 共存 | 可能拒绝共享 | 调 `FILE_SHARE_*` 或临时停 HID 栈 |
| 4 | Secure Boot 是否干扰测试签名 | 加载被拒 | 先关 Secure Boot，或改用 Linux 线 |

---

## 九、文件索引

### 必读

| 文件 | 内容 |
|---|---|
| **本文件** | 总入口 |
| `ROUND70_SPB_CONNECTION_ID_FOUND.md` | Connection ID 解析 + Sunia 实证 |
| `ROUND61-67_UEFI_CAPSULE_TRUTH.md` | UEFI 胶囊真相（关闭了"改固件"那条路） |
| `STATUS_OVERVIEW_现状总览.md` | 早期总览（部分已被本文更新） |
| `spb-client\README_INSTALL.md` | 部署步骤 + 回滚 |

### 数据 / 脚本

| 文件 | 用途 |
|---|---|
| `round69_acpi_dump.ps1` | 只读 ACPI 导出（**需管理员**，生成 `round69_acpi_out\`） |
| `round69_acpi_out\06_spb_connections.txt` | SPB 连接资源原始出处 |
| `round61_official_validator.py` | 官方固件格式校验器 |
| `round64_readback.py` / `round65_diag.py` | HID 层实测证据（`read error` 的出处） |
| `round66_driverstack.py` | 驱动栈取证 |
| `spb-client\build.cmd` | 一键构建驱动 |

### 外部参考

- `/tmp/gdix_fw/` —— Goodix 官方更新工具源码克隆（已完整读过）

---

## 十、🔒 红线（照旧，绝不破）

1. 禁批量轮询 `Col04`
2. 单次事务 ≤ 32 B，间隔 ≥ 500 ms
3. 🔴 **红线是四条，不是“三连”**：`00 10` / `00 11` / **`0E 12`（★ 真正写 flash）** / **`0E 13`（重启）** 绝不碰 —— 旧文档漏了 `0E 13`，且常把 `0E 12` 误当“重启”（性质正好说反）
4. **未获明确同意，不动 `bcdedit`**
5. 本驱动保持**只读**，不得移除白名单
6. 不删 `.workbuddy`、不删 `touchpad-lab`

---

## 十一、给继任者的三句话

1. **别再找密钥了** —— 那个 BIN 是 UEFI 胶囊，不是加密固件（见 ROUND61-67）。
2. **别在用户态硬碰 `hidi2c`** —— 实测 `GET_FEATURE` 直接 `read error`，过滤器也救不了。
3. **现在的 correct move 是**：确认要不要开测试签名 → 加载驱动 → 读 `0x4014` 看通不通。
   **读到数据 = 通路打通**，之后才是"能不能震"的问题。

> **编译关已过。剩下的是部署关，而部署要改 BCD —— 这一步必须人来拍板。**
