import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
PATH = r"C:/Windows/Firmware/TB14P_GT7868Q_14030522_20240202.BIN"
data=open(PATH,"rb").read(); N=len(data)
IMG_OFF=0x19ABC; BASE=0x08000000; SIZE=N-IMG_OFF
def u32(o): return struct.unpack_from("<I",data,o)[0]

print("声称分段: 1084+3328+100608+56608 =", 1084+3328+100608+56608, " (文件大小", N,")")
b3 = 1084+3328+100608
print("声称第三段结束偏移 =", b3, hex(b3), " 第四段(56608)起点应=此值")
print("我定位的向量表偏移 =", hex(IMG_OFF), " 差值 =", IMG_OFF-b3, "字节(我比声称早128字节)")

# 0x19AFC 处是否另有合法向量表?
print("\n--- 偏移0x19AFC(声称第四段起点)处16字节 ---")
print(' '.join('%02X'%b for b in data[0x19AFC:0x19AFC+16]))
sp=u32(0x19AFC); rst=u32(0x19AFC+4)
print("SP=",hex(sp),"Reset=",hex(rst)," => 是否为合法vtable:", (0x20000000<=sp<=0x20010000) and (rst&0xFF000000==0x08000000) and (rst&1))

# vec[6] 细节
v6=u32(IMG_OFF+6*4)
print("\nvec[6] =", hex(v6), " 相对镜像末尾0xDCA0偏移 =", hex(v6-BASE-SIZE), "字节越界")
print("欲使vec[6]合法, 镜像至少需", hex(v6-BASE), "=", v6-BASE, "字节; 现仅", SIZE)

# 尾部分支 b #0x800df5a 位置确认
print("\n--- 偏移0x19ABC+(0xD8AE-0x80000000? ) ---")
# 0x800D8AE 对应文件偏移 = IMG_OFF + (0x800D8AE - 0x80000000) = IMG_OFF+0xD8AE
o=IMG_OFF+0xD8AE
print("文件偏移", hex(o), "处指令字节:", ' '.join('%02X'%b for b in data[o:o+8]))
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB)
for ins in md.disasm(data[o:o+8], 0x800D8AE):
    print("  反汇编:", hex(ins.address), ins.mnemonic, ins.op_str)
print("  分支目标0x800DF5A 越界字节数 =", hex(0x800DF5A-(BASE+SIZE)))

# 末尾是否任何0xFF
print("\n末尾2KB中0xFF出现次数:", data[IMG_OFF+SIZE-2048:IMG_OFF+SIZE].count(0xFF))
print("末尾2KB中0x00出现次数:", data[IMG_OFF+SIZE-2048:IMG_OFF+SIZE].count(0x00))
# 全镜像最高被引用地址(精确)
md2=Cs(CS_ARCH_ARM,CS_MODE_THUMB); md2.detail=True
maxr=0
for off in range(0,SIZE,1024):
    for ins in md2.disasm(data[IMG_OFF+off:IMG_OFF+min(off+1024,SIZE)], BASE+off):
        for op in ins.operands:
            if op.type==2 and BASE<=op.imm<=0x080FFFFF:
                maxr=max(maxr,op.imm)
print("全镜像反汇编: 最高被引用Flash地址 =", hex(maxr), " (=镜像内" , maxr-BASE,"字节)" if maxr-BASE<=SIZE else "已越界!"+str(maxr-BASE-SIZE))
