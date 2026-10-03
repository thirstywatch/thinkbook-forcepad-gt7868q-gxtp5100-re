import struct, re, capstone, collections
b=open("touchpad_GT7868Q_fw.bin","rb").read()
IMG_FILE=0x19ABC; IMG_BASE=0x08005000; END=0x26E00
def f2a(f): return IMG_BASE+(f-IMG_FILE)
def a2f(a): return IMG_FILE+(a-IMG_BASE)
md=capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB); md.detail=True
insns=[]; off=IMG_FILE
while off<END:
    got=list(md.disasm(b[off:END], f2a(off)))
    if got: insns.extend(got); off+=sum(i.size for i in got)
    else: off+=2

print("=== 折叠 movw/movt 找地址常量引用 ===")
regs={}; refs=collections.defaultdict(list)
for ins in insns:
    o=ins.op_str
    if ins.mnemonic=="movw" and "," in o:
        try:
            r,v=o.split(","); regs[r.strip()]=int(v.strip(),16)
        except Exception: pass
    elif ins.mnemonic=="movt" and "," in o:
        try:
            r,v=o.split(","); regs[r.strip()]=(regs.get(r.strip(),0)&0xFFFF)|(int(v.strip(),16)<<16)
        except Exception: pass
    elif ins.mnemonic in ("ldr","add","cmp","mov","bl","bx") and regs:
        for r,v in list(regs.items()):
            if re.search(r"\b%s\b"%re.escape(r),o) and IMG_BASE<=v<f2a(END):
                refs[v].append((ins.address,ins.mnemonic,o))
        if ins.mnemonic in ("movw","movt"): pass
        # 用完清掉被覆盖的寄存器
        if o.split(",")[0].strip() in regs and ins.mnemonic not in ("movw","movt"):
            regs.pop(o.split(",")[0].strip(),None)
print("   指向镜像内的地址常量 %d 个"%len(refs))
strs=[(f2a(m.start()),m.group().decode('latin1')) for m in re.finditer(rb"[ -~]{4,}",b) if IMG_FILE<=m.start()<END]
print("\n=== 镜像内串（>=4）与其被引用情况 ===")
for a,s in strs:
    if a in refs or len(s)>=8:
        print("   0x%08X  %-22r 引用 %s"%(a,s,["0x%08X"%x[0] for x in refs.get(a,[])][:4] or "—"))

print("\n=== 明文区里所有 >=6 的串（全量，去噪）===")
seen=set()
for m in re.finditer(rb"[ -~]{6,}", b):
    if IMG_FILE<=m.start()<END:
        s=m.group().decode('latin1')
        if s not in seen and sum(c.isalnum() or c in " ._-" for c in s)>=len(s)*0.7:
            seen.add(s); print("   0x%08X %r"%(f2a(m.start()),s))

print("\n=== 明文区里找可能的 haptic/force 相关（数值表）===")
# 连续递增/递减的 16 位序列（可能是波形/曲线表）
runs=[]
i=IMG_FILE
while i<END-2:
    v0=struct.unpack_from("<H",b,i)[0]
    n=1
    while i+2*n<END and struct.unpack_from("<H",b,i+2*n)[0]>struct.unpack_from("<H",b,i+2*(n-1))[0] and n<64:
        n+=1
    if n>=12: runs.append((i,n,v0)); i+=2*n
    else: i+=2
print("   递增 16 位序列段 %d 个"%len(runs))
for f,n,v0 in runs[:12]:
    vals=[struct.unpack_from("<H",b,f+2*k)[0] for k in range(n)]
    print("      file 0x%X (flash 0x%08X)  %d 项: %s..."%(f,f2a(f),n,vals[:10]))
