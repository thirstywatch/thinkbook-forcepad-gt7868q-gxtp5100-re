import re, sys, io, os

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
path = sys.argv[1]
raw = open(path, encoding="utf-8", errors="replace").read()
c = re.sub(r"\s+", " ", raw)

def show(pat, before=1500, after=1500, label=None, limit=8):
    print(f"\n########## {label or pat} ##########")
    ms = list(re.finditer(pat, c, re.I))
    print(f"matches: {len(ms)}")
    for m in ms[:limit]:
        s = max(0, m.start() - before)
        e = min(len(c), m.end() + after)
        print("----- IDX", m.start())
        print(c[s:e])

for p in sys.argv[2:]:
    show(p)
