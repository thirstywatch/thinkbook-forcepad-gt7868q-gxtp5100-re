# 许可与出处 · `poc/gdix-official-missing/`（官方源码留档）

> 本目录**按许可分级**：只有**能从文件本身证明许可**的内容才随仓库分发；许可不明 / 受版权 / 厂商二进制**一律留在本地**。
> 建立于 **2026-10-14 整理轮**；逐文件 sha256 见 [`vendor-refs/links.md`](../../vendor-refs/links.md) §XII。

## 1. 随仓库分发（原件保留原版权头与 SPDX 标识）

| 子目录 | 内容 | 许可 | 版权人 / 出处 |
|---|---|---|---|
| `2026-07-18新增/`（12 文件） | 汇顶官方 `gdix_hid_firmware_update` 的 `gtx9/` / `marsei/` 等层（`.cpp` / `.h` / `CHANGELOG.md`） | **Apache-2.0**（文件头均为 `Apache License`） | Copyright (C) 2017 / 2018 **Goodix Inc** · `https://github.com/goodix/gdix_hid_firmware_update` |
| `gtx8_driver_linux/`（14 文件） | 汇顶官方 gtx8 Linux 驱动（`goodix_ts_i2c.c` 等 + `docs/`） | **GPL-2.0**（文件头均为 `GNU General Public License`） | Copyright (C) 2019-2020 **Goodix, Inc.** · `https://github.com/goodix/gtx8_driver_linux` |
| `gtx8_mainline_20260228/`（6 文件） | 主线 `goodix_gtx8` 补丁（`patch_0/1/2.txt` + `gtx8.c/h` + README） | **GPL-2.0-only**（文件头 SPDX） | Copyright (c) 2019-2020 Goodix, Inc. · (C) 2023 Linaro Ltd. · (c) 2025 Aelin Reidel · LKML `20260228-gtx8-v2`（lore.kernel.org） |
| `goodix_cfg_bin_20261013/README.md` 与 2 个自写脚本 | **本项目自写**的取回/解析脚本与说明 | 本项目 Apache-2.0（见仓库根 `LICENSE`） | 本项目 |
| `COPYING.GPL-2.0.txt` | **GPL-2.0 许可正本**（为上面 2、3 行随附） | GPL-2.0（FSF 文本，可逐字复制） | Free Software Foundation, Inc. |

### 许可文本

* **Apache-2.0**：仓库根 [`LICENSE`](../../LICENSE) 即该许可全文（本项目自身亦为 Apache-2.0），适用于上表第 1 行。
* **GPL-2.0 / GPL-2.0-only**：适用于上表第 2、3 行。原文件的 SPDX 头与版权声明**原样保留**；**许可全文已随附**同目录的 [`COPYING.GPL-2.0.txt`](COPYING.GPL-2.0.txt)（FSF 现行正本，17,984 B / 338 行，sha256 `edaef632cbb643e4…`，与 <https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt> 同文；（哈希按 **git 存储的 LF 版**计算；Windows 检出若启用 `core.autocrlf` 会转成 CRLF，届时工作区文件的哈希会不同 —— 以 `git cat-file blob HEAD:<path>` 的哈希为准））。

## 2. 不随仓库分发（留在本地 `poc/`，`.`gitignore` 已拦死）

| 路径 | 是什么 | 为什么排除 |
|---|---|---|
| `goodix_cfg_bin_20261013/*.dat`（3 份） | 厂商 `goodix_cfg_group*.bin` 真样本 | 文件内**无任何许可声明** ⇒ 许可不明；且属厂商派生二进制。⚠️ 其上流 URL 现已 404 ⇒ 本机副本可能是**现存唯一副本**（sha256 已存档） |
| `ms_haptics_spec/`（2 份） | 微软《Input Device Haptics Implementation Guide》（HTML + 文本抽取） | **受版权文档**（微软），本仓库只给官方链接（见 `vendor-refs/links.md` §3） |

## 3. 使用与免责

上述开源源码在本仓库中**仅作互操作性研究的技术依据**（对应结论见《全书》§19.54–§19.60 与登记表 B34/B35/B39/B40），未作修改（除 `goodix_cfg_bin_20261013/` 下两个自写脚本外）。
若你是权利人或认为某文件不应在此分发，请开 Issue，我们会立即移除。见 [`NOTICE.md`](../../NOTICE.md) §4。
