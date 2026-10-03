# -*- coding: utf-8 -*-
"""跨芯片子固件块比对矩阵 —— 找"芯片无关的通用资产"（波形库候选）"""
import os, hashlib, collections

FILES = {
 'G7868Q_2024': 'GT7868Q_2024_本机_blocks.bin',
 'G7868Q_2020': 'GT7868Q_2020_Catalog_blocks.bin',
 'GT9896':      'GT9896_blocks.bin',
 'G7863':       'GT7863_PNOR_G1_blocks.bin',
}
# 来自 REPORT.txt：flash 地址表（本机 2024 为准；跨芯片时 flash 地址可能不同）
FLASH = {
 'G7868Q_2024': [0x0FF00,0x16000,0x06000,0x08000,0x0A000,0x0C000,0x1E000,0x10000,0x01000,0x00000,0x04000,0x13000,0x12000],
}
# 块长度（字节）
LEN = [0x800,0x2000,0x2000,0x2000,0x2000,0x2000,0x2000,0x2000,0x3000,0x1000,0x2000,0x3000,0x1000]

def blocks(fn, lens):
    d = open(fn,'rb').read()
    off=0; out=[]
    for L in lens:
        out.append(d[off:off+L]); off+=L
    if off != len(d):
        print(f'  [warn] {fn}: 解析出 {off} / 文件 {len(d)}，尾部多出 {len(d)-off} B')
    return out

BL = {}
for k,fn in FILES.items():
    if not os.path.exists(fn):
        print('MISSING', fn); continue
    BL[k] = blocks(fn, LEN)
    print(f'{k:12s} {len(BL[k])} 块  总长 {sum(len(b) for b in BL[k])}')

def h(b): return hashlib.md5(b).hexdigest()

print()
print('='*100)
print('矩阵：行=块序号(按本机2024 flash序)  列=芯片   "SAME"=与本机2024逐字节相同')
print('='*100)
hdr = f'{"blk":>4} {"size":>7} {"flash":>8}  ' + ' '.join(f'{k:>10}' for k in BL)
print(hdr); print('-'*len(hdr))
for i in range(13):
    row = f'{i:>4} {LEN[i]:>7} {FLASH["G7868Q_2024"][i]:>8X}  '
    ref = BL['G7868Q_2024'][i] if 'G7868Q_2024' in BL else None
    for k in BL:
        if i >= len(BL[k]): row += f'{"-":>10} '; continue
        b = BL[k][i]
        if len(b) != len(ref): row += f'{"LEN?":>10} '
        elif b == ref: row += f'{"SAME":>10} '
        else:
            # 同长度算相似度
            same = sum(1 for x,y in zip(b,ref) if x==y)/len(b)
            row += f'{same*100:>9.1f}% '
    print(row)
