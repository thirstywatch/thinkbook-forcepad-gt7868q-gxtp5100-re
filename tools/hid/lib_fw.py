# -*- coding: utf-8 -*-
"""公共库：固件加载与基础统计。所有审计脚本共用，保证读数一致。"""
import math, os, struct
from collections import Counter

FW_PATH = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"

def load():
    with open(FW_PATH, "rb") as f:
        return f.read()

def entropy(b):
    """Shannon entropy in bits/byte"""
    if not b:
        return 0.0
    c = Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())

def h16(b):
    """byte histogram skew: fraction of the most common byte"""
    if not b:
        return 0.0
    c = Counter(b)
    return max(c.values()) / len(b)

def be32(b, off):
    return struct.unpack_from(">I", b, off)[0]

def le32(b, off):
    return struct.unpack_from("<I", b, off)[0]

def be16(b, off):
    return struct.unpack_from(">H", b, off)[0]

def le16(b, off):
    return struct.unpack_from("<H", b, off)[0]

def printable_ratio(b):
    if not b:
        return 0.0
    return sum(1 for x in b if 32 <= x < 127) / len(b)

def chi2_uniform(b):
    """chi-square vs uniform byte distribution. df=255. ~254 expected if uniform."""
    if not b:
        return 0.0
    n = len(b)
    exp = n / 256.0
    c = Counter(b)
    s = 0.0
    for i in range(256):
        o = c.get(i, 0)
        s += (o - exp) ** 2 / exp
    return s

def rand_baseline_line(nbytes, trials=200, seed=1):
    """Monte-Carlo baseline: entropy & chi2 for pure random of given length"""
    import random
    rng = random.Random(seed)
    ents = []
    chis = []
    for _ in range(trials):
        b = bytes(rng.randrange(256) for _ in range(nbytes))
        ents.append(entropy(b))
        chis.append(chi2_uniform(b))
    ents.sort(); chis.sort()
    return (ents[len(ents)//2], chis[len(chis)//2], chis[int(len(chis)*0.95)])
