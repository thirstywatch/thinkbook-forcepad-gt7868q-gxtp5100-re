import math, collections
BIN=r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data=open(BIN,"rb").read(); REC=1084
# 取记录 5..96 的拼接（高熵区）
hi = b"".join(data[i*REC:(i+1)*REC] for i in range(5,97))
print("高熵区长度:", len(hi))
def H(b):
    c=collections.Counter(b); n=len(b)
    return -sum((v/n)*math.log2(v/n) for v in c.values())
print(f"  整体熵 = {H(hi):.4f}")
print(f"  偶数字节熵 = {H(hi[0::2]):.4f}   奇数字节熵 = {H(hi[1::2]):.4f}")
def Hn(b):
    c=collections.Counter(b); n=len(b)
    return -sum((v/n)*math.log2(v/n) for v in c.values())
# 16 位小端值的分布
hi16 = [hi[i] | (hi[i+1]<<8) for i in range(0, len(hi)-1, 2)]
print(f"  16 位值: 总数={len(hi16)} 唯一={len(set(hi16))} (随机期望唯一≈{len(hi16)*(1-math.exp(-len(hi16)/65536)):.0f})")
# ECB 重复块检测
for bs in (8,16,32):
    blocks=[bytes(hi[i:i+bs]) for i in range(0, len(hi)-bs, bs)]
    dup = len(blocks)-len(set(blocks))
    exp = len(blocks)*len(blocks)/(2*256**bs)
    print(f"  {bs} 字节块: 共 {len(blocks)}  重复块 {dup}  (随机期望 ≈{exp:.2e})")
# 尝试 lz4 / zstd 若可用
for mod in ("lz4.block","zstandard","lzo"):
    try:
        __import__(mod); print(f"  {mod}: 可用")
    except Exception as e:
        print(f"  {mod}: 不可用 ({type(e).__name__})")
