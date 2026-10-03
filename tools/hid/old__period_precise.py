"""精确测周期：细扫 L，找 byte-match rate 的峰。
并做 δ 相容性检验 —— 追加二十三 用 YELSTO 对齐得到 delta=0xCA4=3236（非 1024 倍数）
却有 32,877 B 逐字节相同。若变换周期 P 不整除 3236，此事不可能。"""
import os

FW = r"<WORKSPACE>"
data = open(os.path.join(FW, "touchpad_GT7868Q_fw.bin"), "rb").read()
seg = data[0x1400:0x19800]
n = len(seg)

def rate(L):
    if L <= 0 or L >= n:
        return 0.0
    hits = 0
    tot = n - L
    for i in range(tot):
        if seg[i] == seg[i + L]:
            hits += 1
    return hits / tot

cands = []
cands += list(range(1000, 1101))
cands += list(range(1600, 1701))
cands += list(range(3230, 3243))
cands += [256, 512, 768, 1024, 1280, 1536, 2048, 2560, 3072, 4096, 809, 1618, 3236]

res = sorted(((rate(L), L) for L in sorted(set(cands))), reverse=True)
print("=== byte-match rate 最高的 30 个候选周期 ===")
print("   L      匹配率      相对基线(0.0039)")
for r, L in res[:30]:
    print("   %-6d %.6f   %6.2f×" % (L, r, r / 0.0039))

print("\n=== 关键候选 ===")
for L in (809, 1024, 1618, 3236, 2048, 512, 3072):
    r = rate(L)
    print("   L=%-5d 匹配率 %.6f  %6.2f×   |  3236 %% L = %d" % (L, r, r / 0.0039, 3236 % L))

print("\n=== δ 相容性 ===")
print("   3236 = 2^2 × 809   （809 是素数）")
print("   若变换是【位置型且周期 P】，则 delta=3236 对齐下密文逐字节相同")
print("   必须要求 P | 3236 ⇒ P ∈ {1,2,4,809,1618,3236}")
print("   实测这些 P 的匹配率见上 —— 若均 ≈ 基线，则【位置型周期 keystream】假说被否证。")
