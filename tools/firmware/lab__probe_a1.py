#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
载荷A 结构测绘 · 第1步：把 13 块当"扁平大数组"看，找全局的行/列结构。

已知（§19.13.2）：「16 字节/条 × 8 = 128 字节/组」在 11/11 块成立。
本脚本要回答三个还没人答过的问题：
  Q1 那个"16 B 条 × 8 = 128 B 组"在【字节级】上到底长什么样？
  Q2 13 块的 flash 地址与 type（0x01/0x02/0x03）有没有语义对应？
     type 是位索引（官方 firmware_flag & (1<<type)），0x03 = FLASH_SUBSYS_TYPE_CONFIG
     ⇒ 若0x03 块真是"配置数据"，它应该有配置该有的形态
  Q3 用官方常量去撞：0x0C000(HW_REG_ISP_ADDR) / 0x1E000(CONFIG_DATA) /
     0x04000(CPU_RUN_FROM_YS) / 0xFF00 —— 那些块里应该出现【指向自己的地址常量】
"""
import sys, os, math, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decrypt import find_container, parse_container, DATA_OFF

HERE = os.path.dirname(os.path.abspath(__file__))
K = open(os.path.join(HERE, r'..\anchor-hunt\GT7868Q_scramble_key.bin'), 'rb').read()
FW = os.path.join(HERE, r'..\..\bios-re\GT7868Q_native_fw.bin')
PH = 572


def entropy(b):
    if not b: return 0.0
    c = collections.Counter(b); n = len(b)
    return -sum(v/n*math.log2(v/n) for v in c.values())


def load_blocks(path):
    buf = open(path,'rb').read()
    o = find_container(buf); info = parse_container(buf, o)
    base = o + DATA_OFF
    out = []; off = 0
    for s in info['subsys']:
        raw = buf[base+off: base+off+s['size']]
        out.append((s, bytes(v ^ K[(i+PH) % 1024] for i, v in enumerate(raw))))
        off += s['size']
    return info, out, buf, o


def _lz(b):
    best = cur = 0
    for x in b:
        cur = cur+1 if x == 0 else 0
        if cur > best: best = cur
    return best


def main():
    info, blocks, buf, o = load_blocks(FW)
    alld = b''.join(b for _, b in blocks)
    print('='*110)
    print('Q1 · 全载荷A（%d B）的行/列结构扫描'%len(alld))
    print('='*110)
    # 假设"一行 = L 字节"，逐 L 试：按行切，看每行内部是否一致（同一行应是同类数据）
    for L in (8, 16, 32, 64, 128, 256):
        rows = [alld[i:i+L] for i in range(0, len(alld)//L*L, L)]
        # 指标：整行为零的行占比 + 行内熵的方差（结构化数据应有方差）
        zero_rows = sum(1 for r in rows if not any(r))
        ent = [entropy(r) for r in rows]
        avg = sum(ent)/len(ent)
        var = sum((e-avg)**2 for e in ent)/len(ent)
        # 相邻行相似度（同 L 对齐的行之间的逐字节相同率）
        same = sum(1 for a, b in zip(rows, rows[1:]) for x, y in zip(a, b) if x == y) / \
               max(1, (len(rows)-1)*L)
        print('  L=%4d  行数=%6d  全零行=%5.1f%%  行熵均值=%.3f 方差=%.4f  相邻行同位相同率=%.1f%%'
              % (L, len(rows), zero_rows*100.0/len(rows), avg, var, same*100))
    print()
    print('  参考：真随机同长度 —— 相邻行同位相同率应 ~0.39%（1/256）')
    print()

    print('='*110)
    print('Q2 · type / flash 地址 / 数据形态的对应')
    print('='*110)
    print('idx type flash    size    H0     零%最长0串| u16去重/32768 |16B组重复|  最常见字节 top3')
    print('-'*110)
    for s, pl in blocks:
        n = len(pl)
        c = collections.Counter(pl)
        c16 = collections.Counter(int.from_bytes(pl[i:i+2],'little') for i in range(0, n-1, 2))
        # 16B 组的重复度
        grp = collections.Counter(pl[i:i+16] for i in range(0, n-15, 16))
        rep16 = sum(v-1 for v in grp.values() if v > 1)
        tc = c.most_common(3)
        print('%3d 0x%02X 0x%05X %6d %.3f %5.1f %6d | %8d     | %6d | %s'
              % (s['idx'], s['type'], s['flash_addr'], n, entropy(pl), pl.count(0)*100.0/n,
                 _lz(pl),
                 len(c16), rep16,
                 ' '.join('0x%02X:%.1f%%' % (v, k*100.0/n) for v, k in tc)))
    print()

    print('='*110)
    print('Q3 · 官方常量在各块内的出现次数（BE+LE u16 与 u32）')
    print('='*110)
    CONSTS = (('ISP_ADDR      0x0C000', 0x0C000),
              ('CONFIG_DATA   0x1E000', 0x1E000),
              ('RUN_FROM_YS   0x04000', 0x04000),
              ('GTX8_OFF      0x0FF00', 0x0FF00),
              ('SCRATCH       0x00000', 0x00000))
    hdr = '  %-22s' % 'idx flash    type' + ''.join('%14s' % c[0].split()[0] for c in CONSTS)
    print(hdr)
    print('  ' + '-'*100)
    for s, pl in blocks:
        row = '  idx=%2d 0x%05X 0x%02X ' % (s['idx'], s['flash_addr'], s['type'])
        for name, val in CONSTS:
            pats = set()
            for w in (2, 3, 4):                    # 地址可能被存成 u16/u24/u32
                if val < (1 << (8*w)):
                    pats.add(val.to_bytes(w, 'big')); pats.add(val.to_bytes(w, 'little'))
            n = sum(pl.count(p) for p in pats)
            row += '%14s' % (n if n else '·')
        print(row)
    print()
    print('  · = 0 次。随机基线：8192 B 里 u16 命中 ~32 次、u32 ~0.1 次 ⇒')
    print('    出现几十次的常量不是"随机命中"，是【该块自己引用自己的地址】。')


def _lz(b):
    best = cur = 0
    for x in b:
        cur = cur+1 if x == 0 else 0
        if cur > best: best = cur
    return best


if __name__ == '__main__':
    main()
