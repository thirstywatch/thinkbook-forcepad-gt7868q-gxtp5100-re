#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ec_head.py -- 攻 overlay 头部。

已知（事实，不是猜）：
  overlay 前 6 字节两版**完全相同**：7A 6C 62 1A 1A E1
  overlay[10..13] = 5D 00 23 15   ← ★★ 这很像 LZMA1 的 props(0x5D) + dictsize 起始
  overlay[14..17] = C6 DC 8D 0D   ← dictsize 续？
  两版只有 offset 6,7,9 三个字节不同
  熵 7.999；自相关无周期⇒ 不是 §19.2 那种 1024 周期 XOR

★★ 关键推理：
  offset 0x0A 起的字节 = 5D 00 23 15 C6 DC 8D 0D 49 19 28 73 67 18 A5 ...
  LZMA1 alone 格式 = [props:1][dictsize:4][uncompressed size:8]...
  props=0x5D ⇒ lc=3 lp=0 pb=2（最常见）
  dictsize = 00 23 15 C6 = 0x002315C6 = 2,305,478 （不是 2 的幂 ⇒ 不合法）
  但如果字节序是 LE： C6 15 23 00 = 0x002315C6同样
  ⇒ 也许 dictsize 是 4 字节 = C6 15 23 00?? 仍非 2 幂

  ★ 换个思路：0x0A 往后看 8 字节 = 5D 00 23 15 C6 DC 8D 0D
    若这是 LZMA header，uncompressed size = C6 DC 8D 0D 49 19 28 73 = 0x7328194 8D DC C6 = 巨大
    不合理。

  ★★ 所以：0x0A 开头的不是 LZMA header。
     那么 "5D 00" 可能只是巧合，或者它属于【加密后的密文】。

  ⇒ 反过来：若整个 overlay 是 XOR/流密码加密的密文，
     则 LZMA header（含0x5D）是被加密的 ⇒ 需要找 keystream。

  ★★ 突破口：两版只有 3 字节不同（offset 6,7,9）
     若两版用的是【同一密钥】、且明文只在少数位置不同（版本号/长度/校验），
     那么 offset 6,7,9 处的【明文】就是我们要的。
     而其余 313 万字节的密文相同率仅 0.39% ⇒ 说明【整个明文都不同】
     ⇒ **两版 payload 的明文是两份不同的固件** ⇒ 只有少量字段相同

  ⇒ 结论方向：这不是"同明文异密钥"，是"两份不同固件用同一算法加密"。
    ⇒ 找 keystream 的唯一办法：从 .text 里反出算法。
"""
import struct, collections, math

a = open('NJME01WW.exe', 'rb').read()[0x2C000:]
b = open('NJME07WW.exe', 'rb').read()[0x2C000:]

print('=' * 88)
print('1) 两版 overlay 头部逐字节对照（前 96 B）')
print('=' * 88)
print('  offA  offB   A      B     异或')
for i in range(96):
    x = a[i] ^ b[i]
    print('  %3d  %3d   %02X    %02X    %02X %s'
          % (i, i, a[i], b[i], x, '' if x == 0 else '  <== 差异'))

print()
print('=' * 88)
print('2) 找更长的公共子串（两版共有的片段 => 可能是"头/索引/常量区"）')
print('=' * 88)
n = min(len(a), len(b))
# 滑窗找公共 16B 串
w = 16
pos = collections.defaultdict(list)
for i in range(0, n - w, 4):
    pos[a[i:i + w]].append(i)
hits = []
for k, v in pos.items():
    if len(v) <= 1:
        continue
    for x in v:
        if b[x:x + w] == k:
            hits.append(x)
hits = sorted(set(hits))
print('  16B 公共子串出现位置：%d 处' % len(hits))
if hits:
    # 聚类
    groups = []
    cur = [hits[0]]
    for x in hits[1:]:
        if x - cur[-1] <= 64:
            cur.append(x)
        else:
            groups.append(cur)
            cur = [x]
    groups.append(cur)
    print('  聚成 %d 组，前 12 组:' % len(groups))
    for g in groups[:12]:
        print('     0x%06X..0x%06X  (%d 个位置, 跨度 %d B)'
              % (g[0], g[-1] + w, len(g), g[-1] - g[0] + w))

print()
print('=' * 88)
print('3) 用两版差分反推 keystream（若明文相同处，密文异或=0）')
print('=' * 88)
print('  A^B == 0 的位置数（前 100KB）:',
      sum(1 for i in range(100000) if a[i] == b[i]))
print('  ⇒ 只有 %d/100000 = %.2f%%  ⇒ 两版明文几乎处处不同'
      % (sum(1 for i in range(100000) if a[i] == b[i]),
         sum(1 for i in range(100000) if a[i] == b[i]) / 1000.0))

print()
print('=' * 88)
print('4) 检查 overlay 尾部（常见：原始长度 + CRC + 结束标记）')
print('=' * 88)
print('  A 末 64B:', a[-64:].hex(' '))
print('  B 末 64B:', b[-64:].hex(' '))
for name, buf in (('A', a), ('B', b)):
    tail = buf[-32:]
    le = struct.unpack_from('<I', tail, 0)[0]
    le2 = struct.unpack_from('<I', tail, 4)[0]
    be = struct.unpack_from('>I', tail, 0)[0]
    print('  %s 末 8B: LE32=%d/%d  BE32=%d' % (name, le, le2, be))
