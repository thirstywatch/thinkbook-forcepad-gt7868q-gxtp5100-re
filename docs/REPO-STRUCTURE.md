# 仓库结构方案 · 目录、文件命名与归类

> 本文是**整理方案本身**：给出完整目录树、每类的命名规则、以及**原工区 → 新仓库的映射表**。
> 分类原则：**按"读者要回答什么问题"分，而不是按"材料是什么格式"分。**

---

## 一、分类原则（4 条）

| # | 原则 | 说明 |
|---|---|---|
| 1 | **结论 / 方法 / 复现 三分** | 结论（`docs/`）= 是什么；方法（`method/`）= 怎么做；复现（`reproduce/`）= 照着做。三者互不混放 |
| 2 | **`docs/` 按主题分，不按时间分** | 只有 `10-journal/` 按时间（逐轮日志），其余按主题 |
| 3 | **已作废的结论不删，进 `99-archived/` 并加横幅** | 本项目的价值一半在"哪些错路走过"。删掉 = 别人会重踩 |
| 4 | **`tools/` 按"对谁操作"分** | firmware / hid / acpi-ec / i2c / bios / analysis，而不是按语言分 |

---

## 二、完整目录树

```
thinkbook-forcepad-gt7868q-gxtp5100-re/
│
├── README.md                      入口：目标 · 结论 · 怎么读 · 红线摘要
├── LICENSE                        ⚠️ 待定（见 gaps/GAPS.md P0-1）
├── NOTICE.md                      第三方组件与合规声明
├── .gitignore                     排除固件/BIN/第三方二进制
│
├── docs/                          ── 结论与证据 ──
│   ├── 00-START-HERE.md           导航：你是谁 → 从哪读
│   ├── 01-overview/               项目目标 · 平台基线 · 器件总表 · 证据分级定义
│   ├── 02-hardware/               三颗芯片逐个到引脚级（GT7868Q / TF100A / AW86927 / LRA）
│   ├── 03-firmware/               容器 · 分区表 · 加扰破解 · cfg 语义
│   ├── 04-host-control/           三层关卡（描述符 / 驱动 / 固件）
│   ├── 05-i2c/                    五条总线的实测边界 · Windows 三条路线
│   ├── 06-ec-acpi/                零权限 ACPI 导出 · DSDT TPAD 子树 · EC RAM 差分
│   ├── 07-hid/                    HID usage 语义 · Col04 命令空间边界
│   ├── 08-findings/               ★ 结论总表 · 全链证据分级 · 跨工区矛盾排查
│   ├── 09-safety/                 ★★ 红线 · 事故 · 恢复阶梯 · 风险矩阵
│   ├── 10-journal/                逐轮日志（§19.x，按时间，一人一轮）
│   └── 99-archived/               已作废结论（保留 + 作废横幅）
│
├── method/                        ── 方法论（可复用于其它机型）──
│   ├── METHOD.md                  主方法论（是什么 / 做什么 / 得到什么）
│   ├── 01-recon-workflow.md       侦察工作流总览
│   ├── 02-firmware-unpack.md      固件解包与容器解析
│   ├── 03-obfuscation-crack.md    ★ 周期 XOR 加扰破解
│   ├── 04-disassembly.md          ARM/Thumb 反汇编 · 基址三步解法 · 输出端追溯
│   ├── 05-hid-probing.md          HID 通道探测（含两个协议陷阱）
│   ├── 06-i2c-spb.md              I²C/SPB 边界与旁路
│   ├── 07-ec-acpi.md              零权限 ACPI 导出 · EC RAM 读取与差分
│   ├── 08-evidence-grading.md     ★ 证据分级与判据纪律
│   └── 99-pitfalls.md             踩坑清单（102 条纪律）
│
├── reproduce/                     ── 复现 ──
│   ├── REPRODUCE.md               P0–P10 操作顺序（输入/命令/期望/失败处理）
│   ├── ENVIRONMENT.md             依赖 · 版本 · 第三方工具获取 · 环境坑
│   ├── DATA-INVENTORY.md          数据资产清单 + sha256 + 获取方式
│   ├── requirements.txt           Python 依赖
│   └── checklists/                分步验收单
│
├── tools/                         ── 脚本（自写）──
│   ├── firmware/                  解包 · 解扰 · cfg 解析 · 补丁生成
│   ├── hid/                       HID 枚举 / 描述符 / feature / Col04（C# + py）
│   ├── acpi-ec/                   ACPI 导出 · AML 扫描 · EC 差分
│   ├── i2c/                       RWE 脚本 · Linux 探测
│   ├── bios/                      FFS 扫描 · DXE 反汇编 · DSDT patch
│   ├── analysis/                  通用分析（熵 / 调用图 / ISA 指纹 / 常量搜索）
│   └── third-party/               只放 README（获取方式），不放二进制
│
├── data/                          ── 数据 ──
│   ├── firmware/                  ⚠️ 不入库（.gitignore）；放 README 说明获取
│   ├── acpi/                      ✅ 本机 DSDT/SSDT（bin + dsl）
│   ├── hid-descriptors/           ✅ 描述符 / caps / feature 样本
│   ├── reference/                 ✅ cfg 解析产物 · 常量表 · 对照样本统计
│   ├── logs/                      ✅ 实测日志
│   └── manifest.sha256            ✅ 校验和清单
│
├── vendor-refs/                   ── 第三方参考（仅可再分发内容）──
│   ├── README.md                  出处清单 + 许可说明
│   └── links.md                   全部外部链接
│
└── gaps/
    └── GAPS.md                    待补充清单（本文档）
```

---

## 三、文件命名规则

| 类别 | 规则 | 示例 |
|---|---|---|
| **主题文档** | 小写英文 / 拼音无空格，连字符分词 | `03-obfuscation-crack.md` |
| **逐轮日志** | `YYYY-MM-DD-轮次-主题.md` | `2026-10-02-round19-加扰解开.md` |
| **已作废文档** | 原名 + `.archived` 后缀，并在**首行加作废横幅** | `00-交接文档.archived.md` |
| **脚本** | 动词开头，小写下划线 | `find_container.py`、`ec_diff.ps1` |
| **数据产物** | `<来源>-<处理>-<版本>.<ext>` | `GT7868Q_2024_本机_plain_data.bin` |
| **日志** | `<实验>-YYYYMMDD-HHMMSS.txt` | `ec-haptic-20261003-122410.txt` |

### ★ 作废横幅模板

```markdown
> ## 🔴 本文已作废（YYYY-MM-DD）
> **作废原因**：<一句话>
> **正确结论见**：<链接>
> **保留理由**：<为什么还要留着 —— 通常是"防止别人重踩">
```

---

## 四、原工区 → 新仓库映射表

### 4.1 主工区 `touchpad-lab/`（2,736 份 / 182 MB）

| 源 | 目标 | 处理 |
|---|---|---|
| `2026-10-01-软件逆向全书-芯片固件主机控制.md`（12,632 行） | **拆分**到 `docs/01`–`10` + `method/*` | ★ 建议拆分；若不拆，整体放 `docs/08-findings/` 并在 README 指向 |
| `00-统一入口-唯一权威索引.md` | `docs/00-START-HERE.md` | 合并 |
| `00-触控板结论总表.md` | `docs/08-findings/结论总表.md` | |
| `2026-10-01-跨工区文档矛盾排查报告.md` | `docs/08-findings/矛盾排查.md` | |
| `PREFLIGHT-STATE.md` | `docs/99-archived/` | ⚠️ 顶部已有 2026-10-02 作废声明 |
| `2026-10-01-两处归属错误裁定与全链证据分级.md` | `docs/08-findings/全链证据分级.md` | |
| `2026-10-01-TF100A输出端反向追溯.md` | `method/04-disassembly.md` + `docs/03-firmware/` | |
| `2026-10-01-最终结论-纯软件路终止.md` | `docs/04-host-control/` | |
| `2026-10-02-主机侧有无触觉控制面-三条硬事实闭合.md` | `docs/04-host-control/` | |
| `2026-10-03-方案A审计-漏洞清单与修正版流程.md` | `docs/05-i2c/` | |
| `2026-10-03-蓝莓新项目实证-总线定案-同构forcepad挖掘清单.md` | `docs/05-i2c/` + `vendor-refs/` | |
| `2026-10-02-EC收工总结-含一处自我推翻.md` | `docs/06-ec-acpi/` | |
| `COL04-BOUNDARY.md` | `docs/07-hid/Col04-边界.md` | 需加 `0xA2` 异步横幅 |
| `GXTP5100-HID-usage-report.md` | `docs/07-hid/` | |
| `DSDT-TPAD子树完整解读.md`（在 docs-触控板） | `docs/06-ec-acpi/` | |
| `BIOS-FmpDxeY750与I2cTouchPanelDxe反汇编.md` | `docs/06-ec-acpi/` | |
| `追加一`–`追加三十七`（老线 47 份） | `docs/99-archived/old-line/` | 加"历史轨迹"横幅 |
| **`re/`（205 个 py）** | `tools/analysis/` | 需标注哪些在用 |
| **`poc/`（113 MB）** | 拆分到 `tools/{firmware,hid,i2c}/` + `data/logs/` | ⚠️ `_cabs/` 需标注来源 |
| `poc/decrypt-v2/*` | `tools/firmware/` | ★ 核心 |
| `poc/fw-mod/TB14P_..._sens40to8.BIN` | `data/firmware/`（**不入库**，留 sha256） | |
| `poc/*.cs`（22 个） | `tools/hid/` | |
| `*.ps1`（56 个） | `tools/acpi-ec/` + `tools/i2c/` | ⚠️ 16 个有解析错误，标注 |
| `acpi/acpi_all/*`、`dsdt-asl/*` | `data/acpi/` | ✅ 只入 `.bin`/`.dsl`，**排除 `iasl.exe`** |
| `bios-re/*` | `tools/bios/` + `data/reference/` | `GoodixTpDxe.asm.txt` ✅ 可入 |
| `linux/*` | `tools/i2c/` | |
| `driver-patch/*` | `tools/bios/` | ⚠️ `.efi` 二进制需确认 |
| **`rwe/`（17 MB）** | ❌ **不入库** | 专有软件，见 `tools/third-party/README.md` |
| **`pawnio/`** | ❌ **不入库** | 同上 |
| **`vendor/`** | 拆分：wiki md → `vendor-refs/`（待确认许可）；PDF/EXE ❌ | |
| **`_bak/`（22 MB）** `_dup-archive/` `_rebuild/` | ❌ **不入库** | |

### 4.2 老线 `docs-触控板/`（47 份）

→ `docs/99-archived/old-line/` + 少量技术文档并入主题目录（`触控板固件反汇编-TF100A.md` → `method/04-disassembly.md`）。

### 4.3 ★ **10 个源工区全表**（2026-10-03 终审定稿）

> 前三轮共发现 **10 个**工区。第一版地址清单只有 5 个 → 第二轮补到 7 个 → **第三轮终审补到 10 个**。

| 前缀 | 工区 | 入库份数 | 要点 |
|---|---|---|---|
| `lab__` | `touchpad-lab/`（2,736 份 / 182 MB） | **809** | 主工区：全书、全书前身、`poc/`(522)、`re/`(205)、`acpi/`、`bios-re/`、`driver-patch/` |
| `old__` | `2026-09-27-14-52-52/`（**整个工区**，439 MB） | **345** | ⚠️ **第二轮只取了 `docs-触控板/`（47 份）**，终审改为全工区扫描。<br>★ 找回 `bios/out/` 的 `FmpDxeY750.asm.txt`、`I2cTouchPanelDxe.asm.txt`、`CompalEcDxeDrv.asm.txt`、`CompalEcSmmDrv.asm.txt`；<br>另有 `fw-touchpad/`(270)、`scripts-acpi/`(13)、`scripts-ec/`(15)、`acpi-dump/`(32)、`docs-角度/`、`docs-BIOS与EC/` |
| `gxt__` | `2026-09-30-14-25-11/fw-touchpad/`（269 份） | **247** | `goodix-tool/`（cfg 样本、**`K_gt7868q.bin`**、40 个审计脚本）；★ §19.10「复现」直接引用 |
| `surf__` | `2026-10-03-00-05-18/surface-vs-mine/`（77 份） | **24** | AW86927 Linux 驱动、蓝莓 GT7863 源码实证 |
| `sfw__` | `2026-10-02-22-06-58/`（**整个工区**） | **54** | `surface_fw/`(127) + `ESP32-Haptic-Precision-TouchPad/`(20) |
| `probe__` | `2026-10-03-01-46-16/probe/`（83 份） | **39** | 蓝莓项目实证、PawnIO 调研、总线定案 |
| `root__` | `<LAB>`（根目录散件） | **11** | `追加十`–`追加二十六`、`00-★交接文档`、PDF 抽取文本 |
| **`early__`** | **`2026-09-14-17-18-21/`（88 份）** | **35** | 🔴 **终审新发现**。**最早工区**：FW 候选清单、`TF100A_完整性验证报告.md`、`ESP32-Haptic-Precision-TouchPad_项目解析.md`、ACPI/PNP/UEFI 扫描日志 |
| **`hidp__`** | **`2026-10-02-16-11-42/`** | **12** | 🔴 **终审新发现**。`hidprobe/`：`hiddiag.py` + `etwcheck.py` 及输出（§19.26.8 ETW 实证）；`ecfw/ec_text.asm`（4 MB，EC 固件反汇编） |
| **`ca4f__`** | **`ca4f-hunt/`（221 份）** | **11** | 🔴 **终审新发现**。**全书引用 25 次**却在 `SKIP_DIR` 里被静默整目录跳过。<br>★ §19.30.1「推翻『描述符主机改不了』」的决定性证据出自此处的 `goodix-gt7868q.c`。<br>自写脚本入库；clone 的上游驱动按第三方红线记入 `vendor-refs/links.md` §5 |

> ⚠️ **`fw-touchpad` 与 `surface-vs-mine` 必须纳入**，否则 P3（加扰破解）和 P8（cfg 语义）无法完整复现。见 `gaps/GAPS.md` P1-1。
> 🔴 **`ca4f-hunt` 必须纳入**，否则 §19.30.1 那条"推翻定案"的证据在仓库里找不到出处。

### 4.4 未入库的部分（红线，逐条有据）

| 排除对象 | 理由 |
|---|---|
| 厂商固件 BIN / `.Cap` / `.cab` / `.hlkx` / `.iso` | 厂商可再分发性未确认 |
| `rwe/`（17 MB）· `pawnio/` 签名模块 | 专有 / 签名二进制，不可再分发 |
| `vendor/*.pdf`、HMM PDF、数据手册 PDF | 第三方文档 |
| `_bak/`(22 MB) · `_dup-archive/` · `_rebuild/` | 备份与重复归档 |
| `poc/_cabs/` | 驱动 CAB 解包产物 |
| `x9bios/` 里的 `n4cur09w.iso`(127 MB) / `n4cuj09w.exe`(40 MB) | 厂商 BIOS 包（脚本部分已入库） |
| **第三方 C/H/CPP 源码（93 份）** | 许可不明 → 改记 `vendor-refs/links.md` §5 |
| **`…_TF100A-sens40to8.BIN`（161,628 B）** | 厂商固件派生品 → 改为入库**生成脚本** `tools/firmware/make_tf100a_sens_patch.py`（已验证可逐字节复现） |

---

## 五、实测体积（2026-10-03 第四轮后）

> 口径：`git ls-files` 跟踪文件，按字节和统计，截至 2026-10-05（含第十一～十三轮新增的 56 份文件）。

| 部分 | 实测 |
|---|---|
| 文件总数 | **1,613**（其中 md 207 / py 698 / 脚本合计 760） |
| `docs/`（185 个文件，含 774 KB 全书） | 4.63 MiB |
| `tools/`（760 个脚本 + 索引） | 3.47 MiB |
| `data/`（569 个，其中 `logs/` 489、`acpi/` 62、`reference/` 15） | 33.48 MiB |
| `method/` + `reproduce/` + `gaps/` + 根目录文件 | 0.21 MiB |
| **合计（实测字节和）** | **41.78 MiB ≈ 43.8 MB** ✅ |

### 5.1 第四轮新增（跨文档矛盾排查 + 硬件来源归属）

| 文件 | 作用 |
|---|---|
| `docs/08-findings/00-矛盾与推翻登记表.md` | ★ **读任何老文档之前先查这份** —— A/B/C/D 四类 20+ 条被推翻结论 + 仍写旧版的位置（精确到行号） |
| `docs/02-hardware/00-X9-15硬件信息归属与差异声明.md` | ★ **引用硬件观察之前先查这份** —— 本机 21LD vs 购入的 X9-15 模块，16 条观察逐条归属 |
| `docs/99-archived/README.md` | 归档区顶部警示（11 条已作废结论） |
| `docs/10-journal/README.md` | 日志区顶部警示（6 条需核对） |

> 🔴 **本仓库是「过程档案」，不是一致的自洽文档** —— 老工区文档不会自动同步，
> 早期结论被推翻过 20 次以上（《全书》里「更正/推翻/作废」标记 **210** 处）。
> 已在 **23 处**派生文档里就地加了更正标记（A1–A8 / B1–B3）。

* 无单文件 > 5 MB（最大的 3 份 DSDT `.dsl` 各 3.8 MB，`ec_text.asm` 4.1 MB）
* 已删除 227 个重复副本（首轮脱敏造成哈希漂移 → 重跑产生的 `xxx__2.ext`）
* 排除项：`rwe/` 17 MB、`pawnio/`、`_bak/` 22 MB、`poc/_cabs/`、厂商固件 BIN ~100 MB、`x9bios/` 的 iso/exe 167 MB、第三方 exe/PDF ~10 MB

---

## 六、开源前检查单

```
[ ] LICENSE 已选定并放入
[ ] 序列号 <DEVICE-SERIAL> 已脱敏
[ ] 98 份 md 的绝对路径已替换为占位符
[ ] .gitignore 已排除 *.BIN / *.bin（固件）/ *.exe / *.pdf / rwe/ / pawnio/ / _bak/
[ ] 两个遗漏工区已纳入或已在 GAPS 说明
[ ] 已作废文档全部加了作废横幅并移入 99-archived/
[ ] NOTICE.md 已列全部第三方组件与出处
[ ] vendor/wiki 第三方 md 的许可已确认（否则只留链接）
[ ] README 的"下一步"与实际状态一致
```
