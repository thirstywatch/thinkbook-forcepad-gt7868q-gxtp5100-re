# flash_map.py —— 把可读的 64KB 芯片窗口与官方 BIN 系统化比对，还原 flash 布局
import re
import struct

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
DUMP = r"<LAB>\touchpad-lab\poc\mem-scan-16bit.txt"
REC = 1084
IMG_OFF = 0x19ABC

data = open(BIN, "rb").read()
mem = bytearray(0x10000)
for line in open(DUMP, encoding="utf-8", errors="replace"):
    m = re.match(r"^0x([0-9A-F]{4})\s+([0-9A-F ]+)$", line.strip())
    if m:
        a = int(m.group(1), 16)
        b = bytes.fromhex(m.group(2))
        mem[a:a + len(b)] = b

print(f"BIN={len(data)}  可读窗口=64KB  明文镜像起点=0x{IMG_OFF:X}")

# 索引窗口内的所有 16 字节块
BLK = 16
win = {}
for a in range(0, 0x10000 - BLK + 1):
    win.setdefault(bytes(mem[a:a + BLK]), []).append(a)

def scan_region(name, start, end, step=BLK):
    hit = 0
    tot = 0
    pairs = []
    for off in range(start, end - BLK + 1, step):
        blk = data[off:off + BLK]
        if len(set(blk)) <= 1:      # 跳过全同/全零块
            continue
        tot += 1
        if blk in win:
            hit += 1
            pairs.append((off, win[blk][0]))
    print(f"\n{name}: {hit}/{tot} 个唯一块在窗口中命中 ({100*hit/max(tot,1):.1f}%)")
    return pairs

# 1) 明文镜像段 (0x19ABC .. 末尾)
p_img = scan_region("A) 明文 MCU 镜像段 (0x19ABC-末尾)", IMG_OFF, len(data))
# 2) 配置记录 0-4
p_cfg = scan_region("B) 配置记录 0-4", 0, 5 * REC)
# 3) 高熵记录 5-96
p_hi = scan_region("C) 高熵记录 5-96", 5 * REC, 97 * REC)

print("\n=== 布局规律 (前若干命中: BIN偏移 -> 窗口地址, 差) ===")
for nm, prs in (("配置记录", p_cfg), ("高熵记录", p_hi), ("明文镜像", p_img)):
    print(f"\n{nm}:")
    for off, addr in prs[:12]:
        print(f"   BIN 0x{off:06X} -> 窗口 0x{addr:04X}   差 0x{addr - off & 0xFFFFFF:06X}")

# 反向: 窗口被 BIN 解释的比例
explained = bytearray(0x10000)
for off in range(0, len(data) - BLK + 1, BLK):
    blk = data[off:off + BLK]
    for a in win.get(blk, []):
        for k in range(BLK):
            explained[a + k] = 1
print(f"\n窗口中被 BIN 解释的字节: {sum(explained)}/65536 ({100*sum(explained)/65536:.1f}%)")

# 高熵区在窗口中的分布
print("\n=== 高熵记录命中在窗口中的地址分布 (每 4KB 计数) ===")
buckets = [0] * 16
for off, addr in p_hi:
    buckets[addr // 4096] += 1
for i, c in enumerate(buckets):
    if c:
        print(f"   0x{i*4096:04X}-0x{i*4096+4095:04X}: {c}")
