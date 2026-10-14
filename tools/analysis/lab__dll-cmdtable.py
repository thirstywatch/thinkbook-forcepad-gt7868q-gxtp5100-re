#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lab__dll-cmdtable.py —— N4：从厂商 `tpupdate_driver.dll` 里挖出【Col04 私有命令的完整清单】

背景（2026-10-14 §19.62 / §19.63）：
  · 已确认 DLL 在 `.text` 里用 `mov dword [rip+disp32], imm32`（C7 05 …）初始化一张
    「寄存器地址表 + 期望值 + 命令帧长度 + 命令字面量」的结构（基址 RVA 0x18B04）。
  · 命令帧形如 `{cmd, a1, a2, a3, cmd^a1^a2^a3}`（5 B），例如 `{33,00,00,00,33}` / `{34,00,00,00,34}`。
  · 本脚本把那个结构区**逐字节 dump**，并用 capstone 反汇编 `.text` 找**所有**写入该区的指令，
    从而还原：**DLL 一共会发哪些命令、每条命令的 5 字节载荷、以及发送函数是谁**。

⇒ 产物 = 纪律 154 需要的【Col04 命令空间 · 语义已知区】。

用法：
    python lab__dll-cmdtable.py <dll> [--base 0x18B04] [--span 0x300] [--dispatch 0x56F0]
"""
import struct, sys, os, argparse, re

try:
    import capstone
except ImportError:
    print("[FATAL] 需要 capstone"); raise SystemExit(2)


def parse_pe(d):
    e_lfanew = struct.unpack_from('<I', d, 0x3C)[0]
    nsec = struct.unpack_from('<H', d, e_lfanew + 6)[0]
    optsz = struct.unpack_from('<H', d, e_lfanew + 20)[0]
    opt = e_lfanew + 24
    magic = struct.unpack_from('<H', d, opt)[0]
    pe32p = (magic == 0x20b)
    ib = struct.unpack_from('<Q' if pe32p else '<I', d, opt + (24 if pe32p else 28))[0]
    secs, so = [], opt + optsz
    for i in range(nsec):
        e = so + i * 40
        name = d[e:e + 8].rstrip(b'\0').decode('latin1')
        vsz, va, rsz, ra = struct.unpack_from('<IIII', d, e + 8)
        secs.append(dict(name=name, va=va, vsz=vsz, raw=ra, rsz=rsz))
    return dict(ib=ib, secs=secs)


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


def hexdump(data, rva0, width=16):
    out = []
    for i in range(0, len(data), width):
        chunk = data[i:i + width]
        hx = " ".join("%02X" % c for c in chunk)
        asc = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
        out.append("  %06X  %-47s  %s" % (rva0 + i, hx, asc))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dll")
    ap.add_argument("--base", type=lambda x: int(x, 0), default=0x18B04)
    ap.add_argument("--span", type=lambda x: int(x, 0), default=0x300)
    ap.add_argument("--dispatch", type=lambda x: int(x, 0), default=0x56F0)
    args = ap.parse_args()

    d = open(args.dll, 'rb').read()
    pe = parse_pe(d)
    print("=" * 86)
    print("N4 · Col04 私有命令清单 —— %s（%d B）" % (os.path.basename(args.dll), len(d)))
    print("镜像基址 0x%X · 段：" % pe['ib'] + " ".join("%s@0x%X" % (s['name'], s['va']) for s in pe['secs']))
    print("=" * 86)

    # ---------- 1) dump 结构区 ----------
    off = rva2off(pe, args.base)
    print("\n[1] 结构区 dump  RVA 0x%X .. 0x%X" % (args.base, args.base + args.span))
    if off is None:
        print("  ✘ RVA 不在任何段内")
    else:
        print(hexdump(d[off:off + args.span], args.base))

    # ---------- 2) 反汇编 .text，找所有写入结构区的指令 ----------
    text = next((s for s in pe['secs'] if s['name'] == '.text'), None)
    if not text:
        print("\n✘ 没有 .text 段"); return
    code = d[text['raw']:text['raw'] + text['rsz']]
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True

    lo, hi = args.base, args.base + args.span
    base_lo, base_hi = args.base, args.base + args.span

    print("\n[2] 写入结构区（RVA 0x%X–0x%X）的指令" % (base_lo, base_hi))
    hits, ptr_hits = [], []
    for ins in md.disasm(code, text['va']):
        for op in ins.operands:
            if op.type != capstone.x86.X86_OP_MEM:
                continue
            if op.mem.base != capstone.x86.X86_REG_RIP:
                continue
            tgt = ins.address + ins.size + op.mem.disp
            if base_lo <= tgt < base_hi:
                imm = None
                if len(ins.operands) >= 2 and ins.operands[1].type == capstone.x86.X86_OP_IMM:
                    imm = ins.operands[1].imm & 0xFFFFFFFF
                hits.append((ins.address, tgt, op.size, imm, ins.mnemonic, ins.op_str))
            # 顺带记录：把结构区地址【当常量取用】的（lea/mov reg, imm —— 绝对地址引用的变体）
        # 找 lea/mov reg, [rip+d] 指向结构区（非 RIP 情形上面已覆盖）

    # 也扫一遍"绝对地址常量"出现在 .text 里的情况（有些编译器用 mov reg, imm64）
    for m in re.finditer(rb'\x48\xB8' + re.escape(struct.pack('<Q', 0x140000000 + args.base))[:4], code):
        ptr_hits.append(off2rva(pe, text['raw'] + m.start()))

    if not hits:
        print("  （无 RIP 相对写指令命中 —— 结构可能是【只读常量】，见 [1] 的 dump）")
    for a, tgt, size, imm, mn, ops in sorted(hits, key=lambda x: x[1]):
        print("  RVA 0x%06X → 0x%06X  size=%d  %-5s %s%s" % (
            a, tgt, size, mn, ops, ("   imm=0x%08X" % imm) if imm is not None else ""))

    # ---------- 3) 从 dump 里解剖"命令帧" ----------
    print("\n[3] 命令帧候选（5 字节，末字节 == 前 4 字节 XOR）")
    if off is not None:
        blob = d[off:off + args.span]
        # 结构里帧的起点：先找"看起来像 {cmd,0,0,0,cmd}"的 5 元组
        found = set()
        for i in range(len(blob) - 4):
            f = blob[i:i + 5]
            if f[1] == 0 and f[2] == 0 and f[3] == 0 and f[4] == f[0] and f[0] != 0:
                if i not in found:
                    found.add(i)
                    print("   @+0x%03X  RVA 0x%06X  帧 = %s   (cmd=0x%02X)" % (
                        i, args.base + i, " ".join("%02X" % c for c in f), f[0]))
        if not found:
            print("  （未找到 {cmd,0,0,0,cmd} 形态 —— 帧可能不在该区、或首字节非 cmd）")

    # ---------- 4) 找调用派发器的所有点 ----------
    print("\n[4] 调用派发器（RVA 0x%X）的位置" % args.dispatch)
    calls = []
    for ins in md.disasm(code, text['va']):
        if ins.mnemonic.startswith('call') and ins.op_str.strip():
            try:
                t = int(ins.op_str.strip(), 16)
            except ValueError:
                continue
            if t == args.dispatch:
                calls.append(ins.address)
    if not calls:
        print("  （无直接 call —— 可能通过 rcx 之外的路径、或 thunk）")
    for a in calls:
        # 打印前 24 条指令，便于人工看 payload 构造
        start = max(text['va'], a - 0x90)
        print("\n  ── 调用点 RVA 0x%06X（上下文）──" % a)
        for ins in md.disasm(d[rva2off(pe, start):rva2off(pe, a + 6)], start):
            mark = " <<< call" if ins.address == a else ""
            print("     0x%06X  %-6s %s%s" % (ins.address, ins.mnemonic, ins.op_str, mark))

    # ---------- 5) 非标准段 ----------
    print("\n[5] 非标准段")
    for s in pe['secs']:
        if not s['name'].startswith(('.text', '.data', '.rdata', '.pdata', '.xdata', '.reloc')):
            o = s['raw']
            print("  段 %-8s RVA 0x%06X  size=%d" % (s['name'], s['va'], s['rsz']))
            print(hexdump(d[o:o + min(s['rsz'], 0x80)], s['va']))

    print("\n完成。")


if __name__ == "__main__":
    main()
