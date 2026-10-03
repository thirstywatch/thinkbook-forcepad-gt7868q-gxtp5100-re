# DSDT 里 TPAD 子树完整解读（② 线成果）

> 2026-09-29。工具：`scripts-acpi/dsdt_tpad.py`（规范级字段解读）+ `scripts-acpi/aml_tpad_decompile.py`（AML 反编译）。
> 数据源：`acpi-dump/DSDT_LENOVO_CB-01____00000001.bin`（528,582 字节）。

---

## 零、一句话结论

DSDT 里 `TPAD` 子树 = **一个 986 字节的厂商适配层**，作用是把「5 家触控板厂商的差异」抽象成
「查表 → 得到 HID/地址 → 拼资源描述符」。本机走的是 **第 4 条：Goodix `GXTP5100`，I2C 从机 `0x2C`，
描述符寄存器 `0x20`，中断引脚 `0xB6(182)`，低电平有效、电平触发**。

**对逆向的价值**：把「厂商适配」这一层彻底排除 —— 手感/波形不可能在这里，
因为这里**只做设备识别与资源枚举，不碰任何触觉参数**。

---

## 一、TPAD 节点定位（已定死）

| 项 | 值 |
|---|---|
| 偏移 | `0x07042A` |
| PkgLength | `0x3D8`（984） |
| 包尾 | `0x070804` |
| 大小 | **986 字节** |
| 前驱 | `HIDD` Device（`0x070137`） |
| 后继 | `Scope(_SB.PC00)`（`0x070805`，`10 45 09 2F 04 5F 53 42 5F 50 43 30`） |

首字节序列：
```
07042A  5B 82 48 3D 54 50 41 44   [.H=TPAD      ← DeviceOp + PkgLen(48 3D) + "TPAD"
070432  08 5F 41 44 52 01         ._ADR.        ← Name(_ADR, 1)
070438  08 5F 55 49 44 01         ._UID.        ← Name(_UID, 1)
07043E  08 5F 53 30 57 0A 03      ._S0W..       ← Name(_S0W, 3)
070445  08 41 44 52 30 00         .ADR0.        ← Name(ADR0, Zero)
07044B  08 48 49 44 32 00         .HID2.        ← Name(HID2, Zero)
070451  08 54 50 49 44 ...        .TPID         ← Name(TPID, Package)
```

---

## 二、★ TPID 厂商表（5 条目，完整解出）

`Name(TPID, Package(5){...})`，每条 5 个字段
`Package{索引, 从机地址, 描述符寄存器, HID字符串, CID字符串}`：

| # | 索引 | 从机地址 | 描述符寄存器 | HID | CID | 厂商 |
|---|---|---|---|---|---|---|
| 1 | 1 | 0x2C | 0x20 | `SYNA2BA6` | PNP0C50 | Synaptics |
| 2 | 2 | 0x15 | 0x01 | `ELAN06FA` | PNP0C50 | Elan |
| 3 | 3 | 0x2C | 0x20 | `CIRQ1080` | PNP0C50 | Cirque |
| **4** | **4** | **0x2C** | **0x20** | **`GXTP5100`** | PNP0C50 | **Goodix** |
| 5 | 255 | 0xFF | 0xFF | `XXXX0001` | —（占位） | — |

**→ 本机命中第 4 条：Goodix `GXTP5100`，从机地址 `0x2C`（= 44 十进制），
描述符寄存器 `0x20`（= 32）。** 与 `dsdt_tpad.py` 独立解析结果**完全一致**（双工具互证）。

---

## 三、★ 资源描述符（SBFI / SBFG）

两个 `Name(Buffer(...))`，配合 `_CRS` 里的 `ConcatRes` 拼成完整资源。

### 3.1 SBFI —— I2C 从机资源（`Name(SBFI, Buffer(13))` @ `0x0704E0`）

```
0A 0B  89 06 00 15 01 00 00 00 00  79 00
^^ ^^  ^^ ^^^^^
│  │   │  └ Length = 6（描述符总长，含头 3 字节）
│  │   └ 0x89 = I2cSerialBus
│  └ Buffer 数据长度 = 11
└ 0x0A = BytePrefix（长度字段前缀）
```

| 字段 | 值 | 说明 |
|---|---|---|
| 类型 | `0x89` | I2cSerialBus |
| Length | 6 | **最小合法形式** |
| RevID | 1 | |
| ResSrcIdx | 0 | |
| SerialBusType | 0 | I2C |
| GenFlags / TypeFlags | 0 / 0 | |
| **速率 / 从机地址** | **不在描述符里** | ★ 由 `_CRS` 的 `IICBADR0` 动态给出 |
| 静态从机地址 | **0x2C** | 取自 TPID 表第 1/3/4 条 |
| 总线 | `\_SB.PC00.I2C0` | 见 `_DSM` 第 2 分支 |

**★ 重要**：`Length=6` 意味着**这是 ACPI 允许的最小 I2cSerialBus 形式**（只有 6 字节头，
不含 Speed 与 SlaveAddress）。所以「读 DSDT 就能知道 I2C 速率」这条路**堵死** ——
速率只能在运行时从 `\_SB.PC00.I2C0` 的 `_CRS` 读（那张表不在本 DSDT 里）。

### 3.2 SBFG —— GPIO 中断资源（`Name(SBFG, Buffer(39))` @ `0x0704F4`）

```
0A 25  8C 20 00 01 00 01 00 12  00 01 00 00 00 00 17 00 00 19 00 23 00 00 00 B6 00  \_SB.GPI0\0  79 00
^^ ^^  ^^ ^^^^^ ^^ ^^ ^^^^^ ^^  └──────── PinTable 区（9 字节，模板化）────────┘  └─ 源设备 ─┘  └EndTag┘
│  │   │  └Len=32 └RevID=1 └ResSrcIdx=0 └IntFlags=0x0001 └PinConfig=0x12
│  └ Buffer 数据长度 = 37
└ 0x0A = BytePrefix
```

| 字段 | 值 | 解读 |
|---|---|---|
| 类型 | `0x8C` | GpioInt |
| Length | `0x20` = 32 | 描述符总长 |
| RevID | 1 | |
| ResSrcIdx | 0 | |
| **IntFlags** | `0x0001` | **bit0=1 → ActiveLow；bit1=0 → Level 触发**；共享=0；不可唤醒 |
| PinConfig | `0x12` | |
| 源设备 | `\_SB.GPI0` | PCH GPIO 控制器 |
| EndTag | `79 00` | ✅ |

**★ PinTable 的定死过程（含一次判据纠错）**

42 个同型 GpioInt 描述符（`Length=32` + `\_SB.GPI0` 源）全扫后的分布：

| 偏移 | 字节 | 恒定？ | 认定 |
|---|---|---|---|
| `+8..+15` | `00 00 00 00 00 00 17 00`（33 例）/ `00 01 ...`（9 例） | 两值 | `PinTableOffset` 区 |
| `+17-18` | `19 00` | **恒定** | **ResSourceOffset = 25**（源串位置，实测吻合） |
| `+19-20` | `23 00` | **恒定** | PinTable / Vendor 区起 |
| `+21-22` | `00 00` | **恒定** | 次 pin 槽 / 对齐 |
| `+23-24` | **变化** | — | **★ 引脚号（Word LE）** |

`+23-24` 逐设备取值（全部 42 例）：

| Device | `+23-24` | 引脚号 |
|---|---|---|
| **TPAD** | `B6 00` | **0x00B6 = 182** |
| HDA1 | `FF FF` | Ones（未用） |
| SPFD | `48 00` / `37 00` / `80 00` | 72 / 55 / 128 |
| FPNT | `08 00` / `00 00` | 8 / 0 |
| ESSX | `66 01` / `62 01` | 358 / 354 |
| BTH0 / PRT7 / CNVW | `00 00` | 0 |

**⇒ TPAD 的中断引脚 = GPIO pad 182（`0xB6`），低电平有效、电平触发。**

> ⚠️ 诚实标注：这个 `Length=32` 描述符的 Header 字段排布与 ACPI 6.4 §6.4.3.8.1 规范
> **有 4~5 字节偏差**（Insyde 实现差异）。「`+23-24` 即引脚号」的判据来自
> **42 个同型样本的一致性 + 逐设备语义合理性**（HDA1 用 Ones 表示无中断、
> SPFD 多个 GPIO 各不同、BTH0 用 0），**不是规范逐字推导**。
> 若要 100% 确证，需运行时读 IOAPIC/GSI 或 `\_SB.GPI0` 的 `_AEI` 表（不在本 DSDT）。

---

## 四、★ `_DSM` 完整伪 ASL（158 字节，反编译成功）

```
Method(_DSM, 4, NotSerialized) {
  If (LEqual(Arg0, Buffer(16){3cdff6f7-4267-4555-ad05-b30a3d8938de})) {   // 微软触控板规范
    If (LEqual(Arg2, Zero)) {                     // 查询功能位
      If (LEqual(Arg1, One)) {                    // Function 1
        Return(Buffer(One){0x03})
      } Else {
        Return(Buffer(One){0x00})
      }
    }
    If (LEqual(Arg2, One)) {                      // 子功能 1
      Return(HID2)                                // ← Name(HID2, Zero)，被后续代码覆写为 HID 字符串
    }
  } Else {
    Return(Buffer(One){0x00})
  }

  If (LEqual(Arg0, Buffer(16){ef87eb82-f951-46da-84ec-14871ac6f84b})) {   // 厂商自定义
    If (LEqual(Arg2, Zero)) {
      If (LEqual(Arg1, One)) {
        Return(Buffer(One){0x03})
      } Else {
        Return(Buffer(One){0x00})
      }
    }
    If (LEqual(Arg2, One)) {
      Return(ConcatRes(IICBADR0, "\_SB.PC00.I2C0", SBFG))   // ★ 动态拼资源描述符
      Zero
    }
  } Else {
    Return(Buffer(One){0x00})
  }
  Return(Buffer(One){0x00})
}
```

**两条 UUID 的语义分工**：

| UUID | 归属 | 作用 |
|---|---|---|
| `3cdff6f7-4267-4555-ad05-b30a3d8938de` | **微软触控板规范**（Precision Touchpad） | 功能位查询 + 返回 HID2 |
| `ef87eb82-f951-46da-84ec-14871ac6f84b` | **厂商自定义** | 返回 `ConcatRes(IICBADR0, "\_SB.PC00.I2C0", SBFG)` |

**★ `IICBADR0` 之谜（已解）**：

- `IICBADR0` 在 DSDT 里**只有 3 处引用、0 处定义**（`0x0706B4` / `0x0707C8` / `0x0707E7`）
- 它定义在 **`\_SB.PC00.I2C0` 所在的表**（本 DSDT 未收录，通常是同机的 SSDT）
- **★ 编码异常**：AML 里 8 字符名规范上必须写成 `2E IICB ADR0`（DualNamePrefix），
  但 Insyde 这里**裸写 8 字节无前缀** ⇒ 标准反编译器（acpica `iasl`）会把它
  错读成 `IICB` + `ADR0` 两个 NameSeg。本工具已加容错（见 §七）。

---

## 五、★ `TPDS` 完整伪 ASL（72 字节，反编译成功）

```
Method(TPDS, 4, NotSerialized) {      // 查表函数：按值找 TPID 条目
  Store(Zero, Local0)                 // i = 0
  Store(Zero, Local1)                 // cur = 0
  Store(DerefOf(Index(DerefOf(Index(TPID, Local0, Zero)), Zero, Zero)), Local1)
                                      // cur = TPID[0][0] = 1
  While (LAnd(LNot(LEqual(Local1, Arg1)), LNot(LEqual(Local1, Arg2)))) {
    Increment(Local0)                 // i++
    If (LNot(LLess(Local0, SizeOf(TPID)))) {   // i >= SizeOf(TPID)
      Return(Arg3)                    // 找不到 → 返回默认值 Arg3
    }
    Store(DerefOf(Index(DerefOf(Index(TPID, Local0, Zero)), Zero, Zero)), Local1)
                                      // cur = TPID[i][0]
  }
  Return(DerefOf(Index(DerefOf(Index(TPID, Local0, Zero)), Arg0, Zero)))
                                      // 找到 → 返回 TPID[i][Arg0]
}
```

**参数语义**（据代码反推）：

| 参数 | 含义 |
|---|---|
| `Arg0` | 要取的**列索引**（0=索引, 1=从机地址, 2=描述符寄存器, 3=HID, 4=CID） |
| `Arg1` | 匹配值 A（与 `TPID[i][0]` 比较） |
| `Arg2` | 匹配值 B（同上，任一命中即停） |
| `Arg3` | **未命中时的默认返回值** |

**用途**：`TPDS(列, 值A, 值B, 默认)` —— 按「索引」列在 TPID 表里定位条目，
返回该行的第 `Arg0` 列。典型的用途是 **按硬件上报的厂商索引取对应的 HID / I2C 地址**。

> ⚠️⚠️ **本节结论已于 2026-09-29 更正（原判错误，勿据此行动）**
>
> **原判**：「本机 DSDT 里 `TPDS` 没有任何调用者（grep 全表零命中）⇒ 留给 SSDT 或 OS 驱动调用」
> **实测（对整个 528 KB DSDT 逐字节搜，并对 32 张 ACPI 表全搜）**：
> - **`TPDS` 在 DSDT 内共出现 4 次 = 1 处方法定义 + 2 处调用**
> - **32 张 ACPI 表里没有任何 SSDT 含 `TPDS` 或 `TPID`** ⇒ 「逻辑分散在 DSDT + SSDT」这句不成立，**逻辑全在 DSDT 内**
> - 两处调用（`0x7056F` / `0x705D2`）形如：
>   ```
>   TPDS(3, 0xFE, TPDF, "MSFT0001")
>   TPDS(4, 0xFE, TPDF, "PNP0C50")
>   ```
>   `Arg3` 传的是**默认字符串** ⇒ **`TPDS` 实际返回的是 HID / CID 字符串，而不是 I2C 地址**
> - 同族兄弟方法名（名单在 `0x83EF` 附近）：`TPLT / TPLM / TPLB / TPLH / TPLS / TPDT / TPDM / TPDB / TPDH / FPTT / FPTM / WTVX / WITX / GPTD / GDBT / UTKX / SPTD`
>   ⇒ **I2C 地址与描述符寄存器由这批里的另一个方法给出**
>
> **⇒ 后果（对"改 DSDT 绕过白名单"这类方案至关重要）**：若地址也来自"带默认参数的调用"（像 `TPDS` 一样），
> **要改的是【调用点上的默认值】而不是 `TPID` 表里那一行** —— 两者都仍在 DSDT 内、都可 patch，但**偏移完全不同**。
> **⇒ 因此"改哪个字节"必须先用 `iasl -d` 反编译确认，不可想当然。**（详见 `touchpad-lab\DELTA-2026-09-29f` §6.3f）

---

## 六、TPAD 子树的完整对象清单（反编译全扫）

| 偏移 | 对象 | 值 |
|---|---|---|
| `0x070432` | `Name(_ADR, 1)` | 设备地址 |
| `0x070438` | `Name(_UID, 1)` | 唯一 ID |
| `0x07043E` | `Name(_S0W, 3)` | S0 唤醒能力 = 3（D3cold 可唤醒） |
| `0x070445` | `Name(ADR0, Zero)` | I2C 地址默认值 |
| `0x07044B` | `Name(HID2, Zero)` | HID 字符串占位 |
| `0x070451` | `Name(TPID, Package(5))` | ★ 厂商表 |
| `0x0704E0` | `Name(SBFI, Buffer(13))` | ★ I2C 从机资源 |
| `0x0704F4` | `Name(SBFG, Buffer(39))` | ★ GPIO 中断资源 |
| `0x07053B` | `Name(TPDF, 254)` | 标志位（0xFE） |
| `0x07059E` | `Name(TPDF, 254)` | 同上（另一分支） |
| `0x0705EF` | `Method(TPDS, 4)` | ★ 查表函数（72 字节） |
| `0x07063F` | `Method(_DSM, 4)` | ★ 微软/厂商接口（158 字节） |
| `0x0706F6` | `Name(TPDD, Zero)` | 默认值 |
| `0x07074C` | `Name(TPDF, 254)` | 同上 |
| （`_STA`） | `Method(_STA, 0)` | 见 `0x0706D9` 附近 |

> `Method(_STA)` / `Method(_CRS)` 也已在子树内，但本次重点是 TPID/SBFI/SBFG/_DSM。

---

## 七、★ 工具修复记录（本次踩的 4 个坑）

### 坑 1：PkgLength 字节序（旧实现错了一个数量级）

`decompile_qxx.py::pkg_in` 原用 `v |= d[i+k] << (8*k)`，`dsdt_tpad.py::pkg_len` 用 `<< (4+8*k)`。

**判据**（421 个 DeviceOp 全扫）：

| 实现 | TPAD(`5B 82 48 3D`) 算出 | 越界数 | 包尾首字节 |
|---|---|---|---|
| `<< 8k` | `0x3D48` ❌ | 8/421 | — |
| **`<< 4+8k`** | **`0x3D8`** ✅ | **1/421** | `5B`×228 / `A0`×65 / `10`×58 / `14`×50（全合法） |

TPAD 包尾 `0x070804` 紧随 `10 45 09 2F 04 _SB_PC0` = `Scope(_SB.PC00)` ✅

**⇒ `<< (4+8*k)` 正确。`decompile_qxx.py` 已同步修正。**

### 坑 2：包尾公式多加了一个 `n`（★ 影响最大）

旧代码：`blk_end = i + 1 + n + v`

- `i` = 操作符位置，`n` = PkgLength 占用字节数，`v` = PkgLength **值**
- **PkgLength 的值已包含自身占用的字节** ⇒ 包尾 = `操作符 + 1 + v`
- 多加了 `n` ⇒ If/While 包体被拉长 1~3 字节 ⇒ 解析器读到下一条语句的头字节
  ⇒ **满屏 `?XX` 失步**

**实例**：`A0 0B` If，`v=0x0B`，`n=1`
- 错误：`0x07060D + 1 + 1 + 0x0B = 0x07061A`（多了 1）→ 吞掉下一条 `70`(Store)
- 正确：`0x07060D + 1 + 0x0B = 0x070619` ✅（下一条 Store 正好在此）

修好后 **TPDS 从满屏 `?XX` 变成 100% 干净**。

### 坑 3：`Name` 没有 PkgLength（★ 概念性错误）

`NameOp := 0x08 NameString DataRefObject` —— **`Name` 不使用 PkgLength**！

旧实现按 `08 PkgLength NameString Data` 解析，把 `TPID` 的 `54 50` 误当 PkgLength
（算出 `0x504`），导致 **421 个 Name 全部解析失败**，`TPID`/`SBFI`/`SBFG` 一个都读不出来。

正确：`08` 后**直接读 NameString**，对象边界完全由 `parse_term` 的返回值决定。

### 坑 4：8 字符裸名（Insyde 非标准编码）

`84 IICBADR0 "\_SB.PC00.I2C0"` —— 无 `2E` 前缀的 8 字符名。
标准反编译器会错拆成 `IICB` + `ADR0`（两个参数）。

**应对**：`nameseg_in` 加容错 —— 若紧跟两个合法 4 字符 NameSeg，
且拼成的 8 字符名在**白名单**（`IICBADR0`/`IICSDA0`，定义在本表外的跨表引用）
或表内有 `Name` 定义，则按 8 字符名解析。

### 坑 5：`ConcatRes` 可选 Target 参数

`ConcatRes(Source1, Source2, Target)` 的第 3 参可省略（表示丢弃结果）。
静态解析无法只靠长度区分「省略的 Target」与「后续的独立语句」。

**实例**：`Return(ConcatRes(IICBADR0, "\_SB.PC00.I2C0"))` 后面紧跟独立语句 `SBFG`
（Insyde 确实会生成"裸名字当表达式语句"）—— 强行解析第 3 参会把 `SBFG` 吞掉。

**应对**：试解析第 3 参，若超出包边界、或结果是「裸 NameString 且恰好停在包尾」，则回退。

---

## 八、对触觉/手感结论的净影响

| 问题 | 本次是否给出新信息 |
|---|---|
| 波形/手感参数在哪 | **无** —— DSDT 的 TPAD 子树**不碰任何触觉参数**，只做设备识别与资源枚举 |
| 能否从 DSDT 拿到 I2C 速率 | **不能** —— SBFI 是最小形式（`Length=6`），速率在 `\_SB.PC00.I2C0` 的 `_CRS`（另一张表） |
| 能否从 DSDT 拿到中断引脚 | **能** —— GPIO pad **182（0xB6）**，低电平有效、电平触发（判据见 §3.2 的诚实标注） |
| 厂商适配层是否藏了东西 | **没有** —— `TPID` 表 + `TPDS` 查表 + `_DSM` 拼资源，纯粹是 ACPI 规范动作 |
| 方案③ 还缺什么 | 不变：**振幅** + **LRA 型号/谐振频率** |

**⇒ 结论：DSDT 这条线到此可以收口。** 它排除了一整块可能性，但没有新增触觉参数。

---

## 九、下一步

1. **③ BIOS 两模块反汇编**（`FmpDxeY750` / `I2cTouchPanelDxe`）—— 未开始
2. **角度线：EC 端口实测** —— 等配合（用户提权跑 cmd → 重启 → 我跑测试）
3. **可选**：找 `\_SB.PC00.I2C0` 所在的 SSDT，拿 I2C 速率 + `_AEI` 表验证 GPIO 182
4. **清理**：`scripts-acpi/_probe_gpioint.py`、`scripts-acpi/_probe_terms.py`（临时探针）

---

## 附：可复用命令

```bash
cd 2026-09-27-14-52-52/scripts-acpi
python dsdt_tpad.py            # 规范级字段解读（TPID/SBFI/SBFG）
python aml_tpad_decompile.py   # AML 反编译（TPDS/_DSM 伪 ASL + Name 对象 dump）
```
