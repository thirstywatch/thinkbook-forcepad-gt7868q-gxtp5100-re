# 联想固件 hunt：触控板固件到手，EC 的 FwClass 认出来了

> 日期：2026-09-27　机型：ThinkBook 14 G6+ IMH（21LD）
> 目标：找 Lenovo 的① 触控板固件 capsule　② EC firmware
> 结果：**① 拿到实物（161,628 B）　② 拿到 FwClass GUID + 当前版本，实物不在本机**

---

## 一、结论速览

| 目标 | 结果 |
|---|---|
| **触控板固件** | ✅ **到手**：`C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN`（161,628 B） |
| 触控板 FwClass | ✅ **`b6ae105a-ba93-4fc8-aa28-e63903ffedde`**（ESRT 里显示为 **"Goodix Update UEFI"**，REV **14030522**） |
| 触控板固件版本 | **14030522** = 固件文件名里的版本号，ESRT 的 REV 与之逐位一致 |
| 触控板驱动包 | `goodixtouchpad.inf`，Provider=**Goodix**，`DriverVer=02/02/2024, 0.0.2.8` |
| **EC 固件** | ⛔ 本机没有实物；但 **FwClass GUID = `a9898afa-ef58-48fe-b09a-f476afce467c`**，当前版本 **REV 267 = 2.67**（与 DMI 的 "Embedded Controller Firmware Revision: 2.67" 吻合） |
| 顺带拿到 | ✅ **电池固件 258.5**（`5B11M67497.CAP`，2,113,472 B，`BTFW` 魔数） |
| 机制 | ✅ **联想固件投递全链路摸清**（见第四节），以后任何部件都能按同一套路找 |
| 更正 | ⚠️ 上一轮把 `_AUTOPAD_` 当 capsule 标签是**错的**（见第六节） |

---

## 二、触控板固件：实物 + 全部元数据

### 2.1 文件位置与来源

```
C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN     161,628 B   2024-02-02

来源驱动包（Windows 固件类驱动，非 UEFI capsule）：
C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\
    GoodixTouchpad.inf / GoodixTouchpad.cat / TB14P_GT7868Q_14030522_20240202.BIN
```

`goodixtouchpad.inf` 关键行：
```ini
Class       = Firmware
ClassGuid   = {f2e7dd72-6468-4e36-b6f1-6488f42c1b52}
Provider    = "Goodix"
DriverVer   = 02/02/2024, 0.0.2.8
HKR,,FirmwareFilename,,TB14P_GT7868Q_14030522_20240202.BIN
```
→ 走的是 Windows **Firmware 类驱动**（`FirmwareFilename` + CFU/固件更新类扩展）下发，**不是** UEFI capsule。

### 2.2 文件名解码

| 段 | 含义 |
|---|---|
| `TB14P` | **T**hink**B**ook **14** **P**lus = ThinkBook 14 G6+ IMH（本机） |
| `GT7868Q` | Goodix **GT7868Q** 触控板芯片 |
| `14030522` | 固件版本（与 ESRT 的 REV **14030522** 逐位一致） |
| `20240202` | 构建日期 2024-02-02 |

### 2.3 二进制结构实测

| 项 | 值 |
|---|---|
| 大小 | 161,628 B（0x2775C） |
| 整体熵 | 7.743 |
| 熵分布 | `0x2000–0x18000` ≈ **7.96**（紧凑代码段）｜`0x1A000–0x26000` ≈ **6.1–7.0**（配置/表）｜尾部有 `12 7A 54 12 7A 54 …` 规律重复 |
| 明文标识 | **`7868Q`** @0x1149；板级标签 **`_7YELSTO`** @0x1142 |
| 头部 | `73 C0 11 04 | 00 00 04 3C | 00 00 04 3C` … 随后是配置/区域表 |
| 区域表样例 | `0x1160` 起：`03 00 00 20 00 01 60 00` / `03 00 00 20 00 00 60 00` / `… 00 80 00` / `… 00 A0 00` / `… 00 C0 00` / `… 01 E0 00` … |

**注意**：这个 `.BIN` 是**原生 CFU 固件文件**，与 `GoodixTpDxe` 里描述的 **FMP capsule 包**（带 `Firmware package protocol` / PID / VID / chip type / subsystem 表）**不是同一种容器**。别拿驱动里的包格式去套这个文件。

---

## 三、ESRT 全量（本机 11 个可升级固件部件）

来源：`HKLM\SYSTEM\CurrentControlSet\Enum\UEFI\RES_*`（这就是 ESRT 的 Windows 落地形态）

| FwClass GUID | 设备描述 | REV | 判定 |
|---|---|---|---|
| **`a9898afa-ef58-48fe-b09a-f476afce467c`** | Device Firmware | **267** | ★ **EC 固件**（2.67，与 DMI 一致） |
| **`b6ae105a-ba93-4fc8-aa28-e63903ffedde`** | **Goodix Update UEFI** | **14030522** | ★ **触控板** |
| **`652d4eee-b41c-4809-80e7-ef22561db51e`** | **Lenovo Battery Firmware 258.5** | 1020005 | ★ **电池** |
| `6b791d8c-9286-4800-91d9-929dc2f23053` | **System Firmware** | 72595067 | BIOS/系统固件 |
| `3b8a509d-ef4a-4e0a-be64-6a45f903c38c` | Device Firmware | 1131A | 待查 |
| `978b4cea-7c60-41f8-b5dd-93797fd3f314` | Device Firmware | 0 | 待查 |
| `993bd1ce-03d4-7747-8565-7ebb67b714fe` | Device Firmware | 72595067 | 待查（REV 与 System FW 同） |
| `b9c68cc2-2096-a846-a743-e8c2795d97c9` | Device Firmware | 1 | 待查 |
| `c725e332-8c08-450b-97ba-57cccfa0da35` | Device Firmware | 0 | 待查 |
| `e196ad37-fe57-4ba6-a5fb-ce9374f301a9` | Device Firmware | AA4 | 待查 |
| `f224e838-4e1d-3c4a-4196-2fc3eef962f7` | Device Firmware | CF | 待查 |

### 3.1 EC 是怎么认出来的

1. **`EcCapsuleDxe` 的代码里包含 7 个 device-firmware GUID** —— 其中就有 `a9898afa-…`。
2. 该 GUID 的 **REV = `267`**，而 DMI 报 **Embedded Controller Firmware Revision: 2.67**。
3. BIOS 版本 `NJCN67WW` 与 EC 2.67 版本同步（Lenovo 把两者版本号绑在一起）。

→ **`{a9898afa-ef58-48fe-b09a-f476afce467c}` = EC 固件的 FwClass。**

### 3.2 `EcCapsuleDxe` 覆盖的 7 个 FwClass

`{3b8a509d-…}` / `{978b4cea-…}` / `{993bd1ce-…}` / **`{a9898afa-…}`(EC)** / `{b9c68cc2-…}` / `{c725e332-…}` / `{e196ad37-…}`

→ 它其实是**联想通用 device-firmware capsule 处理器**，不只管 EC。

---

## 四、联想固件投递机制（★ 全链路，以后照这套找）

```
① ESRT 声明可升级部件
     HKLM\SYSTEM\CurrentControlSet\Enum\UEFI\RES_{FwClassGUID}&REV_xxxxx
        ↓
② 两条投递通道
   (a) Windows 固件类驱动（FirmwareFilename）—— 用于触控板
        DriverStore\FileRepository\*.inf   Class=Firmware
        HKR,,FirmwareFilename,,<BIN 文件名>       → 文件落在 C:\Windows\Firmware\<BIN>
   (b) UEFI FMP capsule（FirmwareCapsuleFilename）—— 用于电池
        UEFI\RES_{GUID} 设备 → Windows Update 下发 → C:\Windows\Firmware\{GUID}\<name>.CAP
        ↓
③ CAP 文件 = Insyde isFlashApp 外壳
        PE32+ Subsystem=10，节表与 isflash.bin 同构
        PDB: c:\_edk2\Build\FlashUtilityPkg\RELEASE_DEVTLS\X64\
             FlashUtilityPkg\Application\isFlashApp_1M\isFlashApp\DEBUG\…
        .reloc 节 = $_IFLASH_* 容器
            $_IFLASH_DRV_IMG        （外层，铺满）
            $_DEVICE_FW_IMG_        ← ★ 设备固件本体（含 BTFW 头）
            $_IFLASH_BIOSIMG / INI_IMG / BIOSCER   （尺寸全 0，模板占位）
```

### 4.1 电池 capsule 实测（作为格式样板）

```
5B11M67497.CAP   2,113,472 B

$_DEVICE_FW_IMG_ @payload+0x1E1158
   +0x00  总长 0x00017D68 = 97,640
   +0x04  载荷长 0x00017D65 = 97,637
   +0x1D  "BTFW"  ← 魔数
   … 0x00010064 / 0x00017D40 / 0x00056D03(=355,587，疑为解压后大小)
   载荷体熵 7.81（压缩）
   尾部 0x1F9160+ ：X.509 证书链（"Certificate_S6"、sha256WithRSA、RSA-2048）
```

`oem88.inf`：
```ini
Provider     = "Lenovo Ltd."
FirmwareDesc = "Lenovo Battery Firmware 258.5"
DriverVer    = 01/24/2025, 258.0.0.5
FirmwareId      = {652d4eee-b41c-4809-80e7-ef22561db51e}
FirmwareVersion = 0x01020005
Device: UEFI\RES_{652d4eee-b41c-4809-80e7-ef22561db51e}
```

### 4.2 顺带发现：联想 AI 芯片用 CFU over HID

`zhanlufirmwareupdate.inf`（oem72.inf）：
```ini
Class = Firmware
%ZhanluFirmwareUpdate.DeviceDesc%=ZhanluFirmwareUpdate, HID\VID_17EF&UP:FFCF_U:0080
HKR,CFU\chixiao_0, Offer,   0,, %13%\offer0.bin
HKR,CFU\chixiao_0, Payload, 0,, %13%\payload0.bin
HKR,CFU\chixiao_1, Offer,   0,, %13%\offer1.bin
HKR,CFU\chixiao_1, Payload, 0,, %13%\payload1.bin
```
→ "湛卢/Zhanlu"AI 芯片，走标准 **CFU（Component Firmware Update）** 的 offer/payload 双文件模式。**这条通道以后可以用于别的 HID 设备固件升级。**

---

## 五、EC 固件的下一步（明确）

本机 `C:\Windows\Firmware\` 只有 2 个文件（触控板 BIN + 电池 CAP），**没有 EC capsule** —— 说明 EC 固件是靠 BIOS 出厂刷入 / 或通过 Windows Update 在需要时才下发。

**要拿到 EC 固件，三条可行路径：**

| # | 路径 | 具体做法 |
|---|---|---|
| 1 | **Windows Update / MS Update Catalog** | 触发 Windows Update 检查固件更新，观察是否新建 `C:\Windows\Firmware\{a9898afa-…}\`；或在 Catalog 里按 "Lenovo Ltd. - Firmware - <版本>" 逐个下载、解 CAP 看 FwClass 是否 `a9898afa` |
| 2 | **Lenovo 的 EC 独立包** | 查 21LD 的驱动列表里是否有 "Embedded Controller Firmware"/"固件" 类目（联想中国站 `newthink.lenovo.com.cn` 有，但页面是 JS 渲染，需抓其 API） |
| 3 | **从 EC 本身 dump** | EC 有 768 B 内存窗口（见上一份报告），但读不到自身固件；要靠 EC bootloader 或 SPI 读 |

**注意**：第 1 条最靠谱 —— 因为机制已验证（电池就这么来的），且设备硬件 ID 已知：`UEFI\RES_{a9898afa-ef58-48fe-b09a-f476afce467c}`。

---

## 六、更正：`_AUTOPAD_` 不是 capsule 标签

上一轮我把 `EcCapsuleDxe` / `CapsuleUpdateApp` 里的 `_AUTOPAD_` 当成了 capsule 标签目录。**错了。**

实测：`_AUTOPAD_` 在 **每个模块里都恰好出现一次**（`HddSpinDownDxe`、`ConPlatformDxe`、`CpuDxe`、`PiSmmCpuDxeSmm`、`TcgMor` …… 互不相关），出现位置固定模式：

```
[16 字节高熵数据] + "___AUTOPAD___" + 3 个 0 + [16 字节 GUID] + "_HFDM" + …
```

→ 这是 **Insyde 构建工具给每个 PE 镜像做的"自动填充"标记**（构稿期占位），**不是 capsule 标签**。

真正的 capsule 标签是：`$_IFLASH_*` / `$_DEVICE_FW_IMG_` / `$_PFAT_*`，以及组件级 `_TBT_IMG` / `_ISH_IMG` / `_ME_IMG_` / `_MGPHY__` / `$_MICROCODE_IMG` / `_IOM_IMG`。

---

## 七、产物

目录：`fw-touchpad/`

| 文件 | 内容 |
|---|---|
| **`touchpad_GT7868Q_fw.bin`** | ★ **触控板固态固件本体**（161,628 B，与系统 `C:\Windows\Firmware\` 内一致） |
| `battery_capsule_258.5.cap` | 电池固件 capsule（2,113,472 B），可作 CAP 格式样板 |
| `goodix_touchpad_oem87.inf` | 触控板固件驱动 inf（Goodix，FirmwareFilename 模式） |
| `goodixtouchpad_driver.inf` | 同上（DriverStore 原件） |
| `battery_fw_oem88.inf` | 电池固件 inf（Lenovo Ltd.） |
| `zhanlu_cfu_oem72.inf` | 湛卢 AI 芯片 CFU over HID inf |

中间件（`fw-touchpad/`）：`gt7868q.bin`、`fmp.cap`、`cap_payload.bin`（CAP 的 `.reloc` 节）、`device_fw_1E1175.bin`（`$_DEVICE_FW_IMG_` 载荷）、`device_fw_1E3000.bin`

---

## 八、下一步

| 优先 | 动作 |
|---|---|
| ★★★ | **反汇编 `touchpad_GT7868Q_fw.bin`** —— 这是触觉所在的实体。芯片名（`7868Q`）与板级标签（`_7YELSTO`）已知，配置/区域表在 0x1160 起 |
| ★★★ | 拉 `ty2/goodix-gt7868q-linux-driver` 对照，并用它验证固件里的 HID 报文结构 |
| ★★ | **抓 Lenovo 中国站驱动列表的 API**（`newthink.lenovo.com.cn/driveList.html?selname=MP2NRN6M` 是 JS 渲染），找 EC/固件类目 |
| ★★ | 触发 Windows Update 固件检查，看是否新建 `C:\Windows\Firmware\{a9898afa-…}\` |
| ★ | 把剩下 8 个 ESRT GUID 逐个定性（在固件模块里搜 GUID 归属） |
| ⚠️ | **复原 Windows 安全设置**（VBS/HVCI/驱动黑名单仍是关闭态） |
