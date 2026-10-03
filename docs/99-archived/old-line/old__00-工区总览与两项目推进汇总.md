# 工区总览与两项目推进汇总（2026-09-27）

> ⚠️ **2026-09-28 20:0x 更新 —— 本文是**历史快照**（09-27 当日）。**
> **现在的入口是 `README-工区导航.md`；触控板结论以 `docs-触控板/00-触控板结论总表.md` 为准；**
> **09-28 的成果见 `01-2026-09-28成果汇总.md`。**
> 目录结构已在 09-28 调整（`fw-touchpad/`+`fw-touchpad/`+`fw-touchpad/hid-probe/` → **`fw-touchpad/`**；新增 `fw-bios/`）——
> 下方「目录地图」已按新结构更新，其余内容保持当日原貌。

> 本文件是工区 `<WORKSPACE>` 的历史索引。
> 两个正式项目的主仓库在别处，本工区是 2026-09-27 一天突进的战场与产物。

---

## 一、目录地图（★ 2026-09-28 已更新为新结构）

| 目录 | 内容 |
|---|---|
| **`README-工区导航.md`** | **★ 工区入口（新）** |
| `docs-触控板/` | 10 份。**`00-触控板结论总表.md` = 权威收口**；其余为专题证据（多份带更正横幅） |
| `docs-角度/` | 角度项目报告 4 份（ACPI 事件表 / EC-RAM 地图 / 窗口实测 / 4KB 执行手册） |
| `docs-BIOS与EC/` | BIOS 全链路拆解报告 + 联想固件 hunt 报告 |
| `docs-方法情报/` | 逆向方法总谱 v2 / 侧面情报 / 关键人物 / 路径标记总结 |
| `scripts-acpi/` | ACPI 转储与 AML 解析脚本 12 个（dump_acpi / all_fields / decompile_qxx / dsdt_tpad / haptic_ram_xref …） |
| `scripts-ec/` | EC 实测脚本 15 个（RwDrv 读物理内存 / 端口协议 `ec_port_rw.py` / 快照差分 / LIDF 连拍） |
| `安全设置复原/` | `fix-unblock-rwdrv.cmd`（关 VBS，需重启）+ `revert-unblock-rwdrv.cmd` + 三份注册表备份 |
| `bios/` | BIOS 拆解全链：`extract/`（isflash.bin 19.2MB、fw_decompressed.bin 30.88MB、ffs_scan.py…）、`out/`（447 文件树 + 389 模块清单 + 13 个关键模块 bin + 3 份反汇编 + DSDT-528KB） |
| **`fw-touchpad/`** | **★ 触控板物料总汇（09-28 新整理，由原 `fw-touchpad/`+`fw-touchpad/`+`fw-touchpad/hid-probe/` 合并）**：固件本体、TF100A 反汇编 20,314 行、反汇编工具、`hid-probe/`、`lenovo-hunt/`、参考驱动 |
| **`fw-bios/`** | 非触控板固件样板：电池 capsule（`.cap`）、湛卢 CFU inf |
| `acpi-dump/` | 32 张 ACPI 表原始转储（761,872 B） |
| `hmm-figs/` + `tb14g6_hmm.pdf` | 联想硬件维护手册 13.7MB + 抽图 |
| `data/` | `af.txt`（全字段表）、`qxx.txt`（25 个 _Qxx）、`ecram_live_samples.bin`（336×4KB EC 窗口采样） |
| `tools-rw/` | `rwdrv/RwDrv.sys`、`rw/Win64`（RWEverything 工具） |
| `ec-lid-snaps/` | EC 窗口快照（含 LIDF 实证的 236 帧 `capture-20260927-212353/`） |

**两个项目主仓库（正本）**：
- 触控板：`<LAB>\touchpad-lab\`（状态权威 `PREFLIGHT-STATE.md`，入口 `NEXT-SESSION.md`）
- 角度：`<WORKSPACE>`（今日新增 `ec-re/` 子目录）

---

## 二、触控板项目（触觉/震动）推进情况

### 正本结论（touchpad-lab，9/13 起，未被今日工作推翻）
- **主机侧全封死**：HID 无 Manual Trigger OUTPUT 报表；Col04 厂商通道已真机判否（发 `A1` 无 `0xA2` 应答，`err=122` 是未处理类默认应答）；固件加密（128 位分组 + ECB 式 + 跨 4 年同密钥）；无第二份固件容器。
- **唯一可行路线 = 方案③：实体接管 `HDP`/`HDN` 焊盘直接驱动 LRA**（拆底盖可达，焊盘位置已定位）。
- 红线：禁批量轮询 Col04；≤2 往返/秒；刷机三连 `00 10 / 00 11 / 0E 12` 绝不碰。

### 今日真实增量（已并入 lab，见 `touchpad-lab/DELTA-2026-09-27-*.md`）
1. **★ N1 结论更正（最重要）**：旧结论「BIOS 里没有 Goodix 代码」是**两层错误**的产物——搜的是 Intel ME 区文件而非 BIOS 本体 + 在 LZMA 压缩态上搜字符串。真 BIOS 解压后（30.88MB / 447 模块）内含 **`GoodixTpDxe`**（48,590 B，`Goodix`×12），上游源码开源（`edk2-platforms\Vlv2TbltDevicePkg\GtpUpdate\GoodixTouchpadFMPImpl.c`）。
2. **★ 触控板固件本体到手**：`fw-touchpad/touchpad_GT7868Q_fw.bin`（161,628 B，TB14P_GT7868Q_14030522_20240202，一直在 `C:\Windows\Firmware\`）。其中 54KB 明文 TF100A（钛方）代码已完整反汇编；另 100KB 确认为加密。
3. BIOS 侧 vendor 寄存器模型：`0x100`(写17B命令)/`0x200`(变长)/`0x300`(读5B)，命令包 `01 A1 <24位参数>…[0x35]=0xAA`。
4. 新增纪律：结论卫生规矩 A/B（"容器里没有 X"须附明文旁证；引用文件须注明所属区）。

### 今日作废的自产结论（已在报告加横幅）
「推翻主机没有入口」（Col04 早已判否）· TF100A 是 M4F（实为 STM32F1 类 M3）· "Goodix 的 TF 子系统"（实为钛方科技）· 明文区无数值表（项目已有 39 条命令表）。

### 下一步
- 主线：**方案③ HDP/HDN 接线与驱动设计** + **PC 侧手势软件**（可并行，零风险）。
- 备选：用 GT7868Q 侧新物料（`0x100/0x300` 寄存器模型）对照项目命令表复核 H1 旁证。

---

## 三、角度传感器项目（开盖角度）推进情况

### 正本结论（lid-probe 报告）
11 条路线全部封死：EC 只对外交出 `_Q15` 事件信号 + `_LID` 二元状态；4KB 读取路线因窗口只实现 768 字节而作废；无角度专用传感器暴露。

### 今日突破（`lid-probe/ec-re/`，这是全天最有价值的新路径）
1. **★ 解出 EC 命令协议 `ERCD`**（DSDT 反编译）：6 字节入参 → 8 字节响应，寄存器 `ECMD`/`EDT1-5`/`ECTB`(门铃)/`ECTE`(使能)/`ERN1-8`(响应)，10ms×100 轮询（比 EC 高频轮询红线慢 30 倍，按设计安全）。
2. **★ EC 命令表**（12 个调用点）：**`0xB0` = EC 任意地址读**（ERRD）/ `0xB1` = 任意地址写 / `0x5B 0x80/81/82` = 16 位地址操作 / `0x45 0x20-0x23` = 风扇转速 / `0x45 0xF6` = 适配器功率。
3. **★ 全部命令寄存器落在 768 字节可读窗口内**（ECCD 块 @`0xFE0B0400+0x220`，签名 `5A A5` 实测在位；ECMD@0x22B、EDT1-5@0x22C-230、ERN1-8@0x223-22A）。
4. **LIDF 正确定位 = 字节 0x0B8 位 1**（此前 0x856/0x0BD 两次都是 AML PkgLength 公式错误；判据：8 位寄存器字节对齐 + 温度锚点 0x12-0x17）。
5. **噪声基线**：768 字节中 98% 稳定，仅 14 字节自然漂移（温度/定时器），差分实验自动过滤。

### 状态：有一个零风险实验待执行
`scripts-ec/ec_lid_verify.py` —— 开盖基线 → 合盖 → 开盖（A/B/A 三快照，纯只读），验证 LIDF 位随盖子状态翻转。**只需用户 3 次回车。**
之后可评估：发 `0xB0` 事务（写命令寄存器，需点头）→ 扫 EC 地址空间找随角度变化的字节。

---

## 四、跨项目待办（★ 2026-09-28 20:0x 更新为当前状态）

> 原始当日待办已不适用，下表为**当前**状态。完整版见 `README-工区导航.md` §四。

| # | 事项 | 当前状态 |
|---|---|---|
| **1** | **EC 端口路径实测**：`fix-unblock-rwdrv.cmd` → 重启 → `run-ec-port-test.cmd` | ⏸ **等喆执行**（VBS/HVCI 已复原为 1，RwDrv 未加载） |
| 2 | 触控板：TF100A「播放/波形」通路回溯（CCER ×21） | ⭕ 未做，纯离线 |
| 3 | 触控板：DSDT 的 GXTP 子树解析 | 🟡 脚本 `dsdt_tpad.py` 已写一半 |
| 4 | 角度：**LIDF 实证已成功** ✅（236 帧，零假阳性）；`\LIDS` 消费方待查 | ⭕ |
| 5 | 触控板方案③（HDP/HDN 接线与驱动设计） | ⭕ 待喆决策 |
| 6 | PC 侧手势软件 Phase 1（从未实现，零风险） | ⭕ 随时可开工 |
| ~~7~~ | ~~NJCN68WW 差分（Copilot→右Ctrl）~~ | 搁置 |
