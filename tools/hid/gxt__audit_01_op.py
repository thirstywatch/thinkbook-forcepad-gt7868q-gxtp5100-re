# -*- coding: utf-8 -*-
"""
自查 #1：变换到底是不是 XOR？
C[i] = P[i] OP K[i % 1024]，OP 可能为 XOR / ADD / SUB / 其他
若 P 为常量填充（全 0），则：
  XOR: C = K
  ADD: C = 0 + K = K
  SUB(P-K): C = 0 - K = -K  => K = -C  (= 256-C)
  SUB(K-P): C = K - 0 = K
  ROL/ADD-chain 等非线性：常量填充段不再等于 K

结论方向：常量填充段能同时兼容 XOR/ADD/SUB(K-P)/SUB(P-K 取补)。
   所以「找到常量填充段」只能证明"存在某种周期 1024 的位置型变换"，
   不能单独区分 XOR 与 ADD。

判别实验：在**已知明文段**上重放——TF100A 明文段是已知的（未加扰），
   或者用 GT9896 与 GT7868Q 的同一 K 的不同相位。
真正可判别的办法：取两个不同固件版本（若同芯片两份固件共享 K 但明文不同），
   C1 ^ C2 = P1 ^ P2 只在 XOR 下成立；ADD 下 C1 - C2 = P1 - P2。

本脚本：先验证常量填充段在四种算子下的自洽性，再报告哪些算子不能被排除。
"""
import os

KEY = 'GT7868Q_scramble_key.bin'
RAW = None

# 原始加扰固件
CAND = [
    r'<LAB>\touchpad-lab\poc\anchor-hunt',
    r'<LAB>\touchpad-lab\poc\firmware',
    r'<LAB>\touchpad-lab\poc\fw-candidates',
    os.path.dirname(os.path.abspath(__file__)),
]

def find(name_frag, min_size=50000):
    hits = []
    for d in CAND:
        if not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            for f in files:
                if name_frag.lower() in f.lower():
                    p = os.path.join(root, f)
                    try:
                        sz = os.path.getsize(p)
                    except OSError:
                        continue
                    if sz >= min_size:
                        hits.append((sz, p))
    hits.sort(reverse=True)
    return hits

print('=== 查找原始加扰固件 ===')
for frag in ['7868', 'gt7868', 'touchpad', 'gx']:
    for sz, p in find(frag)[:6]:
        print('  %9d  %s' % (sz, p))

print()
print('=== 常量填充段兼容性矩阵 ===')
K = open(KEY, 'rb').read()
print('K 长度', len(K), '熵', end=' ')
from math import log2
from collections import Counter
c = Counter(K)
ent = -sum((v / len(K)) * log2(v / len(K)) for v in c.values())
print('%.4f' % ent, '唯一值', len(c))

# 对常量填充段 cont[0x084F0 : +1024]，检查 C 与 K 的关系
print()
print('取自证段：若 P 全 0，则不同算子下 C 与 K 的关系：')
variants = {
    'XOR  (C = 0 ^ K)': lambda k: k,
    'ADD  (C = 0 + K)': lambda k: k,
    'SUB K-P (C = K - 0)': lambda k: k,
    'SUB P-K (C = 0 - K)': lambda k: bytes((256 - b) % 256 for b in k),
}
for name, fn in variants.items():
    print('  %-22s => C == %s' % (name, 'K' if fn(bytes([1,2])) == bytes([1,2]) else '(256-K) mod 256'))

print()
print('>>> 常量填充段无法区分 XOR / ADD / SUB(K-P)。')
print('>>> 唯一能区分的是 SUB(P-K)（会得到 256-K）。')
print('>>> 要在已知明文上重放，才能定案。')
