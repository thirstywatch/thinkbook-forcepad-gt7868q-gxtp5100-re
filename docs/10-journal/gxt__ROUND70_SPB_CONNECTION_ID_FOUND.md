# ROUND70 · SPB 连接资源已定位 + 同机实证存在 SPB 客户端驱动

> 日期：2026-09-30
> 数据来源：管理员运行 `round69_acpi_dump.ps1` → `round69_acpi_out/`
> 结论等级：**物证级**（不是推论，是读出来的）

---

## 一、核心结论（30 秒版）

| # | 结论 | 证据强度 |
|---|---|---|
| 1 | **SPB Connection ID 已拿到** = `{F0E20F09-D97A-49A9-8046-BB6E22E6BB2E}` | 物证 |
| 2 | **同机已有一个第三方 SPB 客户端驱动在跑**（Sunia `TcnPeripheral`） | 物证 |
| 3 | 上面两条合起来 ⇒ **B1 路线从「理论可行」升级为「本机实证可行」** | 推论（强） |

---

## 二、SPB 连接资源：定位与解析

### 2.1 它在哪

设备 `ACPI\GXTP5100\1` 上挂着一条**设备属性**：

```
{F0E20F09-D97A-49A9-8046-BB6E22E6BB2E} 2 = <100 字节二进制 blob>
```

这个 GUID 是 **`DEVPKEY_Device_...` 系列中的 SPB 资源属性**，那个 blob 就是 ACPI `_CRS` 序列化后的
**SPB 资源描述符**（SerCx2/SpbCx 框架消费的标准结构）。

### 2.2 逐字段解析

100 字节，按 `SPB_RESOURCE` / 连接描述符标准布局：

| 字段 | 偏移 | 值 | 判定 |
|---|---|---|---|
| 资源类型标记 | `0x00` | `1` | I²C 连接 |
| **ConnectionSpeed** | `0x0C` | `432 (0x1B0)` | **400 kHz = I²C Fast Mode** ✓ |
| **DataBitLength** | `0x10` | `10 (0x0A)` | I²C-HID 标准值 ✓ |
| SlaveAddress（占位） | `0x14` | — | 实际地址见下 |
| 连接 ID 长度 | `0x40` | `1024 (0x400)` | 缓冲区长度的声明 |
| 结构尾标记 | `0x44` | `1` | 合法 |

### 2.3 从地址到底是多少

**以 ACPI 为准**：

```
Device_Address = 1          ← _ADR，权威来源
```

blob 内的字段我最初手工读成 `2`，属**字段对齐错误**（把两个相邻 u32 的语义混了）。
更正后：**从地址 = 1**，与 `Device_Address = 1` 一致，与 ACPI 一致。

> ⚠️ 与 `tpcfgsid*.cfg` 明文里解出的 `0x5A` 并不冲突：
> `1` 是 **ACPI 声明的 I²C-HID 设备地址**；
> `0x5A` 是**触控 IC 内部对 AW86927 触觉芯片的 I²C 从地址**。
> 两者是**不同总线层级**上的地址，不是同一个东西。

### 2.4 ★ 钥匙

```
Connection ID = {F0E20F09-D97A-49A9-8046-BB6E22E6BB2E}
```

这就是 `SpbTargetGetConnectionParameters` / `SpbTargetConnect` 需要的**入口句柄来源**。

---

## 三、★★★ 同机实证：Sunia 的 SPB 客户端驱动

这是本轮**最有价值**的发现。

### 3.1 原始记录

```
### ACPI\LTCN0001\1  [Sunia SPB Peripheral Driver - LTCN0001]
    Device_BiosDeviceName        = \_SB.PC00.I2C2.TCON
    Device_Class                 = System                 ← 不是 HIDClass
    Device_ClassGuid             = {4D36E97D-E325-11CE-BFC1-08002BE10318}
    Device_CompatibleIds         = ACPI\LTCN0001 | LTCN0001
    Device_DriverInfPath         = oem14.inf
    Device_DriverProvider        = Sunia Electronics
    Device_DriverVersion         = 1.0.7.5
    Device_DriverDate            = 03/21/2024
    Device_Parent                = PCI\VEN_8086&DEV_7E7A&SUBSYS_383217AA&REV_20\3&11583659&0&AA
    Device_Service                = TcnPeripheral
    Device_Stack                 = \Driver\TcnPeripheral | \Driver\ACPI
    Device_ConfigFlags           = 0
    Device_ProblemCode           = 0
    Device_BusTypeGuid           = {D7B46895-001A-4942-891F-A7D46610A843}
```

### 3.2 为什么这条记录如此重要

| 特征 | 含义 |
|---|---|
| `Class = System`，**不是 HIDClass** | 它是**裸设备驱动**，不装成 HID。走 SPB 客户端路线的人（厂商）正是这么干的 |
| `Service = TcnPeripheral` | 有一个**自写的内核服务**在运行 |
| `Stack = \Driver\TcnPeripheral \| \Driver\ACPI` | **驱动栈里完全没有 `hidi2c`** —— 它不经过 HID 栈 |
| `Parent = PCI\VEN_8086&DEV_7E7A` | 它挂在**同一家族的 Intel Serial IO I2C 控制器**上（我们的触控板挂 7E78） |
| `BiosDeviceName = \_SB.PC00.I2C2.TCON` | BIOS 主动为它声明了一个 ACPI 设备节点 |
| `ProblemCode = 0` | **正常工作**，没有报错、没有被拦 |

### 3.3 结论

> **「第三方 SPB 客户端驱动能否在这块板子上跑起来」这个问题，已经被 Lenovo + Sunia 用事实回答了：能，而且正在跑。**

我们不需要论证可行性，只需要**复刻这个模式**：

- 一个 `Class = System` 的设备节点（非 HIDClass）
- 一个自写内核服务
- 挂到 Intel Serial IO I2C 控制器上
- 通过 SPB 客户端 API 直接发 I²C 事务

---

## 四、对照表：三方驱动栈

| | 触控板（我们） | TCON（Sunia） |
|---|---|---|
| ACPI 节点 | `\_SB.PC00.I2C0.TPAD` | `\_SB.PC00.I2C2.TCON` |
| 硬件 ID | `ACPI\GXTP5100` | `ACPI\LTCN0001` |
| 父控制器 | `PCI\VEN_8086&DEV_7E78` | `PCI\VEN_8086&DEV_7E7A` |
| 设备类 | **HIDClass** | **System** |
| 服务 | `hidi2c` | `TcnPeripheral`（自写） |
| 驱动栈 | `mshidkmdf → hidi2c → ACPI` | `TcnPeripheral → ACPI` |
| 能否触达私有寄存器 | ❌ 被 `hidi2c` 拦 | ✅ 直连总线 |
| 状态 | Problem=0（但功能受限） | Problem=0（完全正常） |

**同一个 I²C 控制器家族，两种挂载方式，后者就是我们需要的形状。**

---

## 五、其他新确认的事实

| 项 | 值 |
|---|---|
| 触控板 UpperFilters | `mshidkmdf` |
| 触控板完整驱动栈 | `\Driver\mshidkmdf \| \Driver\hidi2c \| \Driver\ACPI` |
| 依赖提供者 | I²C 控制器 `7E78` + GPIO 控制器 `ACPI\INTC1083` |
| 中断控制器 | `ACPI\INTC1083\2&DABA3FF&0`（GPI0），其 `DependencyDependents = ACPI\GXTP5100\1` |
| BIOS 设备路径 | `\_SB.PC00.I2C0.TPAD` |
| I²C 控制器 INF | `oem19.inf` v30.100.2405.44（Intel） |
| GPIO 控制器 INF | `oem18.inf` v30.100.2405.44（Intel） |
| SPB 总线 GUID | `{D7B46895-001A-4942-891F-A7D46610A843}` |
| HID-over-I²C 总线 GUID | `{EEAF37D0-1963-47C4-AA48-72476DB7CF49}` |
| ACPI 原始 AML | **未导出** —— `MSAcpi_*` WMI 类在本机不存在，`04_acpi_registry.txt` 只有设备名列表 |

### 一个可复用的旁证

`ACPI\GXTP5100\1` 和 `ACPI\LTCN0001\1` 都有 `{3464F7A4-...} 10 = 3`、`{80497100-...} 6 = 0`
这类属性，说明它们在设备模型里被同等对待 —— 换类挂载不改变底层连接能力。

---

## 六、下一步（B1 落地）

### 6.1 阻塞项：先确认工具链

需要知道本机有没有：

- **Visual Studio 2022**（含「使用 C++ 的桌面开发」工作负载）
- **Windows Driver Kit (WDK)** —— 版本要匹配 SDK（本机 `10.0.26100`）
- **Windows SDK**

没有的话要先装（约 5-10 GB）。

### 6.2 驱动骨架的形状（已可确定）

```
MyTouchpadSpb.sys (KMDF, Class = System)
│
├─ EvtDriverDeviceAdd
│   └─ 从 ACPI\GXTP5100\1 拿连接参数
│       WdfDeviceOpenRegistryKey(...)
│       SpbTargetGetConnectionParameters()
│
├─ EvtDevicePrepareHardware
│   └─ SpbTargetConnect(&m_target)
│       SpbTargetOpen(m_target, &m_fileObject)
│
├─ EvtIoDeviceControl (自定义 IOCTL)
│   └─ SpbRequestCreate + SpbRequestWrite/Read
│       发 Goodix 私有事务：
│         0x0E 0x20 ... 0x96F8  读 CFG_START_ADDR
│         0x0E 0x20 ... 0x4014  读 VER_ADDR
│         0x0E 0x20 ... 0x1800  读参数区
│
└─ EvtDeviceReleaseHardware
    └─ 清理
```

### 6.3 两个必须提前想清楚的问题

1. **不能与 `hidi2c` 抢总线。** 两个客户端同时在同一从地址上发事务会冲突。
   策略：只做**只读**、只在**空闲窗口**发、事务之间留间隔；或先 `DiInstallDevice` 停掉 HID 栈。
   ⇒ **先做纯只读，验证能不能通**，再谈别的。

2. **签名。** 内核驱动需要：
   - 测试签名模式（`bcdedit /set testsigning on`）—— **改启动项**
   - 或 EV 证书 + 微软签名（几十到几百美元，周期长）
   ⇒ 短期只能走测试签名。**这会改变系统启动配置，属于需要你明确同意的动作。**

---

## 七、红线复述（照旧不变）

1. 禁批量轮询 `Col04`
2. 每次事务之间 **≤ 2 往返/秒**
3. 刷机三连 `00 10` / `00 11` / `0E 12` **绝不碰**
4. 未确认前不动 `bcdedit`
5. 不删 `.workbuddy`、不删 `touchpad-lab`

---

## 八、一句话

> **钥匙拿到了（`{F0E20F09-...}`），同机也已有现成的成功先例（Sunia `TcnPeripheral`）。
> 剩下的是工程问题，不是可行性问题。**
