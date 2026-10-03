# correlate.py —— 检查 16 位地址空间是否对应固件 BIN 的某个偏移
import sys

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
print("BIN 大小:", len(data))

# 从设备读到的样本（地址 -> 字节）
samples = {
    0x1000: bytes.fromhex("4301000050010051002700000000" "1F00010021000000"),
    0x452C: bytes.fromhex("A7EB20908F73A8C4C13AD5ABC184BBC4739A304B22CB492437A5BA02DB928ECF"),
    0x4100: bytes.fromhex("0000000000000000000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF"),
}

for addr, pat in samples.items():
    # 用前 8 字节做锚点
    anchor = pat[:8]
    hits = []
    start = 0
    while True:
        i = data.find(anchor, start)
        if i < 0:
            break
        hits.append(i)
        start = i + 1
    print(f"\n地址 0x{addr:04X} 锚点 {anchor.hex(' ')} -> BIN 中出现 {len(hits)} 次")
    for i in hits[:8]:
        # 打印候选偏移，并检查 addr -> offset 的映射常数
        print(f"   offset 0x{i:X}  (addr->offset 差: 0x{i - addr:X})")
        print(f"   匹配: {data[i:i+len(pat)].hex(' ')}")
        print(f"   设备: {pat.hex(' ')}")
        print(f"   一致: {data[i:i+len(pat)] == pat}")
