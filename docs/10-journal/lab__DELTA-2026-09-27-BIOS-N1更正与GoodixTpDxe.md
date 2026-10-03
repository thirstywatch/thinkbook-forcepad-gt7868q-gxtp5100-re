# DELTA 2026-09-27 · N1 更正：**BIOS 里确实有 Goodix 代码**

> 来源会话：另一个 AI 会话（WorkBuddy，工作目录 `<WORKSPACE>`）
> 性质：**对既有结论 N1 的更正** + 一批新物料
> 请与 `PREFLIGHT-STATE.md` 合并；本文只写「变了什么」。

---

## 0. 一句话

**N1（"BIOS 里没有 Goodix 代码 ⇒ 从 BIOS 取容器解析器是死路"）判据错误，结论已被推翻。**
真实情况：**BIOS 里存在官方主机侧驱动 `GoodixTpDxe`（48,590 B），含 GT7868Q 完整 vendor 协议**。

---

## 1. N1 错在哪（两层错误，可精确指认）

### 错误 1：**用错文件** —— 搜的 `NJCN67WW_FWUpdate.bin` 是 Intel ME 区，不是 BIOS 本体

`HANDOVER.md:224` 自己就写明了：

> `C:\Drivers\Flash\` 两个 `NJCN*WW_FWUpdate.bin` 是 **Intel ME 区**（配 `FWUpdLcl64.exe` + `FLASH_me.BAT`），**不是 BIOS 本体**

而 N1 的表述是「`NJCN67WW_FWUpdate.bin`（Intel FPT，20 分区）**全镜像** 0 个 Goodix…」—— **把一个 ME 区文件当成了 BIOS 全镜像**。

### 错误 2：**在压缩态上搜字符串**

即便拿到真正的 BIOS 镜像，直接搜字符串也会得 0 —— 因为主 BIOS 卷是 **LZMA 压缩**的。本会话实测：**压缩比 5.18 MB → 30.88 MB（5.95:1）**，长串（`Goodix` 之类）根本不会以明文出现在压缩流里。

> 这与项目已有的那段更正同源：*「用标准 FFS 特征去搜 Insyde 容器 ⇒ 0 命中被误读成『加密』」*。
> 现在是同一类病的第二次发作：**0 命中被误读成「本来就没有」。**
> **规矩建议**：凡「某容器里没有 X」的结论，**必须附一条「我已经把它解开了/确认它是明文」的旁证**，否则降级为【未定】。

---

## 2. 正确的链路与数字（可复现）

```
<HOME>\Downloads\NJCN67WW.exe            12,790,536 B   ← BIOS 更新包（7-Zip SFX）
  └─ 7z x  →  isflash.bin                           19,205,640 B
       └─ 前 2 字节 MZ → 这是【外壳 PE32+，Subsystem=10 EFI_APPLICATION，FileAlignment=0x20】
            └─ .reloc 节 (0x5860, 19,181,568 B = 99.9%) = Insyde $_IFLASH_* 容器
                 ├─ $_IFLASH_DRV_IMG   最外层
                 ├─ $_IFLASH_BIOSIMG   声明 0x01000000 = 16 MiB
                 │    └─ 实体在 payload+0x1E1170（判据：所有 _FVH 偏移 ≡ 0x170 mod 0x1000）
                 │         └─ bios16+0x2F8000 的 FV 里有个 LZMA 段
                 │              （GUID EE4E5898-3914-4259-9D6E-DC7BD79403CF，段长 0x4F1C9F）
                 │              └─ 解压 5,184,647 → 30,883,968 B  ★ 长度与声明分毫不差
                 │                   └─ 一个完整 FFS2 卷：447 个文件 / 389 个具名 / 1660 个段
                 ├─ $_IFLASH_INI_IMG   （内嵌 platform.ini，与包外那份不同）
                 └─ $_IFLASH_BIOSCER / $_PFAT_CER_IMG__ / $_PFAT_HDR_IMG__
```

**解析正确性的判据**：解压出的卷里**第一个文件是 `FC510EE7-FFDC-11D4-BD41-0080C73C8881`（PEI APRIORI）**。

### 关键更正：`platform.ini` 的 `[Region] EC=0` 不是 BIOS 侧的判据
顺带澄清一个易误读点：`[MULTI_FD] FD#01=ID,ILVR4,isflash.bin` 里的 `ILVR4/ILVR6` 是 **14"/16" 两个机型代号**，不是 BIOS 版本；`[Region] BIOS=1 … EC=0` 说的是**不要把 EC 区当独立区刷**，与「BIOS 本体在不在包里」无关。

---

## 3. ★ 新增物料：`GoodixTpDxe`（官方主机侧驱动）

| 项 | 值 |
|---|---|
| GUID | `F540704A-50B5-4BB6-93A8-377EA20F1030` |
| 大小 | **48,590 B**（PE32+，x86-64，DXE_DRIVER） |
| 名字 | `GoodixTpDxe`（FFS 的 UI 段） |
| 关键串 | `Goodix` ×12；`GTPGetBasicProperties7863` / `…7868Q`；`GoodixTouchpadUpdate`；`[GTP-DEBUG/INFO/WARNING/ERROR]` |
| **来源（编译期路径，白拿的）** | `c:\minnowboard\edk2-platforms\Vlv2TbltDevicePkg\GtpUpdate\GoodixTouchpadFMPImpl.c` |
| | **⇒ 该包在开源 `edk2-platforms` 内，可直接读参考源码** |

### 3.1 GT7868Q 侧 vendor 寄存器模型（★ 项目此前没有这一侧）

从反汇编里把三条通道定位到（`cx` = 16 位寄存器号，`r8d` = 长度）：

| 寄存器 | 方向 | 长度 | 用途 |
|---|---|---|---|
| **`0x100`** | 写 | **固定 17 字节（0x11）** | 命令包 |
| **`0x200`** | 写 | 变长（分块，块尾追加校验字节） | 数据块 |
| **`0x300`** | 读 | **固定 5 字节** | 状态/响应 |
| `0x303` | 读 | — | 状态子寄存器 |
| `0x2194` | 读 | 4 字节 | flag 寄存器 |
| `0xB68A` | — | — | 传输层 `GtTransmissionWrite` |

函数：**写 `0x18bc`｜读 `0x161c`｜延时 `0x11d8`（单位 ms；实测 70 / 100 / 150 / 500）**

### 3.2 命令包格式（0x1660–0x1702 逐字节还原）

```
[0]     = 0x01            协议/版本
[1]     = 0xA1            命令码        ← ★ 见 §3.4
[2..4]  = 24 位参数
[0x35]  = 0xAA            终止字节（第 53 字节）
校验     = byte[0..4] 累加和（5 次循环）
```

**`0x35 = 53 < 64` ⇒ 这个 54 字节报文正好装得进 Col04 的 64 字节载荷。**

### 3.3 固件更新流程（与项目已知的 ESRT/`Goodix Update UEFI` 对齐）

```
enter pass through mode → start updating → erase flash → write flash
→ reload subFW → reset ic
```
FMP / EFI Capsule 体系；包内有 **TP / TF 两个子系统**分别比对版本、分别刷写（`GTPCheckTFUpdate`）。
包格式（字符串即规格）：`Firmware package protocol: V%u` + PID/VID/chip type/size/subsystem num + 每子系统 `type/size/flash_addr`。

### 3.4 ★ 对 H1（唯一未验证的门）的旁证

项目 H1 = 「**GT7868Q 会不会把 `A1` 帧转发给 TF100A**」，且 09-14 真机那一发**没有收到 `0xA2`**。

**本会话新增一条独立旁证**：官方驱动里 **`[1] = 0xA1` 就是一个正常命令码**，而且它是**写给寄存器 `0x100`** 的 ——
⇒ **`0xA1` 属于 GT7868Q 自己的命令空间**（GT7868Q 自己处理），**不像是「转发给 TF100A 的信封」**。
⇒ 倾向与实测一致（H1 = 否），但**这是旁证不是定论**，建议记入 `COL04-BOUNDARY.md` 的 H1 条目。

### 3.5 顺带：`EcCapsuleDxe` 的标签目录（与触控板无关，供角度项目用）

`EcCapsuleDxe`（`C26B2DBB-83B2-4AF2-BBD7-D4558036DE11`）内含 8 字节标签：`_TBT_IMG` / `_ISH_IMG` / `$_MICROCODE_IMG` / `_IOM_IMG` / `_MGPHY__` / `_ME_IMG_`，函数 `FindCpHeader` / `H2OCpTrigger`。

---

## 4. 本会话**重复造轮子**的清单（明确记下，免得下次再犯）

| 本会话"发现" | 项目早已有的 | 项目还更深 |
|---|---|---|
| 四个 HID 集合、Col01/02/03/04 的 In/Out/Feat | `NEXT-SESSION.md §7`、`TOUCHPAD-RE-REPORT.md §1.4` **数字完全一致** | — |
| "Col04 是厂商通道，rid=0x0E，65 字节" | `COL04-BOUNDARY.md` 已解出**读帧语义**（v1/v2 两种取址）+ 写帧 `[4]=len+5` | ✔ 项目更细 |
| "Col02 out=0 ⇒ 主机不能触发" | 已在 `FINAL-CHAIN.md`/`TOUCHPAD-RE-REPORT.md §2.1`，且**微软规范 + 上游 RFC** 三重佐证 | ✔ 项目更全 |
| TF100A 明文反汇编、`TF100A_Test_FW`、版本 `5.21.01.23007`、编译时间 | `VIBRATION-FORENSICS-2.md`、`TOUCHPAD-RE-REPORT.md §3.4` | ✔ 项目已有 **39 条命令表**、LRA 常量、调用图 |
| "载荷 100 KB 高熵 = 加密" | `re/aes_payload_audit*.py` 已定案：**128 位分组密码 + ECB 式 + 跨 4 年同密钥** | ✔ 项目深得多 |
| "gtx8 容器 / 子镜像表" | **官方开源于 `fwupd/plugins/goodix-tp/`**，头部 100% 校验通过、13 条子镜像落位地址全known | ✔ 项目远深 |

**⇒ 本会话在触控板侧唯一没有重复的是第 3 节（BIOS / `GoodixTpDxe`）**，那正是 N1 挡住的那条路。

---

## 5. 本会话**弄错**的地方（一并记录，防止污染）

| 我说过 | 实际 |
|---|---|
| 「**推翻**主机没有入口的结论」 | **错**。Col04 项目早已发现并**已实测判定为死路**（H1 = 否）。这是我自己的回归，不是新发现。已在原文档原位更正 |
| TF100A 是 **Cortex-M4F** | 项目记为 **STM32F1 类（Cortex-M3）**。我把几处字节误读成 `vmov/vpop`（M3 无 FPU）⇒ **以项目为准** |
| TF100A 是「Goodix 的 TF 子系统」 | **错**。是**北京钛方科技** |
| TF100A 镜像尾界 `0x26E00` | 应为**到文件末尾**（56,480 B）；`0x19ABC − 0x113C = 100,480 = 785 × 128` 说明容器是 128 字节块结构 |
| 明文区「无任何数值表」 | 项目已从同段代码里取出**命令表 39 条 + LRA 常量 + 调用图** |

---

## 6. 产物索引（本目录 `bios-re/`）

| 文件 | 内容 |
|---|---|
| `GoodixTpDxe.bin` | 官方主机侧驱动原件（48,590 B） |
| `GoodixTpDxe.asm.txt` | 完整反汇编（6,859 条指令，capstone） |
| `模块清单-389.txt` | 解压后 447 个文件里 389 个具名模块（类型/GUID/大小/名字） |
| `EcCapsuleDxe.bin` | EC capsule 处理器（标签目录 + `FindCpHeader`） |
| `ffs_scan.py` / `pe_dis.py` | UEFI 卷遍历器 / FFS→PE32 提取 + 反汇编器（可复用） |

原始中间件（不在此目录，在来源会话工作区）：
`fw_decompressed.bin`（30.88 MB 主固件）、`bios16.bin`（16 MiB）、`payload_reloc.bin`（19.18 MB）

### 复现要点（防踩坑）
```
FFS 文件头：GUID(16) + IntegrityCheck(2) + Type(1) + Attributes(1) + Size(3) + State(1) = 24 B
            ★ Type 在 +18（不是 +17）——IntegrityCheck 是 2 字节
FV 头：0x20=FvLength / 0x30=HeaderLength / 0x34=ExtHeaderOffset(u16)
       ★ 忘了 ExtHeaderOffset → 文件区起点算错，读出一堆 GUID=FFFFFFFF
LZMA GUID 的 LE 字节：98 58 4E EE 14 39 59 42 9D 6E DC 7B D7 94 03 CF
       ★ 手抄十六进制必错（我第一次把 Data4 写成 D6 9E → 0 命中）
解析正确性判据：解压卷首文件应为 PEI APRIORI FC510EE7-FFDC-11D4-BD41-0080C73C8881
```

---

## 7. 这对项目意味着什么（不夸大）

| 问题 | 影响 |
|---|---|
| 重开"从 BIOS 取容器解析器"这条路？ | **部分重开**：拿到了**官方主机侧驱动**（GT7868Q 的寄存器模型 + 命令包 + FMP 流程）。但请注意：**它描述的是 GT7868Q 侧**，而主机侧不可达的结论依然成立（约束来自 Col02 描述符）。**它不能把命令送进 TF100A。** |
| 对方案 ③（HDP/HDN 接管 LRA） | **无影响**，方案 ③ 仍是唯一确定可行的路 |
| 对 H1 | 提供一条**独立旁证**（§3.4），倾向"否" |
| 对 PC 侧手势软件 | 无影响 |
| 对**角度项目**（另一个项目） | `bios-re/` 里的 `EcCapsuleDxe` + EC 访问机制（见来源会话报告）另有用途 |

---

## 8. 建议给项目加的两条规矩

1. **「某容器里没有 X」必须附「我已解开它/确认它是明文」的旁证**，否则降级【未定】。（N1 就栽在这）
2. **引用文件时必须写明它是哪一区**（BIOS 区 / ME 区 / 描述符 / 独立芯片）——`NJCN*WW_FWUpdate.bin` 被当"BIOS 全镜像"用了 5 天。
