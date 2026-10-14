# ★★★★★ 官方「命令表」到手：`goodix_cfg_bin` 的 `reg_info` + 本机全表只读核验

> 日期：2026-10-13（第四轮：**信息固化 + 资产盘点 + 动手前的外部核查**）
> 触发：用户「先把所有信息固化…尝试前还是去看看官方，看看网上的相关信息」
> 来源（网上找到的新入口）：
> · `github.com/sm7150-mainline/goodix-cfg-bin`（Rust，**cfg bin 内容 dumper**，作者 Jens Reidel）
> · LKML `[PATCH v2 0/3] Input: add initial support for Goodix GTX8 touchscreen ICs`（2026-02-28）
> · 3 份厂商 vendor 仓库里的真实 `goodix_cfg_group*.bin`
> 归档：`poc/gdix-official-missing/goodix_cfg_bin_20261013/`（3 份样本 + README + 解析脚本）
> 工具：`tools/hid/gdix_cfgbin_scan.py`（全盘/内嵌扫描）
> 登记表：**B39** · 全书：**§19.59**

---

## §0 一句话

> **项目找了很久的「官方命令表」找到了 —— 它不是一张固件里的表，而是【每个 cfg 包头部内嵌的 `reg_info`】。**
> **从 3 份官方 `goodix_cfg_bin` 样本里提取出的地址表，与本机实测【完全一致】：`command = 0x4160`、`cfg_addr = 0x96F8`。**
> **并且本机只读核验：该表的 12 个地址在本机【全部响应】—— 其中 `0x4018` = ASCII `"YELSTO"`（活体 IC 自报 Yellowstone 家族），`0x4022` = `"7869"`（IC 自报 PID），`0x402F` = `04`（sensor_id）。**

---

## §1 新找到的外部入口（这是本轮"看网上"的核心收获）

| 来源 | 是什么 | 对我们的价值 |
|---|---|---|
| **`sm7150-mainline/goodix-cfg-bin`** | Rust 写的 **`goodix_cfg_group.bin` 内容 dumper**（`src/main.rs` 5,473 B） | ★★★★★ **给出了 `goodix_cfg_bin` 的逐字节格式**（项目此前只知道结构体名，不知字节布局） |
| **LKML `[PATCH v2] Goodix GTX8 touchscreen`**（Jens Reidel，2025-09 → 2026-02） | 主线化 gtx8 触屏驱动（563 行） | ★★★★ **官方外部的家族谱系陈述**与**校验和差异**说明（见 §5） |
| 3 份 `goodix_cfg_group*.bin`（摩托罗拉 / 小米 vendor 仓库） | 真实官方 cfg bin | ★★★★★ **可解析出 `reg_info` 地址表真值** |

> ★ LKML 原文两句直接相关：
> · 「**The checksum method differs yet again**」·「the evolution seems to be: **Normandy → Yellowstone → Berlin**」
> · 「**I extracted the addresses from a couple of config files using a small tool**」⇒ **作者也确认：地址是从 cfg 文件里提的** —— 与本轮结论同源。

---

## §2 ★★★★★ `goodix_cfg_bin` 的完整字节格式（首次给出）

来源：`goodix-cfg-bin/src/main.rs`，与官方 `gtx8_driver_linux/goodix_cfg_bin.h` 的每个结构体**逐字段一致**。

```
head（10 B，packed）
  u32 bin_len          ① 必须 == 文件长度
  u8  checksum         ② 必须 == sum(data[5 .. bin_len]) & 0xFF
  u8  bin_version[4]
  u8  pkg_num
+ 6 B 保留                                   → TS_CFG_BIN_HEAD_LEN = 16

pkg_num × u16 LE 偏移表（各 2 B，绝对文件偏移；依次递增）

各包 @偏移（GoodixCfgPackage）：
  GoodixCfgPkgConstInfo  56 B
      u32 pkg_len
      u8  ic_type[15] · u8 cfg_type · u8 sensor_id
      u8  hw_pid[8] · u8 hw_vid[8] · u8 fw_mask[9] · u8 fw_patch[4]
      u16 x_res_offset · u16 y_res_offset · u16 trigger_offset
  GoodixCfgPkgRegInfo    65 B
      14 × { u16 addr; u8 reserved1; u8 reserved2 }   （共 56 B）
      + u8 reserved[9]
      ⇒ cfg_send_flag · version_base · pid · vid · sensor_id · fw_mask ·
        fw_status · cfg_addr · esd · command · coor · gesture ·
        fw_request · proximity
  cfg 数据 …
```

**⇒ 结构体名（`goodix_cfg_pkg_reg_info`）项目早就知道（§19.55.4）；本轮补上的是【字节布局与偏移算法】。**

---

## §3 ★★★★★ 从 3 份官方样本提取的 `reg_info` 地址表（三份**完全一致**）

| 角色 | 地址 | 备注 |
|---|---|---|
| `version_base` | **`0x4014`** | 版本块起点 |
| `pid` | **`0x4022`** | 指向 `patch_pid` |
| `vid` | **`0x402A`** | |
| `sensor_id` | **`0x402F`** | |
| `cfg_send_flag` | **`0x4034`** | |
| **`command`** | **`0x4160`** | ★ 项目实测 `CMD_ADDR` |
| `esd` | **`0x4166`** | |
| `coor` / `gesture` / `fw_request` | **`0x4180`** | 三者同址 |
| `proximity` | **`0x4182`** | |
| **`cfg_addr`** | **`0x96F8`** | ★ 项目实测 cfg 地址 |
| `fw_mask` / `fw_status` | `0x0000` | 三份样本均未设 |

**样本**：`lfs-moto-cybert.dat`（1729 B）· `lfs-moto-dubai-csot.dat`（1701 B）· `lfs-xiaomi-manet.dat`（1601 B）；
三份均 `pkg_num=1`、`ic_type='Berlin'`、`cfg_type=1`、`sensor_id=255`。

---

## §4 ★★★★★ 本机只读核验：**地址表全部适用**（零风险，未写任何字节）

```
0x4000  (对照·存活位)  = A7 E0 ED B1     ✅ 与历史健康基线一致
0x4014  version_base   = 00 87 00 00
0x4022  pid            = 37 38 36 39 00 00   → ASCII "7869"
0x402A  vid            = 1C 02 03
0x402F  sensor_id      = 04                  ★ 不是 0
0x4034  cfg_send_flag  = 65
0x4160  command        = FF                  ✅ TS_CMD_REG_READY
0x4166  esd            = FF
0x4180  coor/gesture   = 40 01
0x4182  proximity      = 01 00
0x452C  (历史 fw_info)  = A6 EB A2 90
0x96F8  cfg_addr       = 22 00 1B 00 3D 01 04 65   ✅
```

### 4.1 `version_base` 起 40 字节整块（只读）

```
0x400e: DC 97 32 3E C4 F5 00 87 00 00 59 45 4C 53 54 4F |..2>......YELSTO|
0x401e: 00 00 06 00 37 38 36 39 00 00 00 00 1C 02 03 05 |....7869........|
0x402e: 00 04 00 00 03 75 65 A7                         |.....ue.|
```

| 偏移 | 内容 | 解读 |
|---|---|---|
| `0x4018` | **`59 45 4C 53 54 4F`** = ASCII **`"YELSTO"`** | ★★★★★ **活体 IC 自报 `YELSTO`** = **Yellowstone** |
| `0x4022` | `37 38 36 39` = ASCII **`"7869"`** | ★★★★ **IC 自报 PID 字符串** |
| `0x402A` | `1C 02 03 05` | vid 区（reg_info 指向 `0x402A`） |
| `0x402F` | **`04`** | ★★★ **sensor_id = 4** |
| `0x4034` | `65` | `cfg_send_flag` |

### 4.2 ★★★★★ `"YELSTO"` 出现在活体 IC 上的意义

- 项目此前**只在固件容器里**见过 `YELSTO`（memory：`YELSTO` = Yellowstone）；
- 现在它出现在 **IC 的 `version_base` 块里（`0x4018`）**；
- ⇒ **这是「本机 IC 属 Yellowstone 家族」的【IC 自报】证据** ——
  与三件独立事实完全吻合：① 官方 YS 5 字节命令帧与本机**逐字段相同**（§19.57.6）；
  ② YS 袋 sum-to-zero 校验在**本机 cfg 上 27/27 通过**（§19.56）；③ 官方 YS cfg 会话流程在本机**拿到 `0x7F`**（§19.58）。
- **⇒ 三条独立证据链（IC 自报 + 帧格式 + 校验算法）指向同一结论：本机 = Yellowstone。** 此前"本机属哪个家族"的反复，可以结案。

### 4.3 ⚠️ 一处需要解释的新张力（不掩盖）

| 来源 | 值 |
|---|---|
| 模组丝印 / 官方 INF / 项目文档 | **GT7868Q** |
| **IC 自报 `pid`（`0x4022`）** | **`"7869"`** |
| LKML 作者提到的家族 | Normandy（GT9886）→ **Yellowstone** → Berlin |

**⇒ 「IC 自报 7869」与「丝印 GT7868Q」不一致**，可能原因（**均为假说，未验证**）：
① `0x4022` 是 **`patch_pid`** 而 `rom_pid` 在别处（结构对齐未定）；
② "7869" 是 **patch 代次编号**，与器件型号（7868Q）不同层级；
③ 模组内芯片与丝印名存在代差。
**⇒ 记入待解，**不得把"7869"直接等同于"型号是 GT7869"**（纪律 110：数字相关只能提假说）。

---

## §5 ★★ LKML 提供的家族级校验和知识（外部独立印证）

LKML `[PATCH RFC 0/3]`（Jens Reidel，2025-09-18）原文：

> 「**The checksum method differs yet again**」
> 「Normandy → **Yellowstone** → Berlin」
> 「Yellowstone has a couple of things (**checksum**, fw_version) that appear similar to **Berlin** series ICs」
> 「**Register addresses are 16-bit on GTX8 and 32-bit on Berlin**」

⇒ 与本项目独立得出的结论**吻合**：
- 本机（YS）**帧内地址是 16 位**（`<addr16BE>`）✓
- YS 与 Berlin 的 `checksum_u8_ys` 同族（`sum(前 n-2) == BE16(末 2)`）—— 而 Berlin 样本的 `cfg_bin` 校验是 `sum(data[5..]) & 0xFF`（**U8 型**）⇒ **同一家族内不同层用不同校验型**（与 §19.55.2 的 `CHECKSUM_MODE_U8_LE / U16_LE` 枚举吻合）

---

## §6 ★★ 另一个官方仓库（项目从未看过）：`goodix_advance_touch_platform`

| 项 | 内容 |
|---|---|
| 描述 | Goodix Customized **HID-SPI** protocol driver（GATP），v1.0.1，2023-04-21 |
| 与我们设备的关系 | 我们是 **I²C-HID**，不是 SPI ⇒ **不能直接用** |
| **但结构上高度相关** | `main.h` 里有 **`struct goodix_ic_info`**（**从 IC 运行时读出的完整地址表**）：`version / feature / parm / misc`；<br>`misc` 含 `cmd_addr`、`cmd_reply_addr`、`fw_state_addr`、`fw_buffer_addr`、`frame_data_addr`、`touch_data_addr` …<br>`feature` 含 **`side_touch_feature`**、`stylus_feature`；`parm` 含 **`force_num`**（压感通道数）<br>`struct gatp_hid_desc` 含 **`cmd_register` / `data_register`**（**从 HID 描述符里读寄存器地址**） |
| **新枚举（有价值）** | `enum CHECKSUM_MODE { U8_LE, U16_LE }` · `enum GOODIX_ERR_CODE { EBUS, **ECHECKSUM**, EVERSION, ETIMEOUT, **EMEMCMP**, EOTHER }`<br>⇒ `ECHECKSUM`/`EMEMCMP` 与本项目 `CHKSUM_ERR`/`DATA_EQU` **同一设计语言** |
| **【新待办·零成本】** | **检查本机 Col02/Col04 的 HID 描述符里有没有 `cmd_register`/`data_register` 这类字段**（若 GATP 有，本家族的 HID 描述符可能也有 ⇒ 可据此**在主机侧自动取得地址**） |

> ⚠️ 注意：`parm.force_num` 是 **GATP（SPI）**的字段，**不代表本机有 force 通道**；本项目已确证压感走的是 **TF100A（独立 MCU）**。**不得外推**（纪律 148 扩展）。

---

## §7 ★★★★★ 「两套地址集」之争：**正式结案**

| 问题 | 之前的状态 | 现在 |
|---|---|---|
| 本机的 `command` / `cfg_addr` 是多少 | 靠**行为证据**（读 `0xFF`、写 `0x7F`）推定为 `0x4160` / `0x96F8` | ✅ **官方 `reg_info` 表给出同样两个值**；且本机 12 个地址**全部响应** |
| `0x60CC` / `0x60DC` 那套 | 「官方 gtx8 驱动里有，本机可能也认」 | ✅ **不适用本机**（本机 `0x60DC` 读回 `BB 39 0A E8`，不是版本号）；官方 `reg_info` 也不指向它们 |
| 「地址表在哪」 | §19.55.4 推定"在 cfg bin 里"，但本机 `sid0.bin` 是 TLV、查不到 | ✅ **在官方 `goodix_cfg_bin` 的包头部**（不是 TLV 那种文件）；**已提取并实测** |

**⇒ 结论：地址表 = 官方 cfg bin 包头的 `reg_info`（14 项）；本机适配值 = 上表；`sid0.bin`（TLV）是【另一条产品线（Windows/GT 工具）】的格式，二者不矛盾、不互译。**

---

## §8 资产盘点（本轮新增/改动，全部已落盘）

### 8.1 新增文件

| 路径 | 大小 | 说明 |
|---|---|---|
| `poc/gdix-official-missing/goodix_cfg_bin_20261013/` | 目录 | **3 份官方 cfg bin 样本** + `README.md`（格式+地址表+核验记录）+ 2 个原解析脚本 |
| `tools/hid/gdix_cfgbin_scan.py` | 4.4 KB | 全盘 / **内嵌**扫描 `goodix_cfg_bin`（`bin_len==文件长` + `checksum` + 偏移表 + `ic_type` 可打印，四重判据） |
| `docs/08-findings/2026-10-13-官方cfgbin地址表到手-本机reg_info全表核验.md` | 本文 | 主文档 |
| `poc/gdix-official-missing/gtx8_driver_linux/`（上一轮） | 13 文件 | 官方 YS Linux 驱动 |
| `poc/gdix-official-missing/2026-07-18新增/`（上一轮） | 12 文件 | 官方 `gdix_hid_firmware_update` v1.8.0 |
| `tools/hid/gdix_cfg_tool.py` | 5.3 KB | cfg 校验 / 合法改写 |
| `tools/hid/lab__r62_cfg_legal_write.py` | 11.7 KB | 三例对照实验脚本 |
| `tools/hid/_cfg_115_240_legal.bin` · `_r62_log.txt` | 1.1 / 3.5 KB | 改写样本 + 原始日志 |

### 8.2 本轮新增/改动的文档

| 路径 | 状态 |
|---|---|
| `docs/00-软件逆向全书-芯片固件主机控制.md` | **新增 §19.55 / §19.56 / §19.57 / §19.58 + 目录 + §20.0 数字刷新 + §20.11 第 6/7/8/9/10 项** |
| `docs/08-findings/00-矛盾与推翻登记表.md` | **新增 B33–B39（共 39 条）**；B32 加更正注 |
| `docs/08-findings/2026-10-13-*.md` | **7 篇新文档**（AW86927结案 · cfg校验算法 · gtx8源码 · gtx8驱动linux · 官方回复码全表 · 首次0x7F实验 · 本文） |

### 8.3 实验产物（真机）

| 项 | 结果 |
|---|---|
| `_r62_log.txt` | 三例对照全部命中；**B 例 `7F 00 01 00 80`（项目史上首次）** |
| 设备收尾状态 | `0x4000=A7 E0 ED B1` · `0x4160=FF` · `0x96F8=22 00 1B 00 3D 01…`（正常静息相位）· flash 未动 |

---

## §9 附：本轮外部核查的**结论清单**

| 核查项 | 结论 |
|---|---|
| `goodix/gtx8_driver_linux` 有无更新 | ❌ 最后一次推送 **2019-12-11**（v1.4.4.0）；内容已全量归档 |
| `goodix/gdix_hid_firmware_update` 有无更新 | ❌ 最新 v1.8.0 = **2026-08-22**；项目手上 584 B 的 CHANGELOG **就是最新那份** |
| `goodix` 组织下有无未看过的仓库 | ✅ 有 2 个：`goodix_advance_touch_platform`（本文 §6）· `goodix_ts_berlin`（v1.4.17 / 2026-04-20，项目已有该类文件） |
| 网上有无 gtx8 官方外的权威资料 | ✅ **LKML 主线化补丁**（Jens Reidel）+ 其配套 dumper ⇒ **本文最大收获** |
| 有无现成的 cfg bin 样本 | ✅ 3 份（摩托罗拉 ×2、小米 ×1）⇒ 已归档并实测核验 |

---

## §10 下一步（动手前的清单，全部有明确判据）

| # | 动作 | 成本 | 判据 |
|---|---|---|---|
| 1 | **用「合法改写 + 客观判据」重测历史存疑字段**（`+0x10F`/`+0x115`/`+0x42A`/`+0x119`/`+0x113`/`+0x117`） | 低 | **结果码必须 `0x7F`**（否则本次实验无效）**且**客观行为变化 |
| 2 | **读 `0x4014` 块拿 `rom_pid`/`patch_pid` 完整字符串**（本文只读了 40 B，可再读更长） | 零 | 得到完整版本标识，解释 §4.3 的 7869 张力 |
| 3 | **查 Col02/Col04 HID 描述符里有无 `cmd_register`/`data_register` 类字段**（§6） | 零 | 若有 ⇒ 主机侧可自动取得地址 |
| 4 | **找本机的 `goodix_cfg_group.bin`**（按 `sensor_id == 4` 挑包） | 零 | 找到即可拿到**本机专属的 `reg_info`**（尤其 `fw_mask`/`fw_status`，样本里是 0） |
| 5 | 会话写入持久化（`0E 12` → `0x1E000`） | 中（有退化史） | 仅在 1–4 有结果后再考虑 |
