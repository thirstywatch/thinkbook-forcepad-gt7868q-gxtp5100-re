# -*- coding: utf-8 -*-
"""R8-5b: 严格判据扫真 cfg_bin（限定语料 + 快速预筛，避免超时）"""
import os, glob, string

DIRS = [
    r"<LAB>\touchpad-lab\poc\_cabs",
    r"<LAB>\touchpad-lab\poc\goodix-fw",
    r"<LAB>\touchpad-lab\poc\pkg",
    r"<LAB>\touchpad-lab\poc\anchor-hunt",
    r"<LAB>\touchpad-lab\poc\decrypt-v2",
    r"<LAB>\touchpad-lab\vendor",
    r"<LAB>\touchpad-lab\re",
    r"<LAB>\ca4f-hunt\gdix",
    r"<WORKSPACE>",
    r"<WORKSPACE>",
    r"<WORKSPACE>",
]
EXT = ('.cab', '.Cap', '.cap', '.exe', '.EXE', '.bin', '.BIN', '.efi', '.ffs', '.dat', '.cfg')

FILES = []
for R in DIRS:
    if not os.path.isdir(R):
        continue
    for dp, dn, fn in os.walk(R):
        for f in fn:
            if f.endswith(EXT):
                p = os.path.join(dp, f)
                try:
                    sz = os.path.getsize(p)
                    if 2000 < sz < 3_000_000:
                        FILES.append((p, sz))
                except Exception:
                    pass
FILES = sorted(set(FILES))
print(f"语料 {len(FILES)} 个文件（限 <3MB）")


def check(b, off):
    size = int.from_bytes(b[off:off + 4], 'little')
    if size < 200 or off + size > len(b):
        return None
    if b[off + 4] != (sum(b[off + 5:off + size]) & 0xFF):
        return None
    pn = b[off + 9]
    if not (1 <= pn <= 16):
        return None
    need = 16 + 2 * pn
    if need + 2 > size:
        return None
    offs = [int.from_bytes(b[off + 16 + 2 * i: off + 18 + 2 * i], 'little') for i in range(pn)]
    if any(o >= size or o < need for o in offs):
        return None
    if any(offs[i] >= offs[i + 1] for i in range(pn - 1)):
        return None
    ics = []
    for o in offs:
        t = b[off + o + 4: off + o + 19].split(b'\0')[0]
        if sum(1 for c in t if 48 <= c <= 122) < 3:
            return None
        ics.append(t.decode('latin-1'))
    return dict(size=size, pn=pn, offs=offs, ics=ics, ver=b[off + 5:off + 9].hex(' '))


n = 0; hits = 0
for p, sz in FILES:
    try:
        b = open(p, 'rb').read()
    except Exception:
        continue
    n += 1
    for off in range(0, len(b) - 200):
        r = check(b, off)
        if r:
            hits += 1
            print(f"\n★★★ 真 cfg_bin: {p}\n     @0x{off:x} size={r['size']} pkg={r['pn']} ver={r['ver']} "
                  f"ic={r['ics']} offs={[hex(x) for x in r['offs']]}")
    if n % 40 == 0:
        print(f"  ...已扫 {n}/{len(FILES)}")
print(f"\n=== 读入 {n} 个文件；严格判据命中 {hits} ===")
if not hits:
    print("  ⇒ 本机语料里【没有】真实 cfg_bin ⇒ x/y/trigger_offset 真值拿不到")
