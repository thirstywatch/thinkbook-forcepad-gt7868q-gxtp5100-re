import sys, re
BIN = r"<WORKSPACE>"
ASM = r"<WORKSPACE>"

blob = open(BIN,'rb').read()
print("bin size", len(blob))

BASE_ADDR = 0x08005000
BASE_OFF  = 0x19ABC
def off(a): return a - BASE_ADDR + BASE_OFF
def addr(o): return o - BASE_OFF + BASE_ADDR

# 1) string check
for where in (0x08005410, 0x08005400):
    o = off(where)
    print(hex(where), "-> off", hex(o), repr(blob[o:o+24]))

# 2) search all occurrences of b'TF100A' in file
for m in re.finditer(rb'TF100A', blob):
    print("TF100A at file off", hex(m.start()), "addr", hex(addr(m.start())), repr(blob[m.start()-8:m.start()+40]))

# 3) whole-file string scan of plausible ascii in TF100A segment
seg = blob[BASE_OFF:BASE_OFF+56480]
print("seg len", len(seg))
for m in re.finditer(rb'[\x20-\x7e]{8,}', seg):
    print(hex(addr(BASE_OFF+m.start())), repr(m.group()))
