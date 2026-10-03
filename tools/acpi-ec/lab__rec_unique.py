import math, collections
BIN=r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data=open(BIN,"rb").read(); REC=1084; N=97
recs=[data[i*REC:(i+1)*REC] for i in range(N)]
print("=== 记录唯一性 ===")
cnt=collections.Counter(recs)
print(f"  97 条记录中不同内容 = {len(cnt)} 种")
for r,c in cnt.most_common(12):
    idx=[i for i,x in enumerate(recs) if x==r]
    print(f"    出现 {c:2d} 次  记录号 {idx[:12]}{'...' if len(idx)>12 else ''}  前8字节 {r[:8].hex(' ')}")
def H(b):
    cc=collections.Counter(b); n=len(b)
    return -sum((v/n)*math.log2(v/n) for v in cc.values())
print("\n=== 各记录熵 (每 8 条一行) ===")
for i in range(0,N,8):
    print("  " + " ".join(f"{i+j}:{H(recs[i+j]):.2f}" for j in range(min(8,N-i))))
print("\n=== zstd 解压尝试 ===")
import zstandard as zstd
region=b"".join(recs)
for tag,b in (("记录区",region),("记录5",recs[5]),("记录20",recs[20]),("记录90",recs[90])):
    ok=False
    for ln in (None,):
        try:
            d=zstd.ZstdDecompressor().decompress(b, max_output_size=10_000_000)
            print(f"  {tag}: zstd 框架解压成功 -> {len(d)} 字节, 头 32: {d[:32].hex(' ')}"); ok=True
        except Exception as e:
            pass
    if not ok:
        try:
            d=zstd.ZstdDecompressor().decompressobj().decompress(b)
            print(f"  {tag}: zstd 流式成功 -> {len(d)}"); ok=True
        except Exception as e:
            print(f"  {tag}: zstd 失败 ({type(e).__name__})")
    if ok: break
