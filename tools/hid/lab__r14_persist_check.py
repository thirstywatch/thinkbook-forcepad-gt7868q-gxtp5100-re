# -*- coding: utf-8 -*-
"""lab__r14_persist_check.py — 重启后一条命令验收：cfg 写入到底持不持久

背景：
  2026-10-05 第十三轮打通了 cfg 下发通道，并把两个值写进 cfg 记录：
    · 记录 +0x115 = 0x00F0（触觉强度 240，出厂 120）—— 不在可读窗口内，靠手感判断
    · 记录 +0x01E = 0xAA（持久性标记，出厂 0x00）—— ★ 落在 32 B 可读窗口内，可客观读回
  现在重启一次，再跑本脚本：
    · 若 +0x1E 仍 = AA  ⇒ cfg 写入【进了 flash】⇒ 是持久设置，重启不掉
    · 若 +0x1E 变回 00  ⇒ cfg 写入【只在该次运行的 RAM 里】⇒ 重启即回出厂

用法：python lab__r14_persist_check.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _c in (HERE, os.path.join(HERE, '..', '..', '2026-10-03-13-21-08',
                              'thinkbook-forcepad-haptics-re', 'tools', 'hid')):
    if os.path.isdir(_c):
        sys.path.insert(0, os.path.abspath(_c))
from gxmem import Gx                       # noqa: E402

MARK_OFF = 0x1E                            # 标记在【记录】中的偏移（= 窗口内可见）
ORIG = os.path.join(HERE, 'lab__cfg_ORIGINAL_1084.bin')


def main():
    g = Gx()
    if not g.open():
        print('!! Col04 打开失败 —— 请以管理员身份跑，或确认触控板在位')
        return 1
    try:
        d, _ = g.read(0x96F8, 32)
        if not d:
            print('!! 读 0x96F8 失败')
            return 1
        d = bytes(d)
        print('cfg 窗口 32B = %s' % d.hex(' ').upper())
        print('  记录 +0x%02X = 0x%02X' % (MARK_OFF, d[MARK_OFF]))
        print()
        if d[MARK_OFF] == 0xAA:
            print('★★★ 持久！+0x1E 仍 = AA ⇒ cfg 写入【进了 flash】，重启不掉')
            print('    ⇒ +0x115 = 240 的触觉强度是【持久设置】，可以直接留着用')
        else:
            print('✗ 不持久：+0x1E = 0x%02X（期望 AA）⇒ cfg 写入【只在 RAM】，重启已回出厂'
                  % d[MARK_OFF])
            print('    ⇒ 强度也回到出厂的 120；要"每次开机都用 240"需另想办法（开机脚本重刷）')

        if os.path.exists(ORIG):
            o = open(ORIG, 'rb').read()
            diff = [(i, o[i], d[i]) for i in range(32) if o[i] != d[i]]
            print('\n  与出厂记录前 32 B 的全部差异：%s'
                  % (['0x%02X: %02X->%02X' % t for t in diff] or '无'))
            print('  （0x01/0x04 各 −1 = IC 自己的计数器，与本项目无关）')

        for a, n, l in [(0x4000, 4, 'liveness'), (0x4022, 2, 'pid'), (0x4160, 1, 'cmd')]:
            dd, _ = g.read(a, n)
            print('  0x%04X %-9s = %s' % (a, l, dd.hex(' ').upper() if dd else '<FAIL>'))
    finally:
        g.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
