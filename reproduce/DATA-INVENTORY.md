# 数据资产清单

> **原则：本仓库不打包任何厂商固件二进制、厂商工具、受版权保护的 datasheet。**
> 本节给出每项资产的**内容说明 + 获取方式 + sha256**，供复现者自行取得后核对。

---

## 一、可入库资产（本机生成物 / 分析产物）

这些**随仓库分发**，位于 `data/` 下。

| 资产 | 位置 | 大小 | sha256（前 32 位） | 说明 |
|---|---|---|---|---|
| 本机 DSDT（原始 AML） | `data/acpi/DSDT_LENOVO_CB-01_DSDT.bin` | 528,582 | `8e3088f0c97407054b2b91da5c9a02d2` | 由注册表零权限导出 |
| 本机 DSDT（反编译 ASL） | `data/acpi/DSDT_LENOVO_CB-01_DSDT.dsl` | ~3.8 MB | — | 100,645 行 |
| SSDT 全集 | `data/acpi/SSDT_*.bin` | — | — | 32 表 |
| HID 描述符 / caps | `data/hid-descriptors/` | — | — | 四集合 |
| cfg 解析产物 | `data/reference/` | — | — | TLV 展开、TAG 字典（**不含原始 cfg**） |
| 实测日志 | `data/logs/` | — | — | EC 差分、Col04 探测等 |

### 1.1 ★ `data/reference/` 完整清单（2026-10-03 终审后 15 份）

| 文件 | 大小 | 说明 |
|---|---|---|
| `K_gt7868q.bin` + `.README.md` | 1,024 B | ★ 周期密钥 K（1024 B，卡方 0.00，人工配平）。**不是厂商密钥材料** |
| `gxt__tpcfgsid0_Xiaomi7867_20240307.cfg.txt` | 6.5 KB | 跨厂商 cfg 样本（**小米 7867，非本机**）|
| `gxt__tpcfgsid2_20230407.cfg.txt` | 2.8 KB | NOR_G1 / 7863 |
| `gxt__tpcfgsid3_LaiBao7986P_20220701.cfg.txt` | 9.3 KB | LaiBao 7986P |
| `lab__GoodixTpDxe.asm.txt` | 244 KB | ★ BIOS 侧宿主寄存器访问协议（§10.7.1，6,859 条指令）|
| `lab__TF100A_thumb.asm.txt` | 670 KB | ★ TF100A 全镜像反汇编（§9.5）|
| **`old__FmpDxeY750.asm.txt`** | 142 KB | 🔴 **终审找回**：ESRT 表构建器（§10.7.2）|
| **`old__I2cTouchPanelDxe.asm.txt`** | 124 KB | 🔴 **终审找回**：I2C-HID → AbsolutePointer 通用管道（§10.7.4）|
| **`old__CompalEcDxeDrv.asm.txt`** | 91 KB | 🔴 **终审找回**：EC DXE 驱动 |
| **`old__CompalEcSmmDrv.asm.txt`** | 120 KB | 🔴 **终审找回**：EC SMM 驱动 |
| **`hidp__ec_text.asm`** | 4.1 MB | 🔴 **终审找回**：EC 固件反汇编 |
| `lab__00-scan.rw` / `lab__10-probe.rw` / `lab__I2C0-AW86927.rw` | 10 KB | RWEverything 脚本（**文本，不含 RWE 二进制**）|

---

## 二、不入库资产（需自行获取）

### 2.1 固件

| 资产 | 大小 | sha256（前 32 位） | 获取方式 |
|---|---|---|---|
| **`TB14P_GT7868Q_14030522_20240202.BIN`**（本机） | 161,628 | **`0033d075fae88f0048544696c8941ed7`** | `C:\Windows\Firmware\`；或联想官网固件包 |
| **`TB14P_..._TF100A-sens40to8.BIN`**（补丁副本） | 161,628 | **`f39f80e0766f2a6fb9242ed53302c00f`** | 由 **`tools/firmware/make_tf100a_sens_patch.py`** 生成（P9）。<br>★ 该脚本已用真实镜像验证：**输出与手工补丁件逐字节相同**。<br>⚠️ BIN 本身**不入库**（厂商固件派生品） |
| 解出的明文（`GT7868Q_plain.bin`） | 161,628 | `e2eb2947591bd6b1fa073c889843bd09` | 由 P3 生成 |
| **`GT7868Q_scramble_key.bin`**（周期密钥 K） | **1,024** | **`1a4847391f429a6b233df317bdf4c0b9`** | 由 P3 恢复 |
| 官方明文固件 `tpfw_86272_PNOR_G1_7863.bin` | 86,272 | — | 汇顶官方工具包 |
| `goodix_tp_payload.bin` | 133,628 | `e7d1196e4aa1bc9079505d3e627b2bce` | 项目中间产物 |
| **对照样本 `GT7936L_16753412.bin`**（BERLIN 族真明文） | 258,128 | `d6e438f8f7d33b10f5ba27180e58d4fd` | LVFS（linuxhw/firmware 仓库） |

> ### ✅ 周期加扰表 K **已随仓库提供**
> | 项 | 值 |
> |---|---|
> | 文件 | `data/reference/K_gt7868q.bin` |
> | 大小 / sha256 | 1,024 B · `1a4847391f429a6b233df317bdf4c0b9d0d8dd036c52595bb8f2a36ec4faad65` |
> | 特征 | 256 个值各出现 4 次，**卡方 = 0.00** |
> | 用法 | `plain[x] = raw[x] ^ K[(x + 316) % 1024]` |
> | 说明文件 | `data/reference/K_gt7868q.README.md` |
>
> K **不是厂商分发的密钥材料**，而是**从固件自身恢复出来的**（零填充区 `0 ⊕ K = K`），
> 不含任何设备唯一信息，对不同机器/批次的同型号固件通用。
> 完整恢复方法见 `method/03-obfuscation-crack.md`，任何人都能从自己取得的固件里重新导出。

### 2.2 BIOS / 驱动模块

| 资产 | 大小 | sha256（前 32 位） | 获取方式 |
|---|---|---|---|
| `GoodixTpDxe.bin` | 48,590 | `cd5dff579f560fd9c41f8f41df1eddd9` | BIOS 更新包解包 → FFS 扫描 |
| `EcCapsuleDxe.bin` | 53,578 | `633fbaf079003bbba2ec9e1d29fff094` | 同上 |
| `tpupdate_driver.dll` | — | — | `DriverStore\...\goodixtouchpad.inf_amd64_*` |
| `tpcfgsid{0,2,3}.cfg` | — | — | `C:\Windows\System32\drivers\UMDF\` ⚠️ **本机 DriverStore 只装固件、不带 cfg** |

### 2.3 官方源码（一手依据，务必取得）

| 仓库 | 用途 |
|---|---|
| `gdix_hid_firmware_update`（**含 `gt7868q/` 专目录**） | 容器格式、刷机命令、校验和 |
| `gtx8_driver_linux` | 驱动侧语义、`report_fixup` |
| **`gtx2/` 那一层** | ★ **本项目曾漏掉它，导致一直拿不到官方命令表** |

关键常量出处：

```c
/* gt7868q_firmware_image.h */
#define FW_HEADER_SIZE        256
#define FW_SUBSYS_INFO_SIZE   8
#define FW_SUBSYS_INFO_OFFSET 32        /* 表项自 +0x20 起 */
#define FW_SUBSYS_MAX_NUM     28
#define GT7868Q_SUB_FW_DATA_OFFSET 256  /* 数据区自 +0x100 起 */
```

### 2.4 参考文档（受版权，**只给链接**）

| 文档 | 出处 |
|---|---|
| AW86927FCR datasheet | 艾为官方 / TI E2E 社区附件 `AW86927FCR.PDF` |
| AW86927 Linux 主线驱动 + 绑定 + 设备树 | patchew.org（Fairphone 补丁组） |
| 微软《Haptics implementation guide》 | `learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/input-haptics-implementation-guide` |
| HID Usage Tables（HUT 1.5） | usb.org |
| HMM 官方硬件维护手册 | 联想官方（本机 21LD） |
| 蓝莓（barryblueice）Wiki ×2 | `github.com/barryblueice/ESP32-Haptic-Precision-TouchPad/wiki` |

---

## 三、⚠️ 资产缺口（复现前请先补齐）

以下资产**原项目工区里有，但不在本仓库、且获取路径未在文档中写明**。详见 [`../gaps/GAPS.md`](../gaps/GAPS.md)。

| # | 缺口 | 影响 |
|---|---|---|
| 1 | `goodix-tool/` 工区（cfg 样本 + 审计脚本 269 份）**在地址清单之外** | P8 cfg 分析无法直接复跑 |
| 2 | `surface-vs-mine/` 工区（AW86927 源码 + 蓝莓源码实证）**在地址清单之外** | 外部对照材料缺失 |
| 3 | 本机 `tpcfgsid0.cfg` **手上没有**（三份 cfg 都不是本机） | 本机触觉参数默认值未知 |
| 4 | 部分脚本引用的绝对路径指向已归档工区 | 路径需重映射 |

---

## 四、sha256 归档格式

复现时建议生成 `data/manifest.sha256`：

```
0033d075fae88f0048544696c8941ed7dcca4269beaa84af76323ef5bbdcee72  TB14P_GT7868Q_14030522_20240202.BIN
f39f80e0766f2a6fb9242ed53302c00fd4e6a00313f4abbe94a91492f84fcb02  TB14P_..._TF100A-sens40to8.BIN
```

> **★ 纪律**：任何补丁生成后必须做 **"仅 N 字节差异"证明 + 双 sha256 存档**（原 + 补丁）。
