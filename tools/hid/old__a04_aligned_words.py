import struct, collections
BIN = r"<WORKSPACE>"
BASE_ADDR = 0x08005000; BASE_OFF = 0x19ABC
blob = open(BIN,'rb').read()
def addr(o): return o - BASE_OFF + BASE_ADDR
print("BASE_OFF 4-aligned?", BASE_OFF % 4 == 0, "BASE_ADDR 4-aligned?", BASE_ADDR % 4 == 0)
found = collections.Counter()
loc = collections.defaultdict(list)
for o in range(BASE_OFF, BASE_OFF+56480-3, 4):
    w = struct.unpack_from('<I', blob, o)[0]
    if (w & 0xFFFF0000) in (0x40000000, 0xE0000000):
        found[w] += 1; loc[w].append(addr(o))
print("=== 4-byte-ALIGNED 0x4000xxxx / 0xE000xxxx words in TF100A segment ===")
for w,c in sorted(found.items()):
    print(f"  {w:#010x} x{c}  @ {[hex(x) for x in loc[w]]}")
