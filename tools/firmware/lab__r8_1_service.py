# -*- coding: utf-8 -*-
"""R8-1: 挖汇顶 Windows 服务程序 —— 它是 x_res_offset/trigger_offset 的真正消费者
   ① 提 ASCII/UTF-16 字符串找关键字  ② 在 EXE 内找【内嵌的 cfg_bin】（若有 ⇒ 拿到三个 offset 真值）"""
import re, os, struct

CAND = [
    r"<LAB>\touchpad-lab\poc\_cabs\ex_a\GdixTouchpadService.exe",
    r"<LAB>\touchpad-lab\poc\_cabs\ex_a\GdixTouchpadServiceHelper.exe",
    r"<LAB>\touchpad-lab\poc\_cabs\ex_b\GdixTouchpadService.exe",
    r"<LAB>\touchpad-lab\poc\_cabs\ex_b\GdixTouchpadServiceHelper.exe",
]

KEY = re.compile(rb"cfg|trigger|res_offset|resolution|yellowstone|normandy|marsei|berlin|\.bin|goodix|slave|haptic|vibr|force|press", re.I)


def strings_ascii(b, n=5):
    return [m.group() for m in re.finditer(rb"[\x20-\x7e]{%d,}" % n, b)]


def strings_utf16(b, n=5):
    return [m.group()[::2] for m in re.finditer(rb"(?:[\x20-\x7e]\x00){%d,}" % n, b)]


def find_cfgbin(b):
    """按官方 cfg_bin 头找内嵌文件：u32(LE)==后续可用长度 且 checksum==Σ[5:]&0xFF"""
    hits = []
    for off in range(0, len(b) - 32):
        bl = int.from_bytes(b[off:off + 4], 'little')
        if bl < 200 or bl > 200_000:
            continue
        if off + bl > len(b):
            continue
        if b[off + 4] != (sum(b[off + 5:off + bl]) & 0xFF):
            continue
        pn = b[off + 9]
        if not (1 <= pn <= 32):
            continue
        hits.append((off, bl, pn))
    return hits


for p in CAND:
    if not os.path.exists(p):
        print(f"[跳过] {p}"); continue
    b = open(p, 'rb').read()
    print("=" * 100)
    print(f"### {os.path.basename(p)}  ({len(b)} B)  目录 = {os.path.basename(os.path.dirname(p))}")
    # 是否 .NET
    net = b"mscoree.dll" in b or b"BSJB" in b
    print(f"  .NET 程序集? {net}   ('BSJB' 签名 @ {b.find(b'BSJB')})")
    # 内嵌 cfg_bin
    cb = find_cfgbin(b)
    print(f"  ★ 内嵌 cfg_bin 命中: {[(hex(o), s, f'pkg={n}') for o, s, n in cb[:10]]}")
    # 字符串
    sa = strings_ascii(b)
    su = strings_utf16(b)
    for tag, ss in (("ASCII", sa), ("UTF16", su)):
        k = sorted({s.decode('latin-1') for s in ss if KEY.search(s) and len(s) < 90})
        print(f"  --- {tag} 关键字命中 {len(k)} 条（前 40）---")
        for s in k[:40]:
            print(f"      {s}")
