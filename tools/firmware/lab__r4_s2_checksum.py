# -*- coding: utf-8 -*-
"""R4-2: 用汇顶官方校验和当 oracle —— 独立验证上一轮的解扰。
   官方 FirmwareImage::GetDataFromFile:
      size = BE u32 @[0:4] ; chksum = BE u16 @[4:6]
      chksum == ( Σ byte[6 : size+6] ) & 0xFFFF
"""
import numpy as np

O = open('orig_TB14P.bin', 'rb').read()
A = open('A_2024.bin', 'rb').read()      # 上一轮的解扰产物（子固件数据，100352 B）
K = open('K.bin', 'rb').read()

R0 = 0x113C                                # region A 起点
sz = int.from_bytes(O[R0:R0+4], 'big')
ck = int.from_bytes(O[R0+4:R0+6], 'big')
RA = O[R0:R0+sz+6]
print(f"region A: 起点 0x{R0:x}  size={sz}  size+6={sz+6}  实测长度={len(RA)}")
print(f"官方校验和字段 = 0x{ck:04x}")

hdr = RA[:256]
data_raw = RA[256:]                         # 100352 B 原始（应是加扰后的）
print(f"header 256 B + data {len(data_raw)} B = {256+len(data_raw)}  (应 = size+6 = {sz+6})")

def cks(buf):
    return sum(buf) & 0xFFFF

print("\n=== 测试 1：校验和是否对【原始(加扰)】数据成立 ===")
print(f"  Σ raw[6:size+6] & 0xFFFF = 0x{cks(RA[6:]):04x}   期望 0x{ck:04x}  -> {'✓' if cks(RA[6:])==ck else '✗'}")

print("\n=== 测试 2：校验和是否对【上一轮解扰产物】成立 ===")
tot = cks(hdr[6:]) + sum(A)
print(f"  Σ header[6:256] = 0x{cks(hdr[6:]):04x} (={cks(hdr[6:])})")
print(f"  Σ A_2024        = 0x{sum(A)&0xFFFF:04x} ({sum(A)})")
print(f"  合计 & 0xFFFF    = 0x{tot&0xFFFF:04x}   期望 0x{ck:04x}  -> {'✓✓ 匹配' if (tot&0xFFFF)==ck else '✗ 不匹配'}")
print(f"  （合计不取模 = {tot}）")

print("\n=== 测试 3：扫描 1024 个相位，看哪个能让校验和成立 ===")
Kn = np.frombuffer(K, dtype=np.uint8)
raw = np.frombuffer(data_raw, dtype=np.uint8)
h = sum(hdr[6:]) & 0xFFFF
hits = []
for p in range(1024):
    idx = (np.arange(len(raw)) + p) % 1024
    pl = raw ^ Kn[idx]
    s = (int(pl.sum()) + h) & 0xFFFF
    if s == ck:
        hits.append(p)
print(f"  命中相位: {hits if hits else '无'}")
# 也扫"不加扰"的情形
print(f"  不加扰时 & 0xFFFF = 0x{(int(raw.sum())+h)&0xFFFF:04x}")

print("\n=== 测试 4：diff = raw XOR A_2024 的周期性 ===")
d = raw ^ np.frombuffer(A, dtype=np.uint8)
print(f"  diff 前 32 字节: {' '.join(f'{b:02x}' for b in d[:32])}")
print(f"  diff 中非零字节数 = {int((d!=0).sum())} / {len(d)}")
# 检验 diff 是否为周期 1024
ok = all(np.array_equal(d[i::1024], d[i % 1024::1024]) for i in range(1024))
print(f"  diff 是否严格 1024 周期 = {ok}")
# 前 4 字节
print(f"  diff[0:8] = {' '.join(f'{b:02x}' for b in d[:8])}")
print(f"  若剔除前 4 字节，其余仍是 1024 周期 = "
      f"{all(np.array_equal(d[4+i::1024], d[4+(i%1024)::1024]) for i in range(1024))}")
# diff 里出现了多少个不同的值
print(f"  diff 出现 {len(set(d.tolist()))} 个不同值")
print(f"  diff[:64] 与 K[:64] 的关系: ")
print(f"    K[:64]     = {' '.join(f'{b:02x}' for b in K[:64])}")
print(f"    diff[:64]  = {' '.join(f'{b:02x}' for b in d[:64])}")
# 找 diff[4:8] 在 K 中的位置
pat = bytes(d[4:12])
print(f"  diff[4:12] = {pat.hex(' ')} ; 在 K 中出现于偏移 {[i for i in range(1024) if K[i:i+8]==pat]}")

print("\n=== 测试 5：region B（TF100A）头 ===")
B0 = R0 + sz + 6
print(f"  region B 起点 = 0x{B0:x}  (应 0x19a3c)")
seg = O[B0:B0+64]
print(f"  前 32 字节: {' '.join(f'{b:02x}' for b in seg[:32])}")
print(f"  ascii: {''.join(chr(c) if 32<=c<127 else '.' for c in seg[:32])}")
b_sz = int.from_bytes(seg[0:4], 'big'); b_ck = int.from_bytes(seg[4:6], 'big')
print(f"  size={b_sz} size+6={b_sz+6}  chksum=0x{b_ck:04x}")
print(f"  实测 Σ byte[6:size+6] & 0xFFFF = 0x{cks(O[B0+6:B0+b_sz+6]):04x} -> "
      f"{'✓' if cks(O[B0+6:B0+b_sz+6])==b_ck else '✗'}")
print(f"  文件剩余 = {len(O)-B0} ; size+6 = {b_sz+6}")
