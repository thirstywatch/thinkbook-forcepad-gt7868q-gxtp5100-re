"""verify-B/hunt.py — 针对 H 的反证搜索
搜索主机模式专属证据：I2C1 CR1 的 START(0x100)/STOP(0x200) 写入、
SR1.SB / SR1.BTF / SR2.MSL / SR2.TRA 的位测试、CCR/TRISE 配置、
以及 SPI/USART/DMA 的对外发送路径。
"""
import struct, collections
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_REG, ARM_OP_IMM, ARM_OP_MEM

BIN = r"<WORKSPACE>"
A_LO, A_HI, F_LO = 0x08005000, 0x08012342, 0x19ABC
data = open(BIN, "rb").read()
def off(a): return a - A_LO + F_LO
def rd32(a):
    o = off(a); return struct.unpack_from("<I", data, o)[0] if 0 <= o <= len(data)-4 else None

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN); md.detail = True
ALL = []
a = A_LO
while a <= A_HI:
    ok=False
    for ins in md.disasm(data[off(a):off(a)+4], a):
        ALL.append(ins); a += ins.size; ok=True; break
    if not ok: a += 2
print("指令总数 %d" % len(ALL))

# ---------- 1) 全镜像立即数扫描：哪些指令用到 0x100/0x200/0x400 等"主机位" ----
print()
print("=" * 84)
print("[1] 所有含立即数 0x100(STOP/PE?) / 0x200(START/ACK?) 的指令（I2C 语义候选）")
for ins in ALL:
    for op in ins.operands:
        if op.type == ARM_OP_IMM and 0x100 <= op.imm <= 0x200:
            print("  %08X  %-8s %-30s imm=0x%X" % (ins.address, ins.mnemonic, ins.op_str, op.imm))
            break

# ---------- 2) tst/ands/cmp 与 #1 #2 #4 的位测试，全列（SB/BTF/MSL/TRA） ----------
print()
print("=" * 84)
print("[2] 对立即数 1/2/4 的位测试指令（tst/ands/cmp/bic/orr/ubfx），统计与位置")
bitcnt = collections.Counter()
bitpos = collections.defaultdict(list)
for ins in ALL:
    for op in ins.operands:
        if op.type == ARM_OP_IMM and op.imm in (1,2,3,4):
            bitcnt[(ins.mnemonic, op.imm)] += 1
            bitpos[(ins.mnemonic, op.imm)].append(ins.address)
            break
for k in sorted(bitcnt):
    print("  %-8s #%d  x%d   %s" % (k[0], k[1], bitcnt[k],
          " ".join("%08X" % x for x in bitpos[k][:12])))
