# -*- coding: utf-8 -*-
"""R13-2 ★★★ 用【官方 HID 包语义】重试 cfg 下发，并用 32B 窗口直接读回校验
 假设修正：`0E 20 <cont> <seq> <本块len+5> 00 <addr16BE> <【总长】16BE> <data>`
   —— 之前 19 次都把 [8..9] 填成了"本块长度"，应该是【总长度】
 校验手段：0x96F8 可读窗口 = 32 B（刚实测），写完读回与原 cfg 前 32B 比对即可判定
"""
import sys, os, time
sys.path.insert(0, os.path.join('..', '..', '2026-10-03-13-21-08',
                                'thinkbook-forcepad-haptics-re', 'tools', 'hid'))
from gxmem import Gx

CFG = 0x96F8
CMD = 0x4160
CH = 55
body = open('orig_TB14P.bin', 'rb').read()[0x4C:0x4C + 1024]

g = Gx(); print('open', g.open())


def rd(a, n):
    d, _ = g.read(a, n); return bytes(d) if d else None


def wr(a, data, cont, seq, total):
    pkt = [0x0E, 0x20, cont, seq, (len(data) + 5) & 0xFF, 0x00,
           (a >> 8) & 0xFF, a & 0xFF,
           (total >> 8) & 0xFF, total & 0xFF] + list(data)
    return g._send(pkt)


def stream(cfg, total_mode='total', addr_mode='const'):
    n = (len(cfg) + CH - 1) // CH
    total = len(cfg) if total_mode == 'total' else None
    for i in range(n):
        blk = cfg[i * CH:(i + 1) * CH]
        cont = 0 if i == n - 1 else 1
        a = CFG if addr_mode == 'const' else CFG + i * CH
        t = total if total else len(blk)
        if not wr(a, blk, cont, i & 0xFF, t):
            return False, i
        time.sleep(0.02)
    return True, n


def ic_cycle(label, official33=False):
    """0x80 握手 → 写 → 0x83 → 读结果 → 0x7D"""
    print('\n' + '=' * 84)
    print('### %s' % label)
    print('=' * 84)
    print('  写前窗口 32B =', rd(CFG, 32).hex(' ').upper())
    d, _ = g.read(CMD, 1)
    print('  0x4160 初始 =', d.hex(' ').upper() if d else '<FAIL>')
    if official33:
        for _ in range(3):
            g.write(CMD, bytes([0x33, 0, 0, 0, 0x33])); time.sleep(0.05)
    g.write(CMD, bytes([0x80, 0, 0, 0, 0x80]))
    time.sleep(0.25)
    for _ in range(20):
        d, _ = g.read(CMD, 1)
        if d and d[0] == 0x82: break
        time.sleep(0.03)
    print('  握手回 0x82 =', (d[0] == 0x82) if d else False)
    ok, n = stream(cfg_g, total_mode=MODE_T, addr_mode=MODE_A)
    print('  流式写入 %d 块 -> %s   (总长模式=%s, 地址=%s)' % (n, ok, MODE_T, MODE_A))
    time.sleep(0.12)
    print('  ★ 写后窗口 32B =', rd(CFG, 32).hex(' ').upper())
    print('  ★ 与原 cfg[0:32] 比对 =',
          '逐字节相同 ✓✓' if rd(CFG, 32) == body[:32] else '不同 ✗')
    g.write(CMD, bytes([0x83, 0, 0, 0, 0x83]))
    time.sleep(0.10)
    res = None
    for _ in range(30):
        d, _ = g.read(CMD, 5, rounds=4, delay=0.05)
        if d and d[0] in (0x7E, 0x7F): res = bytes(d); break
        time.sleep(0.03)
    print('  0x83 后结果 =', res.hex(' ').upper() if res else '<FAIL>')
    if res and res[0] == 0x7F: print('  ★★★ 0x7F = cfg 已被接受并写入')
    elif res and res[:3] == b'\x7e\x00\x07': print('  ★★★ 7E 00 07 = 与 flash 完全一致（= 我们写对了！）')
    elif res and res[0] == 0x7E: print('  ✗ 0x7E + 错误码 %02X%02X' % (res[1], res[2]))
    g.write(CMD, bytes([0x7D, 0, 0, 0, 0x7D]))
    time.sleep(0.10)
    if official33:
        for _ in range(3):
            g.write(CMD, bytes([0x34, 0, 0, 0, 0x34])); time.sleep(0.05)
    print('  收尾后窗口 32B =', rd(CFG, 32).hex(' ').upper())


MODE_T = os.environ.get('MT', 'total')
MODE_A = os.environ.get('MA', 'const')
cfg_g = body
ic_cycle('总长=%s / 地址=%s' % (MODE_T, MODE_A))
g.close()
