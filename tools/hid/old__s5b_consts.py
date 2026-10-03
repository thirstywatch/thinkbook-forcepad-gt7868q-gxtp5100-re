import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
data = seg()
m = md()
print("len", len(data)); sys.stdout.flush()

# --- A) movw/movt 常量扫描（只统计，最多打印 100 行）
cnt = collections.Counter(); det = {}
for o in range(0, len(data) - 7, 2):
    a = SEG_LO + o
    i = insn_at(m, data, a)
    if i is None or i.mnemonic != "movw":
        continue
    mt = re.match(r"(r\d+),\s*#(0x[0-9a-fA-F]+)", i.op_str)
    if not mt:
        continue
    reg, lo16 = mt.group(1), int(mt.group(2), 16)
    j = insn_at(m, data, a + 4)
    if j is None or j.mnemonic != "movt":
        continue
    m2 = re.match(r"(r\d+),\s*#(0x[0-9a-fA-F]+)", j.op_str)
    if not m2 or m2.group(1) != reg:
        continue
    full = (int(m2.group(2), 16) << 16) | lo16
    cnt[full] += 1
    det.setdefault(full, a)
print("movw/movt 唯一常量数 =", len(cnt)); sys.stdout.flush()
print("--- 0x05000000-0x06FFFFFF ---")
SR1 = {0:"SB",1:"ADDR",2:"BTF",3:"ADD10",4:"STOPF",6:"RXNE",7:"TXE",8:"BERR",9:"ARLO",10:"AF",11:"OVR",12:"PECERR",14:"TIMEOUT",15:"SMBALERT"}
SR2 = {0:"MSL",1:"BUSY",2:"TRA",4:"GENCALL",5:"SMBDEFAULT",6:"SMBHOST",7:"DUALF"}
n = 0
for v, c in sorted(cnt.items()):
    if 0x05000000 <= v < 0x07000000:
        off = v >> 22; bit = (v >> 16) & 0x1F
        reg = {20:"SR1",24:"SR2"}.get(off, "off%d" % off)
        nm = SR1.get(bit,"?") if reg=="SR1" else (SR2.get(bit,"?") if reg=="SR2" else "?")
        print("  0x%08X x%d 首见0x%08X -> %s.%s low16=0x%04X" % (v, c, det[v], reg, nm, v & 0xFFFF))
        n += 1
        if n > 100:
            print("  ...(截断)"); break
print("落在该区间的常量数 =", sum(1 for v in cnt if 0x05000000 <= v < 0x07000000))
sys.stdout.flush()

# --- B) 字面量池字扫描
print("--- 字面量池 0x05000000-0x06FFFFFF ---")
n = 0
for o in range(0, len(data) - 3):
    w = int.from_bytes(data[o:o + 4], "little")
    if 0x05000000 <= w < 0x07000000:
        n += 1
        if n <= 60:
            print("  0x%08X 字 0x%08X" % (SEG_LO + o, w))
print("字面量池命中数 =", n)
