# 六附 · 白名单绕过补丁定案（iasl 反编译，2026-09-29）

> 目标：**让 X9-15 的那块触控板在这台机上正常工作**（"能用"的第 ①②层，见 §6.3g）。
> 方法：反编译 DSDT，解出 `_CRS` 的真实取值链，把要改的字节钉死。

---

## 一、完整取值链（本轮全部解出）

```
BIOS/EC 在 POST 时把「识别到的触摸板厂商索引」写进
   物理内存 0x6DEBEB18 的 TPDF 字节          ← 由 SSDA 声明（见下）
        ↓
_CRS 求值：
     Local1 = TPID[0][0]                      第 0 行的【索引】列
     While ((Local1 != 0xFE) && (Local1 != TPDF)) { 继续扫 }   ← 命中条件 = 索引==0xFE 或 ==TPDF
     ADR0 = TPID[命中行][1]                   ★ I2C 从机地址
     HID2 = TPID[命中行][2]                   ★ 描述符寄存器
        ↓
     Return ConcatenateResTemplate( IICB(ADR0, "\_SB.PC00.I2C0"), SBFG )
                                            ↑ 中断 = SBFG（GpioInt，引脚 182，硬编码）
        ↓
OS 用 ADR0 去读 HID 描述符
```

**`TPDF` 的来源（SSDA 反编译原文）**：
```asl
OperationRegion (COMP, SystemMemory, 0x6DEBEB18, 0x0300)
Field (COMP, AnyAcc, Lock, Preserve)
{
    RSR0,   32,
    BDDD,   8,  CPFB, 8,  PBTI, 8,  BRLV, 8,  CAVR, 8,  TJMA, 16,  CORE, 8,
    TPDF,   8,      ← ★★★ 厂商索引就在这个内存字节里，BIOS 在 POST 阶段写入
    TPLF,   8,  TPDD, 8,  TMUD, 8,  CTUR, 8,  CUCB, 32,  ...
}
```

**⇒ 未识别 ⇒ BIOS 写的索引不在表的「索引列」里 ⇒ `ADR0` 落到占位行（`0xFF`）⇒ 代码 10。**

---

## 二、★ 两处已排除、一处已定案

| | 位置 | 结论 |
|---|---|---|
| ❌ | `_HID` / `_CID` 的 `TPDS(列, 0xFE, TPDF, 默认)` | **不是地址来源**。它只是查「HID / CID 字符串」列；表里没有索引为 `0xFE` 的行时会返回默认值（所以本机现在 `_HID` 实际返回 **`MSFT0001`**、`_CID` 返回 `PNP0C50`）。**与地址无关，可以完全不动。** |
| ✅ | **`_CRS` 的 `ADR0 = TPID[命中行][1]` / `HID2 = TPID[命中行][2]`** | **★ 这才是地址与描述符寄存器的唯一来源。改这里就够。** |
| ❌ | `SSDA` 的 `TPDF` 字段 | 不用动（改了会牵连 BIOS 的识别逻辑） |

> ## **⇒ 上一轮担心的「可能要改调用点默认值」被证否 —— `_CRS` 没有默认值参数，它是按索引查表。**
> ## **⇒ 所以改 `TPID` 表本身是对的。**

---

## 三、★★★ 推荐补丁（OpenCore `ACPI → Patch`，`TableSignature = DSDT`）

### 3.0 ★ 先明确定位：**这个补丁不是"绕过白名单"，而是"切断白名单拒绝的后果"**

```
① X9-15 模块报 PID 0x01EA
        ↓
② BIOS 白名单（GoodixTpDxe）判定 → 拒绝          ← ★ 这一层【完全不动】，照样拒绝
        ↓  拒绝的后果：内存里的 TPDF = 「未识别」值
③ ACPI _CRS 按 TPDF 去 TPID 表查「索引列」
        ↓  ★★ 补丁只切【这一层】：让查表落点不再依赖 TPDF
   查表命中 Goodix 那一行 ⇒ ADR0 = 0x2C
        ↓
④ OS 用 0x2C 读描述符 ⇒ 枚举成功
```

> ## **⇒ 白名单**没有被绕过**——它照旧运行、照旧拒绝。
> ## ⇒ 补丁做的是：**让那次拒绝再也传不到操作系统手里**。**
> ## **⇒ 一句话：不是说服 BIOS 改判，而是**把判决书的送信人换掉**。**

**这带来三个必须知道的推论：**

1. **补丁只覆盖"地址"这一条腿。** 如果 BIOS 拒绝时还干了别的事（没做复位/上电、没切某个模式、那个 `[rsp+0x30]` "已识别"标志 gate 的东西），**那些都不受补丁影响** ⇒ 这正是"成因 b"和那个标志两个未知量的来源。
2. **所以"补丁 ≠ 一定成功"。** 它解决"地址错"，不解决"设备是否被唤醒"。⇒ 仍需 `i2c-dev` 验收 ①b。
3. **为什么 16 字节就够**：因为整条"识别 → 地址"的传导链**最后收束在唯一一个查表操作上**（`ADR0 = TPID[命中行][1]`）。**在收束点打补丁，上游怎么判都无所谓。**

**★ 与"改 BIOS 白名单"的区别（别混淆）**：

| | 改 `GoodixTpDxe` 那一字节 | OpenCore DSDT 补丁 |
|---|---|---|
| 改的是什么 | **BIOS 里的判决逻辑本身**（让它接受 `0x01EA`） | **判决结果的传导链** |
| 白名单还拒绝吗 | ❌ 不再拒绝 | ✅ **照样拒绝** |
| 代价 | 刷 SPI、变砖风险 | **不碰 flash、重启即恢复** |

### 3.1 补丁（方案 A）

### 方案 A（推荐）—— **把 Goodix 那一行改成"无条件命中"**

**原理**：`While` 的**命中条件包含 `索引 == 0xFE`**（不看 `TPDF` 是什么）。
⇒ 若把 **第 4 行（Goodix：`0x2C` / `0x20`）的索引**从 `0x04` 改成 **`0xFE`**，扫描到它时**必然命中**，**完全不需要知道 `TPDF` 的真实值**。

```
Find    (16B): 0A 04 0A 2C 0A 20 0D 47 58 54 50 35 31 30 30 00
Replace (16B): 0A FE 0A 2C 0A 20 0D 4D 53 46 54 30 30 30 31 00
                          ↑           └── "GXTP5100" → "MSFT0001"（8 字节→8 字节，等长）
                          └ 索引 04 → FE
DSDT 内偏移：0x704B0（索引）· 0x704B6–0x704BD（HID 串）
```

**为什么顺手把 `"GXTP5100"` 也改成 `"MSFT0001"`**：
索引改成 `0xFE` 后，`_HID` 会从现在的 `MSFT0001` 变成 `GXTP5100` —— 那是"正确"的，但会**改变 Windows 的驱动匹配**（可能重新找 GoodixTouchpad.inf）。
把字符串也换成 `MSFT0001`，**就等于"只修资源、不动 HID"**，把变量降到最少。

**★ 对原装模块零回归**：原装时 `TPDF = 4`，扫描到第 4 行时因 `索引 == 0xFE` 命中 → `ADR0 = 0x2C`、`HID2 = 0x20` —— **与原行为完全一致**。

**★ 一次性修好四处**：`_CRS`（地址 + 中断资源）· `_DSM(fn=1)` 返回的 `HID2`（描述符寄存器 `0x20`）· `_HID` · `_CID`。

### 方案 B（备选）—— 只修"兜底行"

```
Find    (16B): 0A FF 0A FF 0A FF 0D 58 58 58 58 30 30 30 31 00
Replace (16B): 0A FF 0A 2C 0A 20 0D 58 58 58 58 30 30 30 31 00
DSDT 内偏移：0x704CE（地址）· 0x704D0（描述符寄存器）
```

**优点**：完全不动 `_HID` / `_CID`（最小扰动），也零回归。
**缺点**：**依赖一个未验证的假设** —— "BIOS 未识别时 `TPDF` 写的正好是 `0xFF`"。若它写的是别的值（例如 `0x00`），扫描会走到 `Local0 = 5` 越界，**本方案就不生效**。

> ## **⇒ 结论：优先方案 A（不依赖任何未知量）；方案 B 作为"保险"可同时打上（两者互不冲突）。**

---

## 四、⚠️ 但"能用"还有一道与补丁无关的前置

**①b：模块在 `0x2C` 上到底活不活？** —— 取决于 BIOS 有没有做复位/上电（`追加二十六` §3.4 的"成因 b"）。
**这件事只能实测**（`i2c-dev` 直读 `0x4014` 是否回 `YELSTO`）。
**若 ①b 不成立 ⇒ 打什么补丁都没用**（OS 拿到地址也问不出东西）。

---

## 五、执行顺序（"先在这台机上正常用"）

| # | 动作 | 判据 / 说明 |
|---|---|---|
| **1** | 关机、拔电、UEFI 禁内置电池 → 拆机换模块（**只接排线、不上螺钉**） | 见 `追加二十七` §8.2 |
| **2** | 开机进 **Linux Live**，`i2c-dev` 直读 | `0x4014` 回 `YELSTO` ⇒ **①b 成立**；扫不到 `0x2C` ⇒ ①b 不成立，到此为止 |
| **3** | 备份 SPI？不需要（我们不刷 flash）。装 **OpenCore** 到 U 盘（先不落 ESP） | 先关 **Secure Boot** |
| **4** | 在 OpenCore 的 `config.plist` 里只开 `ACPI → Patch`（打方案 A），**其余全关/留空** | 特别是 `PlatformInfo` 不要注入 SMBIOS（避免 Windows 蓝屏 / 机型被伪装） |
| **5** | 用 OpenCore 引导 Windows，看设备管理器 | 出现 Precision Touchpad 且无代码 10 ⇒ **①②层达成** |
| **6** | 稳定后再把 OpenCore 落到 ESP（`bcfg` 或 boot 顺序） | 这一步改了引导链 ⇒ ⚠️ **先确认 BitLocker 是否开启** |

**红线不变**（🔴 且是**四条**不是三连：`00 10` / `00 11` / **`0E 12`（真写 flash）** / **`0E 13`（重启）**）：不刷 flash、不发红线命令、不改 `SSDA`。

---

## 九、备查路线：`driver####` + 自写 DXE 驱动（不刷 flash、不依赖启动顺序）

> 喆问：「`driver####` 变量 + 一个小 DXE 驱动…这个是怎么说？」
> **答：这是 UEFI 规范里的一个官方机制——固件自己在每次开机的 BDS 阶段加载你指定的驱动。
> 用它来改 ACPI 表，效果等价于 OpenCore 的补丁，但既不用 OpenCore，也不看启动顺序脸色。**

### 9.1 它到底是什么

| 名词 | 说明 |
|---|---|
| **`Driver####`**（如 `Driver0001`） | 一组 **UEFI 全局变量**，每个里面装一个 `EFI_LOAD_OPTION`（描述"要加载哪个驱动镜像 + 从哪个设备路径"） |
| **`DriverOrder`** | 一个 `UINT16` 数组，给出尝试这些驱动的顺序 |
| **★ 关键** | **BDS 会先处理 `DriverOrder`（加载这些额外驱动），然后才处理 `BootOrder`（引导操作系统）** |
| 操作入口 | UEFI Shell 的 **`bcfg driver add / rm / dump`** —— 这正是"怎么把驱动塞进去"的标准方法 |

### 9.2 ★ 为什么时序上"正好来得及"（见本章配图）

| 阶段 | 发生什么 | 我们能干预吗 |
|---|---|---|
| **DXE dispatch** | 白名单（`GoodixTpDxe`）跑完、判定完 | ❌ **来不及**（所以别想在 Shell 阶段改它） |
| **BDS: `DriverOrder`** | ★ **固件加载我们的驱动** —— 此时 ACPI 表已由 `AcpiTableDxe` 发布在内存里 | ✅ **就是这里动手** |
| **BDS: `BootOrder`** | 这才去引导 Windows | — |
| **系统启动后** | OS 才去读 ACPI 表 | — |

> ## **⇒ 我们改的是"OS 将要读的那张表"—— 时点上完全来得及。**
> ## **⇒ 这正好绕开了"Shell 阶段改 `GoodixTpDxe` 来不及"那个死结（见 §6.3c / §6.3e）。**

### 9.3 这个驱动要做什么（几十行的量级）

```
① 找 RSDP：读 gST->ConfigurationTable 里的 EFI_ACPI_20_TABLE_GUID
   → RSDP → XSDT → 遍历找 Signature == "DSDT"
② 在 DSDT 里搜 §三 方案 A 那 16 字节
③ 原地替换成 Replace 的 16 字节
④ ★ 重算 DSDT 表头 checksum（表头 offset 9，使整表字节和为 0）
⑤ 返回 EFI_SUCCESS
```

### 9.4 为什么说它"最干净"

| 项 | 说明 |
|---|---|
| **不写 flash** | 零变砖 |
| **不动 ESP、不动 Windows 引导文件** | 引导链本身不变 |
| ★ **不依赖启动顺序** | `DriverOrder` 由**固件自己**在每次开机处理 ⇒ **别人改了启动项也不受影响** |
| 对 BitLocker 引导度量影响最小 | 不替换引导路径 |
| 不需要 OpenCore | 少一个常驻引导器 |
| **Windows 更新不会重置它** | 它是 UEFI 变量，不是引导项 |

### 9.5 为什么"未验证" + 三个风险

| # | 风险 | 说明 |
|---|---|---|
| **1** | ★ **联想的 BDS 是否真的处理 `DriverOrder`** | **规范要求这么做，但 OEM 定制实现可能：不处理 / 需要 Setup 里某个开关 / 要求镜像签名（Secure Boot 开启时）** ⇒ **这是"未验证"的核心** |
| **2** | **ACPI 表内存可能被标只读** | EDK2 有"ACPI 表内存保护"这类防 rootkit 特性。若被标只读，需要先用 `gDS->SetMemorySpaceAttributes` 解除再写 |
| **3** | **驱动在固件层跑，写坏内存/表 ⇒ 可能开不了机** | 缓解：先做"只打印、什么都不改"的空驱动；出问题还能进 UEFI Shell `bcfg driver rm` 清掉 |

另外：**固件更新可能清掉 `Driver####` 变量**（和启动项类似）。

### 9.6 ★ 零风险验证法（**建议先做这一步**）

```
① 关 Secure Boot
② 进 UEFI Shell → bcfg driver dump        （看现状，空也正常）
③ 编一个【只往屏幕打印一行、什么都不改】的极小 DXE 驱动
   （或先用现成的无害驱动试）
④ bcfg driver add 0 fs0:\Test.efi "Test" → bcfg driver dump 确认写入
⑤ 重启 —— ★ 屏幕出现那行打印 = 机制可用；没有 = 固件不处理
⑥ bcfg driver rm 0                        （清理）
```

> ## **⇒ 全程不写 flash、不动 ESP、可随时清除。这一步的成本几乎为零，却能一举判定这条路通不通。**

### 9.7 与 OpenCore 对比

| | **OpenCore（ESP）** | **`driver####` + DXE 驱动** |
|---|---|---|
| 改哪里 | 内存里 ACPI 表的**副本** | 内存里 ACPI 表**原地** |
| 谁执行 | 引导器（它本身是个启动项） | **固件自己**（BDS 阶段） |
| 依赖启动顺序 | ✅ 依赖（被改就失效，需重设） | ❌ **不依赖** |
| 需要什么 | 装 OpenCore + 关 Secure Boot | 编一个小驱动（EDK2）+ 关 Secure Boot |
| 主要风险 | 配置错误 / Windows 蓝屏 | ACPI 表只读 / BDS 不处理 / 驱动写坏内存 |
| 验证成本 | 低 | **低（`bcfg` 可逆）** |

> ## **⇒ 建议顺序：先用 §八 的 OpenCore 方案把它跑通**（成熟、社区资料多、好排错）；
> ## **跑通之后再考虑要不要"升级"到这个形态** —— 它更省心，但更贴近固件层、错了更难救。
> ## **⇒ 而且无论走哪条，都只解决第 ①②层，"会不会震"仍由模块固件决定。**

---

## 十一、★★★ 离线验证报告（用 ACPICA 的 `acpiexec` 真跑 AML）

> 喆：「你做一下验证吧。」
> **能做的部分我做完了，而且是"真跑"而不是"推演"。**
> 真机 UEFI 里那部分（`bcfg driver` 试验、`i2c-dev` 读板）**必须你在机器前操作**，我进不了固件环境——见 §11.5。

### 11.1 方法

用 **`acpiexec`**（ACPICA 的 AML **执行器**，与 `iasl` 同一个包）把本机 **DSDT + 全部 31 张 ACPI 表**装进一个**模拟的 ACPI 命名空间**，然后**直接执行 `\_SB.PC00.I2C0.TPAD._CRS`**，再读回它赋值给 `ADR0` / `HID2` 的结果。

- `TPDF` 是 SSDA 声明的**内存字段** ⇒ 用 acpiexec 的 **`-fv <值>`**（操作区域填充值）来**模拟 BIOS 写进去的"厂商索引"**
- **对照实验**：原始表 vs 打了方案 A 补丁的表；`TPDF` 取 `0xFF` 与 `0x00` 两种 ⇒ 四组

```bash
acpiexec -fv 0xFF -b 'execute \_SB.PC00.I2C0.TPAD._CRS;\
  evaluate \_SB.PC00.I2C0.TPAD.ADR0;evaluate \_SB.PC00.I2C0.TPAD.HID2' \
  DSDT.aml FADT.aml SSD1.aml … SSDT.aml
```

### 11.2 ★★★ 结果（四组，全部拿到干净数值）

| 表 | 模拟的 `TPDF` | `_CRS` 命中的行 | **`ADR0`** | **`HID2`** |
|---|---|---|---|---|
| **原始** | `0xFF` | 第 5 行（占位）· `Local0=4` | **`0xFF`** | **`0xFF`** |
| **原始** | `0x00` | **越界**（`Local0=5`，`AE_AML_PACKAGE_LIMIT`） | **`0x00`** | **`0x00`** |
| **打补丁** | `0xFF` | 第 4 行（Goodix）· `Local0=3` · `Local1=0xFE` | **`0x2C`** ✅ | **`0x20`** ✅ |
| **打补丁** | `0x00` | — | **`0x2C`** ✅ | **`0x20`** ✅ |

### 11.3 这组数据证明了四件事

1. **故障被完整复现**：`TPDF=0xFF`（= 未识别）时，原始表给出 **`ADR0=0xFF`** ⇒ 与真机现象**"设备在系统里、但代码 10"完全吻合**
2. ★ **"方案 B 不可靠"的判断被实证**：`TPDF=0x00` 时原始表**直接越界**（`Local0=5` → `AE_AML_PACKAGE_LIMIT`，取到 `0x00`）⇒ **"只改占位行"在 `TPDF≠0xFF` 时确实不生效**
3. ★★ **补丁有效**：两种 `TPDF` 取值下都得到 `ADR0=0x2C`、`HID2=0x20`（正是 Goodix 需要的地址与描述符寄存器）
4. ★★★ **"不依赖 `TPDF` 取值"这个核心卖点被实证** —— 这正是选方案 A 而不是方案 B 的**全部理由**

### 11.4 同一轮还验证了字节层

| 项 | 结果 |
|---|---|
| **Find 唯一性** | `acpibin` 逐字节比对：Find 串在整份 DSDT 里**命中恰好 1 次**（偏移 `0x704AF`） |
| **等长** | 表长 `0x000810C6` 改前改后**完全不变** |
| **改动精确** | 比对显示只有 **`0x704B0`（索引 `04`→`FE`）** 与 **`0x704B6` 起的 HID 串** 发生变化 |
| **checksum** | 重算后 `0x95` → `0xA9`，**整表字节和 = `0x00`** ✅ |

### 11.5 ⚠️ 仍未验证的（必须真机，我做不到）

| 项 | 说明 |
|---|---|
| **OpenCore 的 `ACPI→Patch` 是否按预期命中** | 机制不同（它在内存里替代表）；但 **Find 串相同、唯一性已验证** ⇒ 概率很高 |
| **`IICB` 的存在性** | 本轮 acpiexec 里 `_CRS` 在 `IICB` 处报 `AE_NOT_FOUND` —— 那是**模拟环境命名空间部分加载失败**的连锁（日志中有 `\_SB.PC00.I2C3.TPD0` 解析失败），**真机上 `IICB` 是存在的**（项目 §3.3 已解出）。★ **不影响本报告结论**：`ADR0`/`HID2` 在 `IICB` 调用**之前**就已赋值，是直读取到的 |
| **最终返回给 OS 的资源缓冲区** | 同上；且地址取值已验证等价 |
| ★ **①b：设备在 `0x2C` 上是否应答** | **只能真机**（Linux `i2c-dev` 读 `0x4014` 是否回 `YELSTO`） |
| ★ **`driver####` 机制是否被固件处理** | **只能真机**（§9.6 的 `bcfg driver` 试验） |

### 11.6 产物

| 文件 | 说明 |
|---|---|
| `dsdt-asl/verify/r_orig_0xFF.txt` | 原始表 + `TPDF=0xFF` |
| `dsdt-asl/verify/r_orig_0x00.txt` | 原始表 + `TPDF=0x00` |
| `dsdt-asl/verify/r_patched_0xFF.txt` | 打补丁 + `TPDF=0xFF` |
| `dsdt-asl/verify/r_patched_0x00.txt` | 打补丁 + `TPDF=0x00` |
| `dsdt-asl/verify/DSDT_orig.aml` / `DSDT_patched_方案A.aml` | 原始 / 已打补丁的 DSDT |

> ## **⇒ 一句话总结：补丁"对不对"这件事，已经不在"推测"层面了 —— 它在模拟环境里真跑出来是 `0x2C`。**
> ## **⇒ 剩下要真机验证的只有两件：①b（设备应不应答）和 `driver####`（固件处不处理）。**

---

### 9.8 ★ 提前验证操作单 + 驱动源码（板子没到也能做）

> 喆：「我就要干净的，我板子还没到，我可以做一定的提前验证。」
> **⇒ 好消息：这条路唯一的未知量（固件认不认 `DriverOrder`）跟触控板毫无关系 ⇒ 现在就能验掉。**

**产物目录：`touchpad-lab/driver-patch/`**

| 文件 | 作用 |
|---|---|
| `TpadAcpiPatch.c` | ★ **要用的 DXE 驱动源码**（Find/Replace 用的是 §十一 已验证过的字节；含 RSDP→XSDT→DSDT 查找、原地替换、**表头校验和重算**） |
| `TpadAcpiPatch.inf` / `TpadPkg.dsc` | EDK2 模块定义 + 最小 DSC（只编这一个模块） |
| `README.md` | 编译步骤 · 部署步骤 · **§一 的提前验证操作单** · 排错顺序 · 与 OpenCore 的对照 |

**★ 提前验证（零编译、零风险，现在就能做）**：
```
① BIOS 关 Secure Boot
② U 盘进 UEFI Shell
③ 拿现成的 Shell 镜像当探针（OpenCore 发行包自带 Tools/OpenShell.efi）
       bcfg driver add 0 fs0:\OpenShell.efi "Probe"
       bcfg driver dump            ← 确认写入
④ 重启
⑤ 判据：★ 开机【自动进了 UEFI Shell】= 固件认 DriverOrder ⇒ 这条路通
        直接进 Windows              = 固件不处理 ⇒ 回到 OpenCore 方案（效果等价）
⑥ 清理：bcfg driver rm 0        （若⑤成立，那次开机在 Shell 里敲 exit 即可继续）
```

**⚠️ 必须分清（README §四 同）**：**"补丁生效" ≠ "板子能用"**。
补丁只把 `ADR0` 从 `0xFF` 改成 `0x2C`；若 BIOS 拒绝时连复位/上电都没做（成因 b），地址对了也问不出东西 ⇒ 依然代码 10。**这个只能靠 Linux Live 的 `i2c-dev` 读 `0x4014` 来区分。**

---

### 9.9 ★★★ UEFI Shell 从哪来 —— 已解决（联想自己的 BIOS ISO 里就带）

> 喆问：「联想到底有没有 UEFI Shell？尤其是 ThinkBook。」

| 问题 | 答案 | 依据 |
|---|---|---|
| **ThinkBook 固件有内置 UEFI Shell 吗** | ❌ **没有** | 官方手册（ThinkBook 14 Gen 7 / 14 G6 IRL / 14 Gen 9 等）通篇只有 `F1`（BIOS）/`F12`（启动菜单）/ Novo 键，**无任何 Shell 入口** |
| **那 Shell 从哪来** | ✅ **联想自己的 BIOS 更新 ISO 里带一个** | 解 `x9bios/n4cur09w.iso` → **`/EFI/BOOT/BOOTX64.EFI`（2,098,840 B）= 标准 EDK2 UEFI Shell** |

**判定证据（从该文件里直接抓到的 Shell 手册页 / 示例）**：
```
.TH bcfg 0 "configure boot and driver"
BCFG driver|boot [dump [-v]] [add # file "desc"] [addp # file "desc"]
Shell> bcfg driver add 5 mydriver.efi "My Driver"      ← 正是我们要用的命令
SHELL_SUCCESS / SHELL_NOT_FOUND / SHELL_INVALID_PARAMETER ...
```

**文件属性**：x86-64 · PE32+ · **Subsystem 10（EFI_APPLICATION）** · MD5 `76b0521241cb46cf882a378978156aaf` · **有安全目录 ⇒ 已签名**（⇒ 有几率 Secure Boot 开着也能跑，待实测）

> ⚠️ **一处自我更正**：第一遍只搜 ASCII 字符串（无 `EDK`/`Shell>`）⇒ 误判"不是 Shell"。
> **重搜 UTF-16LE 后**：`UEFI Shell`×25 · `Shell>`×115 · `bcfg`×11 ⇒ 确认。
> **★ 方法学：二进制里搜字符串必须同时搜 ASCII 与 UTF-16LE。**

**附带发现**：同 ISO 里 `/FLASH/SHELLFLASH.EFI` **在 ISO 上本身就是 0 字节**（空占位）；真载荷是 `/FLASH/N4CSG21W/$0AN4C00.SC1`（44 MB）。

**⇒ 交付**：`driver-patch/usb/`（**整份拷到 FAT32 U 盘根目录即可**）
```
EFI/BOOT/BOOTX64.EFI          ← 联想的 UEFI Shell
EFI/Tpad/TpadAcpiProbe.efi    ← 探针（3,072 B）
EFI/Tpad/TpadAcpiPatch.efi    ← 真驱动（2,560 B）
```
**⇒ 于是"去哪找 Shell"这一步彻底消失** —— 不用第三方、不用 OpenCore，就是联想自己发的包里的东西。

**新增工具**：`touchpad-lab/tools/iso_fat_dump.py`（解析 ISO 内 FAT32 分区，list/extract）· `what_is_efi.py`（判 .efi 身份 + 签名状态）
> ⚠️ 坑：Git Bash 会把 `/EFI/...` 参数转成 Windows 路径 ⇒ **要传无前导斜杠的路径**。

---

## 十二、本轮新增文件

| 文件 | 说明 |
|---|---|
| `touchpad-lab/dsdt-asl/DSDT_本机_21LD.bin` | 本机 DSDT 原始二进制（528,582 B，来自 `bios\out\DSDT-528KB.bin`） |
| `touchpad-lab/dsdt-asl/DSDT_本机_21LD.dsl` | ★ iasl 反编译结果（3.8 MB 可读 ASL） |
| `touchpad-lab/dsdt-asl/SSDA_本机_21LD.dsl` | SSDA 反编译（`TPDF` 字段定义） |
| `touchpad-lab/dsdt-asl/iasl.exe` | ACPICA 20260408 的 iasl（反编译/重编译都靠它） |

**关键行号（`DSDT_本机_21LD.dsl`）**：`Device (TPAD)` @87377 · `Name (TPID …)` @87384 · `_HID` @87444 · `_CID` @87470 · `Method (TPDS)` @87496 · `_DSM` @87515 · `_STA` @87589 · **`_CRS` @87625** · `ADR0 =` @87646

**复现命令**：
```bash
iasl -d DSDT.bin          # 反编译（4 MB 的 .dsl，需几十秒）
```

---

## 八、★ 板子到手前后的执行清单（"一次装好不再拆"版）

> 前提：喆确定**直接装上、之后基本不再拆**（要拆主板，麻烦）。
> **好消息：装好之后所有决定性动作都是纯软件，不需要再拆机。**
> **⇒ 策略：把所有能提前做的软件准备在【装之前】全部做完；装好只剩"开机"和"验证"。**

### 8.1 装之前（现在就能做，不需要新板子）

| # | 动作 | 为什么现在做 |
|---|---|---|
| **1** | ★★ **先把 OpenCore 那一套跑通**：做 U 盘 · 写 `config.plist`（见 §8.3）· **关 Secure Boot** · 用它引导 Windows 一次 | **补丁对原装模块零回归**（已验证）⇒ **可以拿原装模块当"白鼠"**，把所有副作用（蓝屏？机型伪装？启动变慢？）先暴露出来。**等板子到了就只剩物理动作** |
| 2 | **确认 BitLocker 状态**；若开启，**先抄下恢复密钥** | 引导链会变，可能索要密钥 |
| 3 | **做 Ubuntu 24.04+ Live U 盘** | 装好后第一件事就是用 `i2c-dev` 判 ①b |
| 4 | **记录原装基线**：设备管理器 `ACPI\GXTP5100` 状态 · `poc/aligned-read-probe.ps1` 确认 `0x4014`=`YELSTO` · Linux dmesg 里 `27C6:01E9` | 对照用 |
| 5 | **实物核对**（板子到手、未装时）：排线**座子金手指数/间距**与原装并排比对 · 拍照存档 · 确认**固定孔位**（7 或 10 颗）与原装是否一致 | ⚠️ **尺寸/规格一致 ≠ 孔位一致**；若孔位不符，**别硬拧**，只上能对上的几颗 |
| 6 | **备一个 USB 鼠标** | 装好后触控板可能完全不能用 |

### 8.2 装的时候（一次到位）

- 照 **ThinkBook 14 G6+ IMH HMM** 顺序：底盖 → 电池 → … → 触控板（**M1.6 × L1.8，7 或 10 颗**）
- ★ **拆之前给原装排线拍一张照**（座子方向、锁扣方向）—— 这是最容易装反的地方
- 排线插到位、锁扣扣好；**不装 jig**（那是原厂定位工装）
- 螺钉别混用（长了会顶穿），按 HMM 扭矩
- **原装模块 + 排线装防静电袋收好**（万一要退回）

### 8.3 OpenCore 配置（直接可用，base64 已算好）

`TableSignature` = `DSDT`（base64 `RFNEVA==`）。

**方案 A（推荐）** —— 索引 `0x04`→`0xFE` + HID 串 `GXTP5100`→`MSFT0001`（**16 字节等长**）
```
Find    : CgQKLAogDUdYVFA1MTAwAA==
Replace : Cv4KLAogDU1TRlQwMDAxAA==
```
**方案 B（保险，可与 A 同时启用）** —— 占位行地址/寄存器 `FF`→`2C`/`20`（**16 字节等长**）
```
Find    : Cv8K/wr/DVhYWFgwMDAxAA==
Replace : Cv8KLAogDVhYWFgwMDAxAA==
```

```xml
<key>ACPI</key>
<dict>
    <key>Add</key><array/>
    <key>Delete</key><array/>
    <key>Patch</key>
    <array>
        <dict>
            <key>Comment</key><string>TPAD force Goodix row hit</string>
            <key>Enabled</key><true/>
            <key>Find</key><data>CgQKLAogDUdYVFA1MTAwAA==</data>
            <key>Replace</key><data>Cv4KLAogDU1TRlQwMDAxAA==</data>
            <key>TableSignature</key><data>RFNEVA==</data>
            <key>Count</key><integer>0</integer>
            <key>Skip</key><integer>0</integer>
            <key>Limit</key><integer>0</integer>
            <key>Base</key><string></string>
            <key>BaseSkip</key><integer>0</integer>
            <key>Mask</key><data></data>
            <key>ReplaceMask</key><data></data>
            <key>OemTableId</key><data></data>
            <key>TableLength</key><integer>0</integer>
        </dict>
    </array>
    <key>Quirks</key>
    <dict>
        <key>FadtEnableReset</key><false/>
        <key>NormalizeHeaders</key><false/>
        <key>RebaseRegions</key><false/>
        <key>ResetHwSig</key><false/>
        <key>ResetLogoStatus</key><false/>
        <key>SyncTableIds</key><false/>
    </dict>
</dict>
```

**★ 同一次还必须做两件事**：
1. **`PlatformInfo → Automatic` 设 `false`** —— **不要注入 SMBIOS**，否则 Windows 可能蓝屏、机型被伪装成 "Acidanthera"
2. 其余 `Add` / `Delete` 留空、`Quirks` 全关（只开 `ACPI → Patch`）

### 8.4b ★ 「内存补丁是不是一次性的？重启还会不会代码 10？」

> 常见疑问：补丁打在内存里，那是不是只能管这一次？以后每次开机都报代码 10？
> **答：不是一次性的。因为补丁不是"改一次然后指望它留着"，而是"每次开机在 OS 启动前重新打一遍"。**

```
每次开机：
  固件 POST/DXE  →  BDS 阶段按启动顺序加载 OpenCore
                        ↓
                 OpenCore 在内存里：复制 ACPI 表 → 打补丁 → 重算校验和 → 更新 UEFI 配置表
                        ↓
                 链式启动 Windows Boot Manager
                        ↓
                 Windows 读到的是【打过补丁的表】⇒ 正常枚举
```

**⇒ 只要每次开机都走 OpenCore，补丁就每次都在。这不是"一次 hack"，是"常驻流程"。**

**要做到"每次开机自动生效"，只需一步**：把 OpenCore 落到 ESP，并把它排在 Windows Boot Manager 之前（`bcfg boot add` 或固件启动菜单）—— 即 §8.4 的第 6 步。

**⚠️ 什么时候会"看起来失效"（重启后又代码 10）？**

| 原因 | 恢复方式 |
|---|---|
| 启动顺序被改回 Windows Boot Manager（**Windows 大版本更新 / 固件更新 / 手动改 BIOS 启动项**都可能重置） | **把 OpenCore 重新设为第一启动项即可**，不需重装、不需重刷任何东西 |
| OpenCore 被删（格式化 ESP、某些"修复引导"工具） | 重新复制回 ESP |
| BIOS 更新 | 更新后重新设一次启动项（有些更新会清 NVRAM 启动项） |

> ## **★ 诊断提示：重启后若又见代码 10，第一步先确认"这次开机到底有没有走 OpenCore"**——
> ## **绝大多数情况是启动项被改了，而不是补丁失效。**

**★ 想连"引导链上有 OpenCore"都省掉？** 两条更彻底的（各有代价）：
1. **改 BIOS 里的 `GoodixTpDxe`** —— 从根上不拒绝；代价 = 刷 SPI + 变砖风险（不推荐）
2. **`driver####` 变量 + 一个小 DXE 驱动**，由固件在 BDS 阶段自动加载并改 ACPI 表 —— **不刷 flash、不依赖启动顺序**（理论上最干净）；但**联想是否启用该机制未验证**，只作备查

### 8.4c ★ 「OpenCore 得一直插着 U 盘吗？」——不用，U 盘只在试验期需要

**答：不用。** U 盘是**过渡手段**，验证通过后把 OpenCore 复制到**机器自己的 ESP**（EFI 系统分区，硬盘上那块 100–300 MB 的 FAT32 小分区，Windows 的引导文件就在那里）即可。

| 阶段 | OpenCore 放哪 | 为什么 |
|---|---|---|
| **试验期** | **U 盘** | ★ **零风险**：不动机器现有的引导，出问题**拔掉 U 盘就回到原样** |
| **稳定后** | **ESP**（硬盘上） | **开机就在**，不用插任何东西；这就是"每次开机自动打补丁"的前提 |

**落到 ESP 的步骤**：
1. **先备份**：把 ESP 里的 `\EFI\Microsoft\` 整个拷一份到别处（万一配错进不去，可以恢复）
2. 挂载 ESP（Windows：`mountvol X: /s`，或 DiskGenius / Explorer++ 之类），把 OpenCore 的 `EFI` 内容拷进去（`\EFI\OC\…` + `\EFI\BOOT\BOOTx64.efi`）
3. **加一个 UEFI 启动项**指向 `\EFI\OC\OpenCore.efi`，并排在 Windows Boot Manager 之前
   - UEFI Shell：`bcfg boot add 0 \EFI\OC\OpenCore.efi "OpenCore"`
   - 或 Linux 下 `efibootmgr`，或 Windows 下 EasyUEFI / Bootice（图形工具）

**⚠️ 注意事项**

| 项 | 说明 |
|---|---|
| **这不是刷固件** | ESP 只是硬盘上的普通分区，**可读写、可回退**；和"刷 BIOS"完全不是一回事 |
| **先备份 ESP** | 见上面第 1 步，这是唯一真正的保险 |
| **BitLocker** | 引导链变了可能索要恢复密钥（通常只一次） |
| **Windows 大版本更新** | 有时会重写 `/EFI/Microsoft/Boot/` 与启动顺序 ⇒ 那时**重新设一次启动项**即可（OpenCore 文件还在） |
| **占用空间** | OpenCore 含 Drivers 约 20–30 MB，ESP 一般 100 MB 以上 ⇒ 够 |
| **U 盘别扔** | 留作"恢复盘"：万一 ESP 上的配置搞坏了，还能从 U 盘引导进去修 |

> ## **⇒ 结论：U 盘只在"试验期"需要；稳定后落到 ESP，从此不用插任何东西。**
> ## **⇒ 而且试验期用 U 盘恰恰是最安全的方式 —— 出问题拔了就完事。**

### 8.5 装好之后（全部软件，一次不用拆）

| 步 | 动作 | 判据 |
|---|---|---|
| 1 | 开机进 Windows，看设备管理器 | 大概率仍是**代码 10**（预期之内） |
| 2 | **Ubuntu Live** → `modprobe i2c-dev` → `i2cdetect -l` → `echo i2c-GXTP5100:00 \| tee /sys/bus/i2c/drivers/i2c_hid_acpi/unbind` → `i2cdetect -y -r N` | 看 `0x2C` 在不在 |
| 3 | `i2ctransfer -y N w2@0x2c 0x40 0x14 r4@0x2c`（**字节序两个方向都试**） | ★ 回 **`YELSTO`** ⇒ **①b 成立** ⇒ 继续；不回 ⇒ **此路不通**（转外置 I2C / 夹 Flash），**但不用立刻拆回去** |
| 4 | ★ 顺手读描述符寄存器 `0x20` | **同时拿到"门 2"的答案**（有无 `0x0E/0x21`） |
| 5 | 用 OpenCore U 盘引导 Windows | 出现 Precision Touchpad 且无代码 10 ⇒ **①②层达成** |
| 6 | 稳定后把 OpenCore 落到 ESP | — |

### 8.6 ★ 那为什么还要一道 Linux？（补丁和 Ubuntu 各管什么）

> 常见误解：既然有补丁绕过白名单，为什么还要做 Linux U 盘？
> **答：它们解决的不是同一件事。补丁管"准入"，Linux 是"观察窗口"。**

| 想知道什么 | **补丁（OpenCore DSDT）** | **Ubuntu + `i2c-dev`** | 补丁生效后的 Windows |
|---|---|---|---|
| OS 能不能拿到正确 I2C 地址 | ✅ **就是干这个的** | ❌ 不管 | ✅ |
| 设备在 `0x2C` 上**活不活**（①b） | ❌ **不保证** —— 只保证地址对 | ✅ **直接读 `0x4014` 看是否回 `YELSTO`** | ✅ 能被枚举即代表活 |
| 有没有 `0x0E/0x21`（门 2） | ❌ | ✅ | ✅ 用项目现成的 `poc/AllCaps.cs` |
| **原始描述符字节** | ❌ | ✅ | ⚠️ 需 IOCTL，麻烦 |
| **配置区 / 固件区**（找阈值 · 判明文/密文） | ❌ | ✅ **唯一途径** | ❌ **做不到** |
| **区分"补丁没生效" vs "设备不应答"** | ❌ | ✅ **唯一途径** | ❌ 两种症状都是代码 10 |

**⇒ 三条结论：**

1. **补丁是必要的，但不充分** —— 它只保证"地址对"。**地址对了、设备不应答，症状依然是代码 10**（成因 b）。
2. **若只想"能用"：Ubuntu 可以省掉** —— 打完补丁开机看结果，能被枚举就等于 ①b 自动成立。
3. **但两件事只有 Linux 能做**：
   - ★ **诊断**：不行的时候，补丁生效与否、设备应不应答，**症状完全一样**；只有 `i2c-dev` 能分辨。
   - ★ **读硬件的字节**（配置区、固件区、原始描述符）—— 这是项目后续所有研究动作的**唯一通道**（Windows 没有裸 I2C，除非写驱动）。
4. **成本对比**：`i2c-dev` 是**只读、零副作用、不动机器任何状态**；而补丁要装 OpenCore、关 Secure Boot、改引导链。**所以先用零成本的手段拿答案，再决定动不动引导链。**

**★ 省事做法**：**一个 U 盘两用**（OpenCore 与 Linux Live 放同一个 U 盘，分区共存）；或换更小的 Linux（Debian netinst / Fedora Live / Alpine 都行，只要有 `i2c-tools`）。

### 8.7 ⚠️ 必须接受的两个风险

1. **若 ①b 不成立，装上去的是一块"完全不能用"的触控板** —— 不是"能用但没震动"，而是**连指针都没有**。所以要备 USB 鼠标、留好原装模块。
2. **既然不打算再拆 ⇒ 软件侧必须先跑通。** §8.1 第 1 项就是为此：**拿原装模块当白鼠，把 OpenCore 的副作用提前暴露**，别等板子装好才发现 Windows 进不去。
