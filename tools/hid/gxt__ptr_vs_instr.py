# -*- coding: utf-8 -*-
# 第十九轮 C：判别"真指针表" vs "ARM Thumb 指令被误读为 u32"
# 关键判据（本轮建立的准则）：
#  真指针表 —— 连续若干 u32 全部落在同一地址段，且低2位为0（对齐）
#  指令误读 —— 高半字(0x0800xxxx) 的成因是 thumb32 后半字 = 0xF0xx/F2xx/...
#             表现为：值的高16位固定、低16位呈 0xF?xx 分布
import struct, os
from collections import Counter

P = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
D = open(P, 'rb').read()
OUT = []
def w(s=''):
    OUT.append(s)

w("="*78)
w("判别：真指针表 vs 指令误读（第十九轮 C）")
w("="*78)

# ---------- 判据 1：低 2 位对齐率 ----------
w()
w("### 1. 对齐率检验")
flash = []
for i in range(len(D) - 3):
    v = struct.unpack_from('<I', D, i)[0]
    if 0x08000000 <= v < 0x08200000:
        flash.append(v)
w("  全文件 u32 落在 Flash 段: %d 个" % len(flash))
lo = Counter(v & 3 for v in flash)
w("  低2位分布: %s" % dict(lo))
w("  -> 真指针应 100%% 落在 low2==0（ARM 4字节对齐）")
al = sum(1 for v in flash if (v & 3) == 0)
w("  实际 low2==0: %d / %d = %.3f" % (al, len(flash), al / len(flash)))

# ---------- 判据 2：高16位分布 ----------
w()
w("### 2. 高 16 位分布（真指针应集中在 0x0800-0x0802）")
hi = Counter(v >> 16 for v in flash)
for h, n in hi.most_common(15):
    w("    0x%04X  x%d" % (h, n))

# ---------- 判据 3：低16位分布 ----------
w()
w("### 3. 低 16 位分布（真指针应较均匀；指令误读会集中在 F0/F2/xxF0）")
low = Counter(v & 0xFFFF for v in flash)
for l, n in low.most_common(20):
    w("    0x%04X  x%d" % (l, n))

# ---------- 判据 4：字节级 —— 是不是 (xx xx F0 0x08) 型 ----------
w()
w("### 4. 字节模式：真指针字节序应为 lo lo hi hi，其中 hi-hi = 08 08 或 08 08/08 08")
c = Counter()
for i in range(len(D) - 3):
    b = D[i:i+4]
    if b[2] == 0x08 and b[3] == 0x08:
        c['xx xx 08 08'] += 1
w("  'xx xx 08 08' 型（=真指针）: %d" % c['xx xx 08 08'])
# thumb32 常见: F0 xx / F2 xx 作为第二半字 => 存成 (xx F0 xx 08)? 不，需看实际
w()
w("### 5. 对照：ARM Thumb 32位指令常见编码 0xF0xx / 0xF2xx / 0xF8xx 作为任一位置的计数")
for pat in [0xF000, 0xF200, 0xF800, 0xF400, 0xF600, 0xF100, 0xF300]:
    n = sum(1 for i in range(len(D) - 1) if (D[i] | (D[i+1] << 8)) == pat)
    w("    0x%04X  x%d" % (pat, n))

# ---------- 判据 6：0x080100F2 / 0x080001F2 的真实出处 ----------
w()
w("### 6. 0x080100F2 的 149 个出现点上下文（前2字节 + 该u32 + 后2字节）")
locs = []
s = 0
tgt = struct.pack('<I', 0x080100F2)
while True:
    i = D.find(tgt, s)
    if i < 0: break
    locs.append(i); s = i + 1
w("  总数 %d" % len(locs))
for i in locs[:25]:
    a = max(0, i-2)
    w("    0x%05X: ...%s [%s] %s..." % (i,
      ' '.join('%02x' % b for b in D[a:i]),
      ' '.join('%02x' % b for b in D[i:i+4]),
      ' '.join('%02x' % b for b in D[i+4:i+8])))
w()
w("  -> 若前一字节是 0xF0/0xF1/0xF2/0xF4/0xF7/0xF8/0xE9/0xEA，则这是 thumb32 指令的第二半字")

# ---------- 判据 7：前2字节统计 ----------
w()
w("### 7. 上述 149 处，其前 2 字节的分布")
prev = Counter()
for i in locs:
    if i >= 2:
        prev[D[i-2] | (D[i-1] << 8)] += 1
for v, n in prev.most_common(15):
    w("    0x%04X  x%d" % (v, n))
w("  -> thumb32 编码规则: 第一半字高5位为 11101(0xE8xx) / 11110(0xF0xx) / 11111(0xF8xx)")

# ---------- 判据 8：真正的 0x0800xxxx 指针（过滤掉指令） ----------
w()
w("### 8. 过滤后：真指针（low2==0 且 高16位==0x0800 或 0x0801/0x0802）")
real = []
for i in range(len(D) - 3):
    v = struct.unpack_from('<I', D, i)[0]
    if 0x08000000 <= v < 0x08100000 and (v & 3) == 0:
        # 排除 thumb32 第二半字：若前一字节是 0xF0/F1/F2/F4/F6/F7/F8 则排除
        if i >= 1 and D[i-1] in (0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF6, 0xF7, 0xF8, 0xE8, 0xE9, 0xEA, 0xEB):
            continue
        real.append((i, v))
w("  过滤后真指针: %d 个" % len(real))
c = Counter(v for _, v in real)
w("  唯一地址 %d 个；>=2 次的：" % len(c))
for v, n in c.most_common(30):
    w("    0x%08X  x%-3d" % (v, n))
w()
w("  唯一地址全列表（升序，前 60）:")
for v in sorted(set(v for _, v in real))[:60]:
    w("    0x%08X -> 假设文件偏移 0x%05X" % (v, v - 0x08000000))

open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cfg_parsed', 'ptr_vs_instr.txt'), 'w', encoding='utf-8').write('\n'.join(OUT))
print('\n'.join(OUT))
