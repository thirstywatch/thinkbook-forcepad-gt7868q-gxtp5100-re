# -*- coding: utf-8 -*-
"""正确做法：
 ① 先标定 Thumb 判据（固定窗口，随机 vs 真代码）
 ② 用【连续向量表】签名定位 Cortex-M 代码段（≥16 连续 word：bit0=1 且落在同段内）
"""
import struct, collections, os
from capstone import *
md=Cs(CS_ARCH_ARM, CS_MODE_THUMB|CS_MODE_MCLASS)
def sweep(b,off,win=0x800):
    seg=b[off:off+win]; nxt=0; ok=0
    for ins in md.disasm(seg,0):
        if ins.address!=nxt: break
        nxt+=ins.size; ok+=1
    return nxt/win*100            # 已消费字节比例
print("="*94); print("① 判据标定（固定窗口 0x800）"); print("="*94)
tf=open("<WORKSPACE>",'rb').read()
samples=[("TF100A 真 Thumb 代码 @0x8000",tf[0x8000:0x8800]),
         ("TF100A @0x9000",tf[0x9000:0x9800]),
         ("random",os.urandom(0x800)),
         ("random2",os.urandom(0x800)),
         ("全 0", bytes(0x800)), ("全 0xFF", b"\xff"*0x800),
         ("文本", ("hello world "*70).encode()[:0x800]),
         ("英文清单", b"".join(b"item %d\n"%i for i in range(120))[:0x800])]
for nm,s in samples:
    if len(s)<0x800: s=s+s[:0x800-len(s)]
    nxt=0;ok=0
    for ins in md.disasm(s,0):
        if ins.address!=nxt: break
        nxt+=ins.size; ok+=1
    print("  %-28s 消费 %5.1f%%  (%.1f%% 若含向量表起始)"%(nm,nxt/0x800*100,ok*2/0x800*100))
print()
print("="*94); print("② 向量表签名定位（连续 ≥16 个 word：bit0=1 且目标落在同段）"); print("="*94)
FW={"GT7867 MARSEI":"<WORKSPACE>",
    "GT7936L BERLIN":"vendor/goodix-lvfs/GT7936L_16753412.bin",
    "GT7986P BERLIN":"<WORKSPACE>",
    "TF100A(对照,真代码)":"<WORKSPACE>"}
info={}
for nm,p in FW.items():
    b=open(p,'rb').read()
    best=[]
    for o in range(0,len(b)-0x100,4):
        sp=int.from_bytes(b[o:o+4],'little'); rs=int.from_bytes(b[o+4:o+8],'little')
        if (sp&3) or (rs&1)==0: continue
        if not (0x1FF00000<=sp<=0x30000000): continue
        tgt=rs&~1
        if not (0<=tgt<len(b)): continue
        # 连续奇数 word 数
        k=1
        while k<64:
            w=int.from_bytes(b[o+4*k:o+4*k+4],'little')
            if (w&1)==0 or not (0<= (w&~1) < len(b)): break
            k+=1
        if k>=16: best.append((o,sp,rs,k))
    print("  %-22s 命中 %d 个候选向量表: %s"%(nm,len(best),[(hex(o),hex(sp),hex(rs),k) for o,sp,rs,k in best[:4]]))
    info[nm]=(b,best)
print()
print("="*94); print("③ 从向量表 Reset 处向后扫描，找【真代码段】起点（标定后判据）"); print("="*94)
for nm,(b,best) in info.items():
    if not best: continue
    o,sp,rs,k = best[0]
    # 从 rs 附近找最优窗口
    cand=[]
    for off in range(max(0,(rs&~1)-0x40), min(len(b)-0x800,(rs&~1)+0x40), 2):
        cand.append((sweep(b,off),off))
    cand.sort(reverse=True)
    print("  %-22s 向量表@0x%X SP=0x%08X Reset=0x%08X ; 最优代码窗口 %s"%(
        nm,o,sp,rs,[(hex(x), "%.1f%%"%c) for c,x in cand[:3]]))
    info[nm]=(b,best,cand[0][1])
print()
print("="*94); print("④ 在定位到的代码段里，搜 I²C 主机 / GPIO 特征"); print("="*94)
for nm,(b,best,cs) in info.items():
    if not cs: continue
    code=b[cs:cs+0x8000]
    ins=list(md.disasm(code,cs))
    nbytes=sum(i.size for i in ins)
    print("  --- %s 代码段 0x%X..0x%X 消费 %d B (%.1f%%) ---"%(nm,cs,cs+0x8000,nbytes,nbytes/0x8000*100))
    # movw/movt 常量
    regs={}; consts=[]
    for i in ins:
        if i.mnemonic=='movw' and len(i.operands)==2: regs[i.operands[0].reg]=i.operands[1].imm&0xFFFF
        elif i.mnemonic=='movt' and len(i.operands)==2:
            r=i.operands[0].reg
            if r in regs: consts.append((i.address,(i.operands[1].imm<<16)|regs.pop(r)))
    c=collections.Counter(v for _,v in consts)
    print("     movw/movt 常量 %d 个 distinct %d ; 外设区(0x4x/0x5x) %d 个"%(
        len(consts),len(c),sum(1 for _,v in consts if 0x40000000<=v<0x60000000)))
    for a,v in [(a,v) for a,v in consts if 0x40000000<=v<0x60000000][:12]:
        print("        0x%08X  0x%08X"%(a,v))
    print("     top12 常量:",[(hex(v),k) for v,k in c.most_common(12)])
