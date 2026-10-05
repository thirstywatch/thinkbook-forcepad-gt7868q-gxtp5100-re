# -*- coding: utf-8 -*-
"""R7-5: 用 HID 描述符真值闭环 —— cfg 里的 X/Y 分辨率与"点数=max+1"规则
   描述符实测（poc/hid-dump.txt）: X LogicalMax=4149  Y=2147  Pressure=2000
   cfg 候选: +0x10F u16BE=4150 (=4149+1)  +0x111 u16BE=2148 (=2147+1)"""
import numpy as np, collections

DESC = {'X LogicalMax': 4149, 'Y LogicalMax': 2147, 'Pressure LogicalMax': 2000}
S = {'本机': ('orig_TB14P.bin', 0x113C), 'capA': ('cap22001E0D.Cap', 0x4F0),
     'capB': ('cap26002816.Cap', 0x4F0)}
RAW = {k: open(p, 'rb').read() for k, (p, _) in S.items()}
BODY = {k: RAW[k][:img] for k, (_, img) in S.items()}
ours = BODY['本机'][0x4C:0x4C + 1024]


def find_body(w, ref):
    wa = np.frombuffer(w, np.uint8); ra = np.frombuffer(ref, np.uint8)
    best = (0, -1.0)
    for off in range(len(wa) - 1024):
        m = float((wa[off:off + 1024] == ra).mean())
        if m > best[1]: best = (off, m)
    return best


CFG = {'本机': ours}
for k in ('capA', 'capB'):
    off, _ = find_body(BODY[k], ours)
    CFG[k] = BODY[k][off:off + 1024]

print("=" * 100)
print("### 1 ★★★ 三份样本在 +0x10F/+0x111/+0x113/+0x115 的取值")
print("=" * 100)
print(f"  {'偏移':>7} {'本机':>8} {'capA':>8} {'capB':>8}   解读")
for p in (0x10F, 0x111, 0x113, 0x115, 0x117):
    vs = [int.from_bytes(bytes(CFG[k][p:p+2]), 'big') for k in ('本机', 'capA', 'capB')]
    note = ''
    if vs[0] == DESC['X LogicalMax'] + 1: note = '★ = X LogicalMax+1'
    if vs[0] == DESC['Y LogicalMax'] + 1: note = '★ = Y LogicalMax+1'
    if vs[0] == DESC['Pressure LogicalMax'] + 1: note = '★ = Pressure LogicalMax+1'
    print(f"  +0x{p:03x}  {vs[0]:>8} {vs[1]:>8} {vs[2]:>8}   {note}")

print("\n" + "=" * 100)
print("### 2 ★★★ '点数 = LogicalMax + 1' 规则的一致性检验（全容器搜 4150/2148/2001 及其它候选）")
print("=" * 100)
for nm, v in (('X: 4149+1', 4150), ('Y: 2147+1', 2148), ('P: 2000+1', 2001),
              ('X: 4149', 4149), ('Y: 2147', 2147), ('P: 2000', 2000)):
    pat_be = v.to_bytes(2, 'big'); pat_le = v.to_bytes(2, 'little')
    for k in ('本机', 'capA'):
        d = RAW[k]
        hb = [i for i in range(len(d)-1) if d[i:i+2] == pat_be]
        hl = [i for i in range(len(d)-1) if d[i:i+2] == pat_le]
        print(f"  {nm:<12} {k:<5} u16BE@{[hex(x) for x in hb[:6]]}  u16LE@{[hex(x) for x in hl[:6]]}")

print("\n" + "=" * 100)
print("### 3 ★★ 同规则检验：cfg 里还有哪些 u16BE = '某个描述符上限 + 1' 或'合理点数'")
print("=" * 100)
# 描述符里其它逻辑上限：ContactID 15、压力 2000、X 4149、Y 2147、0x0D51=15
for nm, mx in (('ContactID 15', 15), ('Pressure 2000', 2000)):
    p_be = (mx+1).to_bytes(2, 'big'); p_be0 = mx.to_bytes(2, 'big')
    hb = [i for i in range(1023) if ours[i:i+2] == p_be]
    hb0 = [i for i in range(1023) if ours[i:i+2] == p_be0]
    print(f"  {nm}: max+1({mx+1}) u16BE@{[hex(x) for x in hb]}   max({mx}) u16BE@{[hex(x) for x in hb0]}")

print("\n" + "=" * 100)
print("### 4 ★★★ +0x100..+0x120 三份并排（看 4150/2148 的上下文 + 触发候选）")
print("=" * 100)
for p in range(0x100, 0x120, 16):
    for k in ('本机', 'capA', 'capB'):
        print(f"  {k:<5} +0x{p:03x}  " + " ".join(f"{c:02x}" for c in CFG[k][p:p+16]))
    # u16BE 解读
    for k in ('本机', 'capA'):
        vals = [int.from_bytes(bytes(CFG[k][q:q+2]), 'big') for q in range(p, p+16, 2)]
        print(f"        {k} u16BE {vals}")
    print()

print("\n" + "=" * 100)
print("### 5 ★★ 反向验证：capsule 的 3244/2016 ⇒ 该机型 LogicalMax 应为 3243/2015")
print("=" * 100)
for v in (3244, 2016):
    print(f"  capA/capB 的 u16BE {v}  ⇒ 若规则成立，其描述符 LogicalMax = {v-1}")
print("  ★ 这对值的比值 3244/2016 = %.4f；本机 4150/2148 = %.4f" % (3244/2016, 4150/2148))
print("  （X/Y 电极节距不同 ⇒ 比值 ≠ 物理长宽比，这属正常；我此前用长宽比做筛法已撤回）")

print("\n" + "=" * 100)
print("### 6 ★★★ 触发候选：紧跟 X/Y 的两项 90 / 120（压力量程 0..2000 范围内）")
print("=" * 100)
for p in (0x113, 0x115, 0x117, 0x119):
    vs = [int.from_bytes(bytes(CFG[k][p:p+2]), 'big') for k in ('本机', 'capA', 'capB')]
    print(f"  +0x{p:03x}: 本机 {vs[0]:<6} capA {vs[1]:<6} capB {vs[2]:<6}  "
          f"{'三份相同' if vs[0]==vs[1]==vs[2] else '随机型变'}")
print("  ★ 说明：压力上限 2000，故 0–2000 内的阈值都合理；90/120 是否就是 trigger，")
print("    需要「真实 cfg_bin 里的 trigger_offset 真值」或「运行时改这两个字节看行为」来定。")
