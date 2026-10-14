#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lab__dll-find-global-xref.py —— 找 DLL 里【读/写某组全局变量】的指令

用途（2026-10-14）：`tpupdate_driver.dll` 用
    mov dword ptr [rip+disp32], imm32        (C7 05 dd dd dd dd ii ii ii ii)
在启动时初始化一张【寄存器地址表】。本脚本：
  1) 先把那张表的**目标全局 RVA** 正确解析出来（RVA = 指令RVA + 指令长 + disp32）
  2) 再扫 `.text` 里**所有** RIP 相对内存操作数，找出**读写这些全局**的指令
  3) 打印命中处的反汇编上下文 ⇒ 从而拿到"真正使用这些地址的函数"

用法：python lab__dll-find-global-xref.py <dll> [--window 0x600 0x900] [--ctx 40]
"""
import struct, os, sys, argparse

# Windows 控制台默认 GBK：打印 emoji / 生僻字会让 print 抛 UnicodeEncodeError（2026-10-14 实测）
try:  # 只把不可编码字符降级为 '?'，不改变可读内容
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

try:
    import capstone
except ImportError:
    print("[FATAL] 需要 capstone"); raise SystemExit(2)


def parse_pe(d):
    pe = struct.unpack_from('<I', d, 0x3C)[0]
    nsec = struct.unpack_from('<H', d, pe + 6)[0]
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dll")
    ap.add_argument("--window", nargs=2, default=["0x600", "0x900"])
    ap.add_argument("--ctx", type=int, default=40)
    a = ap.parse_args()
    lo, hi = int(a.window[0], 0), int(a.window[1], 0)

    d = open(a.dll, 'rb').read()
    pe = parse_pe(d)
    print("### %s  (%d B, base=0x%X)" % (os.path.basename(a.dll), len(d), pe['ib']))
    txt = next(s for s in pe['secs'] if s['name'] == '.text')
    t0, t1 = txt['raw'], txt['raw'] + txt['rsz']

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    md.skipdata = True

    # ── 1) 抽表：窗口内所有 mov dword [rip+d], imm32
    table = []          # (insn_rva, dst_rva, imm)
    blob = d[t0:t1]
    for ins in md.disasm(blob, txt['va']):
        if ins.mnemonic != 'mov' or ins.size != 10:
            continue
        raw = d[rva2off(pe, ins.address):rva2off(pe, ins.address) + 10]
        if not (raw[0] == 0xC7 and raw[1] == 0x05):
            continue
        disp = struct.unpack_from('<i', raw, 2)[0]
        imm = struct.unpack_from('<I', raw, 6)[0]
        dst = ins.address + 10 + disp
        win = (t0 <= rva2off(pe, ins.address) <= hi)
        if win:
            table.append((ins.address, dst, imm))

    print("\n=== 表项（窗口 %s..%s，共 %d 条）===" % (a.window[0], a.window[1], len(table)))
    dst_set = {}
    for irva, dst, imm in table:
        dst_set.setdefault(dst, []).append((irva, imm))
        print("   指令RVA 0x%06X  →  全局 RVA 0x%06X (VA 0x%X)  =  0x%08X" %
              (irva, dst, pe['ib'] + dst, imm))

    # ── 2) 扫 .text 里所有 RIP 相对内存访问，找命中这些全局的
    print("\n=== 读写这些全局的指令 ===")
    hits = 0
    for ins in md.disasm(blob, txt['va']):
        for op in ins.operands:
            if op.type == capstone.x86.X86_OP_MEM and op.mem.base == capstone.x86.X86_REG_RIP:
                tgt = ins.address + ins.size + op.mem.disp
                if tgt in dst_set:
                    hits += 1
                    mw = dst_set[tgt]
                    acc = getattr(op, 'access', 0)
                    alab = "写" if acc & 2 else ("读" if acc & 1 else "?")
                    print("\n  ★ [%s] RVA 0x%06X  %-8s %-34s → 全局 0x%06X  (表项照写值 %s)"
                          % (alab, ins.address, ins.mnemonic, ins.op_str, tgt,
                             [hex(v) for _, v in mw]))
                    # 上下文
                    o = rva2off(pe, max(0, ins.address - a.ctx))
                    if o is None:
                        continue
                    print("     --- 上下文 ---")
                    for x in md.disasm(d[o:o + a.ctx * 2], max(0, ins.address - a.ctx)):
                        bs = d[rva2off(pe, x.address):rva2off(pe, x.address) + x.size].hex(' ').upper()
                        mk = " <<<" if x.address == ins.address else ""
                        print("       %06X: %-22s %-8s %s%s" % (x.address, bs, x.mnemonic, x.op_str, mk))
    print("\n命中 %d 条" % hits)
    if hits == 0:
        print("⇒ 无命中。可能：① 全局不在本模块被直接访问（有 indirection）")
        print("        ② 表下方/RVA 计算有误  ③ 访问形式不是 [rip+disp]")


if __name__ == "__main__":
    main()
