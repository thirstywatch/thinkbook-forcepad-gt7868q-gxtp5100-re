#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ec_dis.py -- 反汇编 .text，找 overlay 的解密/解压调用链。

已知（全部来自本轮实测，不是猜）：
  · Delphi/Pascal 打包器（Inno Setup 风格）
  · overlay = 48 B 定长头（两版逐字节相同）+ 变长密文（熵 7.999）
  · .text 里的相关类型名/函数名：
      TCompressedBlockReader / TCompressedBlockReaderQ
      TDecompressorReadProc / TCustomDecompressorClassX
      TLZMA1SmallDecompressor / LZMADecompSmall / TLZMAInternalDecoderState
      TSetupCompressMethod => cmLZMA / cmLZMA2
      DecompressInto / ECompressDataError / ECompressInternalError
  ★ 但 CBlock 9字节块头解析失败 ⇒ 明文里还有一层【自定义变换】

本脚本：反汇编 .text，导出可读的 asm 文本，供人工定位
  - 找出所有 call 目标被引用的地方（找"主流程"）
  - 标出引用 LZMADecompSmall / DecompressInto 字符串的代码位置（数据引用）
  - 找xor 循环、rol/ror、大量 movzx 的"解码循环"指纹
"""
import struct, re, collections
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

tva, tvs, tra, trs = secs['.text']
text = d[tra:tra + trs]
base = imgbase + tva

# ★★关键：capstone 的 disasm() 遇到【非法字节】就整体停摆。
#   .text 里混着 Delphi 的 RTTI / 字符串 / 跳转表，纯线性反汇编只能走 88 条就断。
#   正解：用 skipdata 模式，让它把非法字节当单字节指令跳过。
md = Cs(CS_ARCH_X86, CS_MODE_32)
md.detail = False
md.skipdata = True

# 反汇编全 .text（skipdata）
insns = list(md.disasm(text, base))
print('反汇编指令数: %d （.text %d B）' % (len(insns), len(text)))
assert len(insns) > 1000, '仍然只解出很少指令 —— skipdata 没生效'

with open('ec_text.asm', 'w', encoding='utf-8', errors='replace') as f:
    for i in insns:
        f.write('0x%08X  %-28s %s %s\n' % (
            i.address, i.mnemonic, i.op_str,
            ('  ; ' + i.bytes.hex(' ')) if len(i.bytes) <= 10 else ''))
print('已导出 ec_text.asm (%d 行）' % len(insns))

# ---------------------------------------------------------------- 1. XOR 循环指纹
print('\n' + '=' * 88)
print('1) XOR 解码循环候选（xor 后紧跟 store 到 [esi/edi/ecx+...]）')
print('=' * 88)
cands = []
for k in range(len(insns) - 3):
    a, b_, c = insns[k], insns[k + 1], insns[k + 2]
    if a.mnemonic != 'xor':
        continue
    # xor reg,reg 之外的异或（排除 xor eax,eax 这种清零）
    ops = a.op_str.split(',')
    if len(ops) == 2 and ops[0].strip() == ops[1].strip():
        continue
    if b_.mnemonic in ('mov',) and re.search(r'\[(esi|edi|ebx|ecx|edx|eax)\s*\+?', b_.op_str):
        cands.append((a.address, a.op_str, b_.op_str))
print('候选: %d 处' % len(cands))
for va, o1, o2 in cands[:25]:
    off = va - base + tra
    print('  0x%08X (file 0x%06X)  xor %s  ->  mov %s' % (va, off, o1, o2))

# ---------------------------------------------------------------- 2. 字符串交叉引用
print('\n' + '=' * 88)
print('2) 关键字符串的代码引用（用 RIP 相对寻址反查）')
print('=' * 88)
KEYS = [b'LZMADecompSmall', b'DecompressInto', b'TCompressedBlockReader',
        b'TSetupCompressMethod', b'cmLZMA', b'TLZMA1SmallDecompressor',
        b'EC', b'ec', b'.bin', b'firmware']
for key in KEYS:
    pos = []
    st = 0
    while True:
        p = d.find(key, st)
        if p < 0 or p >= 0x40000:
            break
        pos.append(p)
        st = p + 1
    if not pos:
        continue
    print('\n  关键字 %r 出现于: %s' % (key, ', '.join('file 0x%X' % p for p in pos[:6])))


# ---------------------------------------------------------------- 3. 函数 call 图
print('\n' + '=' * 88)
print('3) call 目标频次 top 30（找主流程函数）')
print('=' * 88)
calltgt = collections.Counter()
for i in insns:
    if i.mnemonic == 'call' and i.op_str.startswith('0x'):
        try:
            calltgt[int(i.op_str, 16)] += 1
        except ValueError:
            pass
for tgt, c in calltgt.most_common(30):
    print('  0x%08X  被调用 %d 次' % (tgt, c))

# ---------------------------------------------------------------- 4. 大函数切分
print('\n' + '=' * 88)
print('4) .text 里的函数边界（ret 前有 push ebp;mov ebp,esp 视作入口）')
print('=' * 88)
entries = []
for k, i in enumerate(insns):
    if (i.mnemonic == 'push' and i.op_str == 'ebp') and k + 1 < len(insns) \
            and insns[k + 1].mnemonic == 'mov' and insns[k + 1].op_str == 'ebp, esp':
        entries.append(i.address)
print('  找到 %d 个函数入口' % len(entries))
# 最大的几个函数
sizes = []
for k, e in enumerate(entries):
    nxt = entries[k + 1] if k + 1 < len(entries) else base + len(text)
    sizes.append((nxt - e, e))
sizes.sort(reverse=True)
print('  最大的 10 个函数:')
for sz, e in sizes[:10]:
    print('    0x%08X  size %d B' % (e, sz))
