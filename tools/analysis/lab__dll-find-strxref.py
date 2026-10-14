#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lab__dll-find-strxref.py —— 找 DLL 里【引用某个字符串】的 RIP 相对指令，并反汇编上下文

用途（2026-10-14）：定位 `tpupdate_driver.dll` 里 `" [Info] CHIP = 7868Q."` 的引用点，
       从而找到【7868Q 专属命令函数】与其中的命令字节序列（= Col04 命令表）。

背景：该项目已有 `lab__dll-xref.py`（覆盖率诊断），但它只统计"有没有引用"，
       不打印**引用指令的地址**。本脚本补这一块。

用法：python lab__dll-find-strxref.py <dll> <字符串（子串）> [--ctx 80]
"""
import struct, re, sys, os, argparse

# Windows 控制台默认 GBK：打印 emoji / 生僻字会让 print 抛 UnicodeEncodeError（2026-10-14 实测）
try:  # 只把不可编码字符降级为 '?'，不改变可读内容
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

try:
    import capstone
except ImportError:
    print("[FATAL] 需要 capstone: <venv>/python -m pip install capstone"); raise SystemExit(2)


def parse_pe(d):
    pe = struct.unpack_from('<I', d, 0x3C)[0]
    mach, nsec = struct.unpack_from('<HH', d, pe + 4)
    optsz = struct.unpack_from('<H', d, pe + 4 + 16)[0]
    opt = pe + 24
    pe32p = struct.unpack_from('<H', d, opt)[0] == 0x20b
    ib = struct.unpack_from('<Q' if pe32p else '<I', d, opt + (24 if pe32p else 28))[0]
    secs = []
    so = opt + optsz
    for i in range(nsec):
        e = so + i * 40
        name = d[e:e + 8].rstrip(b'\0').decode('latin1')
        vsz, va, rsz, ra = struct.unpack_from('<IIII', d, e + 8)
        secs.append(dict(name=name, va=va, vsz=vsz, raw=ra, rsz=rsz))
    return dict(ib=ib, secs=secs, pe32p=pe32p)


def rva2off(pe, rva):
    for s in pe['secs']:
        if s['va'] <= rva < s['va'] + max(s['vsz'], s['rsz']):
            return s['raw'] + (rva - s['va'])
    return None


def off2rva(pe, off):
    for s in pe['secs']:
        if s['raw'] <= off < s['raw'] + s['rsz']:
            return s['va'] + (off - s['raw'])
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dll"); ap.add_argument("needle")
    ap.add_argument("--ctx", type=int, default=96)
    a = ap.parse_args()
    d = open(a.dll, 'rb').read()
    pe = parse_pe(d)
    print("### %s  (%d B, imagebase=0x%X)" % (os.path.basename(a.dll), len(d), pe['ib']))
    for s in pe['secs']:
        print("   %-8s va=0x%06X vsz=%-7d raw=0x%06X rsz=%d" % (s['name'], s['va'], s['vsz'], s['raw'], s['rsz']))

    nb = a.needle.encode()
    tgt_rvas = []
    st = 0
    while True:
        i = d.find(nb, st)
        if i < 0:
            break
        r = off2rva(pe, i)
        if r is not None:
            tgt_rvas.append(r)
        st = i + 1
    print("\n字符串 '%s' 出现 %d 处，RVA: %s" % (a.needle, len(tgt_rvas), [hex(x) for x in tgt_rvas]))
    if not tgt_rvas:
        return

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    md.skipdata = True

    # 只扫可执行节
    for s in pe['secs']:
        if not (s['name'] in ('.text', '.code') or (s['va'] == 0x1000 and s['rsz'] > 0)):
            continue
        blob = d[s['raw']:s['raw'] + s['rsz']]
        for ins in md.disasm(blob, s['va']):
            m = ins.mnemonic
            if m not in ('lea', 'mov'):
                continue
            if 'rip' not in ins.op_str:
                continue
            # 解析 [rip + 0xXXXX]
            mm = re.search(r'rip\s*\+\s*(0x[0-9a-fA-F]+)', ins.op_str)
            if not mm:
                continue
            disp = int(mm.group(1), 16)
            tgt = ins.address + ins.size + disp
            if tgt in tgt_rvas:
                print("\n" + "=" * 90)
                print("★ 命中：RVA 0x%06X  %-10s %s   → 指向字符串 RVA 0x%06X"
                      % (ins.address, m, ins.op_str, tgt))
                # 反汇编上下文
                lo = max(0, ins.address - a.ctx)
                hi = ins.address + a.ctx
                off = rva2off(pe, lo)
                if off is None:
                    continue
                print("--- 上下文 [0x%06X .. 0x%06X] ---" % (lo, hi))
                for x in md.disasm(d[off:off + (hi - lo)], lo):
                    mark = " <<<" if x.address == ins.address else ""
                    bs = d[rva2off(pe, x.address):rva2off(pe, x.address) + x.size].hex(' ').upper()
                    print("   %06X: %-24s %-8s %s%s" % (x.address, bs, x.mnemonic, x.op_str, mark))


if __name__ == "__main__":
    main()
