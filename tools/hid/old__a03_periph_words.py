import re, struct, collections
BIN = r"<WORKSPACE>"
BASE_ADDR = 0x08005000; BASE_OFF = 0x19ABC
blob = open(BIN,'rb').read()
def addr(o): return o - BASE_OFF + BASE_ADDR

print("=== every 0x4000xxxx / 0xE000xxxx-looking word inside TF100A segment (dedup) ===")
seen = collections.Counter()
for o in range(BASE_OFF, BASE_OFF+56480-3):
    w = struct.unpack_from('<I', blob, o)[0]
    if (w & 0xFFFF0000) == 0x40000000 or (w & 0xFFFF0000) == 0xE0000000:
        seen[w] += 1
for w,c in sorted(seen.items()):
    print(f"  {w:#010x}  x{c}   (e.g. ADDR if aligned at {[hex(addr(o)) for o in range(BASE_OFF,BASE_OFF+56480-3) if struct.unpack_from('<I',blob,o)[0]==w][:4]})")
