# 复现手册 · 操作顺序与依赖

> 目标：**让一个没参与过本项目的人，按本文顺序独立重跑全部分析。**
> 前提：一台 ThinkBook 14 G6+ IMH（21LD）或同代 ForcePad 机型。
> 每一步都标注：**输入 / 命令 / 期望输出 / 失败怎么办**。

---

## 0. 总览：复现路线

| 阶段 | 名称 | 需要真机 | 风险 | 产出 |
|---|---|---|---|---|
| **P0** | 环境准备 | 否 | 🟢 | 工具链就绪 |
| **P1** | 资产采集 | 是（只读） | 🟢 | 固件 / ACPI / 描述符 / 驱动 |
| **P2** | 容器解析 | 否 | 🟢 | 13 个子固件边界 |
| **P3** | 加扰破解 | 否 | 🟢 | 明文固件 |
| **P4** | 反汇编与追踪 | 否 | 🟢 | 命令表 / 输出端链路 |
| **P5** | 主机侧探测 | 是（只读） | 🟢 | `Out=0` 等三条硬事实 |
| **P6** | I²C 边界实测 | 是 | 🟠 | 5/5 闭合结论 |
| **P7** | EC 差分实验 | 是（只读） | 🟢 | EC 线关闭 |
| **P8** | cfg 语义分析 | 否 | 🟢 | TLV 格式 + TAG 字典 |
| **P9** | 补丁生成（**未刷写**） | 否 | 🟢 | 2 字节补丁镜像 |
| **P10** | 刷写（**未执行**） | 是 | 🔴 | — |

> **★ P0–P4、P8、P9 是纯离线的**，只要有材料就能在任何机器上重跑。
> **P5–P7 需要真机**，但都是只读的。
> **P10 尚未执行**，需要用户自行决策（料板 vs 真机）。

---

## P0 · 环境准备

详见 [`ENVIRONMENT.md`](ENVIRONMENT.md)。最简集合：

| 类别 | 需求 |
|---|---|
| OS | Windows 11（用于 HID/驱动层）+ 可选 Linux live USB（交叉验证） |
| Python | 3.10+ ，依赖见 `ENVIRONMENT.md` |
| .NET | 用于 C# PoC（`HidDump` / `ColProbe` 等） |
| 第三方工具 | **不在本仓库内**，获取方式见 `ENVIRONMENT.md` §3 |

```bash
git clone <this-repo>
cd thinkbook-forcepad-gt7868q-gxtp5100-re
python -m pip install -r reproduce/requirements.txt
python reproduce/checklists/p0-env-check.py     # 自检
```

**期望输出**：所有依赖 `[OK]`。

---

## P1 · 资产采集（真机，只读）

| # | 资产 | 采集方式 | 期望输出 |
|---|---|---|---|
| 1 | **本机固件** | 拷 `C:\Windows\Firmware\*.BIN` | `TB14P_GT7868Q_14030522_20240202.BIN`，161,628 B |
| 2 | **驱动包** | 拷 `C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_*` | 含 `tpupdate_driver.dll` |
| 3 | **完整 ACPI** | `python tools/acpi-ec/dump_acpi_tables2.py` | 32 表 / 761,859 B |
| 4 | **HID 描述符** | `dotnet run --project tools/hid/HidDump` 或 `python tools/hid/hiddiag.py` | 四集合 caps |
| 5 | **BIOS 模块** | 下载 BIOS 更新包 → 解包 → `python tools/bios/ffs_scan.py` | `GoodixTpDxe.bin` 等 |
| 6 | **官方源码** | `git clone` 汇顶 `gdix_hid_firmware_update`、`gtx8_driver_linux` | ★ **必须含 `gtx2/` 那一层** |
| 7 | **记录 sha256** | `python reproduce/checklists/p1-hash.py <dir>` | 写入 `data/manifest.sha256` |

> ⚠️ **坑**：ACPI 导出的关键 —— `SSD1..SSDS` 是**平级表键**，不是 SSDT 的子键。遍历错了只能导出 3 张表。

---

## P2 · 容器解析（离线）

```bash
# 1) 扫容器起点（用官方校验和定位，不要假设从 0 开始）
python tools/firmware/find_container.py data/firmware/TB14P_GT7868Q_14030522_20240202.BIN
#   → 期望：container @ 0x113C, checksum 0x5F37 PASS

# 2) 解析 13 个子固件
python tools/firmware/parse_container.py data/firmware/TB14P_GT7868Q_14030522_20240202.BIN --off 0x113C
```

**期望输出**：

| 校验项 | 期望值 |
|---|---|
| 容器起点 | `0x113C` |
| `size`（u32 BE @ +0） | `100,602`（0x188FA） |
| `checksum`（u16 BE @ +4） | `0x5F37` 且 `sum(payload)&0xFFFF` 通过 ✅ |
| `hw_pid` / `fw_pid` | `YELSTO` / `7868Q` |
| `subsys_num` | `13` |
| 数据区 | `+0x100`，100,352 B |
| **自洽校验** | 13 条 `size` 合计 `= 0x18800 = size + 6 − 0x100` ✅ |

**失败怎么办**：
- 校验和不通过 ⇒ 容器起点找错了，回到第 1 步重扫。
- `subsys_num = 0` ⇒ **几乎肯定是从文件偏移 0 解析了**（假否定），见上。

另：确认三层结构 —— 外层 `0x00000–0x0113C` 明文清单 / 容器 `0x0113C–0x19A3C` / TF100A 镜像 `0x19ABC–0x2775C`。

---

## P3 · 加扰破解（离线，★ 核心）

```bash
python tools/firmware/decrypt.py <BIN> --scan-phase --samples 4
```

**三步逻辑**（这就是全部核心）：

```python
o   = find_container(buf)                                  # 官方校验和定位容器起点
k2  = rot_left(K, 316)                                     # 等价于 K[(x+316)%1024]
dec = bytes(v ^ k2[(i + 0x100) % 1024] for i, v in enumerate(data_region))
```

**期望输出**：

| 指标 | 加扰区 | 解出后 |
|---|---|---|
| 熵 H0 | 7.9977 | **7.0066** |
| 零字节 | 0.36% | **14.99%** |
| **最长连续零串** | **4 B** | **5450 B** ← ★ 最硬的判据 |
| 块数 | — | **13**（= `subsys_num`） |
| 最优相位 | — | **572**（数据区相对）/ **316**（容器相对） |

**★ 必须做的三项验证**（缺一不可，否则会重蹈本项目"两天循环论证"的覆辙）：

| # | 验证 | 通过标准 |
|---|---|---|
| ① | K 的字节直方图是否人工配平 | 卡方 ≈ 0（256 个值各出现 4 次） |
| ② | **穷举全部 1024 相位 + 多份独立样本交叉** | 四份独立固件**全部指向同一相位** |
| ③ | 解出后是否出现整块零填充 | 有（本例 5450 B） |

**失败怎么办**：
- 若只有单一样本：即使"解出来看起来对"，也可能是过拟合。**必须换样本交叉**。
- 若解出后无零填充：相位或 K 不对，回到穷举。

> 🔴 **不要做的事**：不要因为"K 在 raw 里出现了很多次"就判定 K 不是密钥。
> **这是循环论证** —— 零填充区 `0 ⊕ K = K` 必然让 K 出现。**"出现次数"没有判据力。**

---

## P4 · 反汇编与追踪（离线）

```bash
# 1) 确定 TF100A 加载基址（三步解法）
python tools/analysis/locate_base.py <BIN> --region 0x19ABC:0x2775C
#   → 期望：SP=0x200076C8, Reset=0x08005165, base=0x08005000

# 2) 反汇编
python tools/analysis/dis_thumb.py <BIN> --base 0x08005000 --fileoff 0x19ABC --out tf100a.asm

# 3) 命令分派器 + 调用图
python tools/analysis/callgraph.py tf100a.asm --entry 0x0800E1C0
```

**期望输出**：

| 项 | 期望值 |
|---|---|
| 加载基址 | **`0x08005000`**（不是 `0x08000000`） |
| 向量表 | `SP=0x200076C8`、`Reset=0x08005165` |
| 分派器 | `0x0800E1C0` |
| 命令全集 | **39 条**（`0x80`×1 + `0xA0`×16 + `0xA1`×22） |
| 输出例程 | `0x08005E38`，全 asm **唯一调用点** `0x08005B8C` |
| 判据立即数 | `0x28`（= 40），在 `0x08005A90` / `0x08005ABC` |

**★ 反例标定（必做）**：判定"这段是不是代码"时，必须对【真代码 · 随机 · 全零 · 纯文本】四类各跑一次。
> 本项目的教训：`Thumb 消费字节%` 在**全 0x00 上给 100%**、在**英文清单上给 94.7%** ⇒ **它不是代码判据**。

**失败怎么办**：
- 找不到 32 位常量（如 `0x45670123`）⇒ **不要用字节搜索**，ARM/Thumb 用 `MOVW`/`MOVT` 拼立即数，从不连续出现。
- 反汇编看起来像乱码 ⇒ 基址错了，回到第 1 步。

---

## P5 · 主机侧探测（真机，只读）

```bash
python tools/hid/hiddiag.py          # 三条判据一次跑完
python tools/hid/etwcheck.py         # 校验 ETW 样本有效性
```

**期望输出（三条硬事实）**：

| # | 判据 | 期望值 |
|---|---|---|
| 1 | `Col02` 的 `OutputReportByteLength` | **0** |
| 2 | 四集合 `UpperFilters` / `LowerFilters` | **全空** |
| 3 | 厂商触控板 / 触觉服务进程数 | **0** |

**真机只读探测（`Col04` rid=14）** —— ⚠️ 单次 ≤32 B、间隔 ≥500 ms、禁止批量轮询：

| 探测项 | 期望结果 |
|---|---|
| `0x96F8` | ✅ 读得出，与离线配置体**逐字节一致** |
| `0x1800` / `0x3800` | 🔴 读得出但**读不稳** ⇒ 不可作数据 |
| 32 位地址读 | 🔴 判否（带阳性对照） |

**★ 两个必知的协议陷阱**：
1. **读回字节序取决于请求地址的低 2 位。**
2. **`Gx::Write` 帧长度字段是 `+5`，不是 `+7`。** 用错则**每一帧都被静默丢弃**，你会得出完全错误的结论。

**失败怎么办**：`0x96F8` 读不出 ⇒ 通道没打开，先检查 `+5`/`+7` 和字节序。

---

## P6 · I²C 边界实测（真机，🟠 中风险）

| 步骤 | 命令 / 动作 | 期望 |
|---|---|---|
| 1 | 用 RWE **Memory（`R32`/`W32`）** 直打 I2C0 的 BAR | **不要用** `Access → I²C/SMBus`（那是 PCH SMBus，必然假阴性） |
| 2 | **阳性对照**：划手指，看 `IC_STATUS`(+0x70) 的 bit0/bit5 是否跳 | 必须跳，否则探针无效 |
| 3 | 扫 I2C2 / I2C3 | BAR = 0 ⇒ 主机不可访问 |
| 4 | Linux 交叉验证：`bash tools/i2c/probe.sh` | ⚠️ 触控板总线上 `i2cdetect` **会崩内核** |

> ⚠️ **RWEverything 需关 HVCI + 驱动黑名单**（路线 W1）。**实验后必须跑 `step9-restore` 还原。**

**期望输出**：5/5 总线全部闭合 ⇒ **"主机侧不存在任何可达 AW86927 的 I²C 通道"**。

---

## P7 · EC 差分实验（真机，只读）

```powershell
# 1) 自检（不需动作）—— 先确认读链通
.\tools\acpi-ec\ec-selftest.ps1
#   → 期望：pawnio_open HR=0；3×256B 连读非 0xFF、MD5 逐轮不同

# 2) 差分采集（需管理员 + 物理按压）
.\tools\acpi-ec\ec-haptic-probe.ps1 -Rounds 6 -GapMs 40
```

**期望输出**：

| 阶段 | 期望 |
|---|---|
| 自检 | `pawnio_open HR=0`、`pawnio_load HR=0`（2612 B） |
| 采集 | 6 相位 × 6 轮 |
| 分析 | **全零**（噪声底 ≈ 98） |

> **★ 只读保证**：`0x81`（写）出现 **0 次**。
> **★ 诚实标注**：噪声底 98 ⇒ 结论只能是"**在此灵敏度下未见**"，**不能**升格为"不存在"。

**失败怎么办**：`pawnio_open` 返回 `0x80070005` ⇒ 没提权，用管理员重跑。

---

## P8 · cfg 语义分析（离线）

```bash
python tools/firmware/cfg_parse.py <tpcfgsid0.cfg> --head 64
```

**期望输出**：

| 项 | 期望值 |
|---|---|
| 文件头 `0x3B`（u16LE） | TLV 区长度 |
| 文件头 `0x3D`（u8） | 条目数 |
| TLV 区起点 | `0x40` |
| **自校验** | `0x40 + 1238 = 1302` ✅ |
| **帧序** | **`[LEN:u8][TAG:u8][payload: LEN-2]`** ← 不是 `[TAG][LEN]` |
| 触觉区 | `TAG 0x50 – 0x7A` |

**★ 判定帧序的方法**（头对头对比，不要猜）：
`[LEN][TAG]` 覆盖 **94.8% / 96.4%**，`[TAG][LEN]` 覆盖 **0.0%**；且前者下 TAG **严格递增 1.00**。

---

## P9 · 补丁生成（离线，★ 未刷写）

**脚本已就位**：[`tools/firmware/make_tf100a_sens_patch.py`](../tools/firmware/make_tf100a_sens_patch.py)
（★ 2026-10-03 终审补齐。补丁后的 BIN 是厂商固件派生品，**不入库**，但生成方法必须可复现 ——
本脚本已用真实镜像验证：**输出与手工补丁件逐字节相同**。）

```bash
# ① 先只校验两处补丁点（不写盘）
python tools/firmware/make_tf100a_sens_patch.py <原厂 BIN> --check

# ② 生成 40→8（默认）。梯度可试 16 / 24
python tools/firmware/make_tf100a_sens_patch.py <原厂 BIN> --sens 8 \
       --out TB14P_GT7868Q_14030522_20240202_TF100A-sens40to8.BIN
```

脚本内置双重校验：**绝对文件偏移** + **后随 2 字节必须为 `88 42`**，任一不符即拒绝写盘。
（`--sens` 默认 8；加载基准 `0x08005000 ↔ file 0x19ABC` 已固化在脚本里。）

**期望输出**：

| 项 | 期望值 |
|---|---|
| 输出大小 | 161,628 B（与原文件等长） |
| 差异 | **仅 2 字节**：`0x1A54C: 28→08`、`0x1A578: 28→08` |
| sha256 | 原 `0033d075fae88f0048544696c8941ed7dcca4269beaa84af76323ef5bbdcee72` → 补丁 `f39f80e0766f2a6fb9242ed53302c00fd4e6a00313f4abbe94a91492f84fcb02` |
| 互证 | 两处后随指令均为 `88 42` = `cmp r0,r1` ✅ |

**★ 纪律**：每个被改字节必须有反汇编互证。段内另有 5 处同类字节，**一律不碰**。补丁后立即做"仅 N 字节差异"证明 + 双 sha256 存档。

---

## P10 · 刷写（🔴 未执行，需自行决策）

**剩余三步**：

```
① 反汇编核实：版本号从哪读 / 有无哈希·校验拦路 / 触发条件
② 触发方式核实：怎么让 Windows/BIOS 把更新完整再走一遍
③ 零风险预演：先"只改版本号、不动代码"刷一遍相同内容 —— 打通通道、验证时序
   ⇒ 成功后再上 40→8 真补丁 ⇒ 《刷写操作单》+ 回滚方案
④ 决策：A 先买料板刷（稳） / B 直接刷真机（快，有回滚）
```

| 项 | 已知信息 |
|---|---|
| 通道 | **UEFI 胶囊**（`UEFI\RES_{B6AE105A-…}`、`oem87.inf`、DriverVersion 0.0.2.8）+ BIOS 侧 `GoodixTpDxe` —— **不走 HID** |
| 流程 | `enter pass through → start updating → erase flash → write flash → reload subFW → reset ic` |
| 版本机制 | 更新器对 **TP / TF 两个子系统分别比对版本、分别刷写**（`GTPCheckTFUpdate`）⇒ **要让 TF 被重刷，必须让版本字段变化** |
| 版本串 | TF 版本 `5.21.01.23007` 位于 file `0x264EE` |
| 回滚 | 原镜像从未被改动；回滚 = 用原件重刷 |

---

## 附录 · 复现检查单

分步检查单见 [`checklists/`](checklists/)：

| 文件 | 用途 |
|---|---|
| `p0-env-check.py` | 环境自检 |
| `p1-hash.py` | 资产 sha256 归档 |
| `p2-container.md` | 容器解析验收点 |
| `p3-scramble.md` | 加扰破解三项验证 |
| `p4-disasm.md` | 反汇编验收点 + 反例标定 |
| `p5-host.md` | 三条硬事实 |
| `p9-patch.md` | 补丁"仅 N 字节差异"证明 |
