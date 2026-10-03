# -*- coding: utf-8 -*-
"""C04. ★★ 核心发现验证: 0x01200-0x19000 是否存在 **周期 P 的位置型变换**?
已知: FW[0x8600+i] ^ FW[0x8800+i] = mask[i%4], mask = [0x20,0x02,0x04,0x80]
      -> 两个相邻 512B 块之间只差一个 4 周期位置掩码。

推论: 若整区是"同一个明文经过位置掩码 M 变换后按块交替存储"，
      则 FW[i] ^ FW[i+512] 也应 = 某个固定位置的掩码。
进一步: 若 FW[i] ^ FW[i+0x1000] 也有结构 -> 1KiB 周期。

测试清单 (先标定判据!):
 T1 FW[i] ^ FW[i+512]   看是否为固定 4 周期/512 周期掩码
 T2 FW[i] ^ FW[i+1024]  同上
 T3 FW[i] ^ FW[i+2048]
 T4 掩码是否全局一致 (在多个锚点对做同一测试)
 T5 该掩码能否把 FW 还原成"低熵/可读"文本 -> 若不能, 则是数据非代码
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
from collections import Counter
FW = load(); N = len(FW)

def xor_profile(off_a, off_b, ln):
    """返回 xor 序列的周期性质"""
    x = [FW[off_a+i] ^ FW[off_b+i] for i in range(ln)]
    uniq = len(set(x))
    # 各模周期位置上的唯一值数
    prof = {}
    for k in (1, 2, 4, 8, 16, 32, 64, 128, 256, 512):
        # 检查周期 k: x[i]==x[i+k] 的比例
        eq = sum(1 for i in range(ln-k) if x[i] == x[i+k])
        prof[k] = eq/(ln-k) if ln > k else 0
    return x, uniq, prof

print("=" * 96)
print("C04-a. ★ 相邻 512B 块的 XOR 剖面 (T1)")
print("=" * 96)
print("  基准对: 0x8600 vs 0x8800 (已知 = 纯 4 周期掩码 20 02 04 80)")
x, u, prof = xor_profile(0x8600, 0x8800, 512)
print(f"    唯一XOR值数={u}  各周期自洽率=" + " ".join(f"P{k}:{v:.3f}" for k, v in prof.items() if k <= 16))

print("\n  其它相邻对:")
for a in range(0x02000, 0x19000 - 0x1000, 0x1000):
    b = a + 512
    x, u, prof = xor_profile(a, b, 512)
    print(f"    0x{a:05X} vs 0x{b:05X}  唯一值={u:>3d}  4周期自洽={prof[4]:.3f}  "
          f"前8XOR={' '.join(f'{v:02x}' for v in x[:8])}")

print("\n" + "=" * 96)
print("C04-b. ★ 1 KiB 周期 XOR (T2): FW[i] ^ FW[i+0x1000]")
print("=" * 96)
for base in range(0x02000, 0x18000, 0x2000):
    ln = 512
    x, u, prof = xor_profile(base, base + 0x1000, ln)
    print(f"    0x{base:05X} ^ (^0x1000)  唯一值={u:>3d} 4周期自洽={prof[4]:.3f} "
          f"256周期自洽={prof[256]:.3f} 前8={' '.join(f'{v:02x}' for v in x[:8])}")

print("\n" + "=" * 96)
print("C04-c. ★ 掩码的全局一致性: 在 0x8600/0x8800 之外还有哪些对给出 P=4 掩码?")
print("=" * 96)
found = []
for a in range(0, N - 1024, 512):
    for d in (512, 1024, 2048, 4096):
        b = a + d
        if b + 64 > N: continue
        x = [FW[a+i] ^ FW[b+i] for i in range(64)]
        if len(set(x)) <= 8 and all(x[i] == x[i+4] for i in range(60)):
            found.append((a, b, d, tuple(x[:4])))
seen = set()
for a, b, d, m in found:
    key = (d, m)
    if key in seen: continue
    seen.add(key)
    print(f"    0x{a:05X} vs 0x{b:05X}  d=0x{d:X}  掩码={[hex(v) for v in m]}")
print(f"  找到 {len(found)} 个满足'64B 内 4 周期 XOR 掩码'的对; 不同(d,mask)组合 = {len(seen)}")

print("\n" + "=" * 96)
print("C04-d. ★ 用 P=4 掩码 20 02 04 80 去 '解' 0x8600 块, 看是否变低熵/可读")
print("=" * 96)
mask = [0x20, 0x02, 0x04, 0x80]
for off in (0x8600, 0x8800, 0x03800, 0x05800, 0x0F800):
    blk = FW[off:off+512]
    de = bytes(b ^ mask[i % 4] for i, b in enumerate(blk))
    print(f"    0x{off:05X} 原熵={entropy(blk):.4f} 去掩码后熵={entropy(de):.4f} "
          f"零占比 {blk.count(0)/512:.3f}->{de.count(0)/512:.3f} "
          f"可打印率 {printable_ratio(blk):.3f}->{printable_ratio(de):.3f}")
    print(f"       去掩码前16B = {' '.join(f'{b:02x}' for b in de[:16])}")

print("\n" + "=" * 96)
print("C04-e. ★★ 关键: 掩码是否作用于 '同一明文' 的不同副本? 即 A 块去掩码后 == B 块去掩码后?")
print("=" * 96)
A = FW[0x8600:0x8800]; B = FW[0x8800:0x8A00]
# B = A ^ mask  意味着 (A) 和 (B^mask) 应该相等
Bde = bytes(b ^ mask[i % 4] for i, b in enumerate(B))
print(f"  A == (B XOR mask)? {A == Bde}")
Ade = bytes(b ^ mask[i % 4] for i, b in enumerate(A))
print(f"  (A XOR mask) == B? {Ade == B}")
print(f"  即: B = A XOR mask (i%4)  -> {all(B[i] == A[i] ^ mask[i%4] for i in range(512))}")
print(f"      A = B XOR mask (i%4)  -> {all(A[i] == B[i] ^ mask[i%4] for i in range(512))}")
print(f"  => 掩码是对合的(involution), 两次变换回到原值")
