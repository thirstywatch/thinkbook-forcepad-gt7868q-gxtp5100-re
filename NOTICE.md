# NOTICE · 第三方组件与合规声明

## 1. 本项目不包含的内容

本仓库**只分发方法论、自写脚本、分析结论、本机生成的数据、以及许可明确的开源厂商源码**。以下内容**明确不包含**，请自行从官方渠道获取：

- 任何**厂商固件二进制**（Lenovo / Goodix / 钛方 / 艾为）
- 任何**厂商工具二进制**（`GoodixTouchpadTool.exe`、Dell DUP 等）
- 受版权保护的 datasheet / 文档（AW86927FCR、微软触觉规范等）
- 第三方二进制工具（RWEverything、PawnIO 模块、ACPICA iasl）
- **许可不明**的第三方源码与厂商派生二进制（如厂商 `goodix_cfg_group*.bin`）

获取方式见 [`reproduce/ENVIRONMENT.md`](reproduce/ENVIRONMENT.md) 与 [`reproduce/DATA-INVENTORY.md`](reproduce/DATA-INVENTORY.md)。

## 2. 第三方组件（本仓库仅引用，不分发）

| 组件 | 用途 | 许可 | 出处 |
|---|---|---|---|
| **ACPICA iasl** | AML 反编译 | ACPICA 许可（BSD/GPL 双许可以官方为准） | acpica.org |
| **RWEverything** | MMIO / PCI 配置空间直读 | 专有免费软件（**不可再分发**） | rweverything.com |
| **PawnIO** | 签名内核驱动（SMBus / EC / MMIO） | 开源 | github.com/ZenithDevs/PawnIO |
| **capstone** | 多架构反汇编引擎 | BSD-3 | capstone-engine.org |
| **hidapi** | HID 设备访问 | BSD-3 / GPL 双许 | github.com/libusb/hidapi |
| **pywin32** | Windows API | PSF-ish | github.com/mhammond/pywin32 |
| **Linux 内核 `aw86927` 驱动** | AW86927 参考实现 | GPL-2.0 | patchew.org（Fairphone 补丁组） |
| **汇顶开源驱动 / 更新工具源码** | 容器格式与命令表依据 | **Apache-2.0 / GPL-2.0**（以文件头为准） | github.com/goodix —— ★ **2026-10-14 起随仓库分发**（`poc/gdix-official-missing/`，见 §2.1） |
| **ESP32-Haptic-Precision-TouchPad 项目**（barryblueice） | 标准 HID 触觉接口参考 | 以其仓库许可为准 | github.com/barryblueice |

## 2.1 随仓库分发的官方源码子集（2026-10-14 整理轮起）

> 原先「第三方源码一律不入库」的做法在 2026-10-13 被**按许可分级**取代：只有**能从文件本身证明许可**的内容才随仓库分发，其余仍只给链接。
> 逐目录许可、版权人与出处见 [`poc/gdix-official-missing/LICENSES.md`](poc/gdix-official-missing/LICENSES.md)；逐文件 sha256 见 [`vendor-refs/links.md`](vendor-refs/links.md) §XII。

| 路径 | 许可 | 版权人 |
|---|---|---|
| `poc/gdix-official-missing/2026-07-18新增/`（12 文件） | Apache-2.0 | Copyright (C) 2017 / 2018 Goodix Inc |
| `poc/gdix-official-missing/gtx8_driver_linux/`（14 文件） | GPL-2.0 | Copyright (C) 2019-2020 Goodix, Inc. |
| `poc/gdix-official-missing/gtx8_mainline_20260228/`（6 文件） | GPL-2.0-only | Goodix, Inc. / Linaro Ltd. / Aelin Reidel（LKML 补丁） |

**不入库**（`.gitignore` 已按路径拦死）：厂商 `goodix_cfg_group*.bin`（文件内无许可声明）· 微软触觉规范 HTML（受版权文档）。

## 2.2 本机生成的数据（含 `.bin` 证据）

> `.gitignore` 默认拦死 `*.bin`（厂商固件），但**本机实测读回**的数据属「本机生成的数据」，**必须入库**（2026-10-14 起加白名单）：

| 路径 | 是什么 |
|---|---|
| `data/acpi/*.bin` | 本机 ACPI 表导出 |
| `data/reference/*.bin` | 本机 cfg 记录样本（如 `lab__cfg_record_orig_1084.bin`）+ 从固件自身恢复的周期加扰表 K |
| `data/logs/gxt__*.bin` | 退化 / 正常态的 `0x96F8` 状态采样 |
| `tools/hid/lab__cfg_backup_*.bin` · `_cfg_115_240_legal.bin` | cfg 备份与「合法改写」样本（B36 / B38 的复现材料） |

## 3. 周期加扰表 K 的说明

本仓库**提供** `data/reference/K_gt7868q.bin`（1,024 B，sha256 `1a4847391f429a6b233df317bdf4c0b9…`），用于解开固件的周期 XOR 加扰。

**它不是厂商的密钥材料**，而是**从固件自身恢复出来的**：加扰区存在大段零填充，`0 ⊕ K = K` 使 raw 中直接出现 K 的副本。因此它不含任何厂商秘密、不含设备唯一信息，对不同机器与批次的同型号固件通用。

完整恢复方法见 [`method/03-obfuscation-crack.md`](method/03-obfuscation-crack.md)，任何人都能从自己取得的固件中重新导出。

## 4. 免责声明

- **按本文档操作设备有变砖、损坏硬件、丧失保修的风险。**
- 本项目记录的所有写入/刷写类操作，**建议在料板（备用触控板模块）上先行验证**。
- 作者不对任何设备损坏、数据丢失或保修失效负责。
- 本仓库内容仅供安全研究与互操作性研究用途。请遵守当地法律与设备厂商的服务条款。

## 5. 商标

Lenovo、ThinkBook、Goodix、Awinic 等名称为其各自所有者的商标。本仓库仅在指称对应产品时使用，不主张任何权利。
