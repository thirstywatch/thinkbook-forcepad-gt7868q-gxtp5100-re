# crypto_test.py —— 判断 105KB 记录区到底是"压缩"还是"加密"，并寻找可破的痕迹
import re
import struct
import zlib
import bz2
import lzma
import gzip
import math

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
IMG = 0x19ABC
REC = 1084
NREC = 97
print(f"BIN={len(data)}  记录区={NREC*REC}  明文镜像起点=0x{IMG:X}")

region = data[:NREC * REC]
img = data[IMG:]

# ---------- 1) 压缩格式试探 ----------
print("\n=== 1) 压缩格式试探 (前 8 条记录 + 整块) ===")
def try_decompress(b):
    out = []
    for name, fn in (
        ("zlib(15)", lambda x: zlib.decompress(x, 15)),
        ("zlib(-15)", lambda x: zlib.decompress(x, -15)),
        ("gzip(31)", lambda x: zlib.decompress(x, 31)),
        ("bz2", lambda x: bz2.decompress(x)),
        ("lzma", lambda x: lzma.decompress(x)),
        ("lzma_raw", lambda x: lzma.decompress(x, format=lzma.FORMAT_RAW,
                                               filters=[{"id": lzma.FILTER_LZMA2, "preset": 9}])),
    ):
        try:
            d = fn(b)
            if len(d) > 32:
                out.append((name, len(d)))
        except Exception:
            pass
    return out

for i in [5, 6, 7, 8, 20, 50, 90]:
    rec = region[i * REC:(i + 1) * REC]
    r = try_decompress(rec)
    print(f"  记录{i:3d} (H={sum(-((rec.count(b)/len(rec))*math.log2(rec.count(b)/len(rec))) for b in set(rec)):.2f}): {r if r else '无匹配'}")
r = try_decompress(region)
print(f"  整块 105KB: {r if r else '无匹配'}")

# ---------- 2) 异或/周期结构检测 ----------
print("\n=== 2) 异或/周期结构检测 ===")
# 2a: 密文中的相同字节连跑长度（明文的长零串 XOR 周期密钥会暴露周期）
def runs(b):
    best = 0
    cur = 1
    for i in range(1, len(b)):
        if b[i] == b[i - 1]:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return best
print(f"  记录区最长同字节连跑 = {runs(region)}")
for i in [5, 10, 40, 90]:
    rec = region[i * REC:(i + 1) * REC]
    print(f"  记录{i:3d} 最长连跑 = {runs(rec)}")

# 2b: 自相关（检测重复密钥长度）
def autocorr(b, maxk=256):
    res = []
    n = len(b)
    for k in range(1, maxk + 1):
        m = sum(1 for i in range(0, n - k, 7) if b[i] == b[i + k])
        res.append((k, m))
    return res

ac = autocorr(region)
avg = sum(m for _, m in ac) / len(ac)
top = sorted(ac, key=lambda x: -x[1])[:8]
print(f"  自相关均值={avg:.0f}  最高: {[(k, m) for k, m in top]}")
print("  (若某些 k 明显高于均值 -> 存在该周期的重复结构)")

# 2c: 逐字节位置熵（检测列式/分组结构）
print("\n=== 3) 明文段里的密码学常量搜索 (16KB 与 64KB 处) ===")
pats = {
    "AES S-box 头": bytes.fromhex("637C777BF26B6FC5"),
    "AES 逆 S-box 头": bytes.fromhex("52096AD53036A538"),
    "AES Rcon": bytes.fromhex("01020408102040801B36"),
    "CRC32 表头": bytes.fromhex("0000000096300777"),
    "SHA256 K 头": bytes.fromhex("428A2F98D728AE22"),
    "MD5 T 头": bytes.fromhex("D76AA478E8C7B756"),
}
for nm, pat in pats.items():
    hits = [m.start() for m in re.finditer(re.escape(pat), data)]
    print(f"  {nm:16s} 全 BIN: {len(hits)} 处 {[hex(h) for h in hits[:5]]}")

# 4) 明文段的字符串里有没有线索 (key/seed/crypto/secure)
print("\n=== 4) 明文段字符串线索 ===")
kw = re.compile(rb"(?i)(key|seed|crypt|aes|sec|otp|efuse|unlock|password|token|sign)")
n = 0
for m in re.finditer(rb"[\x20-\x7E]{5,}", img):
    if kw.search(m.group()):
        print(f"  +0x{m.start():05X}: {m.group().decode('ascii', 'replace')[:80]}")
        n += 1
        if n > 30:
            break
if n == 0:
    print("  (无)")

# 5) 记录区前 5 条（非高熵）的结构，可能含解密元数据
print("\n=== 5) 记录 0-4 的结构预览 (可能含密钥/长度等元数据) ===")
for i in range(5):
    rec = region[i * REC:(i + 1) * REC]
    print(f"  记录{i}: 前 64 字节 {rec[:64].hex(' ')}")
    print(f"          尾部 16 字节 {rec[-16:].hex(' ')}")
