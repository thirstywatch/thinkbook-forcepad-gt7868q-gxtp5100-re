# Goodix GT7868Q / GXTP5100 Touchpad Host-Control Reverse-Engineering Archive

> 🌐 **Languages**: **English (this file)** · [中文（主）](README.md) · [Handbook summary (EN)](docs/en/HANDBOOK-SUMMARY.en.md) · [全书（中文主档案）](docs/00-软件逆向全书-芯片固件主机控制.md)

> **Subject**: the ForcePad (pressure-sensitive touchpad) on a **Lenovo ThinkBook 14 G6+ IMH (21LD)** — Goodix **GT7868Q** touch controller (Windows instance name `GXTP5100`) + Taifang **TF100A** pressure-sensing MCU + Aiw **AW86927** haptic driver IC.

> **One-liner**: *Making the ForcePad produce haptic feedback while **sliding**, using software only — plus why that road has been blocked for a long time, and what the only remaining route is.*
>
> **As of 2026-10-14**: the **only** host-side interface that measurably changes haptic behaviour is still **`0x09`** (Col02 RID 9 / Usage `0x0E/0x23` Intensity; write `0` = mute, `100` = full — empirically verified). "Trigger haptics on demand" is still impossible — on 2026-10-13 the **Microsoft haptics specification** provided a **normative** explanation of why this machine exposes Intensity but no `0x0E/0x21 Manual Trigger` (the spec *forbids* Manual Trigger inside that collection ⇒ **not a defect, not a search failure**; register **B40**).<br>🔴🔴 **The same day refuted the 2026-10-12 "cfg hard wall" verdict**: the official `gtx8` sources give a **complete, reproducible cfg checksum algorithm**, and the project obtained **`0x7F` (`TS_CMD_CFG_OK`) for the first time — a legally rewritten cfg was accepted by the IC** (register **B36 / B38**).<br>⚠️ **Still open**: `0x09` only sets "how hard the device hits when *it* fires"; the **one injection surface never tried** is **raw OUTPUT reports on Col02's undeclared report IDs** (Windows blocks it, **Linux `hidraw` does not** — Handbook §19.63).

This repository is a **complete reverse-engineering process archive**: not just conclusions, but also *how each step was done, which tools were used, what was obtained, which pitfalls were hit, and which conclusions were later refuted by the project itself*. The goal is that someone who never participated in the project can independently reproduce the entire analysis from these documents.

> ### ⚠️ On accuracy
>
> **This project was largely carried out by AI; accuracy cannot be fully guaranteed.** Verify every conclusion before relying on it —
> especially items marked *inferred / semi-confirmed*, and places in §19 where the project refuted itself.
> **If you find a mistake, please point it out directly** (Issue / PR both fine). This repository is, by design, a "process archive with the error scene left in".

---

## 1. What this project is

| Item | Value |
|---|---|
| **Goal** | Make this laptop's ForcePad vibrate while **sliding** a finger (factory behaviour: it only vibrates on *press*) |
| **Constraint** | **Software only** — no disassembly, no hardware modification, no external modules (hardware-bypass ideas are recorded for reference only) |
| **Target machine** | ThinkBook 14 G6+ IMH (model 21LD) · Intel Meteor Lake-H · BIOS `NJCN67WW` · Windows 11 26100 |
| **Time span** | 2026-09-13 → **2026-10-14** (~**4.5 weeks**, **26+ rounds**) |
| **Size** (as of **2026-10-14**) | **1820 committed files / 44.15 MiB** (1825 in the working tree, of which 5 stay local-only): **256 md** + **887 scripts** (Python 751 / PowerShell 62) + 62 ACPI-related exports + **508 experiment logs**; the main archive *Reverse-Engineering Handbook* is **15,812 lines / ~1.0 MB** (§19.0–§19.77 + Part 20 + the §20.13 follow-up, see §20.0) |
| **⚠️ Nature of the archive** | **A process archive, not a self-consistent document** — early conclusions were refuted **20+ times** (register classes A/B/C/D; class B has reached **B1–B59**). Before reading any older document you **must** check the [Contradiction & Refutation Register](docs/08-findings/00-矛盾与推翻登记表.md) |
| **Source workdirs** | **10** (`lab__` `old__` `gxt__` `surf__` `sfw__` `probe__` `root__` `early__` `hidp__` `ca4f__`) — see `docs/REPO-STRUCTURE.md` §4.3 |

### Three chips + one actuator inside the module

| Component | Role | Identity |
|---|---|---|
| **Goodix GT7868Q / GXTP5100** | Touch controller · HID host interface | `ACPI\GXTP5100\1` · `VID_27C6/PID_01E9` · host-side I²C slave address **`0x2C`** |
| **Taifang TF100A** | Pressure-sensing MCU (detect + report) | on-chip I²C1 slave **`0x2C`** · STM32F1-class = **Cortex-M3** (not M4F) |
| **Aiw AW86927FCR** | Haptic driver IC | silkscreen **`CA4F`** · `HDP`/`HDN` = pin 7 / pin 5 · I²C address `0x5A`/`0x5B` |
| **LRA linear motor** | Actuator | this machine's FRU `5T60S94326` |

---

## 2. Final conclusions (read this first)

### ★ Core conclusion

> **There is no host-side interface that "triggers" haptics, and the device does not listen to host haptic commands.**

**Empirical support (descriptor layer, not Linux)**: the PTP top-level collection `Col02` has `OutputReportByteLength = 0` — the host is **physically incapable** of sending a haptic output report. Under the Haptics page `0x0E` there is only `Intensity`, not the `Manual Trigger (0x0E/0x21)` that Microsoft's spec requires.

> 🔴 **2026-10-03: one early piece of support was withdrawn.** The observation "under a Linux live USB the pointer does not move yet pressing still vibrates" was once listed as *decisive evidence*. **It is withdrawn** — in that Linux environment the touchpad was **never actually exercised** (the driver never took over), so neither pointer movement nor vibration proves anything.
> See [Register §B1](docs/08-findings/00-矛盾与推翻登记表.md). The core conclusion is unaffected (it rests on the descriptor and the device stack, below).

### Three independent hard facts (closed 2026-10-02; mutually independent, no packet capture needed)

| # | Hard fact | Basis |
|---|---|---|
| 1 | **The host physically cannot send haptic commands** — PTP top-level `Col02` has `OutputReportByteLength = 0`. Only the vendor collection `Col04` has `Out=65`, and only this project and Goodix's own tool use it | descriptor layer |
| 2 | **No third-party component on the device stack** — all four collections have empty `UpperFilters`/`LowerFilters` ⇒ only inbox `hidclass` + `hidi2c` on the chain | device-stack layer |
| 3 | **No vendor touchpad service running** — of 311 processes system-wide, zero Goodix/Lenovo touchpad-related | process layer |

### Three gates (all closed)

| Layer | Gate | Status |
|---|---|---|
| 1 | HID descriptor declares no haptic capability (no Manual Trigger / Waveform / Duration) | ❌ closed |
| 2 | `hidi2c.sys` exclusively owns the SPB connection; Microsoft requires a single owner per peripheral connection | 🔒 hard block |
| 3 | No host-callable "trigger" command exists in the device firmware | ❌ closed |

### ★★★ But there is a counter-effect: the host *does* touch the haptic path — in the *suppressing* direction

> **High-frequency reads of `Col04` suppress *all* haptic feedback (both press and release).**
> Measured: during an 89.7-second full dump, holding the touchpad down the whole time → **no vibration at all during the dump**; it resumed once reading stopped.

Before 2026-10-03 this was the **only** phenomenon proving "the host can influence the haptic path":

| Item | Content |
|---|---|
| Inference | Haptic triggering is **not at the memory-data level** but at the **firmware ↔ host I²C communication** level ⇒ this explains why "writing memory never works" (the firmware simply does not read that memory) |
| Open direction | Since reading can *suppress*, can changing the **timing / address / length** of reads *promote* (trigger) it? This is the only direction with positive evidence |

> 🔴 **2026-10-03 correction**: the early wording "suppresses only *press* haptics, does not affect *release*" **is wrong**. What is suppressed is **all** haptic feedback; "it only vibrates on release" is actually *recovery after reading stops*, not "the release path is immune".

> 🟢 **2026-10-05 follow-up**: the claim "the only proof that the host can influence the haptic path" is **outdated** — there is now a **second** one: **`0x09`** (Col02 RID 9 / `0x0E/0x23` Intensity) **demonstrably changes haptic behaviour** (write `0` = mute). ⚠️ But its nature is entirely different: it only sets **how hard the device hits when *it* decides to fire**; **"trigger on demand" is still impossible** (no `0x0E/0x21 Manual Trigger`).
> 🔴 **Correction (2026-10-08)**: the cfg channel's ~~"persists across reboot"~~ **has been refuted** — writes are **session-scoped only** (see next section and register **B12**). This paragraph's own conclusion (reads suppress all haptics) is unaffected.

See [`method/METHOD.md`](method/METHOD.md) chapter 6.

### The software-only road: the main line is terminated, but 2026-10-05 opened a new branch

| Route | Status |
|---|---|
| HID standard trigger | ❌ no Manual Trigger (`Col02 Out=0`) |
| Col04 raw memory write / vendor commands | ❌ firmware does not consume it (**but see the branch below**) / none of the 39 commands reaches the motor |
| **★ `cfg_update` private command channel (`0x96F8`)** | 🔴 **2026-10-13 reversal**: `7E 00 02` was officially named `TS_CFG_REPLY_CHKSUM_ERR` (**failure**, not "applied"), and after recomputing the bag checksums with the official algorithm this machine returned **`0x7F` = `TS_CMD_CFG_OK` for the first time** ⇒ **the "modify cfg" road is open again** (register **B36/B37/B38**).<br>🟢 **opened 2026-10-05**: the IC accepts writes (`7E 00 02`). 🔴 **2026-10-08 correction**: ~~persists across reboot~~ **is wrong** — writes are **session-scoped only** (on session end the IC reloads the original values from flash; register **B12**); `0x96F8` is actually **time-multiplexed RAM**. ⚠️ **No perceptible parameter effect was ever proven** (`+0x115`'s five levels are all unreliable) ⇒ "the channel is open", not "vibration is tunable" |
| **★ HID Feature `0x09` (Col02 RID 9)** | ✅ **verified 2026-10-08**: write `0` ⇒ haptic feedback disappears; write `100` ⇒ restored. **The only host-side interface empirically shown to change haptic behaviour.** ⚠️ But it only sets "how hard the device hits when *it* fires", **cannot trigger**; and it is **not persisted** (register **B14**).<br>★ **2026-10-13 (B40)**: the Microsoft spec *requires* the Intensity collection to omit Manual Trigger ⇒ this is a **compliant configuration**, not a defect |
| GT7868Q threshold table (`0x5B80`) | ❌ old line, already excluded |
| Host-side I²C channels (5 buses) | ❌ **5/5 closed** (either swept clean, or unreachable from the host at all) |
| Does the EC participate in haptics? | ✅ measured: no (at this probe's sensitivity) → closed |
| **TF100A firmware sensitivity patch "40 → 8"** | ✅ the only **device-side** route with a byte-level target — patched image generated, awaiting flashing |

> **The TF100A break-in point**: the vibration predicate is `|baseline − current| > 40`, where `40` is the immediate `0x28` of two Thumb instructions.
> **Change it to 8 ⇒ the predicate becomes sensitive ⇒ natural pressure fluctuations while sliding repeatedly cross the threshold ⇒ the press chain is repeatedly triggered ⇒ sliding vibration** (device-initiated, touching no host protocol at all).
> Carrier `TB14P_GT7868Q_14030522_20240202.BIN`, load base `0x08005000` ↔ file `0x19ABC`;
> patch sites `0x1A54C` (`28 31` → `08 31`) and `0x1A578` (`28 39` → `08 39`), **2 bytes only**.
> 🔴 The BIN itself is **not in the repository** (vendor-firmware derivative) ⇒ instead a reproducible script
> **[`tools/firmware/make_tf100a_sens_patch.py`](tools/firmware/make_tf100a_sens_patch.py)**, verified against the real image: **byte-for-byte identical output**.

### ★★★ The two hardest conclusions from the 2026-10-03 wrap-up

> 🔴 **Conclusion ② was narrowed on 2026-10-05** — do not quote it alone as "all write injection is invalid".

| # | Conclusion | Weight |
|---|---|---|
| **①** | **The host cannot reach AW86927 — not because tools are lacking, but because it is *powered off most of the time*.** All five I²C buses were checked; `0x5A` is **on none of them**; a full DSDT scan shows no device declaring `0x5A`/`0x5B`. ⇒ The haptic IC is powered up by GT7868Q only when playback is needed, and the host can never catch that window | Upgrades "why can't we find it" from "we didn't scan it" to a **structural impossibility** |
| **②** | **Systematic write-injection verification: all ineffective.** Every candidate address in the 32 KB writable space was written back and verified — **none worked**. ⇒ Cross-corroborates with "high-frequency reads suppress haptics": **triggering is not at the memory-data level**; the firmware simply does not consume that memory | Closed the last cell of "change memory parameters"<br>⚠️ **Scope: "direct writes to the 32 KB memory" only, excluding the dedicated cfg command channel** |

> Together these answer the project's original question: **it is not that the door was never found — the door is inside the device.**

### ★★★★★ 2026-10-05 breakthrough: the cfg delivery channel is open

> **From the 2026-10-03 wrap-up state, rounds 11–13 produced the only positive breakthrough. This is still the repository's only "parameter-tuning" result.**

| Item | Content |
|---|---|
| **Channel** | vendor-private command `cfg_update`: `0x80` → IC replies `0x82` → write `0x96F8` → `0x83` → read back → `0x7D` |
| **Length correction** | the cfg record's **true length = 1084 B** (1024 body + 60 B tail). Writing 1024 returns `7E 00 00`; writing 1084 returns `7E 00 07` |
| **Transfer format** | `0E 20 00 00 <chunk len+5> 00 <addr16BE> <chunk len16BE> <data>`; **each chunk is a complete write, address increases by 55 per chunk** |
| **Key takeaway** | **`0x96F8` is a 32-byte readable window** — this explains the long-standing "can only read back the first 32 B" |
| **Behaviour change** | ⚠️ **the `+0x115` "intensity knob" verdict has been withdrawn (doubtful)**. Of five values (0/20/60/120/240) only 60 ("softer") and 240 ("clearly stronger") differ, **and they contradict each other** (if monotonic, 0/20 should be softer than 60) ⇒ most likely perceptual noise. ★ However `+0x115 = 0` **simultaneously refuted both the "amplitude" and the "trigger threshold" hypotheses** (threshold 0 should cause wild false triggering; measured: zero false triggers) |
| **Document** | [`2026-10-05-cfg下发通道打通-首个主机写入改变行为的实证.md`](docs/08-findings/2026-10-05-cfg下发通道打通-首个主机写入改变行为的实证.md) |

**⇒ Effect on prior conclusions** (see [Contradiction & Refutation Register](docs/08-findings/00-矛盾与推翻登记表.md) **B7**):

| Prior conclusion | Now |
|---|---|
| §19.34.4 "all write injection invalid" | 🔴 **narrowed to "direct writes to the 32 KB memory are invalid"** — over the dedicated `cfg_update` channel the **transfer is accepted** (but reaches RAM only) |
| §18 "cfg delivery is an as-yet-unrefuted hypothesis" | ⚠️ **only proven as far as "session-scoped RAM staging"**: the IC accepts the write (`7E 00 02`), but a **2026-10-08 reboot test proves it is not persisted** (register **B12**). 🔴 ~~"persists across reboot"~~ **void**; 🔴 "`+0x115` is an intensity knob" **downgraded to doubtful** (B9 / B10) |
| The very idea "the host can change haptic intensity" | ✅ **holds since 2026-10-08** — but via **`0x09`** (Col02 RID 9 / `0x0E/0x23` Intensity; write 0 = mute, 100 = full; verified), **not a cfg field**. It only sets "how hard the device hits when it fires", **cannot trigger** (register **B14**) |

**⚠️ Semantics still not closed (re-downgraded 2026-10-08)**: `+0x115`'s "intensity/threshold knob" hypothesis has been refuted by two rounds (0/20 ≈ 120; only 60 and 240 differ, contradictorily ⇒ perceptual noise); and since cfg writes **are not persisted**, those felt differences **do not even have the material basis of "a written configuration"** ⇒ maintained at **🟠 doubtful** (register **B9 / B10**). **Next step (objective line)**: switch to a closed loop that does not depend on subjective feel — see Handbook §19.48.5.

### ★★★★ The 2026-10-13 / 10-14 net delta (Handbook §19.52–§19.64 + Part 20)

| # | Conclusion | Weight |
|---|---|---|
| **①** | **The "cfg hard wall" is refuted** — the official `gtx8` sources give the **full checksum algorithm**: YS `sum(data[0..n-3]) == BE16(last 2 B)`; NOR `sum(data) & 0xFF == 0`. This machine's 1084 B cfg passes **27/27 bags**, and its structure is complete for the first time (`head[2] = bag_num`, **not** a "version byte") | the first **legal cfg-rewrite procedure** in seven weeks |
| **②** | **First-ever `0x7F` (`TS_CMD_CFG_OK`)** — three cases: **A** unchanged `7E 00 07` (`DATA_EQU`) · **B legal rewrite `7F 00 01 00 80` (success)** · **C** data changed without recomputing the bag trailer `7E 00 02` (`CHKSUM_ERR`). B and C differ by **2 bytes** | single-variable proof; it also gives the three historical cfg "failures" their **official names** |
| **③** | **Official address table settled** — the table is the `reg_info` block (14 entries) inside the official cfg bin header; on this machine `command=0x4160` / `cfg_addr=0x96F8` match the **behaviourally derived** values exactly; `0x4018` reads ASCII **`YELSTO`** ⇒ **family settled: Yellowstone** | ends the "two address sets" dispute |
| **④** | **AW86927 host reachability closed (B33)** — under a real Linux Live, after unbinding `i2c_hid_acpi`, `0x5A/0x5B` on `i2c-0`/`i2c-1` are **all NACK**; the `aw86927` driver carries only an `of:` alias ⇒ it **can never probe on x86 ACPI** | "drive the haptic IC directly" is closed |
| **⑤** | **The Microsoft spec explains it (B40)** — the spec explicitly requires the Intensity collection to **not** contain Manual Trigger ⇒ this machine's configuration is **compliant**; all three elements needed for host-initiated haptics (`0x0E/0x01` collection + Waveform feature report + Manual Trigger output report) are **absent** | "why it cannot be done" upgraded from inference to a **normative basis** |
| **⑥** | **`7868Q` vs `7869` resolved** — container and live IC report the **same** `fw_version` (`1C 02 03 05`); `7868Q` is the product/module designation, `7869` is the IC's **4-digit number field** | removes a long-standing "model contradiction" |
| **⑦** | **Incident + new red lines (disciplines 153/154)** — a blind scan of `0x4160` command codes (it hit `0x10/0x11/0x12`, which may **share semantics** with the flashing commands) disabled the touchpad; the IC core state was intact and was restored with the official exit sequence | two new **non-negotiable** red lines |
| **⑧** | **The one injection surface never tried** — the project **only ever sent `SET_FEATURE`** and **never sent a Col02 OUTPUT report**; Windows blocks it (`out=0`), **Linux `hidraw` does not** ⇒ experiment surface N1 (tools already written) | the only surface the brute-force line has not structurally ruled out |

> ⚠️ That round's methodology lessons are recorded too: discipline **150** (exhaust the vendor sources before claiming a hidden check), **151** (if the vendor has nothing, look for third-party tools derived from vendor source), **152** (accurate citations ≠ correct prioritisation), **155** (always compare `VirtualSize` vs `RawSize` when dumping PE sections).

---
## 3. ⚠️ Read before touching hardware: safety red lines

**This project has had three device-level incidents (touchpad input freeze ×2; IC wedged; and on 2026-10-14 a blind command-code scan of `0x4160` disabled the touchpad). The red lines below are permanent and outrank "making progress".**

```yaml
Red-line layer (four flashing commands — not three; never touch any of them):
  00 10   switch to patch   ← enter programming mode
  00 11   start update      ← enter programming mode
  0E 12   load flash        ← ★ actually writes flash; most dangerous
  0E 13   restart           ← restart

Other:
  - no bulk polling of Col04
  - a single transaction ≤ 32 B, interval ≥ 500 ms
  - 0xA2 is a reply class; never send it
  - do not touch bcdedit without explicit consent
  - read-only first; write-class commands last
  - 🆕 never blind-scan unknown command codes on 0x4160 (discipline 153)
  - 🆕 before any "write to device" brute-force scan, run a command-space semantic-isomorphism check (discipline 154)
```

Full incident record and recovery ladder: **[`docs/09-safety/RED-LINES.md`](docs/09-safety/RED-LINES.md)** — **the single most important document in this repository.**
★ **Added 2026-10-11: [`docs/09-safety/RECOVERY.md`](docs/09-safety/RECOVERY.md) (device recovery path table R1–R7)** — read together with the red lines before touching real hardware (includes "the official update sequence must never be partially executed", discipline 130).

---

## 4. How to read this repository

| Who you are | Start here |
|---|---|
| **Just want the conclusions** | this README → [`docs/08-findings/`](docs/08-findings/) |
| **Want to reproduce the analysis** | [`reproduce/REPRODUCE.md`](reproduce/REPRODUCE.md) → [`reproduce/ENVIRONMENT.md`](reproduce/ENVIRONMENT.md) |
| **Want the methodology** | [`method/METHOD.md`](method/METHOD.md) |
| **Going to touch real hardware** | [`docs/09-safety/RED-LINES.md`](docs/09-safety/RED-LINES.md) + [`docs/09-safety/RECOVERY.md`](docs/09-safety/RECOVERY.md) — **read first, then act** |
| **Want the pitfalls** | [`method/99-pitfalls.md`](method/99-pitfalls.md) (**80 curated**; the **full discipline set is 169 rules** — 110–145 in Handbook [§19.48.3](docs/00-软件逆向全书-芯片固件主机控制.md), 146–155 in §19.53.7 / §19.55.7 / §19.57.9 / §19.61.7 / §19.64.6 and the [incident document](docs/08-findings/2026-10-14-事故-0x4160命令码扫描致触控板失效.md) §5) |
| **🔴 Reading older documents** | **[`docs/08-findings/00-矛盾与推翻登记表.md`](docs/08-findings/00-矛盾与推翻登记表.md)** — **cross-check before believing** |
| **🔴 Citing hardware observations** | **[`docs/02-hardware/00-X9-15硬件信息归属与差异声明.md`](docs/02-hardware/00-X9-15硬件信息归属与差异声明.md)** |

### 🔴🔴 Two mandatory warnings up front (this is a **process archive**, not a consistent document)

**Warning 1: documents from older workdirs do not auto-sync; early conclusions were refuted 20+ times.**

The repository spans **10 workdirs** and **26+ rounds**. The register (classes A/B/C/D) has reached **B1–B59**; across the repository (**261 md files**) there are **1158** 🔴 correction markers (311 of them inside the Handbook).
`docs/10-journal/` (raw incremental logs) and `docs/99-archived/` (archived old lines) are **historical snapshots** — a "✅ valid (authoritative)" there means only *as judged at the moment it was written*.

> 📋 **Before reading any older document, check [`docs/08-findings/00-矛盾与推翻登记表.md`](docs/08-findings/00-矛盾与推翻登记表.md).**
> It lists **20+ refuted conclusions across classes A/B/C/D**, and **which files still carry the old version** (down to line numbers).

The most dangerous ones (**present in entry documents**):

| Refuted old conclusion | Now |
|---|---|
| "The descriptor comes from device firmware; **the host cannot change it**" | 🔴 refuted: `report_fixup` **can** change the host-side copy (proven for this machine's `0x01E9`). **But the verdict is unchanged** (no receiving branch on the device side) |
| Firmware is "**128-bit block cipher / ECB**" | 🔴 refuted: it is **1024-byte periodic XOR positional scrambling**, **and it has been solved** |
| "flashing **triple**" | 🔴 the red lines are **four** (`0E 13` was missing, and `0E 12` is often mistaken for "restart" — exactly backwards) |
| "high-frequency Col04 reads suppress only **press** haptics" | 🔴 wrong wording: it suppresses **all** haptic feedback (press + release) |

**Warning 2: hardware observations may come from two different boards.**

This project involves **two physical touchpads**: ① the **original** one in this 21LD; ② a **ThinkPad X9-15 Gen 1 module** the owner bought on 2026-09-29 (it does not fit, so it became a research sample).
They share a **chip family, I²C addresses and outline dimensions**, **but have different PIDs and very different actuators**.
**⇒ For any physical photo dated after 2026-09-29, the source must be confirmed item by item.**

| | this 21LD | X9-15 Gen 1 |
|---|---|---|
| PID | `0x01E9` ✅ whitelisted | `0x01EA` / `0x01EB` ❌ ⇒ **Code 10** |
| Actuator | small LRA, FRU `5T60S94326`, **7.5×14 mm** | **Nidec TapSense `NIDEC 55F0410`, 25×25×1.4 mm** |
| Resonance | ⚠️ **not measured** (the 200 Hz in the handbook is TapSense's spec, applied across models) | 200 Hz (Nidec official) |

> 📋 **Discrimination method and item-by-item attribution table: [`docs/02-hardware/00-X9-15硬件信息归属与差异声明.md`](docs/02-hardware/00-X9-15硬件信息归属与差异声明.md).**

### Repository layout

```
thinkbook-forcepad-gt7868q-gxtp5100-re/
├── README.md                ← Chinese front door
├── README.en.md             ← you are here (English front door)
├── LICENSE / NOTICE / CONTRIBUTING.md / .gitignore
│
├── docs/                    ← the archive: conclusions and evidence (by topic)
│   ├── en/                  ← English edition (this summary)
│   ├── 01-overview/         project goals · platform baseline · component table
│   ├── 02-hardware/         three chips, down to pin level
│   ├── 03-firmware/         container · partition table · scrambling crack · cfg
│   ├── 04-host-control/     the three gates
│   ├── 05-i2c/              measured boundaries of the five buses
│   ├── 06-ec-acpi/          zero-privilege ACPI export · EC RAM diffing
│   ├── 07-hid/              HID usage semantics · Col04 command-space boundary
│   ├── 08-findings/         conclusion tables · evidence grading · contradiction audit ★
│   ├── 09-safety/           red lines · incidents · recovery ladder ★★
│   ├── 10-journal/          round-by-round log (§19.x, chronological)
│   └── 99-archived/         refuted-but-retained conclusions (with void banners)
│
├── method/                  ← methodology: how to do it (reusable for other models/chips)
│   ├── METHOD.md            main methodology (what / how / result)
│   ├── 01-recon-workflow.md      recon workflow
│   ├── 02-firmware-unpack.md     firmware unpacking and container parsing
│   ├── 03-obfuscation-crack.md   periodic XOR scrambling crack ★
│   ├── 04-disassembly.md         ARM/Thumb disassembly and sink tracing
│   ├── 05-hid-probing.md         HID channel probing
│   ├── 06-i2c-spb.md             I²C/SPB boundaries and bypass
│   ├── 07-ec-acpi.md             ACPI export / EC RAM read and diff
│   ├── 08-evidence-grading.md    evidence grading and predicate discipline ★
│   ├── 09-memory-map.md          ★ memory map: appendices A–L, addresses and constants
│   ├── 10-semantics.md           ★ semantics: four command tables · cfg TLV · TAG dictionary
│   └── 99-pitfalls.md            pitfall list (70 curated rules)
│
├── reproduce/               ← reproduction: deps · environment · data · order
│   ├── REPRODUCE.md         overall flow and operation order
│   ├── ENVIRONMENT.md       software dependencies and versions
│   ├── DATA-INVENTORY.md    data asset inventory + sha256 + how to obtain
│   └── checklists/          step-by-step checklists
│
├── tools/                   ← scripts (read-only first; write-class ones labelled)
├── data/                    ← data (firmware not included, see DATA-INVENTORY)
├── vendor-refs/             ← third-party references (redistributable content + links only)
└── gaps/                    ← open-items list
```

---

## 5. Evidence grading (the project's core discipline)

**Every conclusion in the handbook carries a grade. Unmarked statements should be treated as background information.**

| Grade | Meaning |
|---|---|
| ✅ **confirmed** | backed by on-machine measurement or a primary specification |
| ⚠️ **semi-confirmed** | measured, but one key link is missing, or only indirect evidence |
| ⚠️ **inferred** | reached by elimination or circumstantial evidence, no direct evidence |
| ❌ **no evidence** | no material at all |

See [`method/08-evidence-grading.md`](method/08-evidence-grading.md).

**Chain grading from host to motor** (full table in `docs/08-findings/`):

| Link | Grade | Missing |
|---|---|---|
| host → GT7868Q | ✅ confirmed | — |
| GT7868Q → TF100A | ⚠️ semi-confirmed | I²C1 vs USART1 unproven; `PA3` peer unproven |
| inside TF100A (sense→detect→report) | ✅ confirmed (for this image) | cannot verify it is the version the device actually runs |
| who decides to vibrate | ⚠️ inferred | reached by elimination |
| → AW86927 | ❌ **no evidence** | who is its I²C master / which bus / which address — all four unknown |
| AW86927 → motor | ⚠️ semi-confirmed | this machine's motor model not directly confirmed |
| press vibration is host-independent | ✅ confirmed | the EC is only "no evidence", not "excluded" |

---

## 5·b Two quick-reference tables (pin them on the wall)

| You want | Go to |
|---|---|
| **what is this address / constant?** | [`method/09-memory-map.md`](method/09-memory-map.md) — appendices **A–L**: I²C layer / I²C-HID registers / Goodix host protocol / touch-IC registers / official constants / on-chip peripherals / **TF100A (ctx struct + sampling-window state machine)** / **AW86927 (full 20-pin table)** / EC·ACPI / I²C-SMBus resources / **flash partition table** / container and scrambling |
| **what is this command / TAG?** | [`method/10-semantics.md`](method/10-semantics.md) — four command tables layered / **TF100A's 39 commands** (`0x80`×1 + `0xA0`×16 + `0xA1`×22) / GT7868Q official 10 / host messages / **cfg `[LEN][TAG]` frame order + TAG dictionary + haptic region `0x50–0x7A`** |

### ★ The periodic scrambling table K ships with the repository

| Item | Value |
|---|---|
| File | [`data/reference/K_gt7868q.bin`](data/reference/K_gt7868q.bin) |
| Size / sha256 | 1,024 B · `1a4847391f429a6b233df317bdf4c0b9…` |
| Property | 256 values each appearing 4 times, **chi-square = 0.00** |
| Usage | `plain[x] = raw[x] ^ K[(x + 316) % 1024]` |

> K **is not vendor key material**; it was recovered from the firmware's own zero-fill region (`0 ⊕ K = K`) and contains no device-unique information. See `data/reference/K_gt7868q.README.md`.

---

## 6. Compliance and disclaimer

- **This repository contains only methodology, scripts, analysis conclusions, and locally readable data. It contains no vendor firmware binaries, no vendor tools, and no copyrighted datasheets.**
  **How to obtain** firmware/tools is documented in [`reproduce/DATA-INVENTORY.md`](reproduce/DATA-INVENTORY.md); please download from official channels yourself.
- Third-party tools (RWEverything, PawnIO, ACPICA iasl, …) are **not** included; only acquisition links and usage notes are retained.
- **Official vendor sources are redistributed under a graded licence policy (since 2026-10-14)**: the Goodix sources (**Apache-2.0**), the official Linux driver and the mainline patches (**GPL-2.0 / GPL-2.0-only**) — **37 files** — are committed with their original copyright headers and SPDX tags (including the GPL-2.0 text as `COPYING.GPL-2.0.txt`); see [`poc/gdix-official-missing/LICENSES.md`](poc/gdix-official-missing/LICENSES.md) and [`vendor-refs/links.md`](vendor-refs/links.md) §XII. The **three vendor cfg bins (no licence statement inside) and the two Microsoft copyrighted documents stay local-only**.
- **Locally generated data (including `.bin` evidence) is now committed**: 19 cfg records / IC state samples are in the repository (the reproduction material for B36 / B38 — see [`NOTICE.md`](NOTICE.md) §2.2).
- **Operating a device according to these documents carries a risk of bricking it.** The authors accept no responsibility for device damage. Do flashing-class operations on a spare board (spare touchpad module) first.
- See [`NOTICE.md`](NOTICE.md).

### Contributing

Found a mistake? Open an Issue or a PR — **no need to be polite, and no need to ask first**.
This repository is positioned as "a process archive with the error scene left in"; one mistake you point out is worth more than ten vague doubts.

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before contributing — it covers what makes this repository unusual (conclusions refuted 20 times, some scripts are "scene records" rather than "tools"), which kinds of help are most needed, and **three non-negotiable safety red lines**.

---

## 7. Status

| Item | Status |
|---|---|
| Host-side I²C reachability | ✅ **closed** (Windows side 5/5 = all unreachable; a 2026-10-13 Linux spot-check of `i2c-0/1` was all-NACK too ⇒ register **B33**) |
| Host-initiated trigger | ❌ impossible — Microsoft's spec explicitly forbids Manual Trigger inside the Intensity collection, and all three required elements are absent (register **B40**) |
| Does the EC participate in haptics | ✅ measured: no → closed |
| Sliding-vibration route | ★★★★ the only one: TF100A 40→8, patched image ready |
| Flashing channel | ✅ recon complete (UEFI capsule + `GoodixTpDxe`, not via HID) |
| **`0E 12` flash-write mechanism** | ✅ **verified on real hardware 2026-10-12**: both blocks returned `0xAA` (previously always `0xBB`) ⇒ §19.46's `gxmem`-truncation root cause holds; ★ and **`unitlen` must be 4096** (1084 ⇒ `0xBB`; 4096 ⇒ `0xAA`, single-variable control) |
| **cfg flash address** | ✅ **`0x1E000`**. The official sources contain **three different values** (`gtx2`/`gtx3` = `0x3E000` · `gt7868q` = `0x19000` · fwupd `gtx8` = `0x1E000`); **`0x19000` lies in an "uncovered" region and writing it degrades the device**, while `0x1E000` was harmless (register **B31** / discipline **143**) |
| 🟢 **Can a cfg *change* take effect / persist?** | 🔴🔴 **the 2026-10-12 verdict was refuted on 2026-10-13** (register **B36 / B38**): **it does go in** — after recomputing the bag checksums with the official algorithm the project obtained **`0x7F` (success) for the first time ever** (three-case single-variable control: B success / C checksum error). ⚠️ But writes still target **session RAM (`0x96F8`) only** and **flash was never touched**; a *perceptible* effect of any changed parameter is **still unproven** (the historical `+0x10F`/`+0x115` "questionable" field experiments were **invalidated by bad bag checksums** and can now be redone for the first time). 🔴 **Withdrawn**: ~~"the IC applies an unknowable extra content check ⇒ cfg modification is hard-blocked at the IC level"~~ (the 2026-10-12 B32 verdict / old discipline 145) |
| ❌ **Is `cfg+0x10F` the descriptor's source?** | **No** — in the fallback state the descriptor still reads `X logi[0..4149]` / `Y logi[0..2147]`, **identical** to the normal state ⇒ **B11's withdrawal stands** |
| ⚠️ **How to recognise degradation (= IC fallback)** | **Primary criterion = `bag_num` (`0x96F8[2]`)**: normal `0x1B` (27) / degraded `0x11` (17). ⚠️ `0x96F8[1]` is a **phase bit** (`0x01` cfg slot / `0x00` sampling slot) and **must not be used**; **`0x4000 = 0` is not a marker either** (discipline **144** criterion narrowed, see B38). Recovery = **full restart** (RECOVERY **R1**) |
| **Next** (re-ordered 2026-10-14) | ① **N1: raw OUTPUT reports on Col02's undeclared report IDs** (Linux `hidraw`; Windows cannot send them because `out=0`) — **the only brute-force surface not structurally ruled out** ② **field scanning via legal cfg rewrites** (official session path, rollback-safe; `gdix_cfg_tool.py` plus the objective criterion `vib_probe.py` are ready) ③ **flash the TF100A 40→8 patch** (device side, needs SWD) ④ **`0x09`** (the only empirically effective haptic control). 🔴 Withdrawn: ~~blind-scanning all 256 command codes of `0x4160`~~ (2026-10-14 incident + discipline 153) |

List of materials still wanted: **[`gaps/GAPS.md`](gaps/GAPS.md)**
