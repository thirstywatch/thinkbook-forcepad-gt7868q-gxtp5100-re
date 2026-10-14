# ThinkBook ForcePad Reverse-Engineering — Handbook Summary (English Edition)

> 🌐 **Languages**: [中文（主档案《软件逆向全书》）](../00-软件逆向全书-芯片固件主机控制.md) · **[English (this summary)](HANDBOOK-SUMMARY.en.md)** · [English front door](../../README.en.md) · [中文门面](../../README.md)
>
> **What this document is**: an **English condensation of the project's main archive**, which is a single Markdown file of **15,812 lines** (Parts 0–20 plus Appendices A–L).
> It carries **all top-level conclusions** at their published evidence grade, plus the late-round developments that changed earlier conclusions.
>
> **What it is not**: a translation of every section. For the full evidence chains, per-byte tables and round-by-round logs, read the Chinese main archive.
> **Status**: **2026-10-14** (updated during the second cleanup round; covers §19.0–§19.95 and Part 20).
>
> ⚠️ **Read this before citing anything**: this project is a **process archive**. Many conclusions were refuted by the project itself and are catalogued in the **Contradiction & Refutation Register** ([`docs/08-findings/00-矛盾与推翻登记表.md`](../08-findings/00-矛盾与推翻登记表.md)). Sections 11 below summarises the register's A-class and the most consequential B-class entries. **When this summary and the register disagree, the register wins.**

---

## Table of contents

1. [The machine and the module](#1-the-machine-and-the-module)
2. [The question, and the short answer](#2-the-question-and-the-short-answer)
3. [Silicon: the four components](#3-silicon-the-four-components)
4. [Firmware: packaging, scrambling, contents](#4-firmware-packaging-scrambling-contents)
5. [The host control path: three gates](#5-the-host-control-path-three-gates)
6. [I²C exposure: what the host can and cannot see](#6-i²c-exposure-what-the-host-can-and-cannot-see)
7. [The EC / ACPI line](#7-the-ec--acpi-line)
8. [Evidence grading: host → motor, link by link](#8-evidence-grading-host--motor-link-by-link)
9. [What demonstrably works, and what is dead](#9-what-demonstrably-works-and-what-is-dead)
10. [Late rounds: the developments that changed conclusions](#10-late-rounds-the-developments-that-changed-conclusions)
11. [Contradiction & Refutation Register — highlights](#11-contradiction--refutation-register--highlights)
12. [Safety: red lines, incidents, recovery](#12-safety-red-lines-incidents-recovery)
13. [Methodology and discipline (155 rules)](#13-methodology-and-discipline-155-rules)
14. [Repository map and reading order](#14-repository-map-and-reading-order)
15. [Compliance](#15-compliance)

---

## 1. The machine and the module

| Item | Value |
|---|---|
| Machine | Lenovo **ThinkBook 14 G6+ IMH**, model **21LD** |
| Platform | Intel **Meteor Lake-H** |
| BIOS | `NJCN67WW` (released 2025-12-17) |
| OS | Windows 11, build `10.0.26100` |
| Input device | **ForcePad** (pressure-sensitive touchpad) |

The touchpad is a **single module containing three chips plus one actuator**:

| Component | Role | Identity |
|---|---|---|
| **Goodix GT7868Q** (Windows instance name `GXTP5100`) | Touch controller; owns the HID host interface | `ACPI\GXTP5100\1` · `VID_27C6 / PID_01E9` · host-side I²C slave **`0x2C`** |
| **Taifang TF100A** | Pressure-sensing MCU (senses, decides, reports) | on-chip I²C1 slave **`0x2C`** · STM32F1-class ⇒ **Cortex-M3** |
| **Aiw AW86927FCR** | Haptic driver IC (drives the motor) | silkscreen **`CA4F`** · `HDP`/`HDN` = pin 7 / pin 5 · I²C address `0x5A`/`0x5B` (set by the `AD` pin) |
| **LRA** (linear resonant actuator) | Actuator | this machine's FRU `5T60S94326` |

> ⚠️ **Two physical boards are involved.** Besides the original 21LD module, the owner bought a **ThinkPad X9-15 Gen 1** module on 2026-09-29 (it does not fit; kept as a research sample). Same chip family, same I²C addresses, same outline — **different PID (`0x01EA`/`0x01EB`, not whitelisted ⇒ Code 10) and a much larger actuator (Nidec TapSense `NIDEC 55F0410`, 25×25×1.4 mm vs 7.5×14 mm)**. Any physical photo dated after 2026-09-29 must be attributed item by item. See [`docs/02-hardware/00-X9-15硬件信息归属与差异声明.md`](../02-hardware/00-X9-15硬件信息归属与差异声明.md).

---

## 2. The question, and the short answer

**Question**: make the ForcePad vibrate **while sliding a finger** — software only, no disassembly, no hardware modification.

**Short answer (as of 2026-10-14)**:

> There is **no host-side interface that triggers haptics**, and the device **does not listen** for host haptic commands. As of 2026-10-13 this is no longer only an inference: Microsoft's haptics specification **forbids** Manual Trigger inside the Intensity collection this machine exposes ⇒ the configuration is compliant.
> The only host-side thing that measurably changes haptics is **`0x09`** — and it only sets *how hard the device hits when the device itself decides to fire*.
> A secondary channel (`cfg_update`) does deliver configuration to the IC, but **it is session-scoped and never reaches flash** — although the 2026-10-13 checksum work **refuted the "hard wall"** and produced the project's first successful (`0x7F`) acceptance of a **legally rewritten** cfg.
> The only remaining **device-side** route with a byte-level target is a **2-byte patch to the TF100A firmware's vibration predicate** (needs SWD).
> The single never-tried host surface is a **raw Col02 OUTPUT report on an undeclared report ID** (Linux `hidraw` only).

---

## 3. Silicon: the four components

### 3.1 Goodix GT7868Q / GXTP5100 — touch controller

| Aspect | Finding |
|---|---|
| Core | **Turbo51** (8051-binary-compatible core; Goodix self-designed dual-core M/S) — established from official source constants, datasheet block diagram and IEEE papers, **independent of the firmware image** |
| The "dual-core 8051 + ARM Cortex-M4F" claim | 🔴 **void** — that ARM code belongs to **TF100A**, mis-attributed to GT7868Q. See §11 (register A-class logic) and Handbook §1.1.2 |
| Payloads in the image | **Payload A = GT7868Q side** (100,736 B, entropy 7.9966) · **Payload B = TF100A side** (56,480 B, ARM Thumb-2, 888 `MOVT`, entropy 6.6452) |
| HID interfaces | Four: `Col01` Mouse (`0x0001`) · `Col02` Touchpad / PTP (`0x000D`) · `Col03` MS Input Config (`0x000D`) · **`Col04` Vendor-Defined (`0xFF00`)** |
| Col04 descriptor | Usage Page `0xFF00`, **Report ID `0x0E`**, 64 B Output + 64 B Input — matches the Blueberry-Wiki record of the same vendor channel word for word |
| PCI/ACPI | `ACPI\GXTP5100\1`; host bus slave address `0x2C` (per DSDT `_CRS`) |

### 3.2 Taifang TF100A — pressure-sensing MCU

| Aspect | Finding |
|---|---|
| Architecture | **STM32F1-class = Cortex-M3** (not M4F). Ironclad: `FLASH_KEY1 = 0x45670123` plus a peripheral map matching STM32 line for line |
| Firmware state | ✅ **fully plaintext** — ~130 ARM functions, median 98 B, longest 1,958 B; disassembly self-consistency **99.81 %** |
| Self-reported identity | `TF100A_Test_FW` (2023-11-28) |
| Command dispatcher | **39 commands**: `0x80`×1 + `0xA0`×16 (all writes) + `0xA1`×22 (**all queries**) |
| Bus role | **I²C1 slave only** — `CR1.START` appears **0 times** in the whole image; it never initiates a master transfer |
| The byte path is **not wired up** | I²C1 slave initialisation is complete (`OAR1 = 0x58 ⇒ slave address 0x2C`, NVIC IRQ31/32 enabled) **but `ITBUFEN = 0`** ⇒ RXNE/TXE interrupts are never generated ⇒ the only code that reads `I2C1_DR` (the RXNE callback) never runs ⇒ the 128-byte receive ring can never fill. **Consistent with the image calling itself a `Test_FW`** |
| The vibration predicate | `|baseline − current| > 40`, where **`40` is the immediate `0x28`** of two Thumb instructions |

**The device-side patch route (the only one left)**: change `0x28` → `0x08` at **file offsets `0x1A54C` and `0x1A578`** (only 2 bytes) in the carrier `TB14P_GT7868Q_14030522_20240202.BIN` (load base `0x08005000` ↔ file `0x19ABC`). The predicate becomes sensitive ⇒ natural pressure fluctuation while sliding repeatedly crosses the threshold ⇒ the press chain is repeatedly triggered ⇒ **sliding vibration, entirely device-initiated, touching no host protocol**.

> 🔴 The patched BIN itself is **not** in the repository (it is a vendor-firmware derivative). Instead a reproducible generator ships: [`tools/firmware/make_tf100a_sens_patch.py`](../../tools/firmware/make_tf100a_sens_patch.py) — verified to produce **byte-for-byte identical** output against the real image.

### 3.3 Aiw AW86927FCR — haptic driver IC

| Aspect | Finding |
|---|---|
| Identification | Vendor datasheet + physical device: silkscreen `CA4F`, 20-pin package, `HDP`/`HDN` = pin 7 / pin 5 |
| Generation | ⚠️ **`AW86927FCR` (V0.9 / 2021-06)** differs from the `AW86927S*LR` family (V1.2). Three hardware criteria distinguish them; parameters must not be carried across generations |
| How it plays | Writing `0x09` (register `PLAYCFG4`) = GO is the industry-standard trigger; register space `0x00–0x80` |
| **Protocol mismatch with the host** | The IC's register space and the GT7868Q's private host framing (`[0E 20 …]` with addresses `0x1800`/`0x3800`/`0x96F8`/`0x4014`/`0x4160`) have **no overlap**, and there is **no evidence the touch IC forwards host-written `0x1800`/`0x3800` to AW86927** |
| Where is it? | ❌ **Not on the PCH SMBus** (a *strong* conclusion: the sweep had a positive control at `0x44`) · **Not declared by any device in the DSDT** · `0x5A` is **on none of the five host I²C buses** |
| Why the host can never reach it | ★ **It is powered off most of the time** — the haptic IC is powered up by GT7868Q only when playback is needed. The host can never catch that window ⇒ "why can't we find it" is upgraded from "we didn't scan it" to a **structural impossibility** |

### 3.4 LRA actuator

Small LRA, FRU `5T60S94326`, roughly 7.5×14 mm. ⚠️ Its resonance frequency was **never measured** on this machine — the 200 Hz quoted in the handbook comes from the X9-15's Nidec TapSense datasheet and was applied across models.

---

## 4. Firmware: packaging, scrambling, contents

### 4.1 Three layers of packaging

```
TB14P_*.BIN
└── ① UEFI capsule (Firmware Management Protocol / FMP)          ← outer layer
    └── ② Goodix container, starting at file offset 0x113C       ← inner layer
        ├── 256 B image header
        └── 13 sub-firmwares, tightly packed
```

★ A hard lesson (discipline 104): **a bare container and a UEFI capsule are two different packagings**; the cfg body's start offset differs by a constant header (here `0x58`). **Never carry offsets across packagings** — locate each one's origin first.

### 4.2 "Encrypted firmware" — resolved three times over

> 🔴 The firmware is **not** a cipher. It is **1024-byte periodic XOR positional scrambling**, **and it has been solved**.

| Item | Value |
|---|---|
| Confirmed-not-cipher | Three different models all refuted; zero-order entropy H0 ≈ 8.0 is a **non-specific** predicate (whitening / compression / scrambling / ciphertext / random all give ≈ 8.0) |
| Actual mechanism | `plain[x] = raw[x] ^ K[(x + 316) % 1024]` |
| K table | 1,024 B, **256 distinct values each appearing exactly 4 times, chi-square = 0.00** |
| Phase | **316**, identical across four independent firmwares (a single sample has no statistical power; four agreeing is the evidence) |
| How K was found | Recovered from the firmware's own zero-fill region — `0 ⊕ K = K`. **K is not vendor key material** and contains no device-unique information |
| Result of unscrambling | Zero-byte fraction `0.36 % → 15–25 %`, longest zero run `4 B → 5,450–8,190 B` |

K ships with the repository as [`data/reference/K_gt7868q.bin`](../../data/reference/K_gt7868q.bin).

### 4.3 Container families (do not mix them up)

| Dimension | **gtx3 / GTX8** (this machine's GT7868Q) | **BRLB** | **PNOR_G1** |
|---|---|---|---|
| Official struct | `gt7868q_firmware_image.h` · fwupd `Gtx8Hdr`/`Gtx8Img` | fwupd `BrlbHdr`/`BrlbImg` | `firmware_info.hw_pid[6]` |
| Header size | **256** | **512** | (a `hw_pid` string, not a header) |
| Length field | `u32` **big-endian** | `u32` little-endian | — |
| Checksum | `u16` **big-endian, byte-wise sum** | `u32` little-endian, `u16` LE word sum | — |
| Sub-firmware entry | `kind:u8` · `size:u32be` · `addr:u16be<<8` · `+1` | `kind:u8` · `size:u32le` · `addr:u32le` · `+1` | — |
| IC type enum | `Yellowstone` (`IC_TYPE = 3`), tag `YELSTO` | another branch | — |

★ **Discrimination recipe** (discipline 124): check header size (256 vs 512), then the length field endianness, then **try both checksum models**. Doing only one will mislead — the project lost time applying BRLB's model to a gtx3 container and concluding "the algorithm is mysterious".

### 4.4 Flash layout and the cfg record

| Address | Constant | Meaning |
|---|---|---|
| `0x000000`–`0x020000` | — | IC-internal flash address space (128 KB); the image covers up to `0x01FFFF` with gaps at `0x00E000–0x00FF00` and `0x018000–0x01E000` |
| **`0x19000`** | `CFG_FLASH_ADDR` | ★ **configuration as stored in flash** — persistent |
| **`0x96F8`** | `CFG_START_ADDR` | ★ **RAM/xdata staging for the configuration** — this is the one the interactive path writes |
| `0x4160` | `CMD_ADDR` | command register / 5-byte command channel |
| `0xC000` | `FLASH_BUFFER_ADDR` | RAM staging for one flash block (≤ 4096 B) |
| `0x5095` | `BL_STATE_ADDR` | bootloader state; `0xDD` = in upgrade mode |
| `0x5096` | `FLASH_RESULT_ADDR` | flash write result; `0xAA` = success |

> ★ **`0x96F8` vs `0x19000` is the "RAM staging vs flash" dividing line** — and the root of symptom B12.

**`type` in the sub-firmware table is not "program/config"** — it is a **bit index** into the host-supplied `firmware_flag` (`if (!(firmware_flag & (0x01 << sub_fw_type))) continue;`). This machine uses `firmware_flag = 0x0C`, i.e. types `0x02` and `0x03` only ⇒ the single `type 0x01` block is **skipped entirely**, so no address overlap occurs.

**The cfg record**: true length **1084 B** = **1024 B body + 60 B tail**, and it appears **four times** inside the outer container (byte-for-byte identical across copies). Body structure (from disassembly plus cross-model alignment): four node/channel mapping tables (ascending 29-item at `+0x037`, ascending 19-item at `+0x064`, unordered 32-item at `+0x09A`, unordered 19-item at `+0x0D3`), a `u16BE` array at `+0x180`, a `u16LE` array at `+0x24F`, more at `+0x2B4`, scattered parameters, `ff` padding.

---

## 5. The host control path: three gates

### Gate 1 — HID descriptor layer ❌ closed

| Requirement | This machine |
|---|---|
| Microsoft requires `Col02` (PTP top-level) to carry haptic output reports if the host is to trigger haptics | **`OutputReportByteLength = 0`** ⇒ the host is **physically incapable** of sending a haptic output report |
| `0x0E/0x01` SHC as a sub-collection of the PTP top-level | ✅ compliant (`lc=6` under `0x0D/0x05`) |
| `0x0E/0x21` **Manual Trigger** (Output) | ❌ absent |
| `0x0E/0x10` Waveform List / `0x0E/0x11` Duration List | ❌ absent |
| `0x0E/0x23` Intensity | ✅ present, but as a **device-initiated Feature**, with `log=[100..1]` (the spec wants `min=0, max>=4`) ⇒ non-compliant |
| `0x0D/0xB0` Button Press Threshold | ❌ absent (required for a haptic touchpad) |

⇒ The device is a **pure device-initiated haptic touchpad**: the vendor implemented the *device-initiated* half of the spec and skipped the *host-initiated* half entirely.

### Gate 2 — driver layer 🔒 hard block

`hidi2c.sys` exclusively owns the SPB (Simple Peripheral Bus) connection. Microsoft documents that **only one component may hold a peripheral's connection at a time**. Empirically:

- `GET_FEATURE` / `SET_FEATURE` fail at this layer;
- all four collections have **empty** `UpperFilters`/`LowerFilters` ⇒ only inbox `hidclass` + `hidi2c` are on the chain ⇒ there is no third-party filter to piggyback on;
- registering a **parallel SPB client driver** is excluded by the same Microsoft rule.

### Gate 3 — device firmware layer ❌ closed

There is **no "trigger" command the host can invoke**. Payload A (the GT7868Q side) contains **zero haptic code**; none of TF100A's 39 commands reaches the motor; driving the AW86927 directly is unreachable (§3.3).

### ★ The counter-effect that keeps the door ajar

**High-frequency reads of `Col04` suppress *all* haptic feedback (press and release).**
Measured: during an 89.7-second full dump with the touchpad held down the whole time, **no vibration occurred during the dump**; it resumed when reading stopped.

⇒ Haptic triggering lives at the **firmware ↔ host I²C communication** level, **not** at the memory-data level. This is precisely why writing memory never works — the firmware simply does not read that memory.

> 🔴 An early wording — "suppresses only *press* haptics, leaves *release* unaffected" — **is wrong** (register A6). Release-appearing vibration is just *recovery after reading stops*.

---

## 6. I²C exposure: what the host can and cannot see

| Fact | Finding |
|---|---|
| ACPI-declared controllers | **16** |
| Controllers Windows actually exposes | **3** |
| The touchpad's own I²C link | Declared via SPB resources; **not reachable from user mode**, and its single kernel slot is already taken by `hidi2c` |
| PCH SMBus | Tested with a **positive control** (`0x44`) ⇒ a **strong** negative: AW86927 is not there |
| Sweep of all five host buses | ❌ **5/5 closed** — either swept clean, or structurally unreachable |
| `0x40005400` inside the TF100A image | 🔴 **It is I2C1** (register **B18**): `CR2(+4)`, `DR(+0x10)`, `SR1(+0x14)`, `SR2(+0x18)` are all genuinely dereferenced, and `0800894C` / `08008978` are **real ISR entry points** (`push {r7,lr}`). The earlier "GPIO pin helper" reading was an artefact of mixing **file offsets** with **runtime addresses** (discipline 117) |

---

## 7. The EC / ACPI line

| Aspect | Finding |
|---|---|
| Zero-privilege ACPI dump | A reproducible method (ACPICA `iasl`) obtains the **complete** ACPI set with no special privileges — reusable |
| Haptic keywords in ACPI | **0 hits** across 762 KB of fully decompiled ACPI |
| `TPAD` subtree mechanism | `TPID` five-vendor table; `IICBADR0`'s real identity resolved |
| EC RAM read | ✅ Achievable via PawnIO `LpcACPIEC` (256 B read demonstrated) — **read-only guarantee verified**: the write opcode `0x81` appears **0 times** |
| EC differential experiment | **No haptic evidence** — key registers static across 6 phases × 6 rounds |
| Re-admission of the EC | §19.29 re-admitted the EC as a candidate after realising §19.25.4 had excluded it by a **boundary error** (it is not *inside the module*, so a "candidates inside the module" filter silently dropped it). Conclusion: ⚠️ **"no evidence"**, not "excluded" |

---

## 8. Evidence grading: host → motor, link by link

The handbook grades **every** conclusion. Unmarked statements are background information only.

| Grade | Meaning |
|---|---|
| ✅ **confirmed** | on-machine measurement or a primary specification |
| ⚠️ **semi-confirmed** | measured, but one key link missing, or only indirect evidence |
| ⚠️ **inferred** | reached by elimination or circumstantial evidence |
| ❌ **no evidence** | no material at all |

| Link | Grade | What is missing |
|---|---|---|
| host → GT7868Q | ✅ confirmed | — |
| GT7868Q → TF100A | ⚠️ semi-confirmed | I²C1 vs USART1 unproven; `PA3`'s peer unproven |
| inside TF100A (sense → detect → report) | ✅ confirmed (for this image) | cannot verify this is the version the device runs |
| who decides to vibrate | ⚠️ inferred | by elimination |
| → AW86927 | ❌ **no evidence** | who is its I²C master / which bus / which address — all unknown |
| AW86927 → motor | ⚠️ semi-confirmed | motor model not directly confirmed |
| press vibration is host-independent | ✅ confirmed | the EC is "no evidence", not "excluded" |

---

## 9. What demonstrably works, and what is dead

| Route | Status |
|---|---|
| HID standard trigger | ❌ no Manual Trigger (`Col02 Out = 0`) |
| Col04 raw memory writes | ❌ firmware does not consume them (scope: **direct writes to the 32 KB memory** only) |
| Col04 vendor command set | ❌ none of the 39 commands reaches the motor |
| **★ HID Feature `0x09`** (Col02 RID 9, Usage Page `0x0E` / Usage `0x23` Intensity) | ✅ **works** — `HidD_SetFeature(h, {0x09, v}, 2)`; handle opened `GENERIC_WRITE` only (**no admin, no device disabling**); write `0` ⇒ haptic feedback gone, write `100` ⇒ full. ⚠️ It only decides **how hard the device hits when *it* fires**; it **cannot trigger**, and it is **not persisted** (register **B14**) |
| **★ `cfg_update` channel** (`0x80` → `0x82` → write `0x96F8` → `0x83` → read → `0x7D`) | 🟢 the IC **accepts** writes (`7E 00 02`) 🔴 but they are **session-scoped and never reach flash** (register **B12**); no perceptible parameter effect was ever proven |
| Direct I²C to AW86927 | ❌ unreachable — the IC is powered off except during playback |
| EC participation | ✅ measured: none (at this probe's sensitivity) |
| **TF100A firmware patch (40 → 8)** | ✅ the only remaining route with a byte-level target; patched image generated, awaiting flashing |

---

## 10. Late rounds: the developments that changed conclusions

The main archive logs every round as §19.x. These are the ones that **overturned** earlier conclusions.

### §19.39 — round 11: X/Y semantics settled by cross-generation "known answers"
Rather than hunting a second identical machine, the project used **five real phone cfg samples** whose panel resolutions are publicly documented. Three of them hit **their own panel's true resolution** as **adjacent `u16` pairs** ⇒ the rule "**X/Y in cfg = an adjacent `u16` pair whose value is the coordinate point count (= input max + 1)**" gained independent cross-generation support.
⚠️ But the phone side is `u16LE` while this machine is `u16BE`, and one sample inserts 3 extra bytes ⇒ **comparing offsets across generations still manufactures phantom fields**.
🔴 Two self-corrections in the same round: the capsule's cfg body starts at `0xA4` (not the bare container's `0x4C` — the `.Cap` carries a `0x58` B UEFI header), and the claimed `[TAG][LEN]` frame chain in the cfg body was **killed by a resolution test** (random data can chain 4–5 frames; shuffled data 5; real data 8).

### §19.40 — round 13 (2026-10-05): the cfg delivery channel opened
First time the project successfully delivered a configuration over the vendor-private `cfg_update` channel. **But** the accompanying `+0x115` "intensity knob" observation was **downgraded the same day** after follow-up tests at `0` and `20` contradicted it. Two disciplines resulted: **108** ("channel valid" ≠ "parameter valid") and **109** (subjective feel cannot alone support a field name).

### §19.42b — 2026-10-08: four experiments that rewrote the foundations
| Experiment | Result |
|---|---|
| `+0x10F` closed loop | Change `cfg+0x10F` from 4150 → 4151; the HID descriptor's X `LogicalMax` **does not move** ⇒ 🔴 **the name "X point count" is withdrawn**. "Two numbers being equal" only suggests a hypothesis (discipline **110**) |
| `0x96F8` four-phase sampling | `0x96F8` is **time-multiplexed RAM**: idle = sampling/baseline buffer; during a `cfg_update` session = cfg staging; after `0x7D` it is overwritten again. ⇒ "only the first 32 B are readable" was a **phase** problem, not a tool defect (discipline **111**) |
| Full 1084 B dump at phase T2 | sha256 identical to what was sent, **1084/1084, zero differences** ⇒ **the IC passes cfg through untouched** (a valuable negative result) |
| **Persistence test** | 🔴 **Write → restart device → read back: the value reverted.** ⇒ **cfg writes are session-scoped only**; `7E 00 02` does **not** mean "written to flash" (discipline **112**). This **overturns round 13's foundation** (register **B12**) — and, because cfg never persisted, it also removes the material basis for every felt difference attributed to `+0x115` |
| `0x09` identified | **The one host-side byte that changes haptic behaviour** (register **B14**) |

### §19.43 — 2026-10-10: I²C1 attribution and the official flashing structure
- 🔴 **`0x40005400` is I2C1** — three lines of §2.5 voided (register **B18**). Root cause: **coordinate-system mixing** (runtime address `0x0800884C` vs file offset `0x08800`) ⇒ discipline **117**.
- ★★ **Three unrelated official firmware updaters share one five-step structure**: enter programming mode → erase → write fixed blocks → **read back / verify** → **a separate commit command + reset**. The project's own sequence skipped steps 4 and 5 ⇒ this became the B12 lead, and eventually identified `0E 12` as the only flush primitive (register **B23**).
- TF100A's I²C1 byte-receive path is **not wired up** in this image (`ITBUFEN = 0`, a `Test_FW` trait — **not** a device trait) (register **B20**).
- Method imports: `cpu_rec`'s **positive/negative/shuffled** control methodology (random data makes `6502` a false-positive attractor); `elgato-cam-link`'s documentation format; Goodix's own fingerprint tool's `empty_buffer()` drain technique.

### §19.44 — 2026-10-10 (cont.): `0E 12` address arithmetic fixed offline
The exact bytes to send were computed **purely offline**, so that execution becomes "send as listed" without any read-back dependency. Also: **idempotency redefined** — a single block write is **not** idempotent even with identical data, because a flash write includes an erase whose granularity may exceed the write length (discipline **132**). One operational incident was recorded.

### §19.45 — 2026-10-11: the BIOS auto-reflash safety net
After the 2026-10-10 real-machine event degraded the touchpad, a **full machine restart** caused the BIOS to reflash the touchpad firmware and restore normal function. ⇒ A **safety net exists**, though its trigger conditions are unknown and it is **not a 100 % guarantee**. A **device recovery path table (R1–R7)** was established in [`docs/09-safety/RECOVERY.md`](../09-safety/RECOVERY.md), including the rule that **the official update sequence must never be partially executed** (discipline **130**).

### §19.46 — 2026-10-11: root cause of `0xBB` — the project's own bug
The persistent `0xBB` (the official code only defines `0xAA`) was traced to **`gxmem.write()` silently truncating**: the send function sent only the first 65 bytes, so a 4096-byte write produced a 55-byte payload while the header declared 4096 ⇒ checksum mismatch ⇒ `0xBB`. The official `GTx5Device::Write` splits into 75 packets; the project did not. **Fixed**, and the contamination surface was audited call site by call site (disciplines **133**, **134**).

### §19.47 — 2026-10-11: `0x09` reproduced; a label downgraded
`0x09` was reproduced end-to-end with a rebuilt tool (`tools/hid/hid_feature.py`, no external dependencies) — 7/7 `SetFeature` calls accepted. A self-inflicted methodology failure was recorded: the first sweep **omitted the `0` level** (discipline **114**), which had to be re-run. Also: the `0x1800` / `0x3800` = "haptic parameter region" label was **downgraded to doubtful** — both regions read all-`00` in healthy and degraded snapshots, and the one non-zero reading varied over time ⇒ it looks like a **live calibration/temporary region** (register **B26**).

### §19.48 — 2026-10-12: the cleanup round
Backfilled the missing **§19.42b** journal entry for 2026-10-08; corrected six classes of stale statements across the handbook; added a **consolidated index of disciplines 110–137**; and **removed a duplicated legacy draft** (lines 356–1030 of the main archive, an obsolete copy of Part 1) to `docs/99-archived/legacy-first-part-fragment.md`.

### §19.52–§19.60 — 2026-10-13 (six rounds in a single day)
The most productive day of the project: ① **AW86927 host reachability closed** — under a real Linux Live the I²C-HID client was properly unbound and `0x5A/0x5B` on `i2c-0`/`i2c-1` were **all NACK**; the `aw86927` kernel driver carries only an `of:` alias ⇒ it **can never probe on x86 ACPI**; ② the official **`gtx8`** and **`gtx8_driver_linux`** sources arrived ⇒ **two coexisting address sets**, the cfg **two write paths** (session RAM vs `0x1E000` flash), and decisively the **complete cfg checksum algorithm** (Yellowstone: `sum(data[0..n-3]) == BE16(last 2 B)`), which **refuted the "hard wall"** and mechanically reproduced this machine's own degradation (it had edited `bag_num` — not a version byte — and ran off the end of the bag chain); ③ the official reply-code table gave `7E 00 02` its real name — **`TS_CFG_REPLY_CHKSUM_ERR`, a failure**, not "applied"; ④ a **real-machine experiment produced the project's first-ever `0x7F` (`TS_CMD_CFG_OK`)** — a legally rewritten cfg accepted by the IC, proven by a **2-byte single-variable** contrast against the checksum-error case; ⑤ the official cfg bin header turned out to carry the long-sought **`reg_info` address table** (14 entries) matching this machine's behaviourally derived `command=0x4160` / `cfg_addr=0x96F8`, while the live IC reports ASCII **`YELSTO`** ⇒ family = **Yellowstone** (and `sensor_id = 4`, not the `0` the file names suggested); ⑥ Microsoft's haptics specification supplied the **normative** reason this machine exposes Intensity but no Manual Trigger (the spec *forbids* it inside that collection) plus the official waveform table (`Collide 0x1012` is the "reaching an edge/limit" pulse), and resolved `7868Q` vs `7869` (`7869` is the IC's 4-digit number field; the firmware versions are identical).
Disciplines added: **146** (a feature working on some platform ≠ the project goal being met), **147** (`modinfo`'s matching table: a driver loading ≠ the device being managed by it), **148** (one chip may have several coexisting address sets — never extrapolate), **149** (exhaust the vendor sources before claiming an unknowable check), **150** (give every failure the vendor's name before writing it into a conclusion), **151** (look beyond the vendor organisation for tools derived from vendor source).

### §19.61–§19.64 — 2026-10-14 (an incident, the Windows command table, and round N4)
① An external EC-decryption proposal was evaluated: every citation accurate, but the **priorities inverted** ⇒ discipline **152**. ② **Incident** — a blind scan of `0x4160`'s command codes (it hit `0x10/0x11/0x12`, which may share semantics with patch-update/flash/reset) **disabled the touchpad**; the IC's core state, version block and `bag_num` were unchanged and flash was never touched; recovery used the official exit sequence ⇒ new red lines **153** (never blind-scan `0x4160`) and **154** (run a **command-space semantic-isomorphism check** before any write-class brute force). ③ The **official Windows command table was recovered from `tpupdate_driver.dll`** (`{address, width, expected value}` triples plus a command table), later corrected from "three-way dispatch" to **five branches** (`[0x18B00] ∈ 1..5`; the 2024 build adds three families using 32-bit register space `0x1001E`) ⇒ discipline **155** (`VirtualSize` vs `RawSize` when dumping PE sections). ④ The vendor's own frame-building code confirmed the 5-byte command frame `{cmd,0,0,0,cmd}` byte for byte. ⑤ **Delivery of the "semantically known region"** that discipline 154 demanded: for this family's `0x4160` only `0x33/0x34/0x01/0x00` are legal — the other 252 codes must never be scanned. ⑥ **The Col02 check closed**: the project has only ever sent `SET_FEATURE`; it has **never sent a Col02 OUTPUT report** — Windows blocks those because `out=0` (`err=87`), **Linux `hidraw` does not** ⇒ the single injection surface never tried. ⑦ Firmware-writing routes assessed: **GT7868Q ❌** (no update code in the container + one-way door), **TF100A ⚠️** (plaintext ARM, needs SWD), **BIOS ❌**.

---

## 11. Contradiction & Refutation Register — highlights

The register ([`docs/08-findings/00-矛盾与推翻登记表.md`](../08-findings/00-矛盾与推翻登记表.md)) has four classes. **Class A** = derived/entry documents still stating refuted conclusions; **class B** = conclusion right but *basis* wrong (the easiest class to miss); **class C** = entire old lines voided; **class D** = auto-synced.

### Class A — read these before trusting an entry document

| # | Refuted | Now |
|---|---|---|
| **A1** | "The descriptor comes from device firmware; the host cannot change it" | 🔴 **refuted**: a kernel driver's `report_fixup` **can** rewrite the host-side copy — demonstrated for this machine's PID `0x01E9`. ⚠️ **But the verdict is unchanged**: the device side has no receiving branch, so "Windows thinks it can control, the device hears nothing" |
| **A2** | Firmware is a "128-bit block cipher + ECB" | 🔴 **refuted**: 1024-byte periodic XOR positional scrambling, **solved** |
| **A3** | Red lines are a "flashing **triple**" | 🔴 there are **four** (`0E 13` was missing); and `0E 12` is often mistaken for "restart" — exactly backwards (`0E 12` writes flash; `0E 13` resets) |
| **A4** | "PWM `ARR=700/CCR=96` and `ARR=1999/CCR=119` are LRA drive parameters" | 🔴 must not be read that way any more |
| **A5** | "Find the firmware decryption key" | 🔴 **the premise does not hold** (no key exists) |
| **A6** | "High-frequency Col04 reads suppress only *press* haptics" | 🔴 **wrong wording**: all haptic feedback (press and release) is suppressed |
| **A7** | "The `ty2/goodix-gt7868q-linux-driver` repo is only 1,663 B ⇒ useless" | 🔴 **misjudged twice** — it does descriptor repair, which is exactly what A1 is about |
| **A8** | "Huawei's slide-follow vibration" | 🔴 does not exist (the target statement is outdated) |

### Class B — the most consequential entries

| # | Conclusion | Status |
|---|---|---|
| **B7** | "Write injection: systematically all ineffective" | 🔴 **must be narrowed to "direct writes to memory only"** — the dedicated cfg channel is outside that scope |
| **B9** | "The first effective knob has been found" | 🔴 **downgraded**: "the write was accepted" is not "a parameter took effect" |
| **B10** | "`+0x115 = 0` feels the same as 120" | 🔴 **two rounds contradict each other**; the `0` level remains pending a blinded A/B test. As of 2026-10-08 the whole field is **doubtful** |
| **B11** | "`cfg+0x10F` = X point count (4150)" | 🔴 **name withdrawn** — changing it does not move the HID descriptor; the equality was coincidence |
| **B12** | "cfg writes reach flash and survive reboot" | 🔴 **completely refuted**: **session-scoped only**; on session end the IC reloads from flash |
| **B13** | "`nwkyz/goodhaptic` is a different device ⇒ its conclusions do not transfer" | 🔴 **must be resolved item by item: 9 of 10 items are identical** |
| **B14** | "The host cannot change this board's haptic behaviour" | 🔴 **refuted**: `0x09` is a working haptic switch, empirically verified |
| **B16** | "Nobody in the open-source world has implemented host-triggered haptics" | 🔴 **partially refuted**: one project did — at the cost of "not being the host" |
| **B18** | `0x40005400` is I2C1 | ✅ resolved a long-standing internal inconsistency in the handbook |
| **B23** | "B12 breakthrough: the official flush primitive **is `0E 12`**" | ✅ it had been sitting in the project's own **red-line list** all along |
| **B25** | "Root cause: `gxmem.write()` silently truncates" | ✅ closed the `0xBB` mystery |
| **B26** | "`0x1800`/`0x3800` = haptic parameter region" | 🔴 **downgraded to doubtful** |
| **B27** | "The live `0x96F8` region can be diffed against saved historical cfg records" | 🔴 **methodologically invalid** (it is a time-multiplexed window) |

**2026-10-13 / 10-14 additions (`B33`–`B45`)**: `B33` AW86927 reachability closed (the old "5/5" denominator was Windows-only) · `B34`/`B35` the official gtx8 sources ⇒ two address sets, cfg's two write paths, the family register and command tables · **`B36` the cfg checksum algorithm fully solved ⇒ the "hard wall" refuted** · `B37` `7E 00 02` officially named (`CHKSUM_ERR`), giving all three historical cfg failures their names · **`B38` first-ever `0x7F` on real hardware** (a legal rewrite accepted) · `B39` the official `reg_info` address table plus a full read-only verification on this machine (`YELSTO`, `sensor_id = 4`) · `B40` mainline-driver cross-confirmation + the Microsoft spec ⇒ the missing Manual Trigger is a **compliant configuration** · `B41` the `0x4160` incident ⇒ disciplines 153/154 · `B42` the "brute force is viable" judgement revised (only the E surface remains safely scannable) · `B43` three-way dispatch → five branches (plus the C1/C2/C3 corrections) · `B44` only `SET_FEATURE` was ever sent; Col02's undeclared-RID OUTPUT is untried · `B45` firmware-writing routes: GT7868Q ❌ / TF100A ⚠️ (SWD) / BIOS ❌.

---

## 12. Safety: red lines, incidents, recovery

**This project has had three device-level incidents** plus one partially-degrading event: touchpad input freeze (2026-09-14, twice), the IC being wedged by high-frequency Col04 polling (2026-09-13), a partial degradation on 2026-10-10 while experimenting with the official update sequence, and — on **2026-10-14** — a **blind command-code scan of `0x4160` that disabled the touchpad** (IC core state intact; restored with the official exit sequence).

### Red lines (permanent; these outrank "making progress")

```yaml
Flashing commands — never touch any of them:
  00 10   switch to patch    ← enter programming mode
  00 11   start update       ← enter programming mode
  0E 12   load flash         ← ★ actually writes flash; the most dangerous
  0E 13   restart            ← reset

Other:
  - no bulk polling of Col04
  - a single transaction ≤ 32 B, interval ≥ 500 ms
  - 0xA2 is a reply class; never send it
  - do not touch bcdedit without explicit consent
  - read-only first; write-class commands last
  - 🆕 never blind-scan unknown command codes on `0x4160` (discipline 153)
  - 🆕 before any "write to device" brute-force scan, run a command-space semantic-isomorphism check (discipline 154)
```

### Recovery (added 2026-10-11)

[`docs/09-safety/RECOVERY.md`](../09-safety/RECOVERY.md) holds the **device recovery path table R1–R7**, the most important being:

> **R1 — the official update sequence must never be partially executed. Either send the whole sequence as listed, or send nothing at all.** (Discipline **130**; paid for with a real degradation on 2026-10-10.)

The known safety net: a **full machine restart** may cause the BIOS to reflash the touchpad firmware. Probability high, but **not 100 %**, and the trigger conditions are unknown.

---

## 13. Methodology and discipline (155 rules)

The handbook maintains a running list of disciplines. Key ones, grouped:

**On naming and evidence**
- **108** — "the channel is valid" ≠ "the parameter is valid"; an accepted write only proves the firmware stored it.
- **109** — subjective feel ("stronger"/"softer") cannot alone support a field name: it requires reproducibility, a falsifiable extreme level, and monotonicity. Missing one ⇒ "doubtful".
- **110** — "two numbers are equal" may raise a hypothesis, never a name.
- **114** — when testing a switch-like field, **always include the `0` (off) level**; a null result from middle levels alone is invalid.
- **137** — attaching a functional label to an address region requires at least one **live non-zero datum** or a **behavioural linkage**.

**On addresses and phases**
- **111** — the same address may map to different physical storage in different protocol phases; sample in **both** idle and session states.
- **112** — any claim of "written to persistent storage" must survive **at least one power cycle**; a result code only proves the transfer was accepted.
- **117** — **file offset** and **runtime address** are two coordinate systems; never mix them in one predicate.
- **127** — "an address is readable" ≠ "what you read is that address's static content" (prove repeatability: the same address read ≥ 5 times byte-identically).
- **136** — content of a **time-multiplexed / dynamic window** must never be diffed against a historical snapshot.

**On structure and analysis**
- **104** — a bare container and a UEFI capsule are different packagings; locate each one's origin before comparing offsets.
- **105** — any "chain/alignment" parse must first report **random** and **shuffled** baselines; if the real signal does not exceed the baseline by +2–3, judge it invalid.
- **124** — do not iterate with self-invented checksum models before finding the authoritative format definition (the project mistook "the algorithm is mysterious" for "wrong family").
- **133** — for any chunked transport, **assert that the declared length equals the length actually sent**.
- **134** — after finding a low-level bug, the contamination surface must be audited **call site by call site**.
- **130** — the official update sequence must not be partially executed.

The full index of rules 110–145 is in Handbook **§19.48.3**; rules **146–155** live in §19.53.7 / §19.55.7 / §19.57.9 / §19.61.7 / §19.64.6 and in the [incident document](../08-findings/2026-10-14-事故-0x4160命令码扫描致触控板失效.md) §5; rules 1–109 are in the handbook's earlier discipline sections, with a curated subset in [`method/99-pitfalls.md`](../../method/99-pitfalls.md).

---

## 14. Repository map and reading order

| Who you are | Read |
|---|---|
| Just want the conclusions | [`README.md`](../../README.md) (Chinese) / [`README.en.md`](../../README.en.md) (English) → this summary |
| Want the methodology | [`method/METHOD.md`](../../method/METHOD.md) (Chinese; the 155-rule discipline set lives in the handbook) |
| Want to reproduce | [`reproduce/REPRODUCE.md`](../../reproduce/REPRODUCE.md) → [`reproduce/ENVIRONMENT.md`](../../reproduce/ENVIRONMENT.md) → [`reproduce/DATA-INVENTORY.md`](../../reproduce/DATA-INVENTORY.md) |
| Touching real hardware | [`docs/09-safety/RED-LINES.md`](../09-safety/RED-LINES.md) **then** [`docs/09-safety/RECOVERY.md`](../09-safety/RECOVERY.md) |
| Reading older documents | **[`docs/08-findings/00-矛盾与推翻登记表.md`](../08-findings/00-矛盾与推翻登记表.md)** — cross-check before believing |
| The full archive | [`docs/00-软件逆向全书-芯片固件主机控制.md`](../00-软件逆向全书-芯片固件主机控制.md) (Chinese, **15,812 lines**: Parts 0–20 + Appendices A–L) |

**Two quick-reference documents** (both Chinese):
- [`method/09-memory-map.md`](../../method/09-memory-map.md) — appendices A–L: every address and constant.
- [`method/10-semantics.md`](../../method/10-semantics.md) — the four command tables layered, TF100A's 39 commands, cfg `[LEN][TAG]` frame order and TAG dictionary.

---

## 15. Compliance

- This document, like the rest of the repository, contains only **methodology, analysis and conclusions**. It contains **no vendor firmware binaries, no vendor tools, and no copyrighted datasheets**.
- How to obtain firmware and tools is documented in [`reproduce/DATA-INVENTORY.md`](../../reproduce/DATA-INVENTORY.md); download them from official channels yourself.
- Third-party tools referenced (RWEverything, PawnIO, ACPICA `iasl`, …) are **not** redistributed; only acquisition links and usage notes are retained.
- **Official vendor sources are redistributed under a graded licence policy (since 2026-10-14)**: 37 files whose licences are provable from the files themselves (the GPL-2.0 text ships as `COPYING.GPL-2.0.txt`) (Goodix **Apache-2.0**, official Linux driver and mainline patches **GPL-2.0 / GPL-2.0-only**) are committed with their copyright headers; three vendor cfg bins and two Microsoft copyrighted documents remain **local-only**. See [`poc/gdix-official-missing/LICENSES.md`](../../poc/gdix-official-missing/LICENSES.md) and [`vendor-refs/links.md`](../../vendor-refs/links.md) §XII.
- **Locally generated `.bin` evidence is now committed too** (19 cfg records / IC state samples) so that the B36 / B38 checksum conclusions can be reproduced from the repository alone. See [`NOTICE.md`](../../NOTICE.md) §2.2.
- **Operating a device according to these documents risks bricking it.** Flashing-class operations should first be validated on a spare board.
- All experiments described were performed on the author's own hardware.
