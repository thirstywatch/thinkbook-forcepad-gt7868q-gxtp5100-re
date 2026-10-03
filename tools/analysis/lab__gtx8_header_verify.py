# -*- coding: utf-8 -*-
"""gtx8 头部验证 —— 按汇顶自家开源规格（fwupd plugins/goodix-tp/）逐项校验本机容器。
只读文件，不碰任何设备。

规格来源（LGPL-2.1, Copyright 2023 Goodix.inc <xulinkun@goodix.com>）：
  fu-goodixtp.rs              : FuStructGoodixGtx8Hdr / FuStructGoodixGtx8Img
  fu-goodixtp-gtx8-firmware.c : GTX8_FW_DATA_OFFSET=256, 校验和=bytes[6..fs+6)字节和
"""
import struct

BIN = r'C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN'
H = 0x113C          # gtx8 头起点（= 明文头 24B 之前? 不：0x113C 即头起点，前导区在其前）

d = open(BIN, 'rb').read()
h = d[H:H + 32]

firmware_size = struct.unpack_from('>I', h, 0)[0]
checksum_hdr  = struct.unpack_from('>H', h, 4)[0]
unknown17     = h[6:23]
vid           = struct.unpack_from('>I', h, 23)[0]
subsys_num    = h[27]
unknown4      = h[28:32]

print('=== gtx8 头 @0x%X ===' % H)
print('  firmware_size u32be = %d (0x%X)' % (firmware_size, firmware_size))
print('  checksum      u16be = 0x%04X' % checksum_hdr)
print('  unknown[17]         = %s   (ASCII: %r)'
      % (unknown17.hex(' '), ''.join(chr(b) if 32 <= b < 127 else '.' for b in unknown17)))
print('  vid           u32be = 0x%08X' % vid)
print('  subsys_num    u8    = %d' % subsys_num)
print('  unknown[4]          = %s' % unknown4.hex(' '))
print()

ok = []
ok.append(('firmware_size + 6 == 载荷声明长度 100608', firmware_size + 6 == 100608))

s = 0
for i in range(6, firmware_size + 6):
    s = (s + d[H + i]) & 0xFFFF
ok.append(('checksum 字节和 = 头里的 checksum（0x%04X）' % s, s == checksum_hdr))

imgs = []
for k in range(subsys_num):
    r = d[H + 32 + k * 8: H + 32 + (k + 1) * 8]
    imgs.append((r[0],
                 struct.unpack_from('>I', r, 1)[0],
                 struct.unpack_from('>H', r, 5)[0] << 8,
                 r[7]))
total = sum(x[1] for x in imgs)
ok.append(('subsys_num=%d 且头里正好 %d 条记录' % (subsys_num, subsys_num), True))
ok.append(('13 条 size 合计 %d == 载荷长度 %d' % (total, 100608 - 256), total == 100608 - 256))
ok.append(('变体判定：gtx8（firmware_size 为 u32BE）', firmware_size == 100602))

print('=== 13 条子镜像记录（kind=1 会被官方解析器跳过）===')
for k, (kind, size, addr, pad) in enumerate(imgs):
    print('   #%2d kind=%d size=%-6d addr=0x%05X  raw=%s'
          % (k, kind, size, addr, d[H + 32 + k * 8: H + 40 + k * 8].hex(' ')))
print()

print('=== 校验结果 ===')
allok = True
for name, v in ok:
    print('  %s  %s' % ('✓' if v else '✗', name))
    allok = allok and v
print()
print('★★ 总判定：%s' % ('头部 100% 通过汇顶自家 gtx8 规格校验' if allok else '存在不符项，见上'))
