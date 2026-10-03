# -*- coding: utf-8 -*-
"""正确步骤：滑动定位 Thumb 代码段 -> 找真向量表 -> 反汇编 -> 找 I²C/GPIO/0x5A"""
import struct, collections
from capstone import *
md=Cs(CS_ARCH_ARM, CS_MODE_THUMB|CS_MODE_MCLASS)
FW={
 "GT7867 MARSEI":"<WORKSPACE>",
 "GT7936L BERLIN":"vendor/goodix-lvfs/GT7936L_16753412.bin",
}
def cov(b,off,lim=0x2000):
    seg=b[off:off+lim]; nxt=0; ok=0
    for ins in md.disasm(seg,0):
        if ins.address!=nxt: break
        nxt+=ins.size; ok+=1
    return ok*2/lim*100
print("="*100)
print("① 滑动扫描找 Thumb 代码段（窗口 8 KB，步长 0x400）")
print("="*100)
info={}
for nm,p in FW.items():
    b=open(p,'rb').read()
    best=sorted(range(0,len(b)-0x2000,0x400), key=lambda o:-cov(b,o))[:3]
    print("  %-16s 最优起点: %s"%(nm,[(hex(o),"%.1f%%"%cov(b,o)) for o in best]))
    # 精扫
    o0=best[0]
    fine=sorted(range(max(0,o0-0x400),min(len(b)-0x1000,o0+0x400),2), key=lambda o:-cov(b,o))[:3]
    print("        精扫: %s"%[(hex(o),"%.1f%%"%cov(b,o)) for o in fine])
    info[nm]=(b,fine[0])
print()
print("="*100)
print("② 在代码段起点附近找真向量表（SP 字对齐且在 SRAM；Reset 指向本文件内）")
print("="*100)
for nm,(b,cs) in info.items():
    found=[]
    for o in range(max(0,cs-0x800), min(len(b)-8, cs+0x800), 4):
        sp=int.from_bytes(b[o:o+4],'little'); rs=int.from_bytes(b[o+4:o+8],'little')
        if (sp&3)==0 and 0x1FF00000<=sp<=0x30000000 and (rs&1) and 0<=rs<len(b):
            found.append((o,sp,rs))
    print("  %-16s 候选 %d 个: %s"%(nm,len(found),[(hex(o),hex(sp),hex(rs)) for o,sp,rs in found[:5]]))
print()
print("="*100)
print("③ 从代码起点反汇编 64 KB，收集 movw/movt 常量 + 0x5A/0x5B 立即数")
print("="*100)
for nm,(b,cs) in info.items():
    code=b[cs:cs+0x10000]
    ins=list(md.disasm(code,cs))
    covered=sum(i.size for i in ins)
    print("  --- %s 起点 0x%X ：%d 条指令，覆盖 %.1f%% ---"%(nm,cs,len(ins),covered/len(code)*100))
    regs={}; consts=[]
    for i in ins:
        if i.mnemonic=='movw' and len(i.operands)==2:
            regs[i.operands[0].reg]=i.operands[1].imm&0xFFFF
        elif i.mnemonic=='movt' and len(i.operands)==2:
            r=i.operands[0].reg
            if r in regs: consts.append((i.address,(i.operands[1].imm<<16)|regs.pop(r)))
    c=collections.Counter(v for _,v in consts)
    print("     movw/movt 常量 %d 个（distinct %d）"%(len(consts),len(c)))
    print("     top15:", [(hex(v),k) for v,k in c.most_common(15)])
    peri=[(a,v) for a,v in consts if 0x40000000<=v<0x60000000]
    print("     外设区(0x4x/0x5x) 常量 %d 个: %s"%(len(peri),[(hex(a),hex(v)) for a,v in peri[:20]]))
    # 所有 movs 的 imm8
    im=collections.Counter(i.operands[1].imm for i in ins
        if i.mnemonic=='movs' and len(i.operands)==2 and i.operands[1].type==1)
    print("     movs 立即数 top16:", [(v,k) for v,k in im.most_common(16)])
    for v in (0x5A,0x5B,0xB4,0xB6):
        poss=[hex(i.address) for i in ins if i.mnemonic=='movs' and len(i.operands)==2
              and i.operands[1].type==1 and i.operands[1].imm==v]
        print("     movs #0x%02X : %d 处 %s"%(v,len(poss),poss[:6]))
    print()
