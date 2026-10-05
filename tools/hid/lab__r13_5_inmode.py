# -*- coding: utf-8 -*-
"""R13-5 ★★★★★ cfg 模式内用【单块写】(已验证的原始语义) + 写后【立刻】读窗口校验
 依据：官方 goodix_i2c_write_trans() 的载荷 = [addr16BE][data...]，地址由主机递增；
       HID 的 0E 20 就是"I²C 直通读写"，所以 dev->Write(addr,data,len) 的拆分
       = 每块 ≤55B、地址逐块 +55、每块自成一次完整写（cont=0）
 之前从没在 cfg 模式内做过"写→立刻读窗口"这一步，这轮补上。
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


def w1(a, data):
    """单块写：官方 i2c 语义的一次 transfer"""
    pkt = [0x0E, 0x20, 0x00, 0x00, (len(data) + 5) & 0xFF, 0x00,
           (a >> 8) & 0xFF, a & 0xFF, (len(data) >> 8) & 0xFF, len(data) & 0xFF] + list(data)
    return g._send(pkt)


print('写前窗口 =', rd(CFG, 32).hex(' ').upper())
d, _ = g.read(CMD, 1); print('0x4160 =', d.hex(' ').upper() if d else '<FAIL>')

g.write(CMD, bytes([0x80, 0, 0, 0, 0x80])); time.sleep(0.25)
for _ in range(20):
    d, _ = g.read(CMD, 1)
    if d and d[0] == 0x82: break
    time.sleep(0.03)
print('握手 0x82 =', (d[0] == 0x82) if d else False)
print('进模式后窗口 =', rd(CFG, 32).hex(' ').upper())

n = (len(body) + CH - 1) // CH
print('\ncfg 模式内：19 个单块写（地址递增、cont=0、[4]=本块len+5、[8..9]=本块len）')
for i in range(n):
    blk = body[i * CH:(i + 1) * CH]
    ok = w1(CFG + i * CH, blk)
    if i in (0, 1, n - 2, n - 1):
        print('   块%2d addr=0x%04X %2dB -> %s' % (i, CFG + i * CH, len(blk), ok))
    time.sleep(0.02)
time.sleep(0.15)
w = rd(CFG, 32)
print('\n★ 写后【立刻】窗口 =', w.hex(' ').upper())
print('★ 与 cfg[0:32] 比对 =', '逐字节相同 ✓✓✓ 【cfg 模式内单块写是有效的！】'
      if w == body[:32] else '不同 ✗')

g.write(CMD, bytes([0x83, 0, 0, 0, 0x83])); time.sleep(0.12)
res = None
for _ in range(30):
    d, _ = g.read(CMD, 5, rounds=4, delay=0.05)
    if d and d[0] in (0x7E, 0x7F): res = bytes(d); break
    time.sleep(0.03)
print('0x83 后结果 =', res.hex(' ').upper() if res else '<FAIL>', end='  ')
if res and res[0] == 0x7F: print('★★★ 已接受并写入')
elif res and res[:3] == b'\x7e\x00\x07': print('★★★ 与 flash 完全一致')
elif res and res[0] == 0x7E: print('（错误码 %02X%02X）' % (res[1], res[2]))
else: print()
g.write(CMD, bytes([0x7D, 0, 0, 0, 0x7D])); time.sleep(0.12)
print('收尾窗口 =', rd(CFG, 32).hex(' ').upper())
g.close()
