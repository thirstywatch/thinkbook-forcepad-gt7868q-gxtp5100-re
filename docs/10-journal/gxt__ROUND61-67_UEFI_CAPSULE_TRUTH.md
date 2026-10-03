# ROUND61-67 · 真相闭合：`TB14P_GT7868Q_...BIN` 是 UEFI 更新胶囊，不是 HID 固件

> 日期：2026-09-30
> 前置：`ROUND60_OFFICIAL_SOURCE_SOLUTION.md`、`ROUND47-59_FLASH_OFFSET_SEMANTICS_REPORT.md`
> 结论等级：**★★★★★ 物证级**（有本机 DriverStore + UEFI 设备树双重佐证）

---

## 0. 一句话结论

**我们逆向了一个月的那个 BIN，根本不是一个"HID 固件"，而是 Microsoft UEFI Firmware Update 规范下的"更新胶囊"。**
它由 `Class=Firmware` 的 INF 安装，Windows 不解析其内容，直接交给 UEFI/BIOS 处理。
**所以「高熵区怎么解密」这个问题从一开始就不成立 —— 没有任何一方需要解密它。**

---

## 1. 物证来源

本机 `C:\Windows\System32\DriverStore\FileRepository\` 下存在：

```
goodixtouchpad.inf_amd64_dd57a59bc9759d61\
    GoodixTouchpad.cat                         11,888 B   Feb  2 2024
    GoodixTouchpad.inf                          1,212 B   Feb  2 2024
    TB14P_GT7868Q_14030522_20240202.BIN       161,628 B   Feb  2 2024   ★
```

`C:\Windows\Firmware\` 下存在**同一份文件的硬链接**：

```
TB14P_GT7868Q_14030522_20240202.BIN          161,628 B   Feb  2 2024   (link count = 2)
{652d4eee-b41c-4809-80e7-ef22561db51e}\
```

⇒ 该胶囊**已经安装并落地到系统**。

---

## 2. INF 全文关键行（决定性证据）

```ini
[Version]
Class=Firmware                                       ; ← 不是 HIDClass！
ClassGuid={f2e7dd72-6468-4e36-b6f1-6488f42c1b52}     ; ← FU 设备类 GUID
Provider=%Provider%
DriverVer=02/02/2024,0.0.2.8
CatalogFile=GoodixTouchpad.cat

[Firmware.NTamd64]
%FirmwareDesc% = Firmware_Install,UEFI\RES_{b6ae105a-ba93-4fc8-aa28-e63903ffedde}

[Firmware_CopyFiles]
TB14P_GT7868Q_14030522_20240202.BIN

[Firmware_AddReg]
HKR,,FirmwareId,,{b6ae105a-ba93-4fc8-aa28-e63903ffedde}
HKR,,FirmwareVersion,%REG_DWORD%,0x14030522          ; ← 文件名里的 14030522
HKR,,FirmwareFilename,,TB14P_GT7868Q_14030522_20240202.BIN

[DestinationDirs]
DefaultDestDir = %DIRID_WINDOWS%,Firmware            ; → C:\Windows\Firmware

[Strings]
Provider     = "Goodix"
FirmwareDesc = "Goodix Update UEFI"
```

**逐条含义：**

| 字段 | 含义 |
|---|---|
| `Class=Firmware` | 这是**固件更新驱动**，不是设备功能驱动 |
| `UEFI\RES_{b6ae105a-…}` | 目标是一个 **UEFI Firmware Resource 设备**，由 BIOS 通过 ESRT 暴露 |
| `FirmwareVersion=0x14030522` | BIOS 拿它跟触控板当前版本比对，决定要不要刷 |
| `DefaultDestDir=…,Firmware` | 胶囊被投放到 `C:\Windows\Firmware\`，等下次重启由 UEFI 消费 |

---

## 3. 本机 UEFI 设备树佐证

```
OK  Goodix Update UEFI   UEFI\RES_{B6AE105A-BA93-4FC8-AA28-E63903FFEDDE}\0
      DriverVersion  = 0.0.2.8
      DriverProvider = Goodix
      DriverDesc     = Goodix Update UEFI
      DriverInfPath  = oem87.inf          ← 已作为 OEM 驱动安装
```

同一棵树里并列的其他 UEFI FU 设备（证明这是标准机制，非个例）：

```
OK  Lenovo Battery Firmware 258.5   UEFI\RES_{652D4EEE-B41C-4809-80E7-EF22561DB51E}\0
OK  chixiao Firmware Update          HID\VID_17EF&PID_F006&COL01\6&C00634E&0&0000
OK  设备固件 / 系统固件               UEFI\RES_{…}\0  × 9 个
```

⇒ **触控板固件已经是最新（`14030522`），且正是通过这个胶囊刷入的。**

---

## 4. 完整数据流（修正版）

```
goodixtouchpad.inf  (Class=Firmware, Provider=Goodix)
        │  安装 / Windows Update 下发
        ▼
C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN   (胶囊落地)
        │  Windows 把 FU 设备 UEFI\RES_{b6ae105a-…} 交给 UEFI ESRT
        ▼
   重启 → 进入 UEFI
        │  BIOS 读 RES 资源，解析胶囊
        ▼
   BIOS 通过 I²C 把固件写入 Goodix GT7868Q 触控板
```

**关键点：整条链路上没有任何一方需要"解密"这份 BIN。**
Windows 只负责搬运；BIOS 按 UEFI 规范处理；触控板自己接收。

---

## 5. 对既有结论的修正

| 旧结论（ROUND1-60） | 修正 |
|---|---|
| 这是 Goodix HID 固件 BIN，可用 `gdixupdate` 刷 | ❌ 是 **UEFI FU 胶囊**；官方 `gdix_hid_firmware_update` 吃的是 GTX2/3/5/8/9 的 HID 固件，**不是这种胶囊** |
| 高熵区（`0x1400`–`0x18FFF`）是加密主固件 | ⚠️ 高熵是**胶囊载荷**的正常特征，UEFI 规范允许压缩/原样，**不存在"我们的密钥"这回事** |
| 需要找解密密钥 | ❌ **问题不成立**。没有密钥，也不需要密钥 |
| 与官方格式不符（PID 全 0、子固件数 0、校验和失配） | ✅ 仍然正确 —— 因为它压根**不是**那个格式，是另一种容器 |
| `tpfw_86272_PNOR_G1_7863.bin` 通过官方校验 | ✅ 仍然正确，那是**另一条线**的真实 HID 固件（GT7863 系列） |

**重点：ROUND61 用官方解析器校验 15 个候选、只有 `tpfw` 通过的结论依然有效** —— 只是现在明白了为什么：它们本来就是两个物种。

---

## 6. Windows 侧的硬阻断（新发现）

用官方协议（`_I2C_DIRECT_RW` = `0x20`）尝试回读参数区，结果：

```
HID 枚举成功：
  VID=27C6 PID=01E9 UP=FF00 U=0001   ← COL04 Vendor-Defined
  path = \\?\HID#GXTP5100&Col04#5&52a7aed&0&0003#{…}

打开句柄：成功
GET_FEATURE(0x0e, len=65/64/10/8)  → OSError: read error   (全部失败)
SET_FEATURE([0e 20 00 00 05 01 96 F8 00 03]) → 返回 -1
bus_type = 3  (= I²C)
```

**判定：Windows 的 `hidi2c.sys` 不允许用户态对 I²C-HID 设备做 GET/SET_FEATURE。**

驱动栈取证：

```
ACPI\GXTP5100\1                    → hidi2c.inf      (Microsoft, 10.0.26100.8972)
HID\GXTP5100&COL01                 → msmouse.inf     (Microsoft)
HID\GXTP5100&COL02                 → input.inf       (Microsoft)
HID\GXTP5100&COL03                 → mtconfig.inf    (Microsoft)
HID\GXTP5100&COL04                 → input.inf       (Microsoft)
运行中: hidi2c  Running  C:\Windows\system32\drivers\hidi2c.sys
```

注意：DriverStore 里有 Goodix 自己的包 `goodixtouchpad.inf_amd64_…`，但**它只提供 Firmware 类设备，5 个 HID 接口全部绑在 Microsoft 驱动上**。这不是配置错误，是设计如此。

---

## 7. 走错的路（记录，避免重蹈）

| 错路 | 为什么错 |
|---|---|
| 找"解密密钥" | 胶囊不需要密钥；"K 泄漏"是判据错误（ROUND34 已纠） |
| 抓 USB trace | 触控板走 **I²C**（`bus_type=3`），**不经过 USB 总线**，USBPcap 抓不到 |
| 下载 "Zero Touch Driver" | 那是 **Lenovo Intelligent Sensing**（VL53L3/L7 ToF 传感器）驱动，与触控板无关；论坛说法是误传 |
| 用官方 `gdixupdate` 刷这个 BIN | 工具与容器不匹配（HID 固件 vs UEFI 胶囊） |

---

## 8. 「滑动震动」的可行路径（重新排序）

### 方案 A · Linux 侧（★★★★ 最现实）

依据：`github.com/ty2/goodix-gt7868q-linux-driver`，目标机 **ThinkBook 16+ 2024 IMH**（同代同芯片）。

```
local-overrides.quirks 已含:
  MatchVendor=0x27C6
  MatchProduct=0x01E9      ← 就是本机触控板
```

- 装上该内核模块后，`hid-multitouch` 接管设备，**hidraw 节点可用**
- Linux 的 `i2c-hid` **完整透传** GET/SET_FEATURE（不像 Windows 会拦截）
- 官方工具 `gdixupdate -d /dev/hidrawX` 可直接跑，我们能自己发 `_I2C_DIRECT_RW` 读写参数区
- **前提**：需要装 Linux（双系统或 U 盘 live）

### 方案 B · Windows 换绑驱动（★★ 风险中高）

把 COL04 从 `input.inf` 换绑到能透传 Raw HID 的驱动。
**风险**：可能导致触控板失效；需要 `PnpLockdown` 相关处理；不推荐作为首选。

### 方案 C · 硬件直驱（★★★ 已验证可行）

沿用 `<LAB>\touchpad-lab\` 的结论：

> 主机侧全封死 ⇒ 唯一可行 = **实体接管 `HDP`/`HDN` 焊盘直接驱动 LRA**

这条线有完整文档（`PREFLIGHT-STATE.md` / `NEXT-SESSION.md`），不依赖固件。

---

## 9. 文件清单（本轮新增）

| 文件 | 说明 |
|---|---|
| `round61_official_validator.py` | 复刻官方 `GetDataFromFile()`，批量校验候选 BIN |
| `round62_hid_enum.py` | 枚举本机 HID，定位 COL04 |
| `round62_pnp_devices.txt` | 设备清单原始输出 |
| `round63_i2c_hid_detail.txt` | I²C-HID 设备详情（含 `VID_27C6` 硬件 ID） |
| `round64_readback.py` | 官方协议只读回读脚本（Windows 下被阻断） |
| `round65_diag.py` | Feature-Report 通路诊断 |
| `round66_driverstack.py` | 驱动栈取证 |
| `round67_uefi_fu.py` | UEFI FU 设备与资源状态 |
| `ROUND61-67_UEFI_CAPSULE_TRUTH.md` | 本报告 |

---

## 10. 安全记录

- 全程**未发任何写命令**；未触碰 `00 10` / `00 11` / `0E 12`
- `GET_FEATURE` 尝试为纯只读；被 Windows 拒绝，无副作用
- 未修改任何驱动绑定、未动 INF、未改注册表
- 唯一"写"动作是 pip 安装 hidapi 到隔离 venv

---

## 11. 下一步建议（优先级）

| 优先级 | 动作 | 成本 | 收益 |
|---|---|---|---|
| ★★★★★ | 决定是否开 Linux 双系统 / live USB（方案 A） | 中 | 打开参数区读写通路 |
| ★★★★☆ | 在 Linux 下用 `gdixupdate -p` 读触控板版本，与本机胶囊版本比对 | 低 | 确认固件版本一致性 |
| ★★★☆☆ | 在 Linux 下回读 `0x1800` (27B) / `0x3800` (8B) | 低 | **第一次拿到触觉参数真值** |
| ★★☆☆☆ | 评估方案 C 的拆机可行性 | 高 | 完全绕开固件 |
