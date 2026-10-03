# dist-compare.py -- value-distribution analysis of the 0x9000 window
# Counts saturate (121 vs 120), so compare the VALUES instead.
import os, statistics as st

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
        m[int(hd, 16)] = bytes(int(t, 16) for t in rest.split() if len(t) == 2)
    return m

FILES = [('A1 (off)', 'diff-A1.txt'), ('A2 (off)', 'diff-A2.txt'), ('B  (press)', 'diff-B.txt')]
D = {n: load(os.path.join(ROOT, f))[0x9000] for n, f in FILES}

def words_be_signed(b):
    out = []
    for i in range(0, len(b) - 1, 2):
        v = (b[i] << 8) | b[i+1]
        out.append(v - 65536 if v >= 32768 else v)
    return out

def words_le_signed(b):
    out = []
    for i in range(0, len(b) - 1, 2):
        v = b[i] | (b[i+1] << 8)
        out.append(v - 65536 if v >= 32768 else v)
    return out

def odd_bytes(b):
    """if the layout is 2 bytes/cell with a flag byte, take the data byte"""

def stats(name, vals):
    return (f"  {name:12s} n={len(vals):3d}  min={min(vals):5d}  max={max(vals):5d}  "
            f"mean={st.mean(vals):8.2f}  sd={st.pstdev(vals):7.2f}")

for label, fn in [('BIG-endian signed', words_be_signed),
                  ('LITTLE-endian signed', words_le_signed)]:
    print(f"=== 0x9000 as {label} ===")
    V = {n: fn(D[n]) for n, _ in FILES}
    for n, _ in FILES:
        print(stats(n, V[n]))
    a1, a2, b = V['A1 (off)'], V['A2 (off)'], V['B  (press)']
    mad_ctrl = st.mean(abs(x - y) for x, y in zip(a1, a2))
    mad_sig  = st.mean(abs(x - y) for x, y in zip(a1, b))
    print(f"  mean|A1-A2| = {mad_ctrl:8.2f}   <-- control (same finger state)")
    print(f"  mean|A1-B | = {mad_sig:8.2f}   <-- signal  (different finger state)")
    print(f"  ratio signal/control = {mad_sig/mad_ctrl:6.3f}   "
          f"({'NOISE -- no pressure signal' if mad_sig/mad_ctrl < 1.5 else 'POSSIBLE SIGNAL'})")
    print()

# also: are the two no-finger reads identical to each other and different from B
# in terms of which cells are > 0 ?
print("=== sign pattern (BE signed) ===")
V = {n: words_be_signed(D[n]) for n, _ in FILES}
for n, _ in FILES:
    pos = sum(1 for v in V[n] if v > 0)
    zer = sum(1 for v in V[n] if v == 0)
    neg = sum(1 for v in V[n] if v < 0)
    print(f"  {n:12s}  positive={pos:3d}  zero={zer:3d}  negative={neg:3d}")
