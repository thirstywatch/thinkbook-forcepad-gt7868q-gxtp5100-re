#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lab__dll-init-table.py —— 把 DLL 里【运行时初始化的全局表】完整还原出来

已知（§19.62）：`tpupdate_driver.dll` 在 `.text` 里用 `mov dword [rip+disp32], imm32`
（C7 05 …）在启动时初始化一张「寄存器地址表」。但窗口式搜索会漏掉**其它分支/其它表**。

本脚本改为**全局扫描**：
  1) 扫 `.text` 所有 RIP 相对内存写、且源操作数是**立即数**的指令
  2) 按目标 RVA 排序、**聚类成"表"**（相邻目标 RVAs 间距 ≤ 8 视为同一张表）
  3) 每张表打印：目标 RVA、写入者指令 RVA、宽度(1/2/4)、立即数
  4) 顺带把每张表的**基址**给出来 ⇒ 便于和 §19.62 的「基址 0x18B04」对齐

用法：
    python lab__dll-init-table.py <dll> [--min-run 4]
"""
import struct, sys, os, argparse, re
from collections import defaultdict

try:
    import capstone
except ImportError:
    print("[FATAL] 需要 capstone"); raise SystemExit(2)


def parse_pe(d):
    e = struct.unpack_from('<I', d, 0x3C)[0]
    nsec = struct.unpack_from('<H', d, e + 6)[0]
    optsz = struct.unpack_from('<H', d, e + 20)[0]
    opt = e + 24
    pe32p = struct.unpack_from('<H', d, opt)[0] == 0x20b
    ib = struct.unpack_from('<Q' if pe32p else '<I', d, opt + (24 if pe32p else 28))[0]
    secs, so = [], opt + optsz
    for i in range(nsec):
        q = so + i * 40
        name = d[q:q + 8].rstrip(b'\0').decode('latin1')
        vsz, va, rsz, ra = struct.unpack_from('<IIII', d, q + 8)
        secs.append(dict(name=name, va=va, vsz=vsz, raw=ra, rsz=rsz))
    return dict(ib=ib, secs=secs)


def sec_name(pe, rva):
    for s in pe['secs']:
        if s['va'] <= rva < s['va'] + max(s['vsz'], s['rsz']):
            return s['name']
    return "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dll")
    ap.add_argument("--min-run", type=int, default=4)
    args = ap.parse_args()

    d = open(args.dll, 'rb').read()
    pe = parse_pe(d)
    text = next((s for s in pe['secs'] if s['name'] == '.text'), None)
    code = d[text['raw']:text['raw'] + text['rsz']]
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True

    writes = defaultdict(list)   # tgt_rva -> [(ins_rva, size, imm)]
    for ins in md.disasm(code, text['va']):
        if len(ins.operands) < 2:
            continue
        dst, src = ins.operands[0], ins.operands[1]
        if dst.type != capstone.x86.X86_OP_MEM or dst.mem.base != capstone.x86.X86_REG_RIP:
            continue
        if src.type != capstone.x86.X86_OP_IMM:
            continue
        tgt = ins.address + ins.size + dst.mem.disp
        writes[tgt].append((ins.address, dst.size, src.imm & ((1 << (dst.size * 8)) - 1), ins.mnemonic))

    tgts = sorted(writes)
    print("=" * 90)
    print("DLL 运行时初始化表 —— %s（%d B）" % (os.path.basename(args.dll), len(d)))
    print("共 %d 个被初始化目标，分布在 %d 张候选表" % (len(tgts), 0))
    print("=" * 90)

    # 聚类
    runs, cur = [], [tgts[0]] if tgts else []
    for t in tgts[1:]:
        if t - cur[-1] <= 8:
            cur.append(t)
        else:
            runs.append(cur); cur = [t]
    if cur:
        runs.append(cur)
    runs = [r for r in runs if len(r) >= args.min_run]

    for r in runs:
        base = r[0]
        print("\n### 表 基址 RVA 0x%06X（%s）  项数=%d  跨度=0x%X" % (
            base, sec_name(pe, base), len(r), r[-1] - base))
        print("  偏移   目标RVA     段     宽度  立即数      写入者RVA")
        for t in r:
            for (insa, size, imm, mn) in writes[t]:
                print("  +0x%03X  0x%06X  %-7s  %d    0x%0*X     0x%06X" % (
                    t - base, t, sec_name(pe, t), size, size * 2, imm, insa))

    # 摘要：所有 2/4 字节立即数，便于肉眼找"地址"
    print("\n" + "=" * 90)
    print("汇总（按目标 RVA 排序，仅 4 字节写入）")
    print("=" * 90)
    for t in tgts:
        for (insa, size, imm, mn) in writes[t]:
            if size == 4:
                print("  0x%06X [%s] = 0x%08X   ← 0x%06X" % (t, sec_name(pe, t), imm, insa))

    print("\n完成。")


if __name__ == "__main__":
    main()
