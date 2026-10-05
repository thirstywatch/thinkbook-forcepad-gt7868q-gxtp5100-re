# -*- coding: utf-8 -*-
"""R13-6 ★★★★★ 用 IC 当预言机扫「cfg 真实长度」
 已知：数据完整进暂存区（窗口读回 = cfg[0:32] ✓），但 0x83 回 `7E 00 02`
 ⇒ 怀疑真正要写入的长度不是 1024。逐点试 N，谁让 IC 回 `7E 00 07`（与 flash 一致）谁就是真长度。
 数据一律取【容器从 0x4C 起的连续 N 字节】（N>1024 时自然带上 60 B 尾 / 下一份副本）。
"""
import sys, os, time
sys.path.insert(0, os.path.join('..', '..', '2026-10-03-13-21-08',
                                'thinkbook-forcepad-haptics-re', 'tools', 'hid'))
from gxmem import Gx

CFG, CMD, CH = 0x96F8, 0x4160, 55
cont_img = open('orig_TB14P.bin', 'rb').read()
g = Gx(); g.open()


def rd(a, n):
    d, _ = g.read(a, n); return bytes(d) if d else None


def w1(a, data):
    pkt = [0x0E, 0x20, 0x00, 0x00, (len(data) + 5) & 0xFF, 0x00,
           (a >> 8) & 0xFF, a & 0xFF, (len(data) >> 8) & 0xFF, len(data) & 0xFF] + list(data)
    return g._send(pkt)


def try_len(N):
    data = cont_img[0x4C:0x4C + N]
    d, _ = g.read(CMD, 1)
    if not d or d[0] != 0xFF:
        time.sleep(0.3)
    g.write(CMD, bytes([0x80, 0, 0, 0, 0x80])); time.sleep(0.22)
    hs = False
    for _ in range(20):
        d, _ = g.read(CMD, 1)
        if d and d[0] == 0x82: hs = True; break
        time.sleep(0.03)
    for i in range(0, len(data), CH):
        w1(CFG + i, data[i:i + CH]); time.sleep(0.02)
    time.sleep(0.12)
    w = rd(CFG, 32)
    g.write(CMD, bytes([0x83, 0, 0, 0, 0x83])); time.sleep(0.10)
    res = None
    for _ in range(30):
        d, _ = g.read(CMD, 5, rounds=4, delay=0.05)
        if d and d[0] in (0x7E, 0x7F): res = bytes(d); break
        time.sleep(0.03)
    g.write(CMD, bytes([0x7D, 0, 0, 0, 0x7D])); time.sleep(0.10)
    ok32 = (w == cont_img[0x4C:0x4C + 32]) if w else False
    code = res.hex(' ').upper() if res else '<FAIL>'
    hit = bool(res) and (res[0] == 0x7F or res[:3] == b'\x7e\x00\x07')
    print('  N=%-5d 握手=%-5s 窗口32B正确=%-5s 结果=%-14s %s'
          % (N, hs, ok32, code, '★★★ 命中！！！' if hit else ''))
    return hit


print('扫描 cfg 真实长度（数据 = 容器 0x4C 起连续 N 字节）')
for N in (1084, 2048, 4096, 512, 256, 128):
    if try_len(N):
        break
g.close()
