# -*- coding: utf-8 -*-
"""在【明文固件】的代码段里找：I²C 主机 / GPIO 触发脉冲 / 0x5A·0x5B 立即数"""
import struct, collections, re, os
from capstone import *
md=Cs(CS_ARCH_ARM, CS_MODE_THUMB|CS_MODE_MCLASS); md.detail=True
FW={
 "GT7867 MARSEI":"<WORKSPACE>",
 "GT7936L BERLIN":"vendor/goodix-lvfs/GT7936L_16753412.bin",
 "GT7986P BERLIN":"<WORKSPACE>",
}
def find_vt(b, lo=0, hi=None):
    """找 Cortex-M 向量表：前两字为 (SP in RAM, Reset in 同段 flash)"""
    hi = hi or min(len(b), 0x40000)
    for o in range(lo, hi-8, 4):
        sp=int.from_bytes(b[o:o+4],'little'); rs=int.from_bytes(b[o+4:o+8],'little')
        if 0x1FF00000<=sp<=0x2FFFFFFF and (rs&1) and 0x00000000<=rs<=0x2FFFFFFF:
            return o,sp,rs
    return None
print("="*100)
print("① 各明文固件：容器头 / 向量表 / 代码段")
print("="*100)
info={}
for nm,p in FW.items():
    b=open(p,'rb').read()
    vt=find_vt(b)
    print("  %-16s %7d B  头: %s | %r"%(nm,len(b),b[:16].hex(' '),b[4:14]))
    if vt: print("       向量表 @0x%05X  SP=0x%08X  Reset=0x%08X"%(vt[0],vt[1],vt[2]))
    else:  print("       未找到向量表")
    info[nm]=(b,vt)
print()
print("="*100)
print("② 代码段扫描：0x5A / 0x5B / 0xB4 作为【立即数】出现多少次（含上下文）")
print("="*100)
# 立即数模式：movs rX,#imm (0x20-0x27: imm8), movw (需解码)
def imm_hits(b, val, limit=0x40000):
    hits=[]
    for off in range(0, min(len(b),limit)-4, 2):
        h=b[off:off+2]
        # movs Rd,#imm8 : 001 00 rrr iiiiiiii  → 0x20-0x27 高位
        if len(h)==2 and (h[1]&0xF8)==0x20 and h[0]==val:
            hits.append((off,'movs #0x%02X'%val))
        # adds/subs/etc 中的 imm8 太杂，先只看 movs
    return hits
for nm,(b,vt) in info.items():
    base = vt[2]&~1 if vt else 0
    d_off = base if base and base<len(b) else 0
    print("  --- %s (代码基址 0x%X) ---"%(nm,d_off))
    for v in (0x5A,0x5B,0xB4,0xB6,0x70,0x46,0x30,0x2F):
        h=imm_hits(b,v)
        print("     movs #0x%02X : %d 处 %s"%(v,len(h),[hex(x[0]) for x in h[:8]]))
print()
print("="*100)
print("③ 反汇编代码段，统计：外设基址(movw/movt 配对) / I²C 位常量 / GPIO 写")
print("="*100)
for nm,(b,vt) in info.items():
    if not vt: 
        print("  --- %s: 无向量表，跳过 ---"%nm); continue
    start=vt[2]&~1
    n=min(0x20000, len(b)-start)
    code=b[start:start+n]
    print("  --- %s  反汇编 0x%X..0x%X (%d B) ---"%(nm,start,start+n,n))
    ins=list(md.disasm(code, start))
    print("     解得指令 %d 条 ; 覆盖字节 %d/%d (%.1f%%)"%(len(ins),
          sum(i.size for i in ins), n, sum(i.size for i in ins)/n*100))
    # movw/movt 配对出的常量
    regs={}; consts=[]
    for i in ins:
        s=i.mnemonic
        if s=='movw' and len(i.operands)==2:
            regs[i.operands[0].reg]=i.operands[1].imm & 0xFFFF
        elif s=='movt' and len(i.operands)==2:
            r=i.operands[0].reg
            if r in regs:
                v=(i.operands[1].imm<<16)|regs[r]; consts.append((i.address,v)); regs.pop(r)
    c=collections.Counter(v for _,v in consts)
    print("     movw/movt 拼出的 32 位常量 %d 个，distinct %d"%(len(consts),len(c)))
    peri=[(a,v) for a,v in consts if 0x40000000<=v<0x60000000]
    print("     落在 0x4xxxxxxx/0x5xxxxxxx（外设区）的 %d 个："%len(peri))
    for a,v in peri[:25]: print("        0x%08X  0x%08X"%(a,v))
    print("     最高频 32 位常量 top15:", [(hex(v),k) for v,k in c.most_common(15)])
    # 小立即数 0x5A/0x5B 在 movs 里
    mv=collections.Counter(i.operands[1].imm for i in ins
                           if i.mnemonic in ('movs','mov','adds') and len(i.operands)==2
                           and i.operands[1].type==1)
    print("     小立即数 top12:", [(v,k) for v,k in mv.most_common(12)])
    print()
