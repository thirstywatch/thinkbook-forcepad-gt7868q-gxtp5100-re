# -*- coding: utf-8 -*-
"""用已解出的 cfg 语义词典，给 1024B 配置体做字段地图"""
import struct, collections
d=open("bios-re/GT7868Q_native_fw.bin",'rb').read()
B=d[0x4C:0x4C+1024]; T=d[0x4C+1024:0x4C+1084]
print("="*96)
print("① 语义词典（来自项目已解出的 cfg 结论 haptic_report/tag_semantic/blocks_all）")
print("="*96)
DICT={
 "时间常量(ms)":[400,600,2000,3000,5000,8000,1920,200,250,30,40,60,39,500,4000,1000,800,100,90,120,1400],
 "通道基线值":[127,128,129],
 "系数区间":[91,93,95,97,99,101,103,111],
 "ASCII 词":["vlec"],
}
for k,v in DICT.items(): print("  %-12s %s"%(k,v))
print()
print("="*96)
print("② 配置体里这些语义值出现了多少次")
print("="*96)
u8=collections.Counter(B)
le=collections.Counter(int.from_bytes(B[i:i+2],'little') for i in range(len(B)-1))
be=collections.Counter(int.from_bytes(B[i:i+2],'big')    for i in range(len(B)-1))
le4=collections.Counter(int.from_bytes(B[i:i+4],'little') for i in range(len(B)-3))
for k,vals in DICT.items():
    if k=="ASCII 词":
        for w in vals:
            print("  %-12s %-10s  出现 %d 次"%(k,repr(w),B.count(w.encode())))
        continue
    print("  --- %s ---"%k)
    print("     %-6s %s"%("值"," ".join("%-6d"%t for t in vals)))
    print("     %-6s %s"%("u8"," ".join("%-6d"%u8[t] for t in vals)))
    print("     %-6s %s"%("LE16"," ".join("%-6d"%le[t] for t in vals)))
    print("     %-6s %s"%("BE16"," ".join("%-6d"%be[t] for t in vals)))
    if max(vals)>70000: pass
    else:
        print("     %-6s %s"%("LE32"," ".join("%-6d"%le4[t] for t in vals)))
print()
print("  ★ 配置体 ASCII 可读串（≥4）")
import re
for m in re.finditer(rb"[ -~]{4,}", B):
    print("     +0x%03X  %r"%(m.start(), m.group().decode()))
print("     (60B 尾)")
for m in re.finditer(rb"[ -~]{4,}", T):
    print("     +0x%03X  %r"%(m.start(), m.group().decode()))
print()
print("="*96)
print("③ 字段地图：按 16B 行逐段列出（u8 平台 / LE16 / BE16 / 类型）")
print("="*96)
for base in range(0,1024,64):
    seg=B[base:base+64]
    kinds=[]
    # u8 平台
    i=0
    while i<len(seg):
        v=seg[i]; j=i
        while j<len(seg) and seg[j]==v: j+=1
        if j-i>=6: kinds.append("u8平台 0x%02X(%d)×%d"%(v,v,j-i))
        i=j
    # LE16 / BE16 全小值
    if len(seg)%2==0:
        lv=[int.from_bytes(seg[k:k+2],'little') for k in range(0,64,2)]
        bv=[int.from_bytes(seg[k:k+2],'big') for k in range(0,64,2)]
        if all(x<4096 for x in lv): kinds.append("LE16小值表")
        if all(x<4096 for x in bv): kinds.append("BE16小值表")
        # 递增
        nz=[x for x in lv if x!=0]
        if len(nz)>6 and all(nz[k]<=nz[k+1] for k in range(len(nz)-1)): kinds.append("LE16单调↑")
        nzb=[x for x in bv if x!=0]
        if len(nzb)>6 and all(nzb[k]<=nzb[k+1] for k in range(len(nzb)-1)): kinds.append("BE16单调↑")
    z=seg.count(0); f=seg.count(0xff)
    tag = "填0" if z>48 else ("填FF" if f>48 else ("混合" if z+f>24 else "内容"))
    print("  +0x%03X %-8s LE16:%s"%(base,tag," ".join("%-5d"%int.from_bytes(seg[k:k+2],'little') for k in range(0,64,2))))
    print("             BE16:%s"%(" ".join("%-5d"%int.from_bytes(seg[k:k+2],'big') for k in range(0,64,2))))
    if kinds: print("             ⇒ %s"%(" | ".join(kinds)))
