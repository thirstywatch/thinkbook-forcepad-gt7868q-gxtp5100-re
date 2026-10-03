# 环境 · 依赖与工具链

> **本仓库不打包任何第三方二进制。** 本节给出全部依赖的**获取方式与版本要求**。

---

## 1. 运行环境

| 项 | 要求 | 备注 |
|---|---|---|
| 目标机 | ThinkBook 14 G6+ IMH（21LD）或同代 ForcePad 机型 | 其他机型需重新确认器件与地址 |
| 主机 OS | Windows 11（`10.0.26100`） | HID / 驱动层分析必需 |
| 交叉验证 OS | Linux live USB（任意现代发行版） | 可选，用于 P5/P6 交叉验证 |
| Python | **3.10+** | 分析脚本 |
| .NET | 6.0+ SDK（或 Windows 内置 .NET Framework + csc） | 22 个 C# PoC |
| 管理员权限 | PawnIO / RWE / EC 相关步骤**必需** | 纯 HID 工具（如 `gxmem.py`）**不需要** |

---

## 2. Python 依赖

```txt
# reproduce/requirements.txt
capstone>=5.0        # 多架构反汇编（ARM/Thumb 判定、ISA 指纹）
numpy>=1.24          # 熵 / 自相关 / 直方图统计
hidapi>=0.14         # 或 hid >= 1.0.5 —— HID 设备枚举与读写
pywin32>=306         # Windows 注册表 / ACPI 表导出
```

可选（仅部分脚本需要）：

```txt
scipy>=1.10          # 卡方检验等统计判据
matplotlib>=3.7      # 相位剖面 / 熵曲线绘图
pyserial>=3.5        # 若做硬件串口旁路
```

安装：

```bash
python -m pip install -r reproduce/requirements.txt
python reproduce/checklists/p0-env-check.py
```

---

## 3. 第三方工具（**不在本仓库内**，自行获取）

| 工具 | 用途 | 获取方式 | 许可注意 |
|---|---|---|---|
| **ACPICA iasl** | AML 反编译（`iasl -e SSDT... -d DSDT.bin`） | acpica.org 或 Intel 分发 | ACPICA 自有许可；**本仓库只记用法，不含二进制** |
| **RWEverything（`Rw.exe`）** | MMIO / PCI 配置空间 / I²C 直读（路线 W1） | rweverything.com | 专有免费软件，**不可再分发** |
| **PawnIO** | 签名内核驱动，提供 SMBus / EC / MMIO ioctl | GitHub `ZenithDevs/PawnIO` release | 开源；**模块经 RSA-4096 签名**，官方版只加载官方模块 |
| `SmbusI801.bin`（55,540 B） | PawnIO 模块：Intel i801/PCH SMBus | 同上 release 包（24 个模块） | — |
| `LpcACPIEC.bin`（2,612 B） | PawnIO 模块：ACPI EC（`0x62`/`0x66`） | 同上 | — |
| **HID 工具** | `hidapi` / Windows `HidD_*` | 见 §2 | — |
| **反汇编器** | capstone（脚本内）或 IDA/Ghidra（人工核对） | — | — |

### PawnIO 用法

```
pawnio_open → pawnio_load(blob) → pawnio_execute(handle, "ioctl_xxx", in, out, &retSize)
```

- 模块 `.bin` 放**同目录**。
- `pawnio_open` **需要管理员**（非管理员返回 `0x80070005`）。
- ⚠️ **PawnIO 校验 RSA-4096 签名**：官方版只加载官方签名模块 ⇒ 自写模块要么提交上游签名（W4），要么装 Unrestricted edition（= 未签名内核驱动 ⇒ 需关 Secure Boot）。

---

## 4. 数据依赖（固件 / 驱动 / 官方源码）

**这些文件不在本仓库内**，需自行从官方渠道下载。清单与获取方式见 [`DATA-INVENTORY.md`](DATA-INVENTORY.md)。

概要：

| 类别 | 来源 | 是否可入库 |
|---|---|---|
| 本机固件 `TB14P_GT7868Q_14030522_20240202.BIN` | `C:\Windows\Firmware\` 或联想官网 BIOS/固件包 | ❌ 厂商固件，**不入库**（只存 sha256） |
| 官方明文固件 `tpfw_86272_PNOR_G1_7863.bin` | 汇顶官方工具包 | ❌ 不入库 |
| `tpcfgsid*.cfg` | `C:\Windows\System32\drivers\UMDF\` 或驱动包 | ❌ 不入库 |
| 汇顶官方源码 | GitHub 开源仓库 | ❌ 不入库（给链接） |
| **本机 DSDT/SSDT 反编译 ASL** | 由 `dump_acpi_tables2.py` 生成 | ✅ **可入库**（本机生成物） |
| HID 描述符 / feature report 样本 | 由 `hiddiag.py` 生成 | ✅ **可入库** |
| cfg 解析产物（TLV 展开、TAG 字典） | 由脚本生成 | ✅ **可入库**（不含原始 cfg） |
| AW86927 datasheet | TI E2E 社区附件 / 艾为官方 | ❌ **受版权，不入库**（给链接） |

---

## 5. 环境相关的坑（实测）

| 坑 | 现象 | 解决 |
|---|---|---|
| **PowerShell 5.1 与非 ASCII** | 中文按 GBK 解码、全角标点吃引号；**bat 里 `chcp 65001` 也救不了提权行** | **ps1 交付前跑 `[ScriptBlock]::Create` 官方解析器全量检查**；**bat 正文一律纯 ASCII（+CRLF）** |
| **多重 BOM** | 文件开头 3 个 U+FEFF ⇒ `param()` 不再是首语句 ⇒ "赋值表达式无效" | 收敛为 1 个 BOM |
| **多行 `-f` 续行** | `L ("…")` 换行后接 `-f`，PS 5.1 不认 | 改单行 |
| **env 大小写重复变量** | `Path/PATH`、`HTTP_PROXY/http_proxy` ⇒ `Start-Process` 抛"字典已添加项" | 启动前清重复项 |
| **agent 会话 vs 用户会话** | 安全层禁止 agent 派生 shell（`Start-Process` 指向 powershell/cmd 直接拦）；普通 exe 可提权 | 提权脚本**只能由用户双击** |
| **用户侧脚本需自带诊断** | 否则"假 DONE-OK" | 必须落盘：提权成败（`_elev-log.txt`）、退出码、**结果文件新鲜度** |
| **iasl `-o`** | 反编译模式报 `Option requires a single-character suboption: -o` | 用 `iasl -e <SSDT...> -d <DSDT.bin>`，不加 `-o` |

---

## 6. 最小可行环境（只想跑离线部分）

只需要：

- Python 3.10+ 与 §2 的前三个包
- 一份本机固件 BIN
- 汇顶官方源码（用于字段对账）

即可完成 **P2 容器解析 → P3 加扰破解 → P4 反汇编追踪 → P8 cfg 语义 → P9 补丁生成**，全部离线、零风险。
