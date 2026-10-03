# -*- coding: utf-8 -*-
"""B01. 架构判定 —— 独立方法。
判据设计（先在已知样本标定，再上真实数据）：
  M1 顺序反汇编"完整指令覆盖率": 从 off 开始，Thumb 逐指令解码，统计
     成功解码字节数 / 总尝试字节数。真代码应 >0.95，数据应 <0.5。
  M2 伪指令率: udf/undefined 占比。
  M3 每条指令平均长度: Thumb-2 混合约 2.6-2.9B，纯 Thumb 16-bit 约 2.0B，
     数据<2.1（随机 16-bit 流被强行解码时长度分布不同）。
  M4 分支目标有效率: bl/b.w 的目标是否落在同区内。
标定样本:
  - 真 Thumb 代码（用固件内被证实区段）／随机数据／全 0x00／全 0xFF
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
from capstone import *
from capstone.arm import *

FW = load(); N = len(FW)

def seq_disasm(buf, base, mode, maxins=200000):
    md = Cs(CS_ARCH_ARM, mode)
    md.detail = False
    n_ok = 0; n_bad = 0; total_bytes = 0
    lens = []
    for ins in md.disasm(buf, base):
        if ins.mnemonic in ("udf", ".byte", "undefined", "invalid"):
            n_bad += 1
        else:
            n_ok += 1
            lens.append(ins.size)
        total_bytes += ins.size
        if n_ok + n_bad >= maxins: break
    return n_ok, n_bad, total_bytes, lens

def report(tag, buf, base, mode):
    ok, bad, tot, lens = seq_disasm(buf, base, mode)
    tot_i = ok + bad
    avg = (sum(lens)/len(lens)) if lens else 0
    f2 = sum(1 for l in lens if l == 2)/len(lens) if lens else 0
    f4 = sum(1 for l in lens if l == 4)/len(lens) if lens else 0
    cov = tot/len(buf) if buf else 0
    print(f"  {tag:34s} 指令={tot_i:>6d} 伪指令率={bad/tot_i if tot_i else 0:.4f} "
          f"平均长={avg:.3f} 2B占比={f2:.3f} 4B占比={f4:.3f} 字节覆盖={cov:.3f}")
    return dict(tot=tot_i, bad=bad, prate=bad/tot_i if tot_i else 0, avg=avg, f2=f2, f4=f4, cov=cov)

print("=" * 92)
print("B01-a. 判据标定（已知样本）")
print("=" * 92)
import random
rng = random.Random(42)
cal = []
cal.append(("NOP sled (真 thumb)", bytes([0x00,0xbf])*2048, 0x1000, CS_MODE_THUMB))
cal.append(("全 0x00", b"\x00"*4096, 0x1000, CS_MODE_THUMB))
cal.append(("全 0xFF", b"\xff"*4096, 0x1000, CS_MODE_THUMB))
cal.append(("随机字节", bytes(rng.randrange(256) for _ in range(4096)), 0x1000, CS_MODE_THUMB))
cal.append(("文本(ASCII)", (b"The quick brown fox jumps over the lazy dog. "*100)[:4096], 0x1000, CS_MODE_THUMB))
cal.append(("真 8051 风格: 递增字节", bytes(range(256))*16, 0x1000, CS_MODE_THUMB))
for tag, buf, base, mode in cal:
    report(tag, buf, base, mode)

print("\n" + "=" * 92)
print("B01-b. 固件真实区段")
print("=" * 92)
regions = [
    ("0x00000 (声称 8051?)", 0x00000, 0x1200),
    ("0x01200 (声称 白化)",   0x01200, 0x2000),
    ("0x08000 (声称 白化中)", 0x08000, 0x2000),
    ("0x10000 (分区长)",      0x10000, 0x2000),
    ("0x19000 (交界前)",      0x19000, 0x1000),
    ("0x19A00 (声称 ARM)",    0x19A00, 0x2000),
    ("0x1A000",              0x1A000, 0x2000),
    ("0x1B000",              0x1B000, 0x2000),
    ("0x1C000",              0x1C000, 0x2000),
    ("0x1D000",              0x1D000, 0x2000),
    ("0x1E000 (声称 ARM)",    0x1E000, 0x2000),
    ("0x1F000",              0x1F000, 0x2000),
    ("0x20000",              0x20000, 0x2000),
    ("0x22000",              0x22000, 0x2000),
    ("0x25000",              0x25000, 0x2000),
    ("0x27000 (尾部)",        0x27000, 0x75C),
]
res = {}
for tag, off, ln in regions:
    ln = min(ln, N-off)
    res[tag] = report(tag, FW[off:off+ln], off, CS_MODE_THUMB)
