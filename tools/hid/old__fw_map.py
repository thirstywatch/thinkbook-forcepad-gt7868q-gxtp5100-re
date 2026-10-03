import struct, re, capstone, collections
b=open("touchpad_GT7868Q_fw.bin","rb").read()
IMG_FILE=0x19ABC; IMG_BASE=0x08005000
def f2a(f): return IMG_BASE + (f-IMG_FILE)
def a2f(a): return IMG_FILE + (a-IMG_BASE)
START=IMG_FILE; END=0x26E00
print("映射: file 0x%X <-> flash 0x%08X"%(IMG_FILE,IMG_BASE))
print("明文镜像: file 0x%X..0x%X (%d B) -> flash 0x%08X..0x%08X"%(START,END,END-START,IMG_BASE,f2a(END)))
md=capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB); md.detail=True
insns=[]; off=START
while off<END:
    got=list(md.disasm(b[off:END], f2a(off)))
    if got: insns.extend(got); off+=sum(i.size for i in got)
    else: off+=2
print("指令数 = %d"%len(insns))
strs=[]
for m in re.finditer(rb"[ -~]{5,}", b):
    if START<=m.start()<END:
        strs.append((m.start(), f2a(m.start()), m.group().decode('latin1')))
print("\n=== 镜像内可读串 %d 条 ==="%len(strs))
for f,a,s in strs: print("   file 0x%X  flash 0x%08X  %r"%(f,a,s))
mapping={}
for ins in insns:
    for op in ins.operands:
        if op.type==capstone.arm.ARM_OP_IMM and op.imm>0x08000000:
            mapping.setdefault(op.imm,[]).append(ins.address)
        if op.type==capstone.arm.ARM_OP_MEM and op.mem.base==capstone.arm.ARM_REG_PC:
            la=(ins.address+4)&~3; mapping.setdefault(la+op.mem.disp,[]).append(ins.address)
print("\n=== 指向字符串的立即数 ===")
hit=0
for f,a,s in strs:
    if a in mapping:
        hit+=1; print("   flash 0x%08X <- 引用 %d 次 (首处 0x%08X)  %r"%(a,len(mapping[a]),mapping[a][0],s))
print("   命中 %d / %d"%(hit,len(strs)))
targets=collections.Counter()
for ins in insns:
    if ins.mnemonic in ("bl","blx"):
        for op in ins.operands:
            if op.type==capstone.arm.ARM_OP_IMM: targets[op.imm]+=1
print("\n=== BL 调用的函数 %d 个（前 30）==="%len(targets))
for a,n in targets.most_common(30):
    print("   0x%08X  ×%d  (file 0x%X)"%(a,n,a2f(a)))
with open("touchpad_TF100A_thumb.asm.txt","w",encoding="utf-8") as f:
    for i in insns: f.write("%08X  %-9s %s\n"%(i.address,i.mnemonic,i.op_str))
print("\n反汇编已写出 touchpad_TF100A_thumb.asm.txt (%d 行)"%len(insns))
