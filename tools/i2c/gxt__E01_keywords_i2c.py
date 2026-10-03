# -*- coding: utf-8 -*-
"""E01. 触觉相关线索 —— 独立关键词表 + I²C 从地址 + GPIO 模式 + 配置语义。
★ 关键: C04 已证明 0x8600/0x8800 是同一张表的两个掩码副本 —— 去掩码后看到的
   内容才是真表。先做关键词搜索, 再做 I²C 地址追踪, 再看 0x1E000 的配置记录。
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
FWR = load(); N = len(FWR)
FW = FWR

print("=" * 96)
print("E01-a. 关键词表全文件搜索 (大小写不敏感 + 拼音隐约形式)")
print("=" * 96)
KW = ["AW869", "86927", "awinic", "AWINIC", "aw87", "LRA", "lra", "haptic", "HAPTIC",
      "Haptic", "vibr", "VIBR", "vibra", "trig", "TRIG", "wave", "WAVE", "BEMF", "bemf",
      "motor", "MOTOR", "goodix", "GOODIX", "GOODI", "GT7868", "GT78", "yelsto", "YELSTO",
      "taifang", "TAIFANG", "TF100", "TF100A", "titan", "click", "CLICK", "sensor",
      "SENSOR", "touch", "TOUCH", "pad", "PRESSURE", "pressure", "force", "FORCE"]
found_any = False
for k in KW:
    hits = []
    st = 0
    kb = k.encode()
    while True:
        p = FW.find(kb, st)
        if p < 0: break
        hits.append(p); st = p + 1
    if hits:
        found_any = True
        print(f"  '{k:10s}' 命中 {len(hits):>3d} -> {[hex(h) for h in hits[:8]]}")
print(f"  (共 {len(KW)} 个关键词, 有命中 {sum(1 for k in KW if FW.find(k.encode())>=0)} 个)")

print("\n" + "=" * 96)
print("E01-b. 二进制关键词: I2C 从地址候选 (0x5A/0x5B) 在数据区的出现")
print("=" * 96)
# 0x5A = 90, 0x5B = 91 (7-bit 0x2D=45 -> 8-bit write 0x5A / read 0x5B)
for name, base in [("0x5A", 0x5A), ("0x5B", 0x5B), ("0x2D", 0x2D)]:
    cnt = FW.count(base)
    print(f"  {name} 单字节出现 = {cnt} 次 (随机期望 {N/256:.0f})")
# 成对/结构出现
for pat, nm in [(b"\x5a\x00", "5a 00"), (b"\x00\x5a", "00 5a"), (b"\x5b\x00", "5b 00"),
                (b"\x5a\x5b", "5a 5b"), (b"\x5b\x5a", "5b 5a")]:
    hits = []; st = 0
    while True:
        p = FW.find(pat, st)
        if p < 0: break
        hits.append(p); st = p + 1
    print(f"  {nm:8s} 命中 {len(hits):>4d} -> {[hex(h) for h in hits[:12]]}")

print("\n" + "=" * 96)
print("E01-c. ★ 在 0x00000-0x1200 (配置区) 找 [reg][val] 形式的配置记录")
print("=" * 96)
print("  0x0140-0x0200 原始内容:")
for o in range(0x140, 0x200, 16):
    print(f"    0x{o:05X}  {' '.join(f'{b:02x}' for b in FW[o:o+16])}"
          f"   |{''.join(chr(b) if 32<=b<127 else '.' for b in FW[o:o+16])}|")

print("\n" + "=" * 96)
print("E01-d. ★ 0x1E000-0x20000 (官方 FLASH_ADDR_CONFIG_DATA) 结构 + 去重")
print("=" * 96)
sub = FW[0x1E000:0x20000]
print(f"  长度={len(sub)} 熵={entropy(sub):.4f} 零占比={sub.count(0)/len(sub):.4f}")
# 找 ASCII 字符串
strs = re.findall(rb"[\x20-\x7e]{5,}", sub)
print(f"  ASCII 串(>=5) 数量 = {len(strs)}")
for s in strs[:30]:
    print(f"    @? {s[:60]}")

print("\n" + "=" * 96)
print("E01-e. ★ 全文件 ASCII 字符串 (>7字符) 提取 —— 看有无语义线索")
print("=" * 96)
strs = [(m.start(), m.group()) for m in re.finditer(rb"[\x20-\x7e]{7,}", FW)]
print(f"  总数 = {len(strs)}")
for off, s in strs[:60]:
    print(f"    0x{off:05X}  {s[:72].decode('ascii','replace')}")
