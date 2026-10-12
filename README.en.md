# Goodix GT7868Q / GXTP5100 Touchpad Host-Control Reverse-Engineering Archive

> 🌐 **Languages**: **English (this file)** · [中文（主）](../README.md) · [Handbook summary (EN)](docs/en/HANDBOOK-SUMMARY.en.md) · [全书（中文主档案）](docs/00-软件逆向全书-芯片固件主机控制.md)

> **Subject**: the ForcePad (pressure-sensitive touchpad) on a **Lenovo ThinkBook 14 G6+ IMH (21LD)** — Goodix **GT7868Q** touch controller (Windows instance name `GXTP5100`) + Taifang **TF100A** pressure-sensing MCU + Aiw **AW86927** haptic driver IC.

> **One-liner**: *Making the ForcePad produce haptic feedback while **sliding**, using software only — plus why that road has been blocked for a long time, and what the only remaining route is.*
>
> **As of 2026-10-12**: the **only** host-side interface that measurably changes haptic behaviour is **`0x09`** (Col02 RID 9 / Usage `0x0E/0x23` Intensity; write `0` = mute, `100` = full — empirically verified). **Every other injection surface (raw memory writes / cfg writes / direct I²C) is negative.** The `cfg_update` channel itself works, but writes are **scoped to the session only and are not persisted to flash**. "Trigger haptics on demand" is still impossible (no `0x0E/0x21 Manual Trigger`).

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
| **Time span** | 2026-09-13 → **2026-10-12** (~4 weeks, **22+ rounds**) |
| **Size** (as of **2026-10-12**) | **1,944 files / 49 MB**: **228 md** + **797 scripts** (Python 735 / PowerShell 62) + 62 ACPI-related exports + 489 experiment logs; the main archive *Reverse-Engineering Handbook* is **13,181 lines** (structurally de-duplicated, see §19.48.4) |
| **⚠️ Nature of the archive** | **A process archive, not a self-consistent document** — early conclusions were refuted **20+ times** (register classes A/B/C/D; class B has reached **B1–B27**). Before reading any older document you **must** check the [Contradiction & Refutation Register](docs/08-findings/00-矛盾与推翻登记表.md) |
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
| **★ `cfg_update` private command channel (`0x96F8`)** | 🟢 **opened 2026-10-05**: the IC accepts writes (`7E 00 02`). 🔴 **2026-10-08 correction**: ~~persists across reboot~~ **is wrong** — writes are **session-scoped only** (on session end the IC reloads the original values from flash; register **B12**); `0x96F8` is actually **time-multiplexed RAM**. ⚠️ **No perceptible parameter effect was ever proven** (`+0x115`'s five levels are all unreliable) ⇒ "the channel is open", not "vibration is tunable" |
| **★ HID Feature `0x09` (Col02 RID 9)** | ✅ **verified 2026-10-08**: write `0` ⇒ haptic feedback disappears; write `100` ⇒ restored. **The only host-side interface empirically shown to change haptic behaviour.** ⚠️ But it only sets "how hard the device hits when *it* fires", **cannot trigger**; and it is **not persisted** (register **B14**) |
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

---

## 3. ⚠️ Read before touching hardware: safety red lines

**This project has had two real-machine incidents (touchpad input freeze; IC wedged). The red lines below are permanent and outrank "making progress".**

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
| **Want the pitfalls** | [`method/99-pitfalls.md`](method/99-pitfalls.md) (curated; the **full discipline set is 137 rules**, index in the Handbook [§19.48.3](docs/00-软件逆向全书-芯片固件主机控制.md)) |
| **🔴 Reading older documents** | **[`docs/08-findings/00-矛盾与推翻登记表.md`](docs/08-findings/00-矛盾与推翻登记表.md)** — **cross-check before believing** |
| **🔴 Citing hardware observations** | **[`docs/02-hardware/00-X9-15硬件信息归属与差异声明.md`](docs/02-hardware/00-X9-15硬件信息归属与差异声明.md)** |

### 🔴🔴 Two mandatory warnings up front (this is a **process archive**, not a consistent document)

**Warning 1: documents from older workdirs do not auto-sync; early conclusions were refuted 20+ times.**

The repository spans **10 workdirs** and **22+ rounds**. The register (classes A/B/C/D) has reached **B1–B27**; across the repository (**228 md files**) there are more than **720** 🔴 correction markers.
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
| Host-side I²C reachability | ✅ 5/5 closed (all unreachable) |
| Does the EC participate in haptics | ✅ measured: no → closed |
| Sliding-vibration route | ★★★★ the only one: TF100A 40→8, patched image ready |
| Flashing channel | ✅ recon complete (UEFI capsule + `GoodixTpDxe`, not via HID) |
| **`0E 12` flash-write mechanism** | ✅ **verified on real hardware 2026-10-12**: both blocks returned `0xAA` (previously always `0xBB`) ⇒ §19.46's `gxmem`-truncation root cause holds; **B12's "mechanism" layer is closed** |
| ⚠️ **But the write caused degradation** | 🔴 On 2026-10-12 the first target was `idx4` (**`type 0x03` = `FLASH_SUBSYS_TYPE_CONFIG`**) ⇒ the device entered the **same degraded state as 2026-10-10** (no click haptics / click broken; cursor and sliding fine), recovered by a **full restart**. **Both degradations happened on `type 0x03` blocks** (register **B29** / disciplines 138–140) |
| **Next** | ① full restart + verify the three criteria ② **redo `0E 12` with a `type 0x02` block (`0x012000`)** ③ **persist cfg via `0E 12 @0x19000`** (equivalent to the official `flash_cfg_with_isp`; the real B12 closure) ④ flash the TF100A 40→8 patch |

List of materials still wanted: **[`gaps/GAPS.md`](gaps/GAPS.md)**
