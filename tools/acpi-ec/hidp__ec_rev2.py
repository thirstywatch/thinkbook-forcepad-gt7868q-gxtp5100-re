#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ec_rev2.py -- 重新审视"overlay 是加密的"这个判断。

触发：本轮在 .text 里【找不到任何 XOR/ROL/ROR 解码循环】
     （.text 146 KB 全反汇编，62,277 条指令，191 个函数，真 XOR = 0 处）
⇒ 强烈提示：payload 未必是"加密"，而可能是【别的东西】。

需要重新考虑的可能性（逐个实测，不猜）：
  H1 压缩流本身看起来像随机（高熵）—— LZMA/zlib 的合法输出就是这样
  H2是"多段拼接"，每段各自压缩 ⇒ 整体看起来随机，但没有任何变换
  H3 是 Delphi TCompressedBlockReader，但块头布局与经典版不同
  H4 有 LZMA2（cmLZMA2 存在！）—— LZMA2 支持字典复位，格式更复杂
  H5 是 xor 循环在 .itext/.didata 等其它节里（我只扫了 .text）
  H6 是"读取时边解密边解压"，循环在写入目标缓冲区时，用的不是 xor 而是 add/sub/rol

本脚本：
  A) 扫【所有节】找 xor/rol/ror 指纹（不止 .text）
  B) 在 .text 里找 add/sub 循环（另一种可能变换）
  C) 系统性地试各种单点解压：把 overlay 的每个偏移当作 LZMA/zlib 流的起点
"""
import struct, zlib, lzma, collections, sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

FN = 'NJME01WW.exe'
d = open(FN, 'rb').read()
pe = struct.unpack_from('<I', d, 0x3C)[0]
imgbase = struct.unpack_from('<I', d, pe + 24 + 28)[0]
nsec = struct.unpack_from('<H', d, pe + 6)[0]
optsz = struct.unpack_from('<H', d, pe + 20)[0]
sec0 = pe + 24 + optsz
secs = {}
for i in range(nsec):
    q = sec0 + i * 40
    nm = d[q:q + 8].rstrip(b'\x00').decode('latin1')
    vsz, va, rsz, ra = struct.unpack_from('<IIII', d, q + 8)
    secs[nm] = (va, vsz, ra, rsz)

md = Cs(CS_ARCH_X86, CS_MODE_32)
md.skipdata = True

print('=' * 90)
print('A) 扫【所有节】找 xor/rol/ror 指纹')
print('=' * 90)
for nm, (va, vsz, ra, rsz) in secs.items():
    if rsz == 0:
        continue
    body = d[ra:ra + rsz]
    ins = list(md.disasm(body, imgbase + va))
    real_xor = 0
    rol = 0
    for k, i in enumerate(ins):
        if i.mnemonic in ('rol', 'ror'):
            rol += 1
        if i.mnemonic == 'xor':
            ops = [x.strip() for x in i.op_str.split(',')]
            if len(ops) == 2 and ops[0] != ops[1]:
                # 排除 xor eax,eax / xor ecx,ecx（清零）
                if not (ops[0] == ops[1]):
                    real_xor += 1
    print('  %-8s raw=%-7d 反汇编=%-6d 真xor=%-4d rol/ror=%d'
          % (nm, rsz, len(ins), real_xor, rol))

print()
print('=' * 90)
print('B) .text 里的 add/sub 与"读-改-写"循环指纹')
print('=' * 90)
tva, tvs, tra, trs = secs['.text']
text = d[tra:tra + trs]
base = imgbase + tva
ins = list(md.disasm(text, base))
pat = collections.Counter()
for k in range(len(ins) - 2):
    a, b_, c = ins[k], ins[k + 1], ins[k + 2]
    if a.mnemonic in ('add', 'sub', 'ror', 'rol', 'imul', 'mul') \
            and b_.mnemonic == 'mov' and '[' in b_.op_str:
        pat[a.mnemonic] += 1
print('  add/sub/mul + store 的模式数:', dict(pat))

print()
print('=' * 90)
print('C) 系统性试解压：overlay 每个偏移当作流起点（只扫前 2 KB 偏移）')
print('=' * 90)
ov = d[0x2C000:]
found = []
for off in range(0, 2048):
    blob = ov[off:]
    # zlib
    for nm, fn in (('zlib', lambda b: zlib.decompress(b)),
                   ('deflate', lambda b: zlib.decompress(b, -15)),
                   ('lzma', lambda b: lzma.decompress(b, format=lzma.FORMAT_ALONE)),
                   ('xz', lambda b: lzma.decompress(b, format=lzma.FORMAT_XZ))):
        try:
            r = fn(blob)
            if len(r) > 1000:
                found.append((off, nm, len(r)))
                print('  ★ off=%-5d %-8s -> %d 字节  头 16B=%s'
                      % (off, nm, len(r), r[:16].hex(' ')))
        except Exception:
            pass
if not found:
    print('  ✘ 前 2048 个偏移里没有任何一处能直接解压成功')
    print('  ⇒ 确有前置变换（加密或自定义容器）')

print()
print('=' * 90)
print('D) 换思路：如果是"多段各自压缩"，看 overlay 里有几个 zlib 头')
print('=' * 90)
for sig, nm in ((b'\x78\x9C', 'zlib default'), (b'\x78\x01', 'zlib low'),
                (b'\x78\xDA', 'zlib best'), (b'\x1f\x8b', 'gzip'),
                (b'BZ', 'bzip2'), (b'\x5d\x00', 'LZMA')):
    hits = []
    st = 0
    while True:
        p = ov.find(sig, st)
        if p < 0:
            break
        hits.append(p)
        st = p + 1
    if hits:
        print('  %-14s 命中 %d 次: %s' % (nm, len(hits), ' '.join('0x%X' % x for x in hits[:12])))
