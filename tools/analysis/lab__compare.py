# compare.py <fileA> <fileB> [--full]
# Compares two diff-probe snapshots. Prints, per window, how many 16-bit words changed.
import sys, os

def load(path):
    m = {}
    for ln in open(path, 'r', encoding='utf-8'):
        ln = ln.strip()
        if ' ' not in ln:
            continue
        hd, rest = ln.split(' ', 1)
        if not hd.startswith('0x'):
            continue
        m[int(hd, 16)] = bytes(int(t, 16) for t in rest.split() if len(t) == 2)
    return m

fa, fb = sys.argv[1], sys.argv[2]
full = '--full' in sys.argv
A, B = load(fa), load(fb)
print(f"A = {os.path.basename(fa)}   B = {os.path.basename(fb)}")
print()
for base in sorted(A):
    a, b = A[base], B.get(base)
    if b is None or len(a) != len(b):
        print(f"0x{base:04X}: size mismatch"); continue
    nw = len(a) // 2
    ch = [i for i in range(0, nw * 2, 2) if a[i:i+2] != b[i:i+2]]
    print(f"0x{base:04X}: changed {len(ch):3d}/{nw} words")
    if ch and full:
        for i in ch[:48]:
            av = a[i] | (a[i+1] << 8); bv = b[i] | (b[i+1] << 8)
            print(f"    0x{base+i:04X}  {av:6d} -> {bv:6d}   d={bv-av:+7d}")
        if len(ch) > 48:
            print(f"    ... and {len(ch)-48} more")
print()

# cross-check: does the SAME window change between two no-finger reads?
print("=== verdict ===")
for base in sorted(A):
    a, b = A[base], B.get(base)
    if b is None or len(a) != len(b): continue
    nw = len(a) // 2
    n_ch = sum(1 for i in range(0, nw*2, 2) if a[i:i+2] != b[i:i+2])
    print(f"  0x{base:04X}: {n_ch}/{nw} words differ")
