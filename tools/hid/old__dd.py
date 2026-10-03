"""定点反汇编 dump：从原始字节 capstone 逐条解码，直到遇到返回/无法解码。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

data = seg()
m = md()

def dump(lo, hi, stop_at_ret=False):
    a = lo
    while a <= hi:
        i = insn_at(m, data, a)
        if i is None:
            print("  0x%08X  <无法解码> %s" % (a, data[a - SEG_LO:a - SEG_LO + 2].hex()))
            a += 2
            continue
        print("  0x%08X  %-8s %s" % (a, i.mnemonic, i.op_str))
        a += i.size

if __name__ == "__main__":
    lo = int(sys.argv[1], 16); hi = int(sys.argv[2], 16)
    dump(lo, hi)
