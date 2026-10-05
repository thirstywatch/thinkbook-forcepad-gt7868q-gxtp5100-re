# 社区外联草稿 · Goodix GT7868Q / GXTP5100

> **【现役 · 2026-09-14 23:3x 已修订】** 项目当前权威状态：`PREFLIGHT-STATE.md`。
> ⚠️ 已修正：原文「5,141 字节」**已推翻**（下界 **837 字节**）；
> **新增 §9 = 向原厂申请 EVK 的中英文话术**（建议优先做，比要固件现实得多）。

> **投递目标（按期望值排序）**
> 1. **GitHub issue** → `github.com/ty2/goodix-gt7868q-linux-driver` ← 首选，持久、可检索、人最对
> 2. **linux-input@vger.kernel.org** → 抄 `Rong Zhang`（上游压感板触觉 RFC 作者）
> 3. LKML 上 `djedi` 报同款芯片锁死的那个串
>
> 下面正文按**纯文本友好**写的（邮件列表不会渲染 markdown）；
> 贴 GitHub issue 时把表格保留即可，其余原样。
> **发出前删掉本段。**

---

**Subject:** [GT7868Q / GXTP5100] descriptor byte 607, vendor-channel protocol, a haptics image that points past its own end, and things that brick the pad

Hi,

I've been reverse-engineering the Goodix touchpad in a Lenovo ThinkBook 14 G6+ IMH
(21LD) — `27c6:01e9`, ACPI `GXTP5100`, chip family GT7868Q, I2C-HID. I have a batch of
results that I'd have wanted on day one, so I'm posting them rather than sitting on
them. All of it is static analysis of vendor firmware plus read-only probes from
Windows. Nothing was ever flashed.

Apologies for the length; the summary is that (a) there's a descriptor bug worth
knowing about, (b) the vendor channel is mapped, (c) the haptics live in an image the
update package only ships part of — and finding the rest is the one thing I'm asking
for.

## 1. Descriptor bug: an inverted logical range at byte 607

`rid=9` (Haptic Intensity, usage `0x0E/0x23`) comes out with its logical range
**inverted, `[100, 1]`**. The byte that should be `0x25` (Logical Maximum, 2-byte
value) is written `0x15` (Logical Minimum, 2-byte value) — so the descriptor declares
a second Logical Minimum where a Logical Maximum belongs.

This looks like the same wall the Arch user hit in
<https://bbs.archlinux.org/viewtopic.php?id=292878> with the same `acpi:GXTP5100` /
`27c6:01e9` ID — `hid-multitouch` probe failing with `error -22` (`-EINVAL`) is exactly
what a parser does with a descriptor like this. I believe ty2's driver already patches
descriptor byte 607; if so, this is independent confirmation of *why* that patch is
needed.

## 2. Vendor channel: collection 4, and a non-obvious length constant

The pad exposes four HID collections. Collection 4 is the vendor one
(`Usage Page 0xFF00 / Usage 0x01`, 65-byte IN and OUT, report ID `0x0E`).

Read:

```
0E 20 00 00 05 01 <addr16BE> <size16BE>
```

Write:

```
0E 20 00 00 <len+5> 00 <addr16BE> <len16BE> <data...>
```

Both go out via `HidD_SetOutputReport` on collection 4; the answer comes back on the
IN report. **The write path only works with the `<len+5>` length constant** — without
it the write is silently dropped, no error. That cost me a while, so: it's `len+5`.

## 3. The 16-bit address space is NOT memory

This is the important negative, because it's the obvious first idea. The vendor
channel takes a 16-bit address, so the hope is "this is a generic read/write window
into SRAM or flash, I can go patch the firmware." **You cannot.** The space is the
touch sensor's data domain.

Evidence:

- I scanned all 64 KB. **There is no ARM vector table anywhere in it.** A Cortex-M
  image must have one; its absence is decisive.
- Two windows are byte-for-byte stable across repeated reads:
  `0x5B80` (128 B) — 0 of 64 words changed; `0x4000` (256 B) — 0 of 128 words changed.
- One window is not: `0x9000` (256 B) changed **49 of 60 bytes between two back-to-back
  reads**, i.e. it is refreshed faster than a single vendor round-trip (~10 ms).
  That matches a ~100 Hz scan frame.

So the writable region is static configuration/calibration and is **insensitive to
touch**; the touch-responsive region is **live scan data and any write to it is
overwritten within one frame**. I verified the writable half directly — writing a cell
in `0x5B80` and reading it back returns what I wrote — and the live half by measuring
the refresh. There is no "write a fake pressure reading" shortcut here.

## 4. The update package carries two payloads, and the plaintext one points past its end

### 4.1 Provenance and real layout

The package is Goodix's own ESRT/UEFI firmware update, delivered by Windows Update —
`TB14P_GT7868Q_14030522_20240202.BIN`, 161,628 bytes,
sha256 `0033d075fae88f0048544696c8941ed7dcca4269beaa84af76323ef5bbdcee72`, resident in
the DriverStore and hardlinked into `C:\Windows\Firmware\`.

Its structure, laid out to the byte:

```
  0x00000      1,084   container header
  0x0043C      3,252   three byte-identical blocks
  0x010F0         76   tail
  0x0113C    100,608   payload A          <- declared 100,608, present 100,608  (exact)
  0x019A3C       128   payload B's header <- 04 14 00 00 then zeros
  0x019ABC    56,480   plaintext ARM image <- vector table here
  ---------------
             161,628   = file size exactly
```

The header declares payload lengths of **100,608** and **56,608** (BE u32 at `0x44` and
`0x48`), and **both match the bytes present exactly** — 56,608 being the 128-byte header
plus the 56,480-byte image. So the package is complete on its own terms; there is no
missing tail *in the file*.

Where the vector table actually is, since it's easy to get wrong: at `0x19ABC` it's
`SP = 0x200076C8`, `Reset = 0x08005165` (valid). At `0x19A3C` it's `SP = 0x00001404`,
`Reset = 0x00000000` — that's payload B's zero-padded header, not a vector table. Both
offsets are real; they just point at different things, 128 bytes apart.

One trap worth flagging: this file admits two decompositions that both sum to 161,628 —
`97 x 1084 + 56,480`, and `1084 + 3252 + 76 + 100608 + 128 + 56480`. They are **not**
competing hypotheses; they are the same file with the cut drawn 128 bytes apart. Block 4
of the first reading straddles the boundary of the second. I lost time treating them as
contradictory, so: they aren't.

Per-block entropy:

```
  block 0        4.93          header (contains a HID *keyboard* descriptor + keymap)
  blocks 1-3     5.19          three byte-identical blocks
  block 4        6.97          straddles the boundary above
  blocks 5-96    7.80 - 7.99   all 92 distinct -> encrypted / compressed
```

So: ~100 KB of encrypted-looking data, plus a 56,480-byte plaintext ARM image at the end.
Payload A opens with a plaintext 24-byte header — `00 01 88 FA | 5F 37 | YELSTO | 00 00 06 |
7868Q` — and is uniformly high-entropy after that.

### 4.2 The plaintext image

It self-identifies with the strings `TF100A_Test_FW`, `Nov 28 2023`, `5.21.01.23007`.
In it I found the LRA drive configuration (**TIM3 -> PWM, amplitude 119, period 999**),
a doorbell byte at `0x20004128`, a play routine at `0x08008628`, and a 39-entry command
dispatcher at `0x080091C0` keyed on a namespace byte plus a command code — none of the
39 touch TIM2 or TIM3.

And it **refers past its own end**. The image is linked at `0x08000000` and is 56,480
bytes, so it covers `0x08000000`–`0x0800DC9F`. Its own vector table is otherwise valid —
84 entries, 73 populated — but two populated handlers land outside it:

| site | points to | past end by |
|---|---|---|
| vector slot 6 | `0x0800DFE5` | 837 B |
| vector slot 53 = **IRQ 37, USART1** | `0x0800DEE9` | 585 B |
| code at `0x08008FF6`: `movw r1,#0xf0b5` + `movt r1,#0x800` | `0x0800F0B5` | ~~5,141 B~~ → **not a length** (corrected 2026-09-14) |

*(The third row is listed only as a raw observation: that constant is **not** proven to be
"the image's intended length" — it is never used as a literal in the image, and it is more
likely just a data pointer. The defensible bound is the **837 B** from vector slot 6.)*

Add to that: the three functions that can set the doorbell (`0x08008AF0`, `0x08008B38`,
`0x08008B5C`) have **zero references anywhere in the whole 161,628-byte container** — no
`bl`, no `blx`, no literal-pool entry.

**So whatever calls the doorbell lies in address space the image points at but does not
contain.** Note this is *not* the same claim as "the file is short" — the file matches its
own declared lengths exactly (§4.1). It's that the image is a partial view of the address
space, not a complete firmware.

### 4.3 What I have NOT established

I want to be explicit about this, because it's the part I'd most like help with. I am
not claiming a two-chip architecture — I don't have the evidence for one.

- **How many dies are actually in this module?** I have not verified it. I have not
  physically inspected a module, and I cannot read the chip markings.
- **What does `TF100A` name?** A physical chip? An internal project? A firmware branch
  (`_Test_FW` reads like a test build)? All I have is an in-image string, and no
  independent confirmation that it names a chip at all.
- **Does the encrypted ~100 KB belong to a second device**, or is it a protected region
  of the same one? I can't tell. The one thing I *can* point at is that the two payloads
  identify themselves differently: payload A's plaintext header self-reports `7868Q`, while
  payload B's image self-reports `TF100A_Test_FW`. That's suggestive of two targets — but
  both are just strings inside the package, and neither is read off a chip, so I'm not
  treating it as an answer.
- **Where does USART1 go?** It is configured in this firmware (~460800 baud,
  `[0x200061B4 + 0x108] = 0x70800`), but a peripheral being configured says nothing
  about what it is wired to. It may be an inter-chip link inside the module; it may be
  a factory-test port on pads.

Worth stating plainly: the family name `GT7868Q` comes only from the **package
filename**, and `TF100A` only from an **in-image string** — neither is read off a chip.
So any "chip A does X, chip B does Y" story, mine included, is currently unverified. If
you've opened one of these modules, you know more than I do.

## 5. HID level: the pad reports presses, but cannot be asked for one

Collection 2 (the PTP collection) declares **zero output reports**. Under Usage Page
`0x0E` (Haptics) it has only `0x0E/0x23` (Intensity) — no `0x0E/0x21` (Manual
Trigger), no `0x0E/0x10` / `0x0E/0x11` (Waveform / Duration List). Per Microsoft's
haptics guide, those are exactly what a host needs in order to trigger.

I confirmed it empirically rather than only by reading the descriptor: I wrote six
different Intensity values (5 / 40 / 75 / 15 / 60 / 90) with a finger resting on the
pad. The click feedback strength **did** change — so the write genuinely reaches the
device, it's a valid positive control — but **no value ever produced a vibration**.

This matches the upstream RFC's statement that device-initiated haptics are not host-
controllable. Just adding one more machine to the pile, with a clean positive control
attached.

## 6. Warning: some vendor opcodes brick the touchpad

Reading collection 4 is safe — I did 1,093 reads in one exhaustive sweep with 0
failures.

**Writing or enumerating it is not.** Specifically, opcodes `0x0E`, `0x0F` and `0x99`
**break the response channel** (`SetOutputReport` then fails with `err=122`), and that
state **degrades further into total failure of the touchpad** — it disappears from the
system entirely. The only recovery I found is a full power drain: power off, unplug
the charger, hold the power button 20-30 seconds, wait a minute, boot. That brought it
back, twice.

So: if you're probing this chip and it goes quiet, **stop sending and power-drain
first.** Don't keep trying opcodes. It does not recover on its own.

## 7. Negative results worth not repeating

- **LVFS / fwupd has no GT7868Q package.** `com.goodix.goodixtp.firmware` exists only
  in the *testing* metadata (`firmware-testing.xml.gz`), not in the main
  `firmware.xml.xz` index. The single GT7936L sample there is a different chip with a
  different container generation (`BERLIN` magic) whose payload is not readable Thumb
  code — encrypted or compressed. Also note the download URL format is
  `https://fwupd.org/downloads/<sha256>-<filename>`; the bare filename 404s.
- **The Lenovo BIOS package does not embed the touchpad firmware.** I checked
  `5B11M67497.CAP` (2,113,472 bytes, 2025-03-21, from
  `C:\Windows\Firmware\{652d4eee-...}\`): zero occurrences of the Goodix container
  magic, zero `GT7868Q` / `TF100A` / `TB14P` / `Goodix` / `GXTP5100` strings, and it
  starts with `4D 5A` — it's a PE flasher, not a bare UEFI capsule. Structurally it
  shouldn't either: the touchpad firmware has **its own ESRT GUID**
  (`{b6ae105a-ba93-4fc8-aa28-e63903ffedde}`) and its own driver package, so it's
  flashed by its own package and not by the BIOS.
- **Reading flash through the vendor channel is not possible** — see section 3, no
  vector table anywhere in the 64 KB.

## 8. What I'm looking for

**First, the cheap one:** if you already know how many dies are in one of these modules
and what `TF100A` names (§4.3), that would save me a disassembly I'd rather not do.

**Then: a complete plaintext image.**

Being careful about what I can actually prove here — the plaintext image covers
`0x08000000`–`0x0800DC9F`, yet its own vector table references `0x0800DFE5` and
`0x0800DEE9`, i.e. **837 bytes past the image's end** (that is the largest genuine
vector-table overrun). **So the image alone is not the whole of what it runs from.**
That's arithmetic on the image itself and doesn't rest on any architecture story.

> **(corrected 2026-09-14)** An earlier draft of this letter said "5,141 bytes past the
> end". That number came from a `movw/movt`-built constant (`0x0800F0B5`) which is
> *not* proven to be a length — it is more likely just a data pointer, and it is never
> used as a literal in the image. The defensible figure is **837 bytes**.

What I *can't* tell from here is why: a partial/overlay image, a test build, or another
region of the same flash all look the same from outside. I'd rather not assert which.

That missing region contains precisely what I need:

- the **USART1 receive ISR** (vector `0x0800DEE9`)
- the **caller of the doorbell setter**

With it I could answer the question I actually care about: *at the moment the pad
decides to fire the LRA, is the trigger a command arriving from elsewhere, or a
pressure value evaluated locally?* That determines whether a host-reachable path could
ever exist at all.

So, concretely — any of these would be enormously helpful:

1. **How many dies are on this module, and what is `TF100A`?** Even "I opened one, here
   are the markings" settles it.
2. **A complete plaintext image** — a full/older Goodix or Lenovo package for this part,
   or the image from a unit on a different firmware branch.
3. A **complete SPI dump** from a board carrying this chip.
4. Any information on **decrypting the ~100 KB encrypted payload**.
5. Anyone who has **scoped the USART1 traffic on this module** — even a partial capture
   would tell us the frame structure, and whether that link is even populated.

I'm happy to share the full write-up, my RE scripts (Capstone-based), the raw
descriptor dump, the 64 KB scan, or any of the captures. If it's useful I can also
post the scan results as a table.

Thanks for reading,
`<name>`

---

## 9. 单独一条：向原厂申请评估套件（EVK）的话术 ★ 建议优先做这件事

> **加这一节的理由**：上面 §8 问的是"持有答案的人"（社区）。
> 但**持有全部技术资料的人只有一个** —— 右侧那颗芯片的原厂。
> 而**直接要固件必被拒**（NDA 内容）；**要 EVK 是他们的标准商务流程**（芯片厂商本来就要发 EVK 给客户做开发），**成功率高得多**。
>
> **★ 最高价值的目标不是固件，是 EVK** —— 拿到 EVK 就有官方文档/原理图/例程，问题从"逆向一个黑盒"变成"读一份文档"。

### 9.1 向原厂（力度/触觉芯片那一家）申请 EVK

**渠道**：官网联系表单 / `sales@…` / 电话（钛方科技：`sales@taifangtech.com`、`010-82874620`）
**要点三条**：① 说清你是谁、在做什么 ② 说清卡在哪 ③ **要具体的东西**（datasheet / 申请一块 EVK），而不是"能给点资料吗"

**中文版**

> 主题：**关于 TF100 系列芯片的开发资料与评估套件申请**
>
> 您好：
> 我在做**基于 TF100 系列力度感应芯片的触控板震动反馈方案开发**，目前在**接口文档**上卡住了 ——
> 需要确认该芯片对外命令接口的**帧格式与命令空间定义**。
> 想请问：
> 1. 能否提供 **TF100 系列的 datasheet / 接口文档**（如需签署保密协议我可以配合）；
> 2. 能否**申请一块 TF100 的评估套件（EVK）**用于开发验证？
>
> 我的应用场景是 PC 触控板的**力度感应 + 触觉反馈**，与贵司已有方案一致。
> 如需要，我可以提供更详细的项目说明。
>
> 顺祝商祺
> `<name>` / `<联系方式>`

**English version**

> Subject: **Request for TF100-series documentation and an evaluation kit (EVK)**
>
> Hello,
> I'm developing **a touchpad haptic-feedback solution built around the TF100-series
> force-sensing chip**. I'm blocked on the **interface documentation** — specifically the
> frame format and command set exposed to the host.
> Could you please tell me:
> 1. whether the **TF100 datasheet / interface spec** can be shared (I'm happy to sign an NDA); and
> 2. whether I can **obtain an evaluation kit (EVK)** for development.
>
> My use case is **force sensing + haptic feedback in a PC touchpad**, which matches your
> existing reference designs. I can provide a fuller project description on request.
>
> Best regards,
> `<name>` / `<contact>`

### 9.2 同时值得问的一家：做同类方案的触摸控制器原厂（汇顶）

同一封信改两个词即可 —— 问 **GT7868Q 是否会转发主机厂商命令给配套的力/触觉芯片**。
**这一问正好命中 `PREFLIGHT-STATE.md` §7 里那个唯一的门（H1）** —— 如果他们答"会/不会"，就省掉样机上的那一发实验。

---

## 10. ★ 一条极小、但能一次定案的问题：同款芯片另一台机器的 X/Y LogicalMax

**背景（2026-10-05 新增）**：本项目在做固件配置（cfg）寄存器像的字段定名，已经把 **X/Y 坐标点数**钉到 cfg 的固定偏移上：

| 项 | 本机（ThinkBook 14 G6+ IMH，`27C6:01E9`） |
|---|---|
| HID 描述符里 X 的 Logical Maximum | **4149** |
| HID 描述符里 Y 的 Logical Maximum | **2147** |
| cfg 寄存器像 `+0x10F` 的 u16BE | **4150** = 4149 + 1 |
| cfg 寄存器像 `+0x111` 的 u16BE | **2148** = 2147 + 1 |

即疑似规则：**cfg 里存的是「坐标点数 = LogicalMax + 1」**。四条独立内部证据支持它（X/Y 双向 +1；4 份配置副本同相对偏移各自命中；跨机型变化；`+1` 的系统性）。

**但缺一台机器的独立复现** —— 本项目手上另外两份 cfg（同芯片、另一机型的两个版本）给出 **X=3244 / Y=2016**。

> ### 想问的一句话
> **GT7868Q（`27C6:01E8` / `0x01E0` / `0x01E9` 任一）的触控板，你机器上 HID 描述符里 X、Y 两个 Usage 的 Logical Maximum 是多少？**
> - 如果某个机型的值是 **3243 / 2015**，那台机器正好对应本项目手上那两份 capsule 固件 ⇒ **规则成立、机型身份同时确定**；
> - 如果是别的值，这条规则就被否证，我们也省得继续在错误方向上走。
>
> **怎么取（任选其一）**
> - Linux：`hidrd-convert -i natv -o spec /sys/bus/hid/devices/*/report_descriptor`，或在 `dmesg`/`libinput record` 里找 PTP 集合的 `Logical Maximum`；
> - Windows：本仓库 [`tools/hid/lab__RawRdesc.cs`](../../tools/hid/lab__RawRdesc.cs) 就是为这个写的（本项目本机那份 `poc/hid-dump.txt` 由它导出）；
> - 只要 **两个十进制数**，不需要描述符全文。

**★ 为什么这条值得单独问**：它是**唯一一条零风险、一次就能把"cfg 字段定名"从"半确认"推到"已确认"**的问题。拿到之后，cfg 里紧跟其后的两个 u16（本机 90 / 120，capsule 90 / 130）就能顺势判定哪个是**触发阈值** —— 而那是本项目"让滑动也震"这条路上**唯一一个官方支持的可调参数**。

### 10.1 后续进展（2026-10-05 深夜）——这一问的**地位又升了一级**

- 已用 **5 份真实手机 cfg 包（GT9916/Berlin）** 做了**跨代"已知答案"**验证：
  三块板各自在自己的 cfg 里命中**自己面板的真实分辨率**（1220×2712 / 1080×2400 / 1440×3200），
  且两块同族板在同一相对位置**逐字段对齐**（X/Y 随板变，`140/30/40/60/80` 五个常量跨板全等）。
  ⇒ **"Goodix cfg 承载 X/Y 坐标点数（= 输入 max + 1）"这条语义已获跨代独立证据**，`+1` 规则升级为**【已确认（语义层）】**。
- **于是缺口只剩这一格**：**"另一台 GT7868Q 上，同一个相对偏移（`cfg +0x10F / +0x111`）是不是同一个字段"**。
  这一问正是唯一的解药 —— 所以**优先级已从"值得问"变成"最先问"**。
- **另外附一个可顺手拿到的对照**：同一条回复里若能给 **cfg 里紧跟 X/Y 之后那两个 u16** 就更好了
  （本机 `+0x113 = 90`、`+0x115 = 120`；capsule 机型 `90 / 130`）——
  若你的机器上也是 `90`、而第二个数是别的值，就说明"第二个数"才是随机型变的触发阈值。
  **获取方式**（只要两个十进制数）：读 cfg body 里 `+0x113`、`+0x115` 两个 **u16BE**。
  ⚠️ **cfg body 的起点分两种封装，别混用**：
  **裸容器**（`orig_*.bin` 这类）从 **`+0x4C`** 起算；**UEFI 胶囊**（`.Cap`）多一个 `0x58` 字节 UEFI 头，从 **`+0xA4`** 起算。
  判据：裸容器 `+0x10F` 处应读出你自己的面板 X 点数（= 描述符 `LogicalMax` + 1）；若读出 `0xFFFF` / 全零，多半是起点选错了。

---

## 附：发出去之前自查

| 检查 | 状态 |
|---|---|
| 有没有夸大？ | 逐条对 `STATUS.md` / `HANDOVER.md` / `VIBRATION-FORENSICS-2.md` 核过。**2026-09-13 晚重核一次**：删掉了"文件缺 128 字节/是增量包"的说法（不成立），改掉了"incomplete"的框架（见 §4.1）|
| **两条载荷的分工，有没有当成结论？** | ✗ **已改成明说"未证"**（§4.3 / §8）。**不要在发出前把它写回去**——`GT7868Q` 只来自文件名，`TF100A` 只来自镜像内字符串，都不是读自芯片 |
| SHA256 对不对 | ✓ `0033d075fae88f0048544696c8941ed7dcca4269beaa84af76323ef5bbdcee72` |
| 结构数字对不对 | ✓ 两个声明长度与在场字节**精确相等**；向量表在 `0x19ABC`（`SP=0x200076C8`/`Reset=0x08005165`），`0x19A3C` 是载荷 B 的头 |
| 有没有泄漏隐私 | 无姓名/城市/序列号；机器型号是公开信息，且有诊断价值 |
| 有没有教人干危险的事 | §6 是**警告**，不是教程；明确写了"停手，别继续发 opcode" |
| 要的东西是否具体 | ✓ 五类，可执行 |
| **发出后要做的事** | 把这个 issue/邮件串的 URL 记进 `HANDOVER.md` §八.4，方便回访 |
