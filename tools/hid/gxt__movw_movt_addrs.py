# -*- coding: utf-8 -*-
# 第十九轮 F：解 0x1E000(MOVW/MOVT) 与尾区 ARM 代码访问的绝对地址
# 目的：看这段代码在访问哪些外设/寄存器 —— 是否触及 LRA / 触觉驱动接口
# Thumb-2 编码（小端半字序）：
#   MOVW Rd,#imm16:  hw1 = 11110 i 10 0100 imm4   hw2 = 0 imm3 Rd imm8
#   MOVT Rd,#imm16:  hw1 = 11110 i 10 1100 imm4   hw2 = 0 imm3 Rd imm8
#   字节序: 内存 = [hw1_lo hw1_hi hw2_lo hw2_hi]
#   即内存 bytes b0b1b2b3 -> hw1 = b0|b1<<8, hw2 = b2|b3<<8
#   imm16 = imm4:imm3:imm8  (i 为 hw1 的 bit10)
# 判定：与已知 0x0801xxxx / 0x2000xxxx 地址对照
import struct, os
from collections import Counter

P = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
D = open(P, 'rb').read()
OUT = []
def w(s=''):
    OUT.append(s)

w("="*78)
w("解 MOVW/MOVT 立即数：0x1E000 与尾区 ARM 代码访问的绝对地址（第十九轮 F）")
w("="*78)

def decode_movw(off):
    """返回 (reg, imm16) 或 None"""
    hw1 = D[off] | (D[off+1] << 8)
    hw2 = D[off+2] | (D[off+3] << 8)
    top5 = hw1 >> 11
    if top5 != 0b11110:
        return None
    op = hw1 & 0x0FF0            # 0x240 = MOVW (10 0100), 0x2C0 = MOVT (10 1100)
    if op not in (0x240, 0x2C0):
        return None
    i = (hw1 >> 10) & 1
    imm4 = hw1 & 0xF
    imm3 = (hw2 >> 12) & 0x7
    rd = (hw2 >> 8) & 0xF
    imm8 = hw2 & 0xFF
    imm16 = (imm4 << 12) | (i << 11) | (imm3 << 8) | imm8
    kind = 'MOVW' if op == 0x240 else 'MOVT'
    return kind, rd, imm16

# ---------- 1. 全文件扫描 MOVW/MOVT 对 ----------
w()
w("### 1. 全文件 MOVW/MOVT 配对统计")
def scan(lo, hi, label):
    pairs = []          # (off, rd, addr32, movw_imm, movt_imm)
    pending = {}        # rd -> (imm16, off)
    off = lo
    while off < hi - 3:
        r = decode_movw(off)
        if r:
            kind, rd, imm = r
            if kind == 'MOVW':
                pending[rd] = (imm, off)
            else:
                if rd in pending:
                    lo16, o1 = pending.pop(rd)
                    addr = (imm << 16) | lo16
                    pairs.append((o1, rd, addr, lo16, imm))
            off += 4
        else:
            off += 2
    w()
    w("  --- %s (0x%05X-0x%05X) ---" % (label, lo, hi))
    w("    MOVW/MOVT 配对成功: %d 组" % len(pairs))
    c = Counter(a for _, _, a, _, _ in pairs)
    w("    唯一绝对地址 %d 个" % len(c))
    return pairs

allp = scan(0x1E000, 0x20000, '0x1E000 config区')
tail1 = scan(0x1A000, 0x1F000, '尾区A 0x1A000')
tail2 = scan(0x20000, len(D), '尾区B 0x20000-END')
pairs = allp + tail1 + tail2

w()
w("### 2. ★所有配对出的绝对地址（按段归类）")
cat = {'Flash 0x080xxxxx': [], 'SRAM 0x200xxxxx': [], '外设 0x4xxxxxxx/0x5xxxxxxx': [],
       '其他': []}
for o1, rd, addr, l, h in pairs:
    if 0x08000000 <= addr < 0x08200000: cat['Flash 0x080xxxxx'].append(addr)
    elif 0x20000000 <= addr < 0x20020000: cat['SRAM 0x200xxxxx'].append(addr)
    elif 0x40000000 <= addr < 0x60000000: cat['外设 0x4xxxxxxx/0x5xxxxxxx'].append(addr)
    else: cat['其他'].append(addr)
for k, v in cat.items():
    w()
    w("  【%s】 %d 个" % (k, len(v)))
    if not v: continue
    c = Counter(v)
    for a, n in c.most_common(40):
        w("     0x%08X  x%d" % (a, n))

w()
w("### 3. ★外设地址细化（0x4xxxxxxx / 0x5xxxxxxx 是芯片外设总线）")
per = [a for a in cat['外设 0x4xxxxxxx/0x5xxxxxxx']]
c = Counter(per)
for a, n in sorted(c.items()):
    bus = (a >> 16) & 0xFF
    w("     0x%08X  x%-3d   (总线 0x%02X)" % (a, n, bus))

w()
w("### 4. 已知相关地址对照（从触控板项目文档）")
known = {
    0x0801A000: 'GT7868Q/TF100A 固件区',
    0x40000000: 'APB',
    0x50000000: 'AHB',
}
for a, n in sorted(set(a for _,_,a,_,_ in pairs)):
    for ka, kn in known.items():
        if a >> 16 == ka >> 16:
            w("     0x%08X -> %s" % (a, kn))

# ---------- 5. 直接查 AW86927 / LRA 常见接口地址 ----------
w()
w("### 5. 触觉相关嫌疑地址（I2C 控制器 / GPIO / PWM / TIMER）")
# 常见 MCU(I2C/GPIO/TIM) 外设基址，仅做提示
for a, n in sorted(Counter(a for _,_,a,_,_ in pairs).items()):
    tag = ''
    if a & 0xFFFFF000 in (0x40000000, 0x50000000):
        tag = '外设基址'
    if 0x48000000 <= a < 0x48002000: tag = '★常见 GPIO 区'
    if 0x40005400 <= a < 0x40005500: tag = '★常见 I2C1 区(STM32)'
    if 0x40012000 <= a < 0x40013000: tag = '★常见 ADC 区'
    if tag:
        w("     0x%08X  x%-3d  %s" % (a, n, tag))

# ---------- 6. 0x1E000 前 2KB 的完整 MOVW/MOVT 序列 ----------
w()
w("### 6. 0x1E000 前 2KB 内的 MOVW/MOVT 配对（含所在偏移）")
for o1, rd, addr, l, h in allp:
    if o1 < 0x1E800:
        w("    0x%05X  R%-2d = 0x%08X   (MOVW #0x%04X / MOVT #0x%04X)" % (o1, rd, addr, l, h))

open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cfg_parsed', 'movw_movt_addrs.txt'), 'w', encoding='utf-8').write('\n'.join(OUT))
print('\n'.join(OUT))
