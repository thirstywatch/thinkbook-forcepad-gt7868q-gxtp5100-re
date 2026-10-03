import re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
path, start, end = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
raw = open(path, encoding="utf-8", errors="replace").read()
c = re.sub(r"\s+", " ", raw)
print(c[start:end])
