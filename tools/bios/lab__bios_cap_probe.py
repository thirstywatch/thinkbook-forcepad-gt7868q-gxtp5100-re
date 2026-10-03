# bios_cap_probe.py -- does the Lenovo BIOS capsule embed a Goodix touchpad image?
#
# HANDOVER.md section 8.4 listed "Lenovo full BIOS package" as an UNTRIED source for
# the missing >=5 KB tail of the TF100A payload. That capsule is on this machine:
#   C:\Windows\Firmware\5B11M67497.CAP   (2,113,472 B, 2025-03-21)
# Check it. READ ONLY -- nothing is written or flashed.
import os, re, math, collections

GOODIX = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
CAP    = r'C:\Windows\Firmware\{652d4eee-b41c-4809-80e7-ef22561db51e}\5B11M67497.CAP'

gx = open(GOODIX, 'rb').read()
cap = open(CAP, 'rb').read()
print(f"Goodix BIN : {len(gx):,} B")
print(f"BIOS CAP   : {len(cap):,} B")
print()

# --- 1. container magic of the Goodix package -------------------------------
print("Goodix BIN first 64 bytes:")
print("  " + ' '.join(f"{b:02X}" for b in gx[:64]))
magic = gx[:16]
print(f"  ascii: {gx[:16]!r}")
print()

# --- 2. search the CAP for that magic ---------------------------------------
n = cap.count(magic)
print(f"[A] Goodix 16-byte header found in CAP : {n} time(s)")

# also try progressively shorter prefixes (in case of minor version differences)
for L in (4, 8, 12):
    print(f"    first-{L:2d}-bytes in CAP            : {cap.count(gx[:L])} time(s)")
print()

# --- 3. string search --------------------------------------------------------
for s in [b'GT7868Q', b'TF100A', b'TB14P', b'Goodix', b'GOODIX', b'goodix',
          b'GXTP5100', b'GT7863', b'14030522', b'\x00\x00\x00\x00GT']:
    print(f"[B] {s!r:22s} in CAP : {cap.count(s)}")
print()

# --- 4. is the CAP compressed? (entropy) ------------------------------------
def entropy(b):
    if not b: return 0.0
    c = collections.Counter(b)
    tot = len(b)
    return -sum((v/tot) * math.log2(v/tot) for v in c.values())

print(f"[C] entropy  CAP   : {entropy(cap):.2f} bits/byte   (8.0 = random/compressed)")
print(f"    entropy  BIN   : {entropy(gx):.2f} bits/byte")
for i in range(0, len(cap), len(cap)//8):
    print(f"      CAP chunk @0x{i:07X} ({len(cap)//8:,} B): {entropy(cap[i:i+len(cap)//8]):.2f}")
print()

# --- 5. what does the CAP actually look like? --------------------------------
print("[D] CAP first 96 bytes:")
print("  " + ' '.join(f"{b:02X}" for b in cap[:96]))
print()

# --- 6. do the TF100A plaintext payload's own strings appear? ----------------
# payload B starts at 1084 + 3328 + 100608 = 105020
PB = gx[105020:105020+56608]
print(f"[E] payload B slice: {len(PB):,} B, first 16: {PB[:16]!r}")
for s in [b'TF100A', b'Test_FW', b'Nov 28 2023', b'5.21.01.23007']:
    print(f"    {s!r:18s} in payload B : {PB.count(s)}   in CAP : {cap.count(s)}")
print()

# --- 7. does the CAP contain any 0x2000xxxx / 0x0800xxxx Thumb-looking run? --
print("[F] Thumb 'push {...,lr}' half-word (0xB5xx) density, per 64KB of CAP:")
for i in range(0, len(cap), 65536):
    chunk = cap[i:i+65536]
    if len(chunk) < 1024: continue
    c = sum(1 for j in range(0, len(chunk)-1, 2)
            if 0xB500 <= ((chunk[j] << 8) | chunk[j+1]) <= 0xB5FF)
    print(f"    @0x{i:07X}  {c:5d}   density {c/(len(chunk)/2):.4f}")
