#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lab__dll-who-touches.py —— 多路搜索"谁碰了某个 RVA 区间"

动机（2026-10-14）：
  `tpupdate_driver.dll` 里有两条分支在 RVA `0x18B04` 起写一个 **寄存器地址结构体**（~0x110 B）。
  但只扫 RIP 相对寻址时**只找到写、零读** ⇒ 说明读取走了**间接寻址**（取基址指针）。
  本脚本三路并查：
    A) RIp 相对：所有 `[rip+disp]` 指向该区间（含 lea/mov/算术）
    B) 绝对地址常量：在 .data/.rdata 里搜该区间的 RVA(4B) / VA(8B)
    C) 重定位表：`.reloc` 里指向该区间的条目（证明"这里有绝对地址")

用法：python lab__dll-who-touches.py <dll> <base_rva> [size]
"""
import struct, os, sys

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


def main():
    dll = sys.argv[1]
    base = int(sys.argv[2], 0)
    size = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x110
    d = open(dll, 'rb').read()
    pe = parse_pe(d)
    lo, hi = base, base + size
    print("### %s  目标区间 RVA 0x%X..0x%X (VA 0x%X..0x%X)"
          % (os.path.basename(dll), lo, hi, pe['ib'] + lo, pe['ib'] + hi))

    # ── A) RIP 相对
    print("\n=== A) RIP 相对寻址指向该区间 ===")
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    md.skipdata = True
    txt = next(s for s in pe['secs'] if s['name'] == '.text')
    n = 0
    for ins in md.disasm(d[txt['raw']:txt['raw'] + txt['rsz']], txt['va']):
        for op in ins.operands:
            if op.type == capstone.x86.X86_OP_MEM and op.mem.base == capstone.x86.X86_REG_RIP:
                t = ins.address + ins.size + op.mem.disp
                if lo <= t < hi:
                    n += 1
                    print("   RVA 0x%06X  %-8s %-40s -> 0x%06X" % (ins.address, ins.mnemonic, ins.op_str, t))
    print("   共 %d 条" % n)

    # ── B) 绝对地址常量（数据段里）
    print("\n=== B) 数据段里的绝对地址常量 ===")
    pat4 = struct.pack('<I', base)
    pat8 = struct.pack('<Q', pe['ib'] + base)
    found = 0
    for s in pe['secs']:
        if s['name'] not in ('.data', '.rdata', '_RDATA', '.gxfg', '.pdata'):
            continue
        blob = d[s['raw']:s['raw'] + s['rsz']]
        for name, pat in (("RVA4", pat4), ("VA8 ", pat8)):
            st = 0
            while True:
                i = blob.find(pat, st)
                if i < 0:
                    break
                print("   [%s] %-8s off=0x%06X (RVA 0x%06X)" % (name, s['name'], s['raw'] + i, off2rva(pe, s['raw'] + i)))
                found += 1
                st = i + 1
    print("   共 %d 条" % found)

    # ── C) 重定位表
    print("\n=== C) .reloc 里指向该区间的条目 ===")
    rl = next((s for s in pe['secs'] if s['name'] == '.reloc'), None)
    if not rl:
        print("   （无 .reloc）")
    else:
        blob = d[rl['raw']:rl['raw'] + rl['rsz']]
        p = 0
        cnt = 0
        base_page = 0
        while p + 8 <= len(blob):
            page_rva, blk_size = struct.unpack_from('<II', blob, p)
            if blk_size < 8:
                break
            base_page = page_rva
            for q in range(p + 8, p + blk_size - 1, 2):
                ent = struct.unpack_from('<H', blob, q)[0]
                typ = ent >> 12
                off = ent & 0xFFF
                rva = base_page + off
                if lo <= rva < hi:
                    print("   reloc type=%d  RVA 0x%06X" % (typ, rva))
                    cnt += 1
            p += blk_size
        print("   共 %d 条" % cnt)

    if n == 0 and found == 0:
        print("\n⇒ 三路都没命中。可能：该结构体在【其它模块】被访问，或访问经【双重间接】")
        print("   （如：另一个全局持有指向它的指针，而那个全局由本模块的构造函数用 reloc 写入）")


if __name__ == "__main__":
    main()
