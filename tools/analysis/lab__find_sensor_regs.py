import re, struct
BIN=r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data=open(BIN,"rb").read(); img=data[0x19ABC:]; BASE=0x08000000
print("镜像长度", len(img))
# 传感器寄存器地址（大端字节对）
regs = {0x60CC:"CMD/disable-report",0x5095:"BL_STATE",0x5096:"FLASH_RESULT",0xC000:"FLASH_BUFFER",
        0x4100:"RAW_STATUS",0x452C:"FW_INFO",0x60DC:"CFG_VERSION",0x3044:"(初始化里出现过)",
        0x44EC:"校准表",0x4938:"(校准相关)",0x61B4:"(某模块结构)"}
print("\n=== 大端字节对搜索 (传感器寄存器地址) ===")
for v,nm in regs.items():
    pat = bytes([v>>8, v&0xFF])
    hits=[m.start() for m in re.finditer(re.escape(pat), img)]
    if hits:
        print(f"  0x{v:04X} {nm:18s}: {len(hits)} 处 {[hex(h) for h in hits[:8]]}")
print("\n=== 小端 16 位搜索 ===")
for v,nm in ((0x60CC,"CMD"),(0x4100,"RAW"),(0xC000,"FLASHBUF"),(0x5095,"BLSTATE")):
    pat=struct.pack("<H",v)
    hits=[m.start() for m in re.finditer(re.escape(pat), img)]
    print(f"  0x{v:04X} {nm:10s}: {len(hits)} 处 {[hex(h) for h in hits[:6]]}")
# 找 I2C 相关：I2C1=0x40005400 的 movw/movt
print("\n=== I2C1 (0x40005400) 构造点 ===")
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
md=Cs(CS_ARCH_ARM, CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN); md.skipdata=True
ins=list(md.disasm(bytes(img), BASE))
i=0; found=[]
while i < len(ins)-1:
    a,b=ins[i],ins[i+1]
    if a.mnemonic=="movw" and b.mnemonic=="movt" and a.op_str.startswith("r") and b.op_str.startswith("r"):
        try:
            ra,va=a.op_str.split(", #"); rb,vb=b.op_str.split(", #")
            if ra==rb:
                full=(int(vb,16)<<16)|int(va,16)
                if 0x40005000 <= full <= 0x40006000 or 0x40020000 <= full < 0x40024000:
                    found.append((a.address, full))
        except ValueError: pass
    i+=1
for a,v in found[:30]:
    print(f"  0x{a:08X} -> 0x{v:08X}  (I2C/DMA 外设)")
print(f"  共 {len(found)} 处")
