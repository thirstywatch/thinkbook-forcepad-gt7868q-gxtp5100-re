import sys, os, re, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

data = seg()
print("len(data) =", len(data)); sys.stdout.flush()

def hexdump(lo, hi):
    print("--- hexdump 0x%08X-0x%08X ---" % (lo, hi))
    a = lo
    while a < hi:
        o = a - SEG_LO
        chunk = data[o:o + 16]
        print("  0x%08X  %s" % (a, " ".join("%02X" % b for b in chunk)))
        a += 16

for lo, hi in [(0x08008A5C, 0x08008A72), (0x0800F9D8, 0x0800F9E8),
               (0x0800FC08, 0x0800FC7E), (0x0800FD30, 0x0800FD62),
               (0x08008B54, 0x08008B68), (0x0800FA50, 0x0800FA70),
               (0x08008AE8, 0x08008AF4), (0x0800FBE0, 0x0800FBF6)]:
    hexdump(lo, hi)
