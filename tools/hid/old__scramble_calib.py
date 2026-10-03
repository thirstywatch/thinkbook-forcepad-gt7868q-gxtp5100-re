"""标定实验：把"类内熵差"这个指标，分别用在
  (a) 真数据
  (b) 强密码代理：AES-CTR（对同一段数据加密）
  (c) 周期加扰代理：周期 256 的重复密钥 XOR
  (d) 周期 16  的重复密钥 XOR
看真数据更像哪一个。
"""
import os, collections, math, random, hashlib

BIN = r"<WORKSPACE>"
d = open(BIN, "rb").read()
seg = d[0x1400:0x19A00]

def entropy(vals):
    c = collections.Counter(vals); t = len(vals)
    return -sum((v / t) * math.log2(v / t) for v in c.values())

def gap(data, Llist=(8, 16, 32, 64, 128, 256, 512)):
    rnd = bytearray(data); random.seed(7); random.shuffle(rnd); rnd = bytes(rnd)
    out = {}
    for L in Llist:
        hs = [entropy(data[j::L]) for j in range(L) if len(data[j::L]) > 40]
        hc = [entropy(rnd[j::L]) for j in range(L) if len(rnd[j::L]) > 40]
        out[L] = sum(hs) / len(hs) - sum(hc) / len(hc)
    return out

# --- AES-CTR 代理（无第三方库，用 hashlib 造 keystream：这不是 AES，但同样是【强哈希型】流密码） ---
def strong_stream(data, seed):
    out = bytearray(len(data))
    for off in range(0, len(data), 32):
        ks = hashlib.sha256(seed + off.to_bytes(4, "little")).digest()
        blk = data[off:off + 32]
        for i, b in enumerate(blk):
            out[off + i] = b ^ ks[i]
    return bytes(out)

# --- 重复密钥 XOR 代理 ---
def rep_xor(data, L, seed=b"key"):
    key = hashlib.sha256(seed).digest()[:L] if L <= 32 else (hashlib.sha256(seed).digest() * ((L // 32) + 1))[:L]
    return bytes(b ^ key[i % L] for i, b in enumerate(data))

cases = [
    ("(a) 真数据", seg),
    ("(b) 强流密码代理 (SHA256-KS)", strong_stream(seg, b"seed")),
    ("(c) 重复XOR 周期256", rep_xor(seg, 256)),
    ("(d) 重复XOR 周期16", rep_xor(seg, 16)),
]

print("%-3s %-28s %-9s %-9s %-9s %-9s %-9s %-9s %-9s" % ("L", "样本", 8, 16, 32, 64, 128, 256, 512))
for name, data in cases:
    g = gap(data)
    print("%-3s %-28s %-+9.4f %-+9.4f %-+9.4f %-+9.4f %-+9.4f %-+9.4f %-+9.4f"
          % ("", name, g[8], g[16], g[32], g[64], g[128], g[256], g[512]))

print("\n判读：强密码代理的差值应≈0；周期加扰在周期及其倍数处明显负。")
print("真数据若普遍负 => 不是强密码 => 加扰是弱变换（可逆/可恢复）。")
