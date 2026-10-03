"""步骤5：验证关键字节 + 搜索 0x05xxxxxx/0x06xxxxxx 形式的 I2C IT/flag 常量
（本固件的编码约定：IT>>22 = 寄存器字节偏移, (IT>>16)&0x1F = 位号, IT&0xFFFF = CR2 使能位）
"""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

data = seg()

def hexdump(lo, hi):
    print("--- hexdump 0x%08X-0x%08X ---" % (lo, hi))
    a = lo
    while a < hi:
        o = a - SEG_LO
        chunk = data[o:o + 16]
        print("  0x%08X  %s" % (a, " ".join("%02X" % b for b in chunk)))

for lo, hi in [(0x08008A5C, 0x08008A72), (0x0800F9D8, 0x0800F9E6),
               (0x0800FC08, 0x0800FC7E), (0x0800FD30, 0x0800FD62),
               (0x08008B54, 0x08008B68), (0x0800FA50, 0x0800FA70)]:
    hexdump(lo, hi)
    print()

m = md()
print("=== 全镜像所有 movw/movt 拼出的 0x05000000-0x06FFFFFF 常量 ===")
seen = set()
found = []
for o in range(0, len(data) - 7, 2):
    a = SEG_LO + o
    if a in seen:
        continue
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
    if 0x05000000 <= full < 0x07000000:
        found.append((a, full))
        seen.add(a); seen.add(a + 4)
SR1 = {0: "SB", 1: "ADDR", 2: "BTF", 3: "ADD10", 4: "STOPF", 6: "RXNE", 7: "TXE",
       8: "BERR", 9: "ARLO", 10: "AF", 11: "OVR", 12: "PECERR", 14: "TIMEOUT", 15: "SMBALERT"}
SR2 = {0: "MSL", 1: "BUSY", 2: "TRA", 4: "GENCALL", 5: "SMBDEFAULT", 6: "SMBHOST", 7: "DUALF"}
for a, v in found:
    off = v >> 22
    bit = (v >> 16) & 0x1F
    reg = {20: "SR1", 24: "SR2"}.get(off, "off=%d" % off)
    nm = SR1.get(bit, "?") if reg == "SR1" else (SR2.get(bit, "?") if reg == "SR2" else "?")
    print("  0x%08X  0x%08X  -> %s.%s (bit%d)  low16=0x%04X" % (a, v, reg, nm, bit, v & 0xFFFF))
print("  合计 %d" % len(found))

print("\n=== 数据/字面量池里落在 0x05000000-0x06FFFFFF 的 32 位字 ===")
n = 0
for o in range(0, len(data) - 3):
    w = int.from_bytes(data[o:o + 4], "little")
    if 0x05000000 <= w < 0x07000000:
        print("  地址 0x%08X 字 0x%08X" % (SEG_LO + o, w))
        n += 1
print("  合计 %d" % n)

print("\n=== 全镜像任何立即数 == 0x100 / 0x200 / 0x300 的 orr/adds/mov 指令（仅 I2C 相关区域附近）===")
for lo, hi, tag in [(0x08008890, 0x08008C70, "driver"), (0x0800F800, 0x0800FE00, "SPL")]:
    print(" [%s]" % tag)
    for o in range(lo - SEG_LO, hi - SEG_LO, 2):
        a = SEG_LO + o
        i = insn_at(m, data, a)
        if i is None:
            continue
        if i.mnemonic in ("orr", "orrs", "adds", "add", "movs", "mov", "movw", "eor", "bic", "and", "ands"):
            mm = re.search(r"#(0x[0-9a-fA-F]+)$", i.op_str)
            if mm and int(mm.group(1), 16) in (0x100, 0x200, 0x300, 0x400, 0x800):
                print("    0x%08X  %-7s %s" % (a, i.mnemonic, i.op_str))
