# ★★★★★ 设备恢复路径总表（一切设备实验的回滚依据）

> **建立日期**：2026-10-11
> **由来**：2026-10-10 首次实机 `0E 12` 写入造成功能退化（触觉消失、按压点击失效），**由 BIOS 自动重刷恢复**。
> **本文件是【设备安全】的第一入口**：任何设备写实验之前，先读这里。

---

## 0. 一句话

> **本机存在一条【BIOS 自动重刷恢复路径】**：开机时联想的 UEFI 固件管理驱动（FMP）会检测触控板固件状态，**若判断需要更新，则自动重刷**。
> **⇒ 设备实验搞坏后的第一动作：完整重启电脑。**

---

## 1. 恢复手段（按优先级）

| # | 手段 | 操作 | 前提/说明 |
|---|---|---|---|
| **0** | ★★★★★ **（2026-10-14 新增）主动重暂存官方固件 ⇒ 再重启** | 见 §2c 的四步命令（管理员） | ★ **把手段 1 从「碰运气」变成「确定性」**：官方路径 = `%SystemRoot%\Firmware` 暂存 + `FirmwareResources` 登记 ⇒ BIOS 下次启动必刷 |
| **1** | ★★★★★ **完整重启电脑**（不是睡眠） | 开始菜单 → 重启；开机时留意是否出现"类似升级 BIOS 的界面" | **已实测有效**（2026-10-10→11 事件）。**这是首选** |
| **2** | ★★★ **重启 + 等待** | 若首次重启未触发，**再次重启**或**关机后冷启动** | BIOS 只在它判断需要更新时才刷 ⇒ 可能一次不触发 |
| **2b** | ★★ **重枚举设备**（`pnputil /restart-device "ACPI\GXTP5100\1"` 或设备管理器禁用/启用） | ⚠️ **需要管理员**（非提权 `Access is denied`）。**实测可用命令**：<br>`Start-Process cmd.exe -ArgumentList '/c','pnputil /restart-device "ACPI\GXTP5100\1" > "%TEMP%\pnp.txt" 2>&1' -Verb RunAs -Wait`<br>（⚠️ `-Verb RunAs` **不能**与 `-RedirectStandardOutput` 同用）<br>作用：清掉 **HID 会话期**状态；**⚠️ 不清除 IC 侧模式**（2026-10-14 修订：设 `err=122` 现象挺过重枚举 ⇒ 见全书 §19.74 / 纪律 **166**） | 比重启快；**不会**触发 BIOS 重刷（那是手段 0/1） |
| **3** | ★★★ **在 Linux 下跑官方 `gdixupdate`** | `sudo gdixupdate -d /dev/hidrawX -s 7868 -f -i <官方固件>` | **官方工具**，对同型号芯片验证过。需**原生 Linux**（Live USB 可行；**WSL 不行**，需 hidraw） |
| **4** | ★★ **联想售后刷固件** | 联系售后 | 保底方案 |
| **5** | ★★ **BIOS 里手动触发固件更新** | 开机 F2 进 BIOS，找固件/TPM/设备更新相关项 | 未实测 |

---

## 2. BIOS 重刷路径的机理（已确证的部分）

**证据**：
- 项目 `data/reference/old__FmpDxeY750.asm.txt` —— **FmpDxe** = UEFI **Firmware Management Protocol** 驱动
- 项目 `data/reference/lab__GoodixTpDxe.asm.txt` —— **GoodixTpDxe** = 触控板 UEFI 驱动
- 2026-10-10→11 实测：写坏后**重启即自动恢复**（连 `0x96F8` 的 2 个被改字节都还原）

**恢复后实测对照**：

| 地址 | 写坏后 | **恢复后** |
|---|---|---|
| `0x96F8` 前 32 B | `22 01 11 00 34 01 04 65 …` | **`22 01 1B 00 3E 01 04 65 A7 C3 E1 02 …`**（= 原始基线） |
| `0x4160` | `FF` | `FF` |
| `0x5095` | `EE` | `CC/DA/E1`（变值，正常空闲态） |
| `0x5096` | `BB` | **`75`**（原始值） |

---

## 2c. ★★★★★ 安全网机制【补全】（2026-10-14，纯只读系统查询）

> 档案此前只知道「方向是 ESRT」（§10.7.2）；本轮把整条链补到**可执行**，并给出**确定性恢复原语**。
> 详细证据：`docs/08-findings/2026-10-14-安全网机制补全-Windows固件资源与暂存路径.md`

| 环节 | 实况 |
|---|---|
| **ESRT 资源** | `UEFI\RES_{B6AE105A-BA93-4FC8-AA28-E63903FFEDDE}`，`FriendlyName = **Goodix Update UEFI**`（本机共 11 条 `UEFI\RES_*`，其中 `{6B791D8C-…}` = 系统固件/BIOS） |
| **Windows 侧驱动包** | `C:\Windows\INF\oem87.inf` = `GoodixTouchpad.inf`（Goodix，Class=Firmware，DriverVer 02/02/2024 0.0.2.8） |
| **INF 关键三行** | `HKR,,FirmwareId,,{b6ae105a-…}` · `HKR,,FirmwareVersion,%REG_DWORD%,**0x14030522**` · `HKR,,FirmwareFilename,,TB14P_GT7868Q_14030522_20240202.BIN`；`DefaultDestDir = 10,Firmware` |
| **暂存目录** | `%SystemRoot%\Firmware\TB14P_GT7868Q_14030522_20240202.BIN`（161,628 B，**sha256 `0033d075fae88f00…`**，与 DriverStore 副本**同哈希**） |
| **注册表实况** | `HKLM\SYSTEM\CurrentControlSet\Control\FirmwareResources\{b6ae105a-…}`：`Version = 335742242 (0x14030522)` · `Filename` · `Phase = 2` · `LastAttemptVersion = 0x14030522` · **`LastAttemptStatus = 0`（上次刷写成功）** |
| **权限** | Administrators = FullControl · **Users = ReadKey**（⇒ 重暂存需管理员） |
| **ESRT 变量直读** | `GetFirmwareEnvironmentVariable("ESRT",…)` → `err=1314`（`ERROR_PRIVILEGE_NOT_HELD`）⇒ 需管理员 + `SeSystemEnvironmentPrivilege` |

### 四步（管理员）

```powershell
$bin = "$env:SystemRoot\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
Get-FileHash $bin -Algorithm SHA256          # 1) 期望 0033d075fae88f0048544696c8941ed7dcca4269beaa84af76323ef5bbdcee72
$pkg = (Get-ChildItem "$env:SystemRoot\System32\DriverStore\FileRepository" -Directory -Filter 'goodixtouchpad.inf_amd64_*' | Select-Object -First 1).FullName
Copy-Item "$pkg\TB14P_GT7868Q_14030522_20240202.BIN" "$env:SystemRoot\Firmware\" -Force   # 2) 缺则补回
Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FirmwareResources\{b6ae105a-ba93-4fc8-aa28-e63903ffedde}'   # 3) 确认 Version/Filename
# 4) 重启 ⇒ BIOS 启动阶段比对并重刷（会看到「类似升级 BIOS 的界面」）
```

**验收**：`FirmwareResources\{…}\LastAttemptStatus = 0` 且 `LastAttemptVersion = 0x14030522`；设备侧 `0x96F8[0:5] = 22 01 1B 00 3E`。

### ⚠️ 三条必须记住的边界

1. **它只覆盖该资源声明的子系统**：REPRODUCE.md 的 `GTPCheckTFUpdate` 表明 **TP（主控）与 TF（力芯片）分别比对版本、分别刷写** ⇒ **「能救主控」≠「能救 TF100A」**（纪律 160）。
2. **它是恢复通道，不是改固件的通道**：镜像受 `Catalog`（`oem87.cat`）签名与 BIOS 校验约束；把它当写入通道会同时踩「签名」与「不可逆」两个风险（纪律 161）。
3. **不要靠「改版本字段」去骗它刷**：那正是 B12/退化路径的同族操作（§19.45.3）。

---

## 2b. ★★★★ 退化签名表（2026-10-12 大量实测后定稿 —— **判「是否退化」只看这张表**）

| 判据 | 正常 | **已退化（= IC 回退到内置默认配置）** |
|---|---|---|
| **`0x96F8` 前 32 B** | **`22 01 1B 00 3E 01 04 65 …`** | **`22 01 11 00 34 01 04 65 …`** |
| `0x4000`（所谓 liveness） | `A7 E0 ED ??` | `00 00 00 00` |
| `0x5096` | `75` | `AA` 或 `BB`（随写入结果） |
| `0x4160` | `FF` | `FF`（**不变**） |
| 用户体感 | 点按有震动 | **点按不震 / 点击失效**（光标与滑动正常） |

### 🔴 两条**必须记住**的判读纪律（2026-10-12 血泪）

1. **`0x4000 = 00000000` 【不是】退化标志。**
   实测：一次**成功且无害**的写入之后 `0x4000` 也是 `00 00 00 00`（设备完全正常）。
   它反映的是**刚跑过 bootloader 周期**，不是健康状态。
   **⇒ 判退化只认 `0x96F8`（`22 01 11…` vs `22 01 1B…`）＋ 用户实测。**
2. **`0x96F8 = 22 01 11…` 的含义 = 「IC 拒绝/未采用 flash 里的 cfg，回退到内置默认」。**
   它不是「cfg 被写坏」—— 该头自身校验 `+0x4 = sum(前 3 B)` 是**自洽**的；
   而是 **IC 对 cfg 有另一层内容校验，不合格就整体回退**。

### ⚠️ 一个重要推论（影响此后所有写实验）

**对 cfg 区的 `0x12` 写入，只要内容与 flash 里的【不完全相同】，就会触发回退**（2026-10-12 实测 4 次）。
**只有「逐字节相同」的写回是无害的。**

---

## 3. ⚠️ 为什么**不能**把它当成"无限次试错"的许可

1. **BIOS 只在【判断需要更新】时才重刷** —— 触发条件的精确边界**未知**
   - 可能依赖 `0x96F8` 的版本字段 `22 01 1B`
   - 也可能依赖固件区的校验/版本比对
2. **若破坏了"版本字段 + 校验"之外的东西，可能【不触发】** ⇒ 安全网**不是 100%**
3. 每次触发都意味着 **BIOS 级别的固件写** —— 本身也有风险（虽然低）

---

## 4. 因此，设备实验的硬规则（**不可协商**）

| 规则 | 内容 | 由来 |
|---|---|---|
| **R1** | ★★ **官方更新序列不可部分执行。要么全序列照单发完，要么一条都不发。** | 纪律 130（2026-10-10 真机代价：功能退化） |
| **R2** | ★★ **单块写入 ≠ 幂等，即使数据完全相同**（IC 的 flash 写含【擦除】，擦除粒度可能大于写入长度） | 纪律 132 |
| **R3** | ★★ **危险动作的前置检查必须比动作本身更严格**（如 `0x5095` 会变值 ⇒ 判"是否已进 bootloader"须连续 N≥5 次一致） | 纪律 129 |
| **R4** | ★ **凡"可能发出设备命令"的脚本，其恢复路径必须与失败原因绑定** —— 前置检查 ABORT 绝不允许触发任何发送 | 纪律 128 |
| **R5** | ★ **"某地址可读" ≠ "读到的就是该地址的静态内容"** —— 用"读回"做安全前提之前，必须先证明该地址读可重复（同址重复读 ≥5 次一致） | 纪律 127 |
| **R6** | **任何设备写之前，先记录**：`0x96F8` 前 32 B、`0x4160`/`0x5095`/`0x5096` 值 | 本次靠它才定位到差异 |
| **R7** | **任何设备写之前，先确认恢复路径可用**（本文件 §1） | — |
| **R8** | ★★★★ **`0x5096 == 0xAA` 不是验收判据** —— 它只表示「传输层接受」。<br>配置类/固件类写入的**唯一验收方式 = 重启后读状态**（本机 = `0x96F8` 前 3 字节）。 | 纪律 144（2026-10-12：改 2 字节 ⇒ `0xAA` 但 IC 回退默认） |
| **R9** | ★★★★ **不要指望「读回」能验证 flash** —— 该通道读不到静态 flash 内容（纪律 127）。<br>⇒ 写前**必须**先记录 `0x96F8` 前 32 B 作为唯一可比的基线。 | 纪律 127 / §2b |

---

## 5. 备用信息

- **官方固件容器**：`TB14P_GT7868Q_14030522_20240202.BIN`（161,628 B，sha256 `0033d075…cee72`）
  - 载荷 A（gtx3 镜像）@ `file 0x0113C`，100,608 B，校验和 0x5F37 ✅
- **官方工具**：`goodix/gdix_hid_firmware_update`（`gtx2/gtx2_update.cpp` `load_sub_firmware`）
- **BIOS 侧参考**：`docs/03-firmware/lab__六附-白名单绕过补丁定案-iasl反编译.md`、`data/reference/old__FmpDxeY750.asm.txt`
