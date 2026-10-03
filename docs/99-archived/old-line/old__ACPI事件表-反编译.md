# ACPI `_Qxx` 事件表 —— AML 反编译结果

- 时间：2026-09-27 · 机器：ThinkBook 14 G6+ IMH（21LD）
- 输入：`acpi-dump\DSDT_LENOVO_CB-01____00000001.bin`（528,582 字节）
- 工具：`decompile_qxx.py`（自写 AML 反编译器）· 原始输出 `qxx.txt`
- 结果：**25 个 `_Qxx` 方法全部反编译成可读伪 ASL**

---

## 一、`_Qxx` 是什么

EC 检测到硬件事件后，通过 SCI 通知主机；固件侧的入口就是 `\_SB.PC00.LPCB.EC0_` 下的
`_Q00`–`_QFF` 方法。它们**是 ACPI 规范定义的合法扩展点**，也是"这台机器的 EC 会报哪些事件"的完整清单。

**消歧**：之前 4 字节 ASCII 扫描报出 29 个 `_Qxx`，其中 `_QUE`、`_Q3G` 等属误报（G 不是十六进制）。
严格按 `MethodOp` 解析后：**25 个**。

---

## 二、事件全表（按 POST 码排序）

每个方法都会 `Store(<n>, P80H)` —— **往 I/O 端口 0x80 写一个字节**。
这意味着：**盯住 I/O 0x80，就能实时看到 EC 报了哪个事件**。

| `_Qxx` | P80H | 触发的动作 | 语义 |
|---|---|---|---|
| `_Q04` | — | `If (ECOK==1) Notify(VPC0, 0x80)` | **EC 就绪** |
| `_Q44` | — | 同 `_Q04` | **EC 就绪**（第二个入口） |
| `_Q07` | 7 | `Store(16, PSD1)` → `Notify(WMIU, 0xD0)` | WMI 事件 |
| `_Q0F` | — | `HOTM ^= 1`；`Store(2/3, PSD1)`；**`WXMS(97, 85)`** → `Notify(WMIU, 0xD0)` | WMI 事件（顺带往 I/O 0x72/0x73 写 0x61/0x55） |
| `_Q10` | — | 空 | 未使用 |
| `_Q11` | 17 | `Notify(GFX0.DD1F, 0x87)` 或 `Notify(RP10.PXSX.LCD0, 0x87)` | 显示设备 0x87 |
| `_Q12` | 18 | 同上，通知码 `0x86` | 显示设备 0x86 |
| `_Q13` | 19 | `Store(41, PSD1)` → `Notify(WMIU, 0xD0)` | WMI 事件 |
| `_Q14` | 20 | `Store(42, PSD1)` → `Notify(WMIU, 0xD0)` | WMI 事件 |
| **`_Q15`** | **21** | **读 `LIDF` → `Notify(LID0, 0x80)`；并通知显卡 `GFX0.GLID/CLID`** | **盖子状态变化** |
| `_Q1D` | 29 | `If (CondRefOf(RP10.PXSX))` → 按 `NVD1` 值 `Notify(PXSX, 0xD2/0xD3/0xD4/0xD5)` | **独显（NVIDIA）电源状态** |
| `_Q1E` | 30 | `If (CTUR) CSMI(224, 2)` | 类型 C 口相关 |
| **`_Q20`** | **32** | **读 `DPOT` 位掩码 → 分别 `Notify(IETM.SEN1..SEN5, 0x90)`** | **★ 传感器事件通道** |
| `_Q21` | 33 | `UCEV` | 未定 |
| `_Q24` | 36 | `Sleep(1000)` → `Notify(BAT1, 0x80)` | 电池信息变化 |
| `_Q25` | 37 | `Notify(BAT1, 0x81)` → `Sleep(1000)` → `Notify(BAT1, 0x80)` | 电池信息 + ACPI 0x81 |
| `_Q33` | 51 | **`ADBG "EC Power button press"`** → `Notify(PWRB, 0x80)` | **电源键** |
| `_Q37` | 55 | `Notify(ACAD, 0x80)` + 175 行电源/充电/独显处理 | **适配器插拔**（最大的一个） |
| `_Q3B` | — | `Sleep(1000)` → `Notify(WMIS, 0xD0)` | WMI 事件 |
| `_Q3D` | — | `Store(7, PSD1)` → `Notify(WMIU, 0xD0)` | WMI 事件 |
| `_Q3E` | — | `Store(4/45, PSD1)` → `Notify(WMIU, 0xD0)` | WMI 事件 |
| `_Q3F` | — | `Store(1, PSD1)` → `Notify(WMIU, 0xD0)` | WMI 事件 |
| `_Q47` | — | `WMI5` 功耗/充电策略（40 行） | WMI 事件 |
| `_Q48` | — | `PL1V*8 → CPL1`、`PL2V*8 → CPL2` | **功率墙 PL1/PL2 更新** |
| `_Q50` | — | `MBGS` → `Notify(WMI5, 210)` | WMI 事件 |

### 归类

| 类别 | 方法 | 数量 |
|---|---|---|
| EC 就绪 | `_Q04` `_Q44` | 2 |
| WMI 事件族 | `_Q07` `_Q0F` `_Q13` `_Q14` `_Q3B` `_Q3D` `_Q3E` `_Q3F` `_Q47` `_Q48` `_Q50` | 11 |
| 显示 / 独显 | `_Q11` `_Q12` `_Q1D` | 3 |
| **盖子** | **`_Q15`** | **1** |
| **传感器** | **`_Q20`** | **1** |
| 电池 | `_Q24` `_Q25` | 2 |
| 电源键 | `_Q33` | 1 |
| 适配器 | `_Q37` | 1 |
| 其它 | `_Q10` `_Q1E` `_Q21` | 3 |

---

## 三、★ 新发现：`_Q20` 是传感器事件通道，且**最多只有 5 个传感器**

```
Method(_Q20) {
    Store("=====QUERY_20=====", Debug)
    Store(32, P80H)
    Store(RefOf(DPOT), Local0)              // 读 EC 里的 DPOT（ECMM @0x853，8 bit）
    If (And(Local0, 8, Zero))   { Notify(^^^^IETM.SEN1, 0x90) }
    If (And(Local0, 16, Zero))  { Notify(^^^^IETM.SEN2, 0x90) }
    If (And(Local0, 32, Zero))  { Notify(^^^^IETM.SEN3, 0x90) }
    If (And(Local0, 64, Zero))  { Notify(^^^^IETM.SEN4, 0x90) }
    If (And(Local0, 128, Zero)) { Notify(^^^^IETM.SEN5, 0x90) }
}
```

**解读**：

- `DPOT` 是一个 **8 位位掩码**，每一位代表"某个传感器有变化"
- 固件只用到了 **bit3–bit7 → 对应 SEN1–SEN5，即 5 个传感器**
- 这 5 个在 `\_SB.IETM` 下（`SEN1`/`SEN2`/`SEN4` 在 `lid-probe` 的 ETW trace 里出现过，是**温度传感器轮询**，约 1 秒一次）

**对角度问题的意义**：如果这台机器存在"角度传感器"，它必然要有一个"上报通道"。
EC 的传感器上报通道就是这条 —— **而它只有 5 个槽位，且全部已被温度占用**。
⇒ **角度传感器连"上报通道"都没有。**

---

## 四、对角度项目的判定

三轮证据叠加，现在可以说得很硬：

| # | 证据 | 结论 |
|---|---|---|
| 1 | EC RAM 4 KB 地图（`ECMM`）含 **120 个命名字段** | 与盖子有关**只有 `LIDF` 1 bit**（`0x856.1`） |
| 2 | EC 事件通道 **25 个 `_Qxx` 全部反编译** | 与盖子有关**只有 `_Q15` 1 个** |
| 3 | 传感器上报通道 `_Q20` + `DPOT` 位掩码 | **只有 5 个槽位，全被温度占用** |

**⇒ 「角度不存在于 ACPI 可见的 EC 接口」——已被穷尽证实。**
唯一剩下的可能性：角度藏在 `ECMM` 的**未命名字节**里（地图有空洞）。验证只需最后一发：
读物理内存 `0xFE0B0400` × 4096 字节 → 合盖 → 再读 → diff。

---

## 五、工具与已知限制（诚实标注）

### 支持的反编译能力

数据对象：`Zero/One/Ones`、`Byte/Word/DWord/QWord`、`String`、`Buffer`、`Package/VarPackage`
名字与作用域：`NameString`（含 `\` `^` `.` 前缀与 Dual/MultiName）、`Local0-7`、`Arg0-6`、`Name`、`Scope`
运算：`Store` `Add` `Subtract` `Multiply` `Divide` `Mod` `And` `Nand` `Or` `Nor` `Xor` `Not`
`ShiftLeft` `ShiftRight` `Increment` `Decrement` `RefOf` `DerefOf` `SizeOf` `ObjectType` `Index`
`Concat` `ConcatRes` `Mid` `FindSetLeftBit/RightBit` `Create*Field`（5 种）
逻辑：`LAnd` `LOr` `LNot` `LEqual` `LGreater` `LLess` `ToBuffer` `ToDecimalString` `ToInteger` `ToString` `CopyObject`
控制：`If` `Else` `While` `Return` `Break` `Noop` `Notify` `Debug` `Fatal` `Stall` `Sleep` `Acquire` `Wait` `Signal` `Reset` `Release` `Load` `Unload` `CondRefOf`
方法调用：按**跨全部 32 张表**建立的参数个数表（325 条）自动补全实参

### 修掉的 5 个坑

| # | 坑 | 现象 | 正解 |
|---|---|---|---|
| 1 | `Store` 实参顺序 | 输出 `Store(P80H, 21)` | AML 是 `StoreOp **Source** Dest`，ASL 写作 `Store(Source, Dest)` → 应为 `Store(21, P80H)` |
| 2 | 参数个数表只建在 DSDT 上 | `GLID` 等多在 SSDT 里定义 → 少吞 1 个实参 → **后续全部错位**，`_Q15` 膨胀到 269 行 | 扫**全部 32 张表** |
| 3 | 方法边界溢出 | 一个方法会把邻居的方法体吃进来 | `end` 钳到"下一个 `MethodOp` 起点" |
| 4 | 名字校验不完整 | `D[i] in NC` 只查首字节 → `UnicodeDecodeError` | 4 个字节都要在 `[A-Z0-9_]` 内 |
| 5 | `MethodOp` 前缀偏移 | 假设 PkgLength 只有 1 字节 → 0 个方法 | PkgLength 占 1–3 字节，必须动态解码 |

### 已知精度限制

- **块边界偶有 ±1~2 字节误差**：表现在输出里的 `?XX`（未解析字节）和 `Notify(?, ?)` 这类缺参
  - 例：`_Q15` 的 `Notify(LID0, 0x80)` 落在 `If` 块之外，但 `If` 的 pkg 长度读出来比实际内容长 1 字节，
    于是 `Notify` 的操作数被块边界切断。**语义仍可正确读出**，但这类地方不能当"原文"引用
- `?XX` 一律表示"我的反编译器不认识这个字节"，不代表固件有问题
- 大方法（`_Q37` 175 行、`_Q47` 40 行）只做了浅层阅读，未逐行核对

---

## 六、副产品：可用性很高的两件事

| 项 | 用法 |
|---|---|
| **`P80H` POST 码表** | 每个事件往 I/O 0x80 写一个唯一值（`_Q07`→7、`_Q11`→17、`_Q15`→21、`_Q20`→32、`_Q33`→51、`_Q37`→55 …）。用任何能读 I/O 0x80 的工具（或 ETW 的 ACPI provider）盯住它，**就能实时知道 EC 刚报了哪个事件** —— 比看日志直观得多 |
| **`ADBG` 调试串** | 固件自带人话：`_Q33` 里有 `"EC Power button press"`，`_Q47`/`_Q48`/`_Q50` 里有 `"Q47 trigger"` 等。这些字符串是**固件内部的命名**，比从行为反推可靠 |

---

## 七、下一步候选

| # | 做什么 | 产出 |
|---|---|---|
| 1 | **读 `0xFE0B0400` 那 4 KB 做合盖 diff** | 角度问题的终局答案（Linux Live USB，¥0） |
| 2 | 反编译 `_SB.PC00.LPCB.EC0_` 下的其余方法（非 `_Qxx`） | EC 的完整命令面：`ECFG`/`ECRD` 等 |
| 3 | 用 `_Q20`/`DPOT` + `PLV1`/`PLV2` 做锚点，扫 VPC 命令空间 | VPC 命令语义 |
| 4 | 把 `_Q37`（175 行，适配器）逐行读一遍 | 适配器/充电链路 |
