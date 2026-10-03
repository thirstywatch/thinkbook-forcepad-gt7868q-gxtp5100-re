"""步骤15：
(1) 整个容器里是否有"另一个镜像"的向量表（0x2000xxxx 栈顶 + 代码指针）
(2) USART1 接收/命令处理（0x0800DD74 跳转表、0x0800DEE8 中断）快速刻画
"""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

FULL = open(BIN, "rb").read()
print("=== (1) 容器内疑似向量表（word0 在 0x20000000-0x20020000 且 word1 带 Thumb 位）===")
n = 0
for o in range(0, len(FULL) - 8, 4):
    w0 = int.from_bytes(FULL[o:o + 4], "little")
    w1 = int.from_bytes(FULL[o + 4:o + 8], "little")
    if 0x20000000 <= w0 <= 0x20020000 and (w1 & 1) and (0x08000000 <= w1 <= 0x09000000 or w1 < 0x10000000):
        print("  文件 0x%05X: SP=0x%08X reset=0x%08X %s" % (o, w0, w1, "(=TF100A 段起点)" if o == FILE_OFF else ""))
        n += 1
        if n > 40:
            print("  ...截断"); break
print("  命中 %d" % n)

print("\n=== (1b) 容器前 0x19ABC 字节的高熵/低熵 ===")
import math
pre = FULL[:FILE_OFF]
freq = collections.Counter(pre)
ent = -sum((c / len(pre)) * math.log2(c / len(pre)) for c in freq.values())
print("  长度 %d 熵 %.3f 零字节比例 %.3f" % (len(pre), ent, freq[0] / len(pre)))
# 可打印字符串
cur = bytearray(); ss = []
for c in pre:
    if 32 <= c < 127:
        cur.append(c)
    else:
        if len(cur) >= 8:
            ss.append(bytes(cur).decode())
        cur = bytearray()
print("  长度>=8 的 ASCII 串 %d 个，前 20：%s" % (len(ss), ss[:20]))

print("\n=== (2) USART1 命令跳转表 0x0800DD74-0x0800DE00 ===")
data = seg(); m = md()
a = 0x0800DD74
while a <= 0x0800DE40:
    i = insn_at(m, data, a)
    if i is None:
        print("  0x%08X ?? %s" % (a, data[a - SEG_LO:a - SEG_LO + 2].hex())); a += 2; continue
    print("  0x%08X  %-8s %s" % (a, i.mnemonic, i.op_str))
    a += i.size
print("\n  跳转表字节（0x0800DD9E 起 14 字节）:", data[0x0800DD9E - SEG_LO:0x0800DD9E - SEG_LO + 14].hex())
