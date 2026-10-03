# driver-patch —— 「最干净」那条路：固件自己每次开机打补丁

> 目标：**不刷 flash、不依赖启动顺序、不需要 OpenCore**，让固件在每次开机的 BDS 阶段
> 自动加载一个自写 DXE 驱动去改内存里的 DSDT。
> 板子还没到也**可以提前验证**——因为验证这个机制**跟触控板一点关系都没有**。

---

## 〇、这份材料包含什么

| 文件 | 作用 |
|---|---|
| **`usb/`** | ★★ **可直接用的 U 盘内容**（整份拷到 FAT32 U 盘根目录即可） |
| **`TpadAcpiProbe.c` + `.inf`** | ★ **探针版**（第一步验证用）：只在屏幕反白打一段字 + 停 3 秒 + 返回，**不改任何内存** |
| `TpadAcpiPatch.c` + `.inf` | ★ 要用的 DXE 驱动（验证通过后编它）：按离线实跑验证过的字节改 DSDT |
| `TpadPkg.dsc` | 最小 DSC（一次把探针和真驱动都编出来） |
| `README.md` | 本文件：编译、部署、**§一 提前验证操作单**、排错顺序 |

---

## 一、★★★ 第一步：验证「联想固件到底认不认 `DriverOrder`」

**这是整条路唯一的未知量，而且现在就能验掉——不需要板子，也不需要 OpenCore。**

**原理**：`bcfg driver add` 往 `Driver####` 变量里写一项。如果固件在开机时真会处理
`DriverOrder`，它就会去 `LoadImage` + `StartImage` 你放进去的那个 `.efi`。
所以我们只要放一个**"跑起来会有明显痕迹"**的驱动即可。

### ★ 探针就用我们自己的：`TpadAcpiProbe.efi`

**不用借任何第三方镜像**（OpenCore 包里的 `OpenShell.efi` 只是"顺便带了一份 Shell"，
跟 OpenCore 本身无关 —— 但既然我们本来就要编驱动，探针也自己出最干净）。

`TpadAcpiProbe.c` 做的事：**在屏幕上反白打一段字，停 3 秒，然后返回。**
- 不找 DSDT、**不改任何内存、不碰 ACPI 表**
- 返回成功 ⇒ **不驻留、不干扰后续启动**（这点比拿 Shell 当探针好得多：Shell 会把开机会卡在 Shell 里）

### ★ UEFI Shell 从哪来（结论：用 `shell/OpenShell_x64.efi`）

**实测结论（含两次误判的更正）：**

| 问题 | 答案 |
|---|---|
| ThinkBook 固件里有内置 UEFI Shell 吗？ | ❌ **没有**。官方手册通篇只有 `F1`（BIOS）/`F12`（启动菜单）/ Novo 键 |
| 联想 BIOS 更新 ISO 里的 `/EFI/BOOT/BOOTX64.EFI` 是 Shell 吗？ | ❌ **不是**。它是**联想的 BIOS 刷新程序**（内部**包含** Shell 库与帮助文本，所以搜字符串会误判） |
| 那 Shell 用什么？ | ✅ **`shell/OpenShell_x64.efi`**（1,183,744 B，MD5 `4ece4971731caad76698f9f12565b545`）—— EDK2 标准 UEFI Shell |

> ⚠️ **两次误判记录（方法学教训）**：
> 1. 第一遍**只搜 ASCII** → 没找到 `EDK`/`Shell>` → 误判"不是 Shell"。
> 2. 第二遍**搜到 UTF-16 的 `bcfg` 手册页 / `Shell>` 示例** → 误判"是 Shell"。
> 3. **真答案**：该文件**内嵌 Shell 库与帮助文本，但入口是 OEM 刷写程序** ——
>    直到喆把它启动起来，屏幕上出现 **`Main Menu / Version 44.15 / 1. Read this first... / 2. Update system program / F3=Exit`**，
>    才在其字符串里搜到 `Select 2.Update system program` · `BIOS is Upgradeable(FLASH)` · `FlashCommand` ⇒ 定案。
>
> **★ 教训：判"某 .efi 是什么"不能只看字符串命中（尤其是库/帮助文本），必须看它的主流程 / UI 字符串。**
> **★ 另一个教训：`OpenShell.efi` 用字符串找不到 `bcfg`（EDK2 Shell 的命令名不经明文暴露），但它是真正的 Shell —— 反之亦然，字符串不能作为充分或必要条件。**

**关于 `OpenShell.efi` 的来源说明（它不是"用 OpenCore"）**：
它取自 `OpenCorePkg` 发行包的 `X64/EFI/OC/Tools/OpenShell.efi`。
但 **UEFI Shell 是 EDK2（Intel/TianoCore 开源项目）的通用工具**，任何发行版都只是**打包**它；
我们**只借这一个 .efi 文件**，不安装 OpenCore、不使用它的引导功能、不依赖它的启动链。

**⚠️ 已从 U 盘移除联想刷写程序** —— 避免误选 `2. Update system program` 导致刷 BIOS。

---

### ⚠️ Secure Boot 仍是硬前提（2026-09-29 实测）

关掉之前：F12 选 U 盘 → **立刻弹回启动菜单**。
原因：本机 `UEFISecureBootEnabled = 1`，而 Shell 未签名 ⇒ 固件拒绝执行。
⇒ **必须先关 Secure Boot**（`F1` → Security → Secure Boot → Disabled → F10）。

### 完整步骤（现在只需三步）

```text
【准备】把本目录下的 usb\ 里的内容整份拷到 U 盘根目录（U 盘格式化成 FAT32）
        拷完后 U 盘上应该是：
            \EFI\BOOT\BOOTX64.EFI          ← 联想的 UEFI Shell
            \EFI\Tpad\TpadAcpiProbe.efi    ← 探针
            \EFI\Tpad\TpadAcpiPatch.efi    ← 真驱动（以后用）

【操作】
① BIOS 里关掉 Secure Boot（Security → Secure Boot → Disabled）
   （若想先试能不能不关，可以直接跳到②——Shell 是签名的，有几率直接能跑）
② 开机按 F12 → 选 U 盘 → 进入 UEFI Shell
③ 在 Shell 里依次敲：
       fs0:
       ls \EFI\Tpad\
       bcfg driver add 0 fs0:\EFI\Tpad\TpadAcpiProbe.efi "TpadAcpiProbe"
       bcfg driver dump
④ 重启
⑤ ★ 判据：
       屏幕上出现反白的 "DriverOrder 探针：TpadAcpiProbe" 那一块
              = 固件认 DriverOrder ⇒ 这条路可行 ⇒ 换成 TpadAcpiPatch.efi 部署
       什么都没有、直接进系统
              = 固件不处理 ⇒ 别再折腾这条路，回 OpenCore 方案（结果等价）
⑥ 清理（无论结果如何都做）：
       bcfg driver rm 0
       bcfg driver dump
```

**⚠️ 两点提醒**
- 探针返回后会**正常继续启动**，不会把你卡在某一屏
- 若重启后屏幕没有任何变化，先回 Shell 确认 `bcfg driver dump` 里那一项**重启后还在**（有些固件会清掉 `Driver####`）

### 判定结果怎么用

| 结果 | 含义 | 下一步 |
|---|---|---|
| 看到探针文字 | ✅ **固件认 `DriverOrder`** | 走 §二，编 `TpadAcpiPatch.efi` 真驱动 |
| 什么都没看到 | ❌ 固件不处理（或要求签名 / 有 Setup 开关） | 检查 Setup 有没有相关开关；否则**回 OpenCore 方案**（改的是同一处字节、结果等价） |

---

## 二、编译（两条路，**A 已在本机跑通**）

### 路线 A ★ 推荐：MSVC 直编，**不需要 EDK2、不需要 NASM、不需要 git clone**

**原理**：MSVC 的链接器本身就支持 EFI 子系统值
（`/SUBSYSTEM:EFI_BOOT_SERVICE_DRIVER` = PE subsystem 11），
配合一个自写的精简头文件 `miniefi.h`（只声明我们用到的 UEFI/ACPI 结构），
就能直接产出合法的 UEFI 驱动。**省掉整个 EDK2 工具链。**

```bat
cd standalone
build.bat
```

`build.bat` 会：初始化 MSVC x64 环境 → `cl /c` 编译两个模块 → `link /SUBSYSTEM:EFI_BOOT_SERVICE_DRIVER` →
调用 `fix_pe.py` 清掉 MSVC 自动打上的 `IMAGE_FILE_DLL` 标志 → 产出：

```
TpadAcpiProbe.efi      3,072 字节   （探针）
TpadAcpiPatch.efi      2,560 字节   （真驱动）
```

**本机实测结果**（`verify_pe.py` 输出）：

| 项 | 值 | 判定 |
|---|---|---|
| Machine | `0x8664` x86-64 | ✅ |
| Magic | `0x020B` PE32+ | ✅ |
| **Subsystem** | **11 `EFI_BOOT_SERVICE_DRIVER`** | ✅ |
| EntryPoint | RVA `0x1000` | ✅ |
| SectionAlign / FileAlign | `0x1000` / `0x200` | ✅ 与 EDK2 产物一致 |
| Characteristics | `0x0022`（EXECUTABLE_IMAGE + LARGE_ADDRESS_AWARE，**DLL 位已清**） | ✅ |
| 节表 | `.text` `.rdata` `.pdata` | ✅ |
| **导入表** | **大小 = 0**（零导入） | ✅ UEFI 驱动惯例 |

**依赖**：Visual Studio 2022 Build Tools（本机已装，`cl.exe` 14.44 / Windows SDK 10.0.26100）+ Python（跑后处理）。
> 本机环境实测：VS 2022 BuildTools 已存在，`wsl.exe` 被沙箱安全策略拦截（**不要试图绕过**），
> 所以 EDK2-via-WSL 那条路不可用 —— 这也是选路线 A 的原因之一。

### 路线 B：EDK2（如果你后来想要"官方产物"）

需要 EDK2 环境（VS + Python + **NASM**）。文件都在 `../edk2/` 目录里：

```bat
git clone --depth 1 https://github.com/tianocore/edk2.git
:: 建包：edk2\TpadPkg\ 放 TpadPkg.dsc + TpadAcpiPatch\ + TpadAcpiProbe\
edksetup.bat Reconfig
build -a X64 -t VS2022 -p TpadPkg\TpadPkg.dsc -b RELEASE
```

> ⚠️ 实测：从本机网络克隆 EDK2 极慢（6 分钟约 7 MB）。**除非有更快的镜像，否则别走这条。**
> （NASM 已提前下好放在 `E:\AAA\nasm\nasm-2.16.03\`，备用。）

---

## 三、部署真驱动

```text
① 把 TpadAcpiPatch.efi 放到 U 盘
② 进 UEFI Shell：
       fs0:
       bcfg driver add 0 fs0:\TpadAcpiPatch.efi "TpadAcpiPatch"
       bcfg driver dump          ← 确认已写入
③ 重启，观察是否生效（见 §四）
```

**★ 建议把 `TpadAcpiPatch.efi` 同时放到 ESP 上**（`\EFI\Tpad\TpadAcpiPatch.efi`），
并把 `bcfg driver add` 指向 ESP 上的那份 —— 这样**不依赖任何 U 盘**。

**清理**：

```text
bcfg driver rm 0
bcfg driver dump
```

---

## 四、怎么确认补丁真的生效了

| 现象 | 说明 |
|---|---|
| ★ 设备管理器里出现 Precision Touchpad 且**没有代码 10** | 说明 `ADR0` 已经是 `0x2C` ⇒ 补丁生效 |
| 仍是代码 10 | 可能是：①机制没生效（回去看 §一）②设备在 `0x2C` 上根本不应答（**①b，就是另一回事了**，见下） |

> ## ⚠️ 必须分清：**"补丁生效" ≠ "板子能用"**
> 补丁只负责把 `ADR0` 从 `0xFF` 改成 `0x2C`。
> 如果 BIOS 拒绝时连**复位/上电**都没给这块板做，那地址对了也问不出东西 ⇒ 依然是代码 10。
> **这一条只能靠 Linux Live 下 `i2c-dev` 读 `0x4014` 是否回 `YELSTO` 来区分。**

**建议的排错顺序**：
```
① bcfg driver dump  → 确认变量还在（重启后可能被固件清掉）
② 进 Linux Live     → i2c-dev 读 0x4014
     ├─ 回 YELSTO  → 设备活着 ⇒ 若 Windows 仍代码 10，说明补丁没生效 ⇒ 查 §一/§三
     └─ 无响应     → ①b 不成立 ⇒ 这条路（以及 OpenCore 那条）都到不了终点
```

---

## 五、和 OpenCore 方案的关系

| | OpenCore（ESP） | **本方案（`driver####`）** |
|---|---|---|
| 改哪里 | 内存里 ACPI 表的**副本** | 内存里 ACPI 表**原地** |
| 谁执行 | 引导器（本身是个启动项） | **固件自己**（BDS 阶段） |
| 依赖启动顺序 | ✅（被改就失效） | ❌ **不依赖** |
| 额外引导器 | 需要一个 | **不需要** |
| BitLocker 影响 | 可能索要恢复密钥 | 更小 |
| Windows 更新重置 | 可能 | 不太会 |
| 唯一未知 | 无（成熟方案） | ★ **固件认不认 `DriverOrder`** |
| 因此 | **先跑通这个** | **机制验证通过后再换过去** |

**两者改的是同一处字节、得到同一个结果**，所以先用哪个都不浪费。

---

## 六、红线（照旧）

```
① 不写 flash、不改 SSDA、🔴 不发红线**四条** {00 10} / {00 11} / **{0E 12}（★ 真正写 flash）** / **{0E 13}（重启）**（旧文档只写“三连”，漏了 `0E 13`）
② 先做 §一 的机制验证，再考虑 §二 编译
③ 首次部署后先确认 bcfg driver dump 还在，再重启第二轮
④ 出问题：进 UEFI Shell → bcfg driver rm 0 即可清掉
```
