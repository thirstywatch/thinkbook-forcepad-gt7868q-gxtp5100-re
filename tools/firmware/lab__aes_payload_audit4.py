# -*- coding: utf-8 -*-
"""加密判决测试：重复块的位置同余性（判定是不是 16 字节分组加密）+ 跨版本共用比例。
只读本机文件。"""
import io, os, collections

BIN = r'C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN'
PA_OFF, PA_LEN = 0x11BC, 100608

out = []
def P(s=''):
    print(s); out.append(str(s))

d = open(BIN, 'rb').read()
A = d[PA_OFF:PA_OFF + PA_LEN]

z0 = 0
while z0 < len(A) and A[z0] == 0: z0 += 1
z1 = len(A)
while z1 > 0 and A[z1 - 1] == 0: z1 -= 1
P("载荷A %d B；前导零 %d B；尾部零 %d B" % (len(A), z0, len(A) - z1))
R = A[z0:z1]
P("⇒ 疑为密文主体 = A[%d:%d] = %d 字节" % (z0, z1, len(R)))
P("   相对容器偏移 0x%X .. 0x%X" % (PA_OFF + z0, PA_OFF + z1))
P()

N = 16
blocks = [R[k:k + N] for k in range(0, len(R) - N + 1, N)]
P("按 16 字节切：%d 块" % len(blocks))
c = collections.Counter(blocks)
rep = [(b, v) for b, v in c.items() if v >= 2]
P("其中重复块：%d 个（覆盖 %d 块 = %.1f%%）"
  % (len(rep), sum(v for _, v in rep), 100.0 * sum(v for _, v in rep) / len(blocks)))
P()

P("=" * 76)
P("★ 判决：重复块出现的【块序号】是否全部同余于 16（字节偏移）")
P("=" * 76)
off16 = collections.Counter()
for idx, b in enumerate(blocks):
    if c[b] >= 2:
        off16[idx % N] += 1
P("   重复块按 (块序号 mod 16) 分布： %s" % sorted(off16.items()))
P("   ⇒ 若只有一个余数有值 ⇒ 重复严格落在 16 字节边界上 ⇒ 分组加密")
P()

P("=" * 76)
P("★ 辅证：同一块多次出现时，两次之间的字节距离是否是 16 的整数倍")
P("=" * 76)
deltas = []
for b, v in rep[:400]:
    idxs = [k for k, x in enumerate(blocks) if x == b]
    for k in range(len(idxs) - 1):
        deltas.append((idxs[k + 1] - idxs[k]) * N)
if deltas:
    good = sum(1 for x in deltas if x % 16 == 0)
    P("   采样 %d 个间距：全部为 16 的倍数 = %s ✓" % (len(deltas), good == len(deltas)))
    P("   最小间距 %d，最大 %d" % (min(deltas), max(deltas)))
    P("   间距的 2 的幂次分布： %s"
      % [(1 << k, sum(1 for x in deltas if x % (1 << k) == 0)) for k in range(10, 17)])
P()

P("=" * 76)
P("★ 同余性（按字节偏移）：所有重复块的实际字节偏移 mod 16")
P("=" * 76)
occ = collections.Counter()
for idx, b in enumerate(blocks):
    if c[b] >= 2:
        occ[idx * N % N] += 1
P("   实际偏移 mod 16 分布： %s" % sorted(occ.items()))
P()

P("=" * 76)
P("跨版本共用（全量扫描，不用抽样）")
P("=" * 76)
caps = [
    ("Cap 22001E0D", r'<WORKSPACE>'),
    ("Cap 26002816", r'<WORKSPACE>'),
]
uniq = list(c.keys())
P("   本机密文不同块总数： %d" % len(uniq))
for nm, cp in caps:
    if not os.path.exists(cp):
        P("   [缺失] %s" % nm); continue
    o = open(cp, 'rb').read()
    hitset = set()
    for b in uniq:
        if o.find(b) >= 0:
            hitset.add(b)
    P("   %-14s：不同块命中 %5d / %5d = %5.1f%%"
      % (nm, len(hitset), len(uniq), 100.0 * len(hitset) / len(uniq)))
    cov = sum(c[b] for b in hitset)
    P("              按体积算：命中块覆盖本机密文 %d 块 = %.1f%%"
      % (cov, 100.0 * cov / len(blocks)))
P()

o = r'<LAB>\touchpad-lab\re\aes_payload_audit4_out.txt'
io.open(o, 'w', encoding='utf-8').write('\n'.join(out))
print("[已写] " + o)
