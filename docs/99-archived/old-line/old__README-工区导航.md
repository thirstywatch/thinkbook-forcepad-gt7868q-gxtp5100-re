# 工区 README —— 从这里开始

> **工区**：`<WORKSPACE>`
> **本机**：Lenovo ThinkBook 14 G6+ IMH（机型号 **21LD**）· Core Ultra 7 155H · BIOS NJCN67WW
> **整理时间**：2026-09-28 20:0x
>
> **两个正式项目的主仓库在别处，本工区是战场与产物。** 见下方「项目正本」。

---

## 一、30 秒上手

| 你想知道 | 打开这个 |
|---|---|
| **工区里都有什么、怎么看** | **本文件**（README） |
| **触控板这条线到底什么结论** | **`docs-触控板/00-触控板结论总表.md`** ← 权威收口 |
| 角度（开盖）这条线什么结论 | `docs-角度/` 4 份（正本在 `lid-probe`） |
| 今天（09-28）做了什么 | `01-2026-09-28成果汇总.md` |
| 09-27 那天做了什么 | `00-工区总览与两项目推进汇总.md` |
| 逆向方法本身怎么选 | `docs-方法情报/硬件逆向-逆向方法总谱.md`（v2） |
| 谁在做同样的事 | `docs-方法情报/关键人物与其研究-调研.md` |

---

## 二、两个项目正本（结论以它们为准）

| 项目 | 主仓库 | 状态权威 | 入口 |
|---|---|---|---|
| **触控板（触觉/震动）** | `<LAB>\touchpad-lab\` | `PREFLIGHT-STATE.md` | `NEXT-SESSION.md` |
| **角度（开盖传感器）** | `<WORKSPACE>` | 同上模式 | — |

---

## 三、目录地图（2026-09-28 整理后）

### 3.1 文档

| 目录 | 内容 |
|---|---|
| `docs-触控板/` | **10 份**。其中 **`00-触控板结论总表.md` = 权威收口**；其余为专题证据（多份顶部带更正横幅） |
| `docs-角度/` | 4 份：ACPI 事件表反编译 / EC-RAM 地图与读取路线 / EC 窗口实测结论 / **4KB 读取执行手册** |
| `docs-BIOS与EC/` | BIOS 全链路拆解 + 联想固件 hunt（触控板固件怎么到手的） |
| `docs-方法情报/` | 逆向方法总谱 v2（**只谈逆向方法，不谈换实现**）· 侧面路线情报 · 关键人物调研 · 现状路径标记 |

### 3.2 物料（按芯片/主题分，不再散落）

| 目录 | 内容 |
|---|---|
| **`fw-touchpad/`** | **触控板物料总汇**（本次新整理） |
| ├ 固件本体 | `touchpad_GT7868Q_fw.bin`（161,628 B，= 原生 `TB14P_GT7868Q_14030522_20240202.BIN`）<br>`gt7868q.bin` · `fmp.cap` · `cap_payload.bin` · `device_fw_*.bin` |
| ├ **反汇编** | **`touchpad_TF100A_thumb.asm.txt`（20,314 行）** ← 核心分析对象 |
| ├ 工具 | `dump.py`（按地址 dump 反汇编）· `site_ctx.py`（外设使用点上下文）· `peripheral_use.py`（movw/movt 折叠→外设清单）· `fw_map/fw_xref/fw_final.py` |
| ├ `hid-probe/` | HID 通道探测脚本与产物（`col02-precise/`、`col02-writeprobe/`、`hid_caps.py`、`hid_all_devices.py`…） |
| ├ `lenovo-hunt/` | 联想固件检索中间产物 |
| └ 参考 | `goodix_gt7868q.c`（Linux 驱动）· 3 份 `.inf` · `local-overrides.quirks` |
| **`fw-bios/`** | 非触控板的固件样板：电池 capsule（`.cap`，CAP 格式样板）· `zhanlu_cfu_oem72.inf`（湛卢 AI 芯片 CFU over HID） |
| `bios/` | **BIOS 拆解全链**：`extract/`（`isflash.bin` 19.2 MB · `fw_decompressed.bin` 30.88 MB · `ffs_scan.py` · `pe_dis.py`）、`out/`（**447 文件树 + 389 模块清单** + 13 个关键模块 + 3 份反汇编 + `DSDT-528KB.bin`）、EC 协议脚本（`ec_cmd_table.py` / `ec_io.py` / `dsd_ercd.py`） |
| `acpi-dump/` | 32 张 ACPI 表原始转储（761,872 B） |
| `data/` | `af.txt`（全字段表）· `qxx.txt`（25 个 `_Qxx`）· `ecram_live_samples.bin`（336×4 KB EC 窗口采样） |
| `ec-lid-snaps/` | EC 窗口连拍快照（**LIDF 实证的 236 帧**在 `capture-20260927-212353/`） |
| `hmm-figs/` + `tb14g6_hmm.pdf` | 联想硬件维护手册 13.7 MB + 抽图 |

### 3.3 脚本

| 目录 | 内容 |
|---|---|
| `scripts-acpi/` | 12 个：ACPI 转储与 AML 解析（`dump_acpi` / `all_fields` / `decompile_qxx` / `dsdt_tpad` / `haptic_ram_xref` …） |
| `scripts-ec/` | 15 个：**EC 端口协议实测**（`ec_port_rw.py` ★）· 连拍（`lidf_capture.py`）· 差分/噪声基线 · 环境准备（`prep-lidf-test.cmd`、**`run-ec-port-test.cmd`** ★） |

### 3.4 工具与安全

| 目录 | 内容 |
|---|---|
| `tools-rw/` | `rwdrv/RwDrv.sys` + `rw/Win64`（RWEverything）——**内核任意读写，需临时关安全设置** |
| **`安全设置复原/`** | `fix-unblock-rwdrv.cmd`（关 VBS/黑名单，**需重启**）· `revert-unblock-rwdrv.cmd`（还原）· 3 份注册表备份 · `run-ecram-experiment.cmd` |

---

## 四、当前待办（跨项目）

| # | 事项 | 状态 | 需要谁 |
|---|---|---|---|
| **1** | **EC 端口路径实测**：`安全设置复原\fix-unblock-rwdrv.cmd` → **重启** → `scripts-ec\run-ec-port-test.cmd` | ⏸ **等你** | 喆跑两步，输出贴回 |
| 2 | 触控板 ①：TF100A「播放/波形」通路回溯（CCER ×21 点） | ⭕ 未做 | 我（纯离线） |
| 3 | 触控板 ②：DSDT 的 GXTP 子树解析（脚本已写一半） | 🟡 半成品 | 我（纯离线） |
| 4 | 角度：LIDF 已实证成功 ✅；`\LIDS` 消费方待查 | ✅ / ⭕ | 我 |
| 5 | 触控板方案③（HDP/HDN 接线与驱动） | ⭕ 待决策 | 喆 + 硬件 |
| 6 | PC 侧手势软件 Phase 1（零风险，随时可开工） | ⭕ 未实现 | 我 |

**环境状态（2026-09-28 18:20 实测）**：VBS=1 · HVCI=1 · 驱动黑名单=1 ⇒ **已复原为开启**；RwDrv 服务未加载（`err=2`）。**要做 EC 实测必须先跑第 1 项。**

---

## 五、⚠️ 红线（两条线共用，务必先读）

### 触控板（来源：`touchpad-lab/PREFLIGHT-STATE.md` §8）
1. **禁止对 `Col04` 做后台轮询**；嗅探只能前台、≤30 秒、间隔 ≥200 ms
2. **禁止枚举 / 批量试探厂商命令空间**（会打断应答通道并恶化成彻底失效）
3. **刷机三连 `00 10 / 00 11 / 0E 12` 绝对不碰**
4. 触控板是本机**唯一指点设备**，先备好不依赖它的退路
5. 打挂后唯一恢复：**关机 → 拔充电器 → 长按电源键 20–30 秒 → 等 1 分钟 → 开机**
   （热重启 / `disable-enable` 全部无效；机底那个孔是 **Novo 按钮孔，只进菜单不断电**）

### EC（来源：`docs-角度/`）
**2024 起 ThinkBook 高频轮询 EC 会崩状态机 → 硬关机**。本项目所有 EC 访问均按 ≤2 往返/秒设计。

---

## 六、跨项目沉淀

| 类型 | 位置 |
|---|---|
| **技能** | `~/.workbuddy/skills/windows-sensor-recon/SKILL.md` —— 含 **3 条"结论卫生"规矩**、**收口测试**、Insyde BIOS 拆解全链、ARM MCU 反汇编、EC 端口协议、HID feature 读取等 |
| 每日日志 | `.workbuddy/memory/2026-09-27.md` · `2026-09-28.md` |
| 关键纪律 | **提方案前先 grep 项目文档**；**读长期项目文档先读顶部 20 行**；**"零结果"先排除解析失败** |
