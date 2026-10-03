import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
PATH = r"C:/Windows/Firmware/TB14P_GT7868Q_14030522_20240202.BIN"
data = open(PATH, "rb").read()
N=len(data); IMG_OFF=0x19ABC; BASE=0x08000000; SIZE=N-IMG_OFF
def u32(o): return struct.unpack_from("<I",data,o)[0]

print("=== 镜像末尾 256 字节 (偏移 %d .. EOF) ===" % (N-256))
tail = data[N-256:]
for i in range(0,256,16):
    off = N-256+i
    row = ' '.join('%02X'%b for b in tail[i:i+16])
    # ascii
    asc = ''.join(chr(b) if 32<=b<127 else '.' for b in tail[i:i+16])
    print("%05X: %s  %s" % (off, row, asc))

# 统计末尾填充情况
print("\n=== 末尾字节统计 ===")
# 从 EOF 往前数连续 0xFF / 0x00
def run_from_end(val):
    c=0
    for b in reversed(data[IMG_OFF:]):
        if b==val: c+=1
        else: break
    return c
print("镜像末尾连续 0xFF 数:", run_from_end(0xFF))
print("镜像末尾连续 0x00 数:", run_from_end(0x00))
# 末尾 1024 字节的字节直方图
last = data[IMG_OFF+SIZE-1024:SIZE+IMG_OFF]
from collections import Counter
c=Counter(last)
print("末尾1KB字节频率(Top8):", c.most_common(8))

# capstone: 反汇编最后 1KB
print("\n=== capstone 反汇编镜像最后1KB (地址基址0x%X) ===" % (BASE+SIZE-1024))
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
code = data[IMG_OFF+SIZE-1024: IMG_OFF+SIZE]
addr = BASE+SIZE-1024
count=0
for insn in md.disasm(code, addr):
    print("0x%X:/t%08X/t%s/t%s" % (insn.address, u32(insn.address-BASE+IMG_OFF) if False else 0, insn.mnemonic, insn.op_str))
    count+=1
    if count>=40: break
print("... 反汇编条数:", count)
