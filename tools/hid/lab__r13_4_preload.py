# -*- coding: utf-8 -*-
"""R13-4 ★★★★★ 关键判定：暂存区能否用【已验证可行的单块写】预装，
                 然后只靠 0x80/0x83/0x7D 让 IC 自己去比对/提交
 已证事实：非 cfg 模式下，单块写(cont=0, [4]=本块len+5, [8..9]=本块len, 地址递增) 100% 生效
 本轮：① 先把原 cfg 1024 B 原样写进 0x96F8（读 32B 窗口校验）→ ② 再 0x80→0x83→0x7D
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


def wr(a, data, cont=0, seq=0):
    pkt = [0x0E, 0x20, cont, seq, (len(data) + 5) & 0xFF, 0x00,
           (a >> 8) & 0xFF, a & 0xFF, (len(data) >> 8) & 0xFF, len(data) & 0xFF] + list(data)
    return g._send(pkt)


print('步骤 0：写前窗口 32B =', rd(CFG, 32).hex(' ').upper())
print('\n步骤 1：非 cfg 模式，用 19 个单块把原 cfg 写进 0x96F8（地址递增）')
n = (len(body) + CH - 1) // CH
for i in range(n):
    blk = body[i * CH:(i + 1) * CH]
    wr(CFG + i * CH, blk)
    time.sleep(0.02)
time.sleep(0.2)
w = rd(CFG, 32)
print('  写完窗口 32B =', w.hex(' ').upper())
print('  与 cfg[0:32] 比对 =', '逐字节相同 ✓✓✓' if w == body[:32] else '不同 ✗')
print('  原始 cfg[0:32]    =', body[:32].hex(' ').upper())

print('\n步骤 2：只走 0x80 → 0x83 → 0x7D（不再写数据），看 IC 是否认为"与 flash 一致"')
d, _ = g.read(CMD, 1)
print('  0x4160 初始 =', d.hex(' ').upper() if d else '<FAIL>')
g.write(CMD, bytes([0x80, 0, 0, 0, 0x80])); time.sleep(0.25)
for _ in range(20):
    d, _ = g.read(CMD, 1)
    if d and d[0] == 0x82: break
    time.sleep(0.03)
print('  握手 0x82 =', (d[0] == 0x82) if d else False)
print('  进模式后窗口 32B =', rd(CFG, 32).hex(' ').upper(), '  ← 若被清零说明进模式即清暂存')
g.write(CMD, bytes([0x83, 0, 0, 0, 0x83])); time.sleep(0.10)
res = None
for _ in range(30):
    d, _ = g.read(CMD, 5, rounds=4, delay=0.05)
    if d and d[0] in (0x7E, 0x7F): res = bytes(d); break
    time.sleep(0.03)
print('  0x83 后结果 =', res.hex(' ').upper() if res else '<FAIL>', end='  ')
if res and res[0] == 0x7F: print('★★★ = cfg 已被接受并写入 -> 说明暂存区被 IC 采纳了')
elif res and res[:3] == b'\x7e\x00\x07': print('★★★ = 与 flash 完全一致 -> 预装法成立，一切吻合')
elif res and res[0] == 0x7E: print('（0x7E + 错误码 %02X%02X）' % (res[1], res[2]))
else: print()
g.write(CMD, bytes([0x7D, 0, 0, 0, 0x7D])); time.sleep(0.12)
print('  收尾后窗口 32B =', rd(CFG, 32).hex(' ').upper())
print('  cfg 版本 3B    =', rd(CFG, 3).hex(' ').upper())
g.close()
