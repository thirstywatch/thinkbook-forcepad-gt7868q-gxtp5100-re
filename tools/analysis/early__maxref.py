import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
PATH = r"C:/Windows/Firmware/TB14P_GT7868Q_14030522_20240202.BIN"
data = open(PATH,"rb").read()
N=len(data); IMG_OFF=0x19ABC; BASE=0x08000000; SIZE=N-IMG_OFF
def u32(o): return struct.unpack_from("<I",data,o)[0]

# 1) 向量表全部条目，找最大越界地址
print("=== 向量表范围检查 ===")
max_vec=0; oob_vec=[]
for i in range(0,256):
    o=IMG_OFF+i*4
    if o+4> N: break
    v=u32(o); a=v&~1
    if a==0: continue
    if a>BASE+SIZE:
        oob_vec.append((i,hex(v)))
        max_vec=max(max_vec,a)
print("越界向量条目:", oob_vec)
print("越界向量中最大地址:", hex(max_vec), "需镜像>=", max_vec-BASE, "字节")

# 2) 全镜像反汇编，收集所有分支/调用/PC相关目标地址
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB)
md.detail=True
max_ref=0; refs=[]
# 逐段反汇编（Thumb，遇到不可解跳过）
addr=BASE
off=0
while off < SIZE:
    chunk=data[IMG_OFF+off:IMG_OFF+min(off+4096,SIZE)]
    for ins in md.disasm(chunk, BASE+off):
        # 收集 jump/call 目标
        for op in ins.operands:
            if op.type==2:  # immediate
                val=op.imm
                if BASE<=val<=BASE+SIZE+0x2000:  # 含略越界
                    if val>max_ref: max_ref=val
                    if val>BASE+SIZE: refs.append((hex(ins.address),hex(val)))
        # 也用 group 判是否跳转
    off+=4096
print("\n=== 反汇编收集到的越界引用(目标>镜像末尾0x%X) ===" % (BASE+SIZE))
refs=sorted(set(refs))
for r in refs[:60]:
    print("  ", r)
print("最大被引用地址:", hex(max_ref), "超出镜像末尾:", hex(max_ref-(BASE+SIZE)), "字节")

# 3) 整个镜像用到的地址上界（数据/代码限）
print("\n=== 镜像内地址使用上界 ===")
print("假定镜像末尾地址:", hex(BASE+SIZE), "=", BASE+SIZE)
