# analyze-diff.py -- full analysis of diff-A.txt vs diff-B.txt (offline, no hardware)
import sys, os

ROOT = os.path.dirname(os.path.abspath(__file__))

def load(path):
    m = {}
    for ln in open(path, 'r', encoding='utf-8'):
        ln = ln.strip()
        if ' ' not in ln:
            continue
        hd, rest = ln.split(' ', 1)
        if not hd.startswith('0x'):
            continue
        base = int(hd, 16)
        b = bytes(int(t, 16) for t in rest.split() if len(t) == 2)
        m[base] = b
    return m

A = load(os.path.join(ROOT, 'diff-A.txt'))
B = load(os.path.join(ROOT, 'diff-B.txt'))

print("loaded A keys:", [hex(k) for k in sorted(A)])
print("loaded B keys:", [hex(k) for k in sorted(B)])
print()

for base in sorted(A):
    a, b = A[base], B.get(base)
    if b is None or len(a) != len(b):
        print(f"0x{base:04X}: size mismatch")
        continue
    ch = [i for i in range(len(a)) if a[i] != b[i]]
    print(f"=== 0x{base:04X}  ({len(a)} bytes, {len(a)//2} words)  changed bytes: {len(ch)} ===")
    if base != 0x9000:
        print(f"    first differing offsets: {ch[:16]}")
        print()
        continue

    # full byte-level listing for 0x9000
    print("  off   A_lo A_hi   A_LE   A_BE   |  B_lo B_hi   B_LE   B_BE   | dLE")
    for i in range(0, len(a), 2):
        alo, ahi = a[i], a[i+1]
        blo, bhi = b[i], b[i+1]
        aLE = alo | (ahi << 8); aBE = (alo << 8) | ahi
        bLE = blo | (bhi << 8); bBE = (blo << 8) | bhi
        print(f"  0x{base+i:04X}  {alo:02X}   {ahi:02X}  {aLE:5d}  {aBE:5d}  |  "
              f"{blo:02X}   {bhi:02X}  {bLE:5d}  {bBE:5d}  | {bLE-aLE:+6d}")
    print()

    # structure probes
    hi = [a[i+1] for i in range(0, len(a), 2)]
    lo = [a[i] for i in range(0, len(a), 2)]
    print("  A: high bytes (odd offsets) distinct:", sorted(set(hi)))
    print("  A: low  bytes (even offsets) distinct:", sorted(set(lo)))
    bh = [b[i+1] for i in range(0, len(b), 2)]
    bl = [b[i] for i in range(0, len(b), 2)]
    print("  B: high bytes distinct:", sorted(set(bh)))
    print("  B: low  bytes distinct:", sorted(set(bl)))
    print()
    print("  B as bytes (one per cell, no word assumption):")
    print("   ", ' '.join(f"{x:02X}" for x in b))
    print()
    print("  A as bytes:")
    print("   ", ' '.join(f"{x:02X}" for x in a))
