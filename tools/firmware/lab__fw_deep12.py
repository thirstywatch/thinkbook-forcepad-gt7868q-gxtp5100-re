# fw_deep12.py - A: 0x08008628 的到达路径  B: I2C1 命令路径
import struct
from capstone import *

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
img = data[0x19ABC:]
BASE = 0x08000000
N = len(img)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True
insns = list(md.disasm(bytes(img), BASE))
pos = {i.address: k for k, i in enumerate(insns)}

def show(a0, a1, title=""):
    print("\n--- %s 0x%08X..0x%08X ---" % (title, a0, a1))
    for i in insns:
        if i.address < a0: continue
        if i.address >= a1: break
        print("  %08X: %-10s %s" % (i.address, i.mnemonic, i.op_str))

print("=" * 70)
print("A1) 全镜像中文字上出现 8628 的指令 (movw/ldr 立即数)")
hits = [i for i in insns if "8628" in i.op_str]
print("   count=%d" % len(hits))
for i in hits[:20]:
    print("    0x%08X: %-10s %s" % (i.address, i.mnemonic, i.op_str))

print("\nA2) 所有 blx rX (间接调用) 的点")
blx = [i for i in insns if i.mnemonic == "blx" and not i.op_str.startswith("#")]
print("   count=%d" % len(blx))
for i in blx[:18]:
    k = pos[i.address]
    print("   --- site 0x%08X ---" % i.address)
    for j in range(max(0, k - 7), k + 1):
        t = insns[j]
        print("       %08X: %-10s %s" % (t.address, t.mnemonic, t.op_str))

print("\n" + "=" * 70)
print("B1) I2C1_EV 中断服务程序 @0x08008978")
show(0x08008978, 0x08008A4C, "I2C1_EV ISR")
print("\nB2) I2C1_ER 中断服务程序 @0x0800894C")
show(0x0800894C, 0x08008978, "I2C1_ER ISR")

print("\n" + "=" * 70)
print("B3) 写入字节 0x0E / 0x20 的代码 (响应帧头线索)")
cnt = 0
for k, i in enumerate(insns):
    if not i.mnemonic.startswith("mov"): continue
    if i.op_str not in ("r0, #0xe", "r1, #0xe", "r2, #0xe", "r3, #0xe",
                        "r0, #0x20", "r1, #0x20", "r2, #0x20", "r3, #0x20"): continue
    nxt = insns[k+1:k+4]
    if any(t.mnemonic.startswith("str") for t in nxt):
        print("   --- 0x%08X: %s %s ---" % (i.address, i.mnemonic, i.op_str))
        for t in insns[k:k+5]:
            print("       %08X: %-10s %s" % (t.address, t.mnemonic, t.op_str))
        cnt += 1
        if cnt >= 12: break
if cnt == 0: print("   (无)")
