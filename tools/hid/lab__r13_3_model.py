# -*- coding: utf-8 -*-
"""R13-3 ★★★★ 新模型验证：IC 内部指针【会自动递增】，但只要 cont 变一次就【重新锚定到 addr】
 铁证（第 1 轮）：19 块全是 cont=1（末块 cont=0）→ 前 18 块自增占 0..989，
   末块 cont 翻转 ⇒ 被重新锚定到 0x96F8 ⇒ 只有末块 34 B 落在偏移 0
   ⇒ 窗口读出 body[990:1024] 与实测【逐字节吻合】
 于是预测：**全部 19 块都用 cont=1、[8..9]=总长1024、addr 恒定** ⇒
   ① 偏移 0 应保持第 1 块内容 ⇒ 窗口应读回 `22 01 1B 00 3E 01 04 65 …`
   ② IC 应回 `7E 00 07`（与 flash 一致，即我们写对了）
"""
import sys, os, time
sys.path.insert(0, os.path.join('..', '..', '2026-10-03-13-21-08',
                                'thinkbook-forcepad-haptics-re', 'tools', 'hid'))
from gxmem import Gx

CFG, CMD, CH = 0x96F8, 0x4160, 55
body = open('orig_TB14P.bin', 'rb').read()[0x4C:0x4C + 1024]
g = Gx(); g.open()


def rd(a, n):
    d, _ = g.read(a, n); return bytes(d) if d else None


def wr(a, data, cont, seq, ln16, flag=0x00):
    pkt = [0x0E, 0x20, cont, seq, (len(data) + 5) & 0xFF, flag,
           (a >> 8) & 0xFF, a & 0xFF, (ln16 >> 8) & 0xFF, ln16 & 0xFF] + list(data)
    return g._send(pkt)


def cycle(tag, cont_last, ln16_mode, addr_mode='const', seq_mode='inc'):
    print('\n' + '=' * 84)
    print('### %s' % tag)
    print('=' * 84)
    print('  写前窗口 32B =', rd(CFG, 32).hex(' ').upper())
    d, _ = g.read(CMD, 1)
    print('  0x4160 =', d.hex(' ').upper() if d else '<FAIL>')
    g.write(CMD, bytes([0x80, 0, 0, 0, 0x80])); time.sleep(0.25)
    hs = None
    for _ in range(20):
        d, _ = g.read(CMD, 1)
        if d and d[0] == 0x82: hs = True; break
        time.sleep(0.03)
    print('  握手 0x82 =', bool(hs))
    n = (len(body) + CH - 1) // CH
    for i in range(n):
        blk = body[i * CH:(i + 1) * CH]
        cont = 1 if i < n - 1 else cont_last
        a = CFG if addr_mode == 'const' else CFG + i * CH
        t = len(body) if ln16_mode == 'total' else len(blk)
        sq = i & 0xFF if seq_mode == 'inc' else 0
        wr(a, blk, cont, sq, t)
        time.sleep(0.02)
    print('  已写 %d 块 (cont末块=%d, [8..9]=%s, addr=%s, seq=%s)'
          % (n, cont_last, ln16_mode, addr_mode, seq_mode))
    time.sleep(0.12)
    w = rd(CFG, 32)
    print('  ★ 写后窗口 32B =', w.hex(' ').upper() if w else '<FAIL>')
    print('  ★ 与 cfg[0:32] 比对 =', '逐字节相同 ✓✓✓' if w == body[:32] else '不同 ✗')
    # 再读一块看偏移 55 处（窗口只有 32B，做个对照）
    g.write(CMD, bytes([0x83, 0, 0, 0, 0x83])); time.sleep(0.10)
    res = None
    for _ in range(30):
        d, _ = g.read(CMD, 5, rounds=4, delay=0.05)
        if d and d[0] in (0x7E, 0x7F): res = bytes(d); break
        time.sleep(0.03)
    print('  0x83 后结果 =', res.hex(' ').upper() if res else '<FAIL>', end='  ')
    if res and res[0] == 0x7F: print('★★★ = cfg 已被接受并写入')
    elif res and res[:3] == b'\x7e\x00\x07': print('★★★ = 与 flash 完全一致（我们写对了！）')
    elif res and res[0] == 0x7E: print('（0x7E + 错误码 %02X%02X）' % (res[1], res[2]))
    else: print()
    g.write(CMD, bytes([0x7D, 0, 0, 0, 0x7D])); time.sleep(0.10)
    print('  收尾后窗口 32B =', rd(CFG, 32).hex(' ').upper())


cycle('V1: 全部 cont=1 / [8..9]=总长 / addr恒定 / seq递增', 1, 'total')
g.close()
