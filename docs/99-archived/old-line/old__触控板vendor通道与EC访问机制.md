# 触控板 vendor 通道 + EC 访问机制（反汇编实测）

> ## ⚠️ 2026-09-27 项目对照说明
>
> 既有的触控板项目（`<LAB>\touchpad-lab`）**在触控板侧的分析远比本文深**，
> 本文的触控板部分（§一、§二）与项目重叠，**以项目为准**：
> - 四个 HID 集合、Col02 `out=0`、「主机无法触发触觉」—— 项目早有，且证据更全（微软规范 + 上游 RFC + 真机阳性对照）
> - **本文的"主机不能触发触觉"结论是对的**
> - 项目另有：Col04 读/写帧语义（`COL04-BOUNDARY.md`）、TF100A 39 条命令表、LRA 常量、gtx8 容器官方规格、加密定案
>
> **本文仍然新增、且项目此前没有的两块：**
> 1. **§四 EC 访问机制**（属于**角度/开盖项目**，与触控板无关）
> 2. **§一 里从 BIOS 解出的 `GoodixTpDxe` 官方主机侧驱动**：GT7868Q 的 vendor 寄存器模型
>    （`0x100` 写 17 B 命令 / `0x200` 变长数据 / `0x300` 读 5 B 状态）、命令包格式
>    （`01 A1 <24位参数> … [0x35]=0xAA` + 累加校验）、FMP 刷写流程
>    —— **这同时更正了项目里 N1 结论（"BIOS 里没有 Goodix 代码"）**
>
> 详见 `touchpad-lab/DELTA-2026-09-27-BIOS-N1更正与GoodixTpDxe.md`

> 日期：2026-09-27　机型：ThinkBook 14 G6+ IMH（21LD）
> 物料：从 30.88 MB 解压固件中提取的 `GoodixTpDxe`(0xBDCE) / `CompalEcDxeDrv`(0x2D96) / `CompalEcSmmDrv`(0x708A)
> 工具：`pe_dis.py`（FFS→PE32 提取 + capstone x86-64 线性扫描）

---

## 一、触控板：vendor 命令通道（★ 本次主要产出）

### 1.1 结论快览

| 项 | 值 |
|---|---|
| 芯片 | **Goodix GT7868Q**（驱动同时支持 **GT7863**） |
| ACPI 标识 | `_HID = "GXTP5100"`，`_CID = "PNP0C50"` |
| BIOS 驱动 | `GoodixTpDxe`（GUID `F540704A-50B5-4BB6-93A8-377EA20F1030`，48.6 KB） |
| 驱动来源 | Intel **`Vlv2TbltDevicePkg\GtpUpdate`**，核心源文件 **`GoodixTouchpadFMPImpl.c`** → 在开源 `edk2-platforms` 内 |
| 固件子系统 | **TP** 与 **TF** 两套，各自比对版本、各自刷写 |
| 固件投递 | **FMP + EFI Capsule**，不内嵌于 BIOS |

### 1.2 寄存器模型（**这是本次最有价值的一块**）

从反汇编里把三条通道全部定位到了（`cx` = 16 位寄存器号，`r8d` = 长度）：

| 寄存器 | 方向 | 长度 | 用途 | 证据 |
|---|---|---|---|---|
| **`0x100`** | 写 | **固定 17 字节** | 命令包 | `mov cx,0x100` + `r8d=0x11` + `call 0x18bc`（@0x4F62 / 0x50C3 / 0x549A） |
| **`0x200`** | 写 | **变长（分块）** | 数据块下发 | @0x534D，含分块取余 + 块尾校验字节 |
| **`0x300`** | 读 | **固定 5 字节** | 状态/响应 | `mov cx,0x300` + `r8d=5` + `call 0x161c`（@0x4FB4 / 0x5109 / 0x53A6） |
| **`0x303`** | 读 | — | 状态子寄存器 | @0x54CF |
| **`0x2194`** | 读 | 4 字节 | flag 寄存器（读回校验用） | 字符串 `0x2194:%02x,%02x,%02x,%02x` |
| `0xB68A` | — | — | 传输层包 `GtTransmissionWrite` | 字符串 `<transRead> GtTransmissionWrite(0xB68A) failed` |

函数表：**写 = `0x18bc`，读 = `0x161c`，延时 = `0x11d8`**（单位 ms，实测调用值 `0x46/0x64/0x96/0x1F4` = **70 / 100 / 150 / 500 ms**）。

### 1.3 命令包格式（写 `0x100`，17 字节）

从 0x1660–0x1702 的构造代码逐字节还原：

```
[0]     = 0x01            协议/版本标识
[1]     = 0xA1            命令码
[2]     = 参数[ 7: 0]
[3]     = 参数[15: 8]
[4]     = 参数[23:16]
[0x35]  = 0xAA            终止字节（第 53 字节）
校验     = byte[0..4] 累加和（5 次循环求和，存 [rsp+0x38]）
```

对应汇编：
```asm
01663  mov byte ptr [rsp+rax+0x40], 1      ; [0] = 1
01671  mov byte ptr [rsp+rax+0x40], 0xa1   ; [1] = 0xA1
01686  mov byte ptr [rsp+rax+0x40], cl     ; [2] = 参数低字节
016a0  mov byte ptr [rsp+rcx+0x40], al     ; [3]
016bd  mov byte ptr [rsp+rcx+0x40], al     ; [4] = 参数>>8
016ca  mov byte ptr [rsp+rax+0x40], 0xaa   ; [0x35] = 0xAA
016e3  cmp dword ptr [rsp+0x34], 5         ; for i in 0..5: sum += buf[i]
```

### 1.4 数据块通道（写 `0x200`）：分块 + 每块校验

@0x52A3 的循环：按 `[rsp+0x44]` 的块大小切分，**最后一块取余数**（`div` 后取 `edx`），每块写完调用 `0x4E5C` 得到一个校验字节并追加在块尾：

```asm
052D4  xor edx, edx
052D6  mov eax, dword ptr [rsp + 0xd8]
052DD  mov ecx, dword ptr [rsp + 0xb0]
052E4  div ecx                    ; 最后一块 = 总长 % 块大小
...
05322  call 0x35fc                ; memcpy 块数据
05327  mov dl, byte ptr [rsp + 0x45]
05330  call 0x4e5c                ; ← 算校验字节
0533A  mov byte ptr [rsp + rcx + 0x68], al   ; 校验字节追加在块尾
0534D  mov cx, 0x200
05351  call 0x18bc                ; 写 0x200
```

### 1.5 刷机流程与延时（按调用序）

```
call 0x97c (debug) → stall 70ms
  → 写 0x100 [17B]                若失败 → 0xFFFFFFFE
call 0x97c → stall 100ms
  → 读 0x300 [5B]                 若失败 → 0xFFFFFFFE
call 0x97c → stall 500ms
  → 读 0x300 [5B]
  → 写 0x200 [变长分块]
  → 读 0x300 [5B]
stall 70ms → memset(55) → 写 0x100 [17B]
stall 150ms → 写 0x303 ...
```

对齐字符串里交代的流程：`enter pass through mode` → `start updating` → `erase flash` → `write flash` → `reload subFW` → `reset ic`。

---

## 二、触控板：**主机能不能触发触觉？—— 证据表明不能**

这是触控板项目追了很久的问题，本次可以给出**有依据的结论**。

**证据链：**

1. **整个 30.88 MB 固件里 `Haptic` / `haptic` 命中 0 次。** 连一个触觉相关的字符串都没有。
2. `GoodixTpDxe` 里出现的全部命令，按字符串分类只有四类：
   - 使能/禁止上报（`7863/7868Q enable|disable report`）
   - 读取基本信息（`pid` / `vid` / `sensorID` / `cfgVer` / `IC version` / `TF version`）
   - 固件更新（`update mode` / `erase` / `write flash` / `reload subFW`）
   - FMP/capsule 解析
   **没有任何"振动 / 触觉 / 力反馈"命令。**
3. 与之前的两项实测吻合：**无 HID Manual Trigger OUTPUT 报表**、`Col02 out=0`。
4. 驱动**从板子自己读** HID 描述符里的 `wCommandRegister` / `wDataRegister` / `wOutputRegister` / `wMaxOutputLength` —— 说明原厂就没打算让主机直接驱动执行器。

**⟹ 结论：触觉由触控板自身的 **TF 子系统固件 + 板内手势引擎**自治，主机侧（BIOS 驱动 / HID 报文）没有触发入口。**

**⟹ 因此触控板项目要往前，目标应转为「拿到 TF 子系统固件」**，路径是 Lenovo 的 Goodix 触控板固件 capsule（FMP/ESRT 体系），而不是继续在主机侧枚举命令。

---

## 三、EC：访问机制全解（★ 第二个主要产出）

### 3.1 三条访问路径（反汇编 + 实测双证）

`CompalEcSmmDrv` 的函数 @0x20D0 是 EC 读字节的统一入口，结构是「**内存窗口优先，端口兜底**」：

```asm
000020D2  mov rbx, rcx                    ; rbx = EC 内偏移
000020D9  call 0x2084                     ; 探测内存窗口是否可用（查签名 0x5A / 0xA5）
000020E0  mov rax, [rip+0x2199]           ; EC 描述符指针
000020E7  je 0x20F9                       ; 不可用 → 走端口
──────── 路径 A：内存映射 ────────
000020E9  mov edx, dword ptr [rax + 0x18] ; 窗口起点
000020EC  mov r8d, dword ptr [rax + 0x14] ; 基址
000020F0  sub r8, rdx
000020F3  mov al, byte ptr [r8 + rbx]     ; 直接按内存读
──────── 路径 B：端口间接 ────────
000020F9  movzx ecx, word ptr [rax + 0x10]  ; 端口基址
00002020  ... 保存 0xD01 / 0xD02 原值
00002120  out dx, al        ; 0xD01 = 偏移高字节
00002127  out dx, al        ; 0xD02 = 偏移低字节
0000212B  in  al, dx        ; 0xD03 = 数据
00002135  out dx, al        ; 恢复 0xD01
0000213D  out dx, al        ; 恢复 0xD02
```

描述符字段：`[+0x10]` = 端口基址（DXE 里填 **`0x0D00`**）｜`[+0x14]` = 内存基址｜`[+0x18]` = 窗口起点（另一处代码用 `[+0x18] + 0x400` 算地址，**正好对上 DSDT 的 `0xFE0B0400`**）。

### 3.2 实测结果（只读，RwDrv）

| 探测 | 结果 | 结论 |
|---|---|---|
| `0xFE0B0000` – `0xFE0B03FF` | **全 `FF`** | 这 1 KB 未实现 |
| `0xFE0B0400` – `0xFE0B06FF` | **非 FF 98%** | **EC RAM 窗口 = 768 字节** |
| `0xFE0B0700` – `0xFE0B07FF` | **全 `FF`** | 768 字节之后不可读 |
| 端口 `0xD00`–`0xD03` | `00 / DF / A6 / 00` | **四寄存器块存在**（`0xD04` 起全 `FF`）|
| 端口 `0x60`–`0x6F` | `9C 20 3B FF 14 FF 08 FF 00 FF FF FF 00 FF FF FF` | 传统通道活着 |
| 端口 `0x1800`–`0x1807` | 有值 | ACPI PM 块（对照） |

**间接读测试**（设索引 → 读数据 → 恢复原值）：`0xD03` **恒返回 `0x00`**，与内存窗口内容对不上。
原值 `0xD01/0xD02` 已成功恢复（`DF`/`A6`），机器正常。**结论：该端口路径从 OS 侧不可用**，可能需 SMM 上下文或先写 `0xD00` 命令触发。**未再试探。**

### 3.3 传统通道映射（`func_0xF48` 解码）

| 通道号（= 状态口） | 数据口 | 归属 |
|---|---|---|
| `0x64` | `0x60` | PS/2 键盘控制器 |
| **`0x66`** | **`0x62`** | **ACPI EC** |
| `0x6C` | `0x6C` | 第二通道（子 EC） |

`func_0xFB4` = 等 IBF 清（读状态口，`test al,2`）｜`func_0xFFC` = 向 `0x64` 发命令（`0xAE`/`0xA8` = 8042 使能键盘）｜`0x1B18` = 延时。

### 3.4 窗口内容验证（不是垃圾数据）

连读两次 768 字节，差异集中在 **`+0x12..+0x17`**：

```
第一次: 50 00 36 27 2E 25 31 2E   →  54, 39, 46, 37, 49, 46  (°C)
第二次: 50 00 3A 28 32 27 36 32   →  58, 40, 50, 39, 54, 50  (°C)
```

**这是实时温度传感器**（与之前 `DPOT` 通道"只有 5 个温度槽"的结论一致）。另外 `+0x6C` 处有 ASCII `2023`（电池/制造日期类字段）。

### 3.5 EC 固件仍然不在本包内

三条独立证据（`[Region] EC=0`、`[UpdateEC] Flag=0`、固件里 `ECFW`/`EmbeddedController` 零命中）之外，本次新增第四条：

**`EcCapsuleDxe` 里有一张标签目录**（`_AUTOPAD` / `_TBT_IMG` / `_ISH_IMG` / `$_MICROCODE_IMG` / `_IOM_IMG` / `_MGPHY__` / `_ME_IMG_`）+ 函数 `FindCpHeader` / `H2OCpTrigger` → **EC 固件走 capsule 单独投递**。

**所以角度项目要拿到 EC 固件，只能靠 Lenovo 的 EC capsule（或等价物），BIOS 包里没有。**

---

## 四、产物

| 文件 | 内容 |
|---|---|
| `bios/extract/pe_dis.py` | **FFS→PE32 提取 + capstone 反汇编器**（可复用） |
| `bios/extract/GoodixTpDxe.asm.txt` | 触控板驱动完整反汇编（6859 条指令） |
| `bios/extract/CompalEcSmmDrv.asm.txt` | EC SMM 驱动完整反汇编（3599 条） |
| `bios/extract/CompalEcDxeDrv.asm.txt` | EC DXE 驱动完整反汇编（2862 条） |
| `ec_window_probe.py` | EC 内存窗口只读探测（RwDrv 物理读） |
| `ec_port_probe.py` | EC 端口只读扫描（默认无写；`--allow-write` 才测间接读） |
| `ec_indirect_test.py` | 间接读一次性测试（含基线稳定性检查 + 原值恢复） |
| `ec_lid_diff.py` | EC 窗口快照/差分工具（`snap` / `diff`），已抓 `ec-lid-snaps/开盖基线.bin` |
| `ec-lid-snaps/开盖基线.bin` | 768 字节基线快照 |

---

## 五、下一步

| 优先 | 动作 | 依据 |
|---|---|---|
| ★★★ | **找 Lenovo 的 Goodix 触控板固件 capsule**，解出 **TP / TF** 两份子系统固件 | 触觉在 TF 里；驱动里已有完整包格式与刷写流程 |
| ★★★ | **找 Lenovo 的 EC capsule**（EC 固件本体） | 角度项目唯一剩余路径 |
| ★★ | 拿磁铁做 `ec_lid_diff.py` 差分 → 定位 **LIDF** 位 | 工具与基线已就绪；一次读数即可定案 |
| ★★ | 反汇编 `CompalEepromDxe` / `CompalGlobalNvsDxe` | 看是否有更直接的 EC 读写通道 |
| ★ | 读开源 `edk2-platforms` 的 `Vlv2TbltDevicePkg/GtpUpdate` | 直接拿到驱动参考源码，省掉大量反汇编 |
| ★ | 拉 `ty2/goodix-gt7868q-linux-driver` | 社区已有同芯片 Linux 驱动（含 report descriptor fixup），可对照 |
| ⚠️ | **复原 Windows 安全设置** | VBS / HVCI / 驱动黑名单仍是关闭态，实验已做完 |
