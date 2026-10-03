# -*- coding: utf-8 -*-
"""70/48 ↔ 140/98 的 2 倍关系：在配置体里严格检验"""
import struct, collections
d=open("bios-re/GT7868Q_native_fw.bin",'rb').read()
B=d[0x4C:0x4C+1024]; T=d[0x4C+1024:0x4C+1084]
W=d[0:0x4C]
def positions(buf,val,mode):
    out=[]
    if mode=='u8':
        for i,c in enumerate(buf):
            if c==val: out.append(i)
    else:
        for i in range(len(buf)-1):
            if int.from_bytes(buf[i:i+2],'little' if mode=='le' else 'big')==val: out.append(i)
    return out
print("="*96)
print("① 四个数的所有出现位置")
print("="*96)
for name,buf in [("配置体",B),("60B尾",T),("76B前导",W)]:
    print("  --- %s (%d B) ---"%(name,len(buf)))
    for v in (70,48,140,98,49,96):
        for mode in ('u8','le','be'):
            p=positions(buf,v,mode)
            if p: print("     %-4d %-3s ×%-3d @ %s"%(v,mode,len(p),[hex(x) for x in p[:14]]))
print()
print("="*96)
print("② 决定性检验：70 与 48（或 49）是否【相邻成对】出现")
print("="*96)
cands=[("LE16 70(46 00) 紧跟 LE16 48(30 00)",b'\x46\x00\x30\x00'),
       ("LE16 70 紧跟 LE16 49(31 00)",b'\x46\x00\x31\x00'),
       ("BE16 70(00 46) 紧跟 BE16 48(00 30)",b'\x00\x46\x00\x30'),
       ("BE16 70 紧跟 BE16 49",b'\x00\x46\x00\x31'),
       ("u8 70,48",b'\x46\x30'),("u8 70,49",b'\x46\x31'),
       ("u8 140,98",b'\x8c\x62'),("LE16 140,98",b'\x8c\x00\x62\x00'),
       ("LE16 140(8C 00) 紧跟 LE16 98(62 00)",b'\x8c\x00\x62\x00')]
for label,pat in cands:
    hb=[hex(i) for i in range(len(B)-len(pat)+1) if B[i:i+len(pat)]==pat]
    ht=[hex(i) for i in range(len(T)-len(pat)+1) if T[i:i+len(pat)]==pat]
    print("  %-38s 配置体:%-22s 尾:%s"%(label,hb or "无",ht or "无"))
print()
print("="*96)
print("③ 70 与 48 在配置体里的分布（看是否落在同一张表内）")
print("="*96)
def seg_of(off):
    if off<0x03B: return "头"
    if off<0x088: return "索引表区"
    if off<0x100: return "索引/填充"
    if off<0x180: return "混合参数"
    if off<0x200: return "★64项 BE16 表"
    if off<0x228: return "64项表尾"
    if off<0x280: return "混合+填充"
    if off<0x300: return "★64项 LE16 表"
    return "参数+填充"
for v,mode in [(70,'u8'),(70,'le'),(70,'be'),(48,'u8'),(48,'le'),(48,'be'),(140,'u8'),(98,'u8')]:
    p=positions(B,v,mode)
    if not p: 
        print("  %-4d %-3s : 无"%(v,mode)); continue
    c=collections.Counter(seg_of(x) for x in p)
    print("  %-4d %-3s ×%-3d : %s"%(v,mode,len(p),dict(c)))
print()
print("="*96)
print("④ 表格长度检验：64 项表里各值的分布（若 70/48 是阈值对，应在同一表里相邻或成组）")
print("="*96)
for off,ln,mode in [(0x180,128,'be'),(0x280,128,'le')]:
    seg=B[off:off+ln]
    vals=[int.from_bytes(seg[i:i+2],mode) for i in range(0,ln,2)]
    print("  +0x%03X %d 项 (%s): %s"%(off,len(vals),mode,vals))
    print("        distinct=%d  70 的位置 %s  48(49) 的位置 %s"%(
        len(set(vals)),[i for i,v in enumerate(vals) if v==70],[i for i,v in enumerate(vals) if v in (48,49)]))
