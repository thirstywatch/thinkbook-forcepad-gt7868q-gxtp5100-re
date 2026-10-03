# ③ BIOS 两模块反汇编：`FmpDxeY750` 与 `I2cTouchPanelDxe`

> 日期：2026-09-28（本轮）
> 原始素材：`bios/out/FmpDxeY750.{bin,asm.txt}`、`bios/out/I2cTouchPanelDxe.{bin,asm.txt}`
> 新增工具：`bios/out/xref.py`（交叉引用）、`bios/out/guid_match.py`（EDK2 官方 GUID 库比对）、`bios/out/edk2_guids.py`（826 条官方 GUID）
>
> **⚠️ 本文档更正了本项目此前三处 GUID 误标**（见 §5）。
> **⚠️ 本文档推翻旧文档《BIOS宿主侧协议与FMP包格式.md》§3 的"这两个模块字符串层无锚点、价值低"的判断** —— 有了交叉引用工具后，两模块的语义已被完整解出。

---

## 1. 方法论：为什么上一轮判断"价值低"是错的

旧文档 §3 的判据是"**字符串层无锚点**"（`FmpDxeY750` 82 条几乎全是假串、`I2cTouchPanelDxe` 28 条含 `___AUTOPAD___` 填充）。

**这个判据本身失效**：Insyde 的 PE32+ 模块字符串全部**分散在 `.rdata`/`.data`**，而且**部分是 UTF-16**。用"扫 ASCII 串"的办法当然扫不到 —— `FmpDxeY750` 的 `The update failed - ErrorCode 0x%x` 就是 UTF-16，藏在 `0x0041E0`。

**正确入口是交叉引用**：先建"谁引用了谁"的倒排表，再从**已知 GUID**（GUID 是二进制、不受编码影响）出发回溯，就能一次性钉住功能函数。

本轮新建的两个工具：

| 工具 | 作用 |
|---|---|
| `xref.py` | ① call/jmp 目标直方图 → 函数入口候选；② 全量 rip-relative 倒排表 → 谁引用了某地址；③ 字符串自动判别 ASCII/UTF-16 |
| `guid_match.py` | 扫 PE 全段取 16 字节块 → 与 **EDK2 官方 GUID 库 826 条**批量比对 → 自动命名 |

★ **关键工具坑（本轮踩到，记录备查）**：
`lea rXX, [rip + disp]` **长度 7 字节**，目标地址 = **下一条指令地址 + disp** = `本指令地址 + 7 + disp`。
我在手工推算时把 `0x415F` 处的 `lea` 算成 `0x415F+7+0x377f`（多加了 7），得到错误的 `0x3A7`；
正确算法是 `0x415F + 7 + disp`，其中"下一条指令地址"本身就是 `0x4166`，**不能再用它去加 7**。
⇒ **所有 rip 目标一律用脚本算，不手推。**

---

## 2. `FmpDxeY750` —— 完整语义：ESRT 表构建器

### 2.1 模块身份

| 项 | 值 |
|---|---|
| FFS 段 | `.text` va=0x2A0 vsz=0x3EE7 / `.rdata` 0x41A0 / `.data` 0x4860 / `.xdata` 0x5020 / `.reloc` 0x5220 |
| 指令数 | 4348 条 |
| 入口 | `0x2A0` → `0x2D4` |
| PDB 路径 | `c:\edk2\Build\CirquePkg\DEBUG_VS2019\X64\CirquePkg\Touchpad\FmpDxe\FmpDxe\DEBUG\FmpDxe.pdb` ⇒ **CirquePkg** |
| UTF-16 字符串 | `GlidePoint Firmware`、`%x.%02x`、`The update failed - ErrorCode 0x%x`、`The update failed for unknown reason` |

### 2.2 ★★ GUID 表（`0x4860`–`0x48B0`，全部有 EDK2 官方名）

| 地址 | GUID | 官方名 | 用途 |
|---|---|---|---|
| `0x4860` | — | — | 槽数组（`cmp [rip+0x4402], rax` 的比对目标） |
| `0x4870` | `B60A3E6B-18C4-46E5-A29A-C9A10665A28E` | **`gEfiI2cIoProtocol`** | ★ 用于读写触控板 |
| `0x4880` | `7CE88FB3-4BD7-4679-87A8-A8D8DEE50D2B` | **`gEfiEventReadyToBoot`** | ★ 事件注册用 |
| `0x4890` | `86C77A67-0B97-4633-A187-49104D0685C7` | **`gEfiFirmwareManagementProtocol`** | 安装 FMP |
| `0x48A0` | `B122A263-3661-4F68-9929-78F8B0D62180` | **`gEfiSystemResourceTable`** | ★ **不是 Cirque 私有！** |

### 2.3 ★★★ 完整执行链（逐字节验证）

**入口 `0x2A0` → 初始化 `0x2D4`**：
```
0x2E9  ebx = 0x78
0x2F3  call 0x31C4              ; allocate(0x78)
0x302  call 0x3124              ; zero(ptr, 0x78)
0x30A  → 存入全局 [rip+0x493f]
0x322  call 0x123C              ; ★ 解析/填充 FMP 描述符
0x34F  call 0x412C              ; ★ 安装 ESRT 事件
0x37F  call [rax+0x80]          ; BS[0x80] = InstallProtocolInterface
```

**`0x412C` = 事件注册器**（★ 这里是本轮最关键的字节级更正）：
```
0000412C  sub rsp, 0x38
00004130  mov rax, [rip+0xd31]        -> 0x4E68  (gBS 指针槽)
00004137  cmp dword [rax+8], 0x20000  ; 可用池 >= 128KB?
0000413E  jae 0x414C
00004140  movabs rax, 0x8000000000000003 ; EFI_BUFFER_TOO_SMALL
0000414C  mov [rsp+0x28], r9
00004151  lea rax, [rip+0x728]        -> 0x4880 = gEfiEventReadyToBoot
00004158  mov r9,  [rip+0xaf1]        -> 0x4C50 (NotifyContext 槽，运行时填)
0000415F  lea r8,  [rip-0x3dc6]       -> 0x03A0 (★ NotifyFunction!)
00004166  mov [rsp+0x20], rax         ; 第 5 参 = &Event
0000416B  mov edx, 8                  ; TPL_APPLICATION
00004170  mov rax, [rip+0xcf9]        -> 0x4E70  (gBS 指针槽)
00004177  mov ecx, 0x200              ; EFI_EVENT_NOTIFY_SIGNAL
0000417C  call [rax+0x170]            ; ★ BS[0x170] = CreateEventEx
```

⇒ `CreateEventEx(Type=EVENT_NOTIFY_SIGNAL, Tpl=8, NotifyFunction=0x3A0, NotifyContext, &Event)`
**事件类型 `EFI_EVENT_NOTIFY_SIGNAL` + 上下文 `gEfiEventReadyToBoot`** ⇒ **`0x3A0` 在 ReadyToBoot 时被调用**。

**`0x3A0` = ESRT 条目构建器**：
```
0x0432  mov r14d, [rdi]              ; ESRT 现有条目数
0x043B  test r14d, r14d
0x0444  mov rdx,  [rip+0x441d]       -> 0x4868 (比对用 GUID 低 8 字节)
0x044B  lea rcx, [rdi+0x10]          ; 条目数组起点 (= 表 + 16)
0x044F  movups xmm0, [rcx]           ; 读条目 GUID
0x0457  cmp [rip+0x4402], rax        ; 比高 8 字节 (0x4860)
0x0465  cmp rdx, [rsp+0x28]          ; 比低 8 字节
0x046C  inc esi ; add rcx, 0x28      ; ★ 条目步长 = 0x28 = 40 字节 ✓
  ── 命中 → 0x0479 ──
0x0479  lea rcx, [rsi + rsi*4]       ; rcx = i*5
0x0480  mov dword [rdi+rcx*8+0x20], 2        ; ESRT Type = 2 = 设备固件
0x048B  mov [rdi+rcx*8+0x24], eax            ; = [rbp+0x28] FirmwareVersion
0x0492  mov [rdi+rcx*8+0x28], eax            ; = [rbp+0x58] LowestSupported
0x0496  mov dword [rdi+rcx*8+0x2C], 0x8010   ; ★ CapsuleFlags = 0x8010
0x04A1  mov [rdi+rcx*8+0x30], eax            ; = [rbp+0x5c] LastAttemptVersion
0x04A8  mov [rdi+rcx*8+0x34], eax            ; = [rbp+0x60] LastAttemptStatus
0x04AC  lea rcx, [rip+0x43ed]        -> 0x48A0 = gEfiSystemResourceTable
0x04BA  call [rax+0xC0]              ; ★ BS[0xC0] = InstallConfigurationTable
```

### 2.4 ★ 与微软 ESRT 规范的逐字段对齐（零偏差）

`rdi` = ESRT 表基址；条目大小 40 字节（`rsi*5` 个 qword = `rsi*40`）；条目 i 起点 = `rdi + i*40 + 16`。

| 反汇编写入 | 表内偏移 | 相对条目 | 微软 ESRT 字段 | 值 |
|---|---|---|---|---|
| `+0x20` | 32 | **+0x10** | **FirmwareType** | **2 = 设备固件** ✓ |
| `+0x24` | 36 | +0x14 | **FirmwareVersion** | `[rbp+0x28]` |
| `+0x28` | 40 | +0x18 | **LowestSupportedVersion** | `[rbp+0x58]` |
| `+0x2C` | 44 | +0x1C | **CapsuleFlags** | **0x8010** |
| `+0x30` | 48 | +0x20 | **LastAttemptVersion** | `[rbp+0x5c]` |
| `+0x34` | 52 | +0x24 | **LastAttemptStatus** | `[rbp+0x60]` |

**六个字段与微软文档 [ESRT table definition](https://learn.microsoft.com/windows-hardware/drivers/bringup/esrt-table-definition) 完全一致，无一偏差。** 表头（Count/Max/Version）在 `0x3A0` 之前的代码里填充。

### 2.5 ★ `GetImageInfo` 回调（`0x540`）—— FMP 描述符填充

```
0x057E  ebx = 0x78                    ; 描述符结构大小
0x05B5  movzx ecx, word [rdi+0x56]    ; 取 ImageTypeId（索引）
0x05B9  cmp [rip+0x45f8], rcx         ; 与某 GUID 槽比对
0x05C2  lea rdx, [rip+0x45d7]         ; → GUID A
0x05CB  cmp [rip+0x4566], rcx         ; 与另一槽比对
0x05D8  lea rdx, [rip+0x4541]         ; → GUID B
0x05F3  lea rsi, [rip+0x4666]         ; → 版本字符串缓冲
0x05FE  lea r8,  [rip+0x3bcb]         -> 0x41D0 = "%x.%02x"   ★ 版本格式化
0x0605  mov edx, 0x100                ; 缓冲大小 256
0x060D  mov [rbx+0x18], rax           ; ← [rdi+0x56] ImageId
0x0615  mov [rbx+0x28], eax           ; ← [rdi+0x58] ImageSize
0x0618  mov eax, 0xb
0x061D  mov [rbx+0x40], rax           ; ← 0x0B  Attribute (IMAGE_ATTRIBUTE_*)
0x0621  mov [rbx+0x48], rax           ; ← 0x0B
0x0625  mov [rbx+0x38], 0x19000       ; ★ 0x19000 = 102400 = 100 KB = 镜像最大尺寸
0x063A  call 0x3268                   ; → 版本字符串格式化
0x063F  mov [rbx+0x30], rsi           ; ← VersionString 指针
0x0643  movzx eax, byte [rdi+5]
0x0647  mov [rbx+0x60], eax           ; ← 描述符某字段
```

⇒ **镜像容量 100 KB**、**属性 0x0B**、**版本号输出成 `%x.%02x` 形式（如 `1.05`）**。

### 2.6 ★ I2C 通信实现（`0x11xx`–`0x13xx`）

`gEfiI2cIoProtocol`（`0x4870`）在 **`0x1296` / `0x12E4`** 被引用：

```
0x1270  ← 函数起点区（I2C 传输封装）
0x1307  cmp r8, [rcx + rsi]           ; 遍历/比对
0x1318  add rcx, 0x10                 ; 步长 16
0x131C  cmp rcx, 0x270                ; 上限 0x270
0x132E  movabs rbx, 0x800000000000000e ; EFI_NOT_FOUND
  ── 命中 ──
0x134D  mov [rdi+0x70], r15           ; 存 I2C IO 协议指针
0x1355  call 0x142C                   ; 建事务结构
0x1377  mov word [rbp+0x40], 0x20
0x1380  and dword [rax+8], 0          ; OperationCount = 0
0x1386  mov dword [rax+0xc], r13d
0x1391  mov dword [r14+0x18], 1       ; ★ EFI_I2C_OPERATION.Flags = 1
0x1399  mov r13d, 0x1e                ; ★ 0x1E = 30
0x13A3  mov dword [r14+0x1c], r13d    ; ★ 长度 = 30 字节
0x13A7  mov qword [r14+0x20], rsi     ; 缓冲指针
0x13AB  call qword [r15]              ; ★ I2C Master → QueueRequest()
```

⇒ **每次传输 30 字节**（对照 `GoodixTpDxe` 的寄存器 `0x100` 命令包 17 字节、`0x300` 状态 5 字节）。
⇒ **`FmpDxeY750` 通过 `EFI_I2C_IO_PROTOCOL` 直接对触控板读写**，数据结构符合 EDK2 `EFI_I2C_OPERATION` 布局。

### 2.7 超时常量与判定

| 常量 | 值 | 判读 |
|---|---|---|
| `0x3E8` | 1000 | 超时 1 秒 |
| `0x2710` | 10000 | 超时 10 秒 |
| `0x4E20` | 20000 | 超时 20 秒 |
| `0x19000` | 102400 | ★ 镜像最大 100 KB |
| `0x8010` | 32784 | ★ ESRT CapsuleFlags |
| `0x200`, `0x201` | 512/513 | 版本比较边界 |
| `0x4000` | 16384 | 缓冲/对齐边界 |

### 2.8 ★ 触觉相关性判定：**无**

全模块**不存在任何触觉/振幅/pattern 相关常量或寄存器**：
- 无 `0x08..`、`0x0A..` 类 HID 命令码
- 无 PWM / Duty / Amplitude 命名痕迹
- 只做两件事：**(a) 把固件包按 I2C 写进触控板；(b) 向 OS 报告 ESRT 条目**

⇒ **与上一轮结论一致，现在有字节级证据**：`FmpDxeY750` **不碰触觉参数**。

---

## 3. `I2cTouchPanelDxe` —— 完整语义：I2C-HID → AbsolutePointer 通用管道

### 3.1 模块身份

| 项 | 值 |
|---|---|
| FFS 段 | `.text` va=0x2A0 vsz=0x3686 / `.data` 0x3940 vsz=0x8A0 / 0x41E0 / `.xdata` 0x4400 / `.reloc` 0x4600 |
| 指令数 | 3697 条 |
| 入口 | `0x4F0` → **`0x5A4`**（真正初始化器） |
| UTF-16 字符串 | **`Generic I2C Touch Panel`** @ `0x3C90`、**`I2C Touch Panel Driver`** @ `0x3CD0` |

### 3.2 ★ GUID 表（`0x3940`–`0x3A70`，21 条）

| 地址 | GUID | EDK2 官方名 |
|---|---|---|
| `0x3940` | `5B1B31A1-9562-11D2-8E3F-00A0C969723B` | `gEfiLoadedImageProtocol` |
| `0x3950` | `DBA6A7E3-BB57-4BE7-8AF8-D578DB7E5687` | —（Insyde 私有） |
| `0x3960` | `1C2E4602-E3BA-4B07-E3B8-3555A51C613A` | — |
| `0x3970` | `B60A3E6B-18C4-46E5-A29A-C9A10665A28E` | **`gEfiI2cIoProtocol`** ★ |
| `0x3980` | `773C5374-81D1-4D43-B293-F3D74F181D6B` | — |
| `0x3990` | `6A7A5CFF-E8D9-4F70-BADA-75AB3025CE14` | `gEfiComponentName2Protocol` |
| `0x39A0` | `776712B7-A2A6-4F67-9028-2178725A8B34` | — |
| `0x39B0` | `ED32D533-99E6-4209-9CC0-2D72CDD998A7` | `gEfiSmmVariableProtocol` |
| `0x39C0` | `13A3F0F6-264A-3EF0-F2E0-DEC512342F34` | `gEfiPcdProtocol` |
| `0x39D0` | `0379BE4E-D706-437D-B037-EDB82FB772A4` | **`gEfiDevicePathUtilitiesProtocol`** ← 入口第一个 Locate |
| `0x39E0` | `F1187E54-995F-49D9-ACEE-C534F45A18C7` | —（Insyde 私有）← 入口第二个 Locate |
| `0x39F0` | `7739F24C-93D7-11D4-9A3A-0090273FC14D` | **`gEfiHobList`** |
| `0x3A00` | `C51F1883-DF00-4F6A-08A0-369F6098FDAF` | — |
| `0x3A10` | `201D65E5-BE23-4875-80F8-B1D4795E7E08` | — |
| `0x3A20` | `18A031AB-B443-4D1A-A5C0-0C09261E9F71` | **`gEfiDriverBindingProtocol`** ★ |
| `0x3A30` | `27ABF055-B1B8-4C26-8048-748F37BAA2DF` | `gEfiEventExitBootServices` |
| `0x3A40` | `107A772C-D5E1-11D4-9A46-0090273FC14D` | **`gEfiComponentNameProtocol`** |
| `0x3A50` | `D9DDACA2-0816-48F3-ADED-6B71656B248A` | — |
| `0x3A60` | `F4CCBFB7-F6E0-47FD-9DD4-10A8F150C191` | **`gEfiMmBaseProtocol`** ← 入口第三个 Locate |
| `0x3A70` | `8D59D32B-C655-4AE9-9B15-F25904992A43` | **`gEfiAbsolutePointerProtocol`** ★★ |

### 3.3 ★ 初始化流程（`0x5A4`）

```
0x5AE  r9 = [rdx+0x60]              ; SystemTable->BootServices
0x5B2  lea r8,  [rip+0x377f]        ; → (参数)
0x5BD  rbx = rcx                    ; ImageHandle
0x5C7  lea rcx, [rip+0x3402]        -> 0x39D0 gEfiDevicePathUtilitiesProtocol
0x5CE  edx = 0
0x5DE  call [r9+0x140]              ; ★ BS[0x140] = LocateProtocol
0x5E5  call 0x215C                  ; 组件名/句柄初始化
0x5EA  lea rcx, [rip+0x33ef]        -> 0x39E0 (Insyde 私有 GUID)
0x5F1  call 0x218C                  ; 查协议
0x5FB  mov eax, [rax+0x2c]
0x5FE  → 存全局（0x3D49）
0x604  r8 = &[rbp+0x28]
0x60F  lea rcx, [rip+0x344a]        -> 0x3A60 gEfiMmBaseProtocol
0x618  call [rax+0x140]             ; LocateProtocol
```

⇒ 三个 `LocateProtocol`：**DevicePathUtilities** → **Insyde 私有** → **MmBase**。

### 3.4 ★ 角色判定

引用统计（`xref.py`）：

| GUID | 引用处 | 判读 |
|---|---|---|
| `gEfiDriverBindingProtocol` (`0x3A20`) | `0x3BB`、`0x41B`、**`0x53A`** | ★ **标准 UEFI 驱动模型**（Supported/Start/Stop 三件套） |
| `gEfiI2cIoProtocol` (`0x3970`) | `0x138B`、`0x14B4`、`0x14D0`、`0x157D`、`0x1B43`、`0x1B63` | ★ **I2C 收发（6 处）** |
| `gEfiAbsolutePointerProtocol` (`0x3A70`) | `0x13D8`、`0x1973`、`0x1AA4`、`0x1BB9` | ★★ **输出绝对坐标指针（4 处）** |
| `gEfiComponentName2Protocol` (`0x3990`) | `0x20D9` | 组件名 = `Generic I2C Touch Panel` |
| `gEfiEventExitBootServices` (`0x3A30`) | `0x2A7F`、`0x2D35` | 退出 BootServices 时清理 |

**`0x20D9` 附近 = ComponentName2 实现**（`lea r8, [rip+0x1bb0]` → `0x3C90` = `Generic I2C Touch Panel`）。

⇒ **`I2cTouchPanelDxe` 的完整角色**：
```
EFI_I2C_IO_PROTOCOL  ──读原始 HID 报文──▶  本驱动（报文解析）
                                              ↓
                                    EFI_ABSOLUTE_POINTER_PROTOCOL
                                              ↓
                                    上层（Windows PTP 驱动 / BDS 鼠标）
```

⇒ **是 I2C-HID 的通用传输+解析管道**，用 `AbsolutePointer` 作为输出面。
（对照：`GoodixTpDxe` 输出的是**厂商私有 HID 通道** + 寄存器协议。）

### 3.5 ★ 触觉相关性判定：**无**

- 4 处 `AbsolutePointer` 引用全在报文解析/状态更新路径
- 无 HID 输出报表（Feature/Output）构造代码痕迹
- 无 PWM/振幅/pattern 常量
- `___AUTOPAD___` @ `0x3B30` 是 **Insyde 编译器填充**，非功能串

---

## 4. 两个模块与本项目的关系（净影响）

| 问题 | 本轮答案 | 依据 |
|---|---|---|
| `FmpDxeY750` 是什么？ | **ESRT 表构建器**，向 OS 暴露"触控板有可更新设备固件（100 KB，设备固件类型）" | §2.4 六字段零偏差 |
| 它写 EC 还是写 TP IC？ | ★ **两者都不是** —— 它走 **`EFI_I2C_IO_PROTOCOL` 直连触控板**，每次 30 字节 | §2.6 |
| 它碰触觉参数吗？ | ❌ **不碰** | §2.8 |
| `I2cTouchPanelDxe` 是什么？ | **I2C-HID → AbsolutePointer 通用管道** | §3.4 |
| 它碰触觉参数吗？ | ❌ **不碰** | §3.5 |
| 对触觉方案③（实体接管 HDP/HDN）有影响吗？ | ❌ **无新增信息，也不构成阻碍** | — |

⇒ **净影响**：消掉了 BIOS 侧最后一整块"可能有触觉逻辑"的猜想。触觉方案的缺口**仍然只有振幅 + LRA 型号/谐振频率**，与上一轮一致。

---

## 5. ⚠️ 三处 GUID 误标更正（本项目历史上记错的）

旧笔记（摘要与早期文档）里有三处**把 GUID 值标错了名**。本轮用 EDK2 官方库 826 条比对后更正：

| 地址 | GUID 值 | **旧标（错）** | **正解** |
|---|---|---|---|
| `I2cTouchPanelDxe` `0x39F0` | `7739F24C-93D7-11D4-9A3A-0090273FC14D` | `EFI_PCI_ROOT_BRIDGE_IO_PROTOCOL` | **`gEfiHobList`** |
| `I2cTouchPanelDxe` `0x3A20` | `18A031AB-B443-4D1A-A5C0-0C09261E9F71` | `EFI_DEVICE_PATH_PROTOCOL` | **`gEfiDriverBindingProtocol`** |
| `I2cTouchPanelDxe` `0x3A40` | `107A772C-D5E1-11D4-9A46-0090273FC14D` | `EFI_PCI_IO_PROTOCOL` | **`gEfiComponentNameProtocol`** |
| `FmpDxeY750` `0x48A0` | `B122A263-3661-4F68-9929-78F8B0D62180` | "Cirque 私有 FMP 实例 GUID" | **`gEfiSystemResourceTable`**（微软 ESRT 标准 GUID） |

**教训**：`176772C-...`/`7739F24C-...` 这类 GUID 值**外观相近但完全不同**；`DEVICE_PATH` 真实值是 `09576E91-6D3F-11D2-8E39-00A0C969723B`，`PCI_IO` 是 `607F766C-7455-42BE-930B-E4D76DB2720F`。
⇒ **一律用 `guid_match.py` 命名，不再手写。**

---

## 6. 交付物与工具

| 文件 | 内容 |
|---|---|
| `bios/out/xref.py` | ★ 新：PE32+ 交叉引用分析器（funcs / xref / around / strrefs） |
| `bios/out/guid_match.py` | ★ 新：PE 全段 GUID 扫描 + EDK2 官方库比对 |
| `bios/out/edk2_guids.py` | ★ 新：EDK2 官方 GUID 库（826 条，来自 `yeggor/uefi_retool`） |
| `bios/out/FmpDxeY750.asm.txt` | 4348 条指令反汇编 |
| `bios/out/I2cTouchPanelDxe.asm.txt` | 3697 条指令反汇编 |

## 7. 尚未定（诚实标注）

1. **`FmpDxeY750` 的两个 Insyde 私有 GUID**（`0x4868` 比对用 GUID、`0x48B0`/`0x48C0`）未识别 —— 需 Insyde HDF 框架资料
2. **`I2cTouchPanelDxe` 的 6 个私有 GUID** 未识别（`0x3950`/`0x3960`/`0x3980`/`0x39A0`/`0x39E0`/`0x3A00`/`0x3A50`）—— 其中 `0x39E0`（入口第二个 Locate）最值得追
3. **`0x4860` 槽数组** 的实际内容需运行时（当前为 0，`.data` 未初始化）
4. `FmpDxeY750` 的 **FMP 三回调表**（GetImageInfo/SetImage/CheckImage）只定位到 `GetImageInfo`（`0x540`），另两个未逐条展开
