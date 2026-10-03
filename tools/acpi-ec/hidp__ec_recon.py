#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ec_recon.py -- EC 固件包（NJME*.exe）侦察
目标：找出 overlay（3.13 MB 加密+压缩 payload）是怎么被解密/解压的。

阶段 1（本脚本）：字符串/常量/资源/入口点侦察
  - Delphi 打包器识别
  - 找 "ReadFile/SetFilePointer/资源" 等IO 字符串 → 定位读 overlay 的代码
  - 找 .text 里的立即数常量（可能是密钥或magic）
  - 导出 .text 全量反汇编（capstone x86 32）供后续查找 call
"""
import re, struct, sys, collections, os

FN = 'NJME01WW.exe'
d = open(FN, 'rb').read()
pe = struct.unpack_from('<I', d, 0x3C)[0]
nsec = struct.unpack_from('<H', d, pe + 6)[0]
optsz = struct.unpack_from('<H', d, pe + 20)[0]
imgbase = struct.unpack_from('<I', d, pe + 24 + 28)[0]
sec0 = pe + 24 + optsz
print('PE @0x%X  ImageBase=0x%X  sections=%d  OptHdrSize=%d' % (pe, imgbase, nsec, optsz))

secs = {}
for i in range(nsec):
    q = sec0 + i * 40
    name = d[q:q + 8].rstrip(b'\x00').decode('latin1')
    vsz, va, rsz, ra = struct.unpack_from('<IIII', d, q + 8)
    secs[name] = (va, vsz, ra, rsz)
    print('  %-8s VA=0x%08X VS=0x%06X RawOff=0x%06X RawSz=0x%06X'
          % (name, va, vsz, ra, rsz))

TEXT_RA = secs['.text'][2]
TEXT_SZ = secs['.text'][3]
text = d[TEXT_RA:TEXT_RA + TEXT_SZ]
TEXT_VA = imgbase + secs['.text'][0]

# ---------------------------------------------------------------- 1. 字符串
print('\n' + '=' * 88)
print('1) .text 里的 ASCII 字符串（>=5），按"可能与 IO/加密相关"分组')
print('=' * 88)
strs = [(m.start() + TEXT_RA, m.group().decode('latin1'))
        for m in re.finditer(rb'[\x20-\x7e]{5,}', text)]


def show(title, pred, limit=40):
    print('\n--- %s ---' % title)
    n = 0
    for off, s in strs:
        if pred(s):
            print('   file 0x%06X  VA 0x%08X  %r' % (off, TEXT_VA + off - TEXT_RA, s[:80]))
            n += 1
            if n >= limit:
                print('   ... (truncated)')
                break
    if n == 0:
        print('   (none)')


show('文件/IO', lambda s: any(k in s for k in
     ('File', 'file', 'Read', 'Write', 'Seek', 'Stream', 'Path', '.bin', '.ec', 'tmp')))
show('压缩/加密', lambda s: any(k in s.lower() for k in
     ('lzma', 'compress', 'decompress', 'crypt', 'cipher', 'xor', 'zlib', 'unpack')))
show('EC/固件相关', lambda s: any(k in s.lower() for k in
     ('ec ', 'ec_', ' ec', 'firmware', 'flash', 'bios', 'embed', 'embed', 'ecfw', 'keyboard')))
show('进度/UI', lambda s: any(k in s for k in
     ('%', 'Progress', 'Label', 'Caption', 'Button', 'Error', 'Success', 'Version')))

# ---------------------------------------------------------------- 2. 资源
print('\n' + '=' * 88)
print('2) .rsrc 里有什么（Delphi 常把 payload 放RCDATA）')
print('=' * 88)
rva, rvsz, rra, rrsz = secs['.rsrc']
rsrc = d[rra:rra + rrsz]
# 资源目录树：找 RCDATA 类型
for m in re.finditer(rb'[\x20-\x7e]{6,}', rsrc):
    print('   str @rsrc+0x%04X  %r' % (m.start(), m.group()[:60]))
# 打印资源目录头
print('   资源目录前 64B:', rsrc[:64].hex(' '))

# ---------------------------------------------------------------- 3. 立即数常量
print('\n' + '=' * 88)
print('3) .text 里的 4 字节立即数候选（可能密钥/魔数），按出现次数排序')
print('=' * 88)
imm = collections.Counter()
for i in range(len(text) - 4):
    v = struct.unpack_from('<I', text, i)[0]
    if v == 0:
        continue
    imm[v] += 1
# 只看既不是小值、又不是地址（imgbase..imgbase+size）的
lo, hi = imgbase, imgbase + 0x60000
cand = [(v, c) for v, c in imm.items()
        if 0x10000 < v < 0xF0000000 and not (lo <= v <= hi) and c >= 3]
cand.sort(key=lambda t: -t[1])
print('   候选数（>=3 次）:', len(cand))
for v, c in cand[:30]:
    print('   0x%08X  x%d' % (v, c))

# ---------------------------------------------------------------- 4. 入口点
print('\n' + '=' * 88)
print('4) 入口点与 Delphi 初始化')
print('=' * 88)
ep = struct.unpack_from('<I', d, pe + 24 + 16)[0]
print('   AddressOfEntryPoint RVA=0x%X  VA=0x%X' % (ep, imgbase + ep))
eprva = ep
epoff = TEXT_RA + (eprva - secs['.text'][0])
print('   入口点处 32B:', d[epoff:epoff + 32].hex(' '))
# Delphi 入口通常是 push ebp/mov ebp,esp 或 jmp 到 _start
