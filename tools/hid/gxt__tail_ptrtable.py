# -*- coding: utf-8 -*-
# 第十九轮 B：指针表 / 运行时地址 / 调试命令面
import struct, os, re
from collections import Counter, defaultdict

P = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
D = open(P, 'rb').read()
OUT = []
def w(s=''):
    OUT.append(s)

w("="*78)
w("尾部运行时指针表与调试面（第十九轮 B）")
w("="*78)

# ---------- A. 0x26500-0x26600 表结构 ----------
w()
w("### A. 0x264F8-0x26620 逐 4 字节（u32LE + 注释）")
for off in range(0x264F8, 0x26620, 4):
    v = struct.unpack_from('<I', D, off)[0]
    tag = ''
    if 0x08000000 <= v < 0x08200000:
        tag = '<-- Flash 指针 0x%08X' % v
    elif 0x20000000 <= v < 0x20010000:
        tag = '<-- SRAM 指针 0x%08X' % v
    elif v != 0:
        tag = '常量 %d' % v
    w("  0x%05X  %-11s  %s" % (off, ' '.join('%02x'%b for b in D[off:off+4]), tag))

# ---------- B. 全尾区 Flash 指针普查 ----------
w()
w("### B. 全文件 Flash/SRAM 指针普查（u32LE 落在已知运行地址段）")
ranges = [(0x08000000, 0x08200000, 'Flash'),
          (0x20000000, 0x20020000, 'SRAM'),
          (0x10000000, 0x10010000, 'CCM/其他')]
hits = defaultdict(list)
for i in range(0, len(D) - 3):
    v = struct.unpack_from('<I', D, i)[0]
    for lo, hi, nm in ranges:
        if lo <= v < hi:
            hits[nm].append((i, v))
            break
for nm, lst in hits.items():
    w("  %s: %d 个" % (nm, len(lst)))
    # 按值聚类
    c = Counter(v for _, v in lst)
    w("    唯一目标地址 %d 个；出现>=2次的：" % len(c))
    for v, n in c.most_common(20):
        locs = ','.join('0x%05X' % o for o, vv in lst if vv == v)[:70]
        w("      0x%08X  x%-3d  位于 %s" % (v, n, locs))

# ---------- C. 尾区函数入口候选（被指针指向的） ----------
w()
w("### C. 被指针引用的尾区内部地址（>=0x19A00 且 <0x2775C），即函数/数据入口")
inner = []
for nm, lst in hits.items():
    for off, v in lst:
        if nm == 'Flash':
            # 映射到文件内：文件基址未知，先试 0x08000000 对应文件 0
            for base in (0x08000000, 0x08010000, 0x08000000 + 0x10000):
                fo = v - base
                if 0x19A00 <= fo < len(D):
                    inner.append((off, v, fo, base))
                    break
            else:
                fo = v - 0x08000000
                inner.append((off, v, fo, 0x08000000))
seen = set()
w("  指针值 -> 假设文件偏移 (base=0x08000000)")
for off, v, fo, base in sorted(inner, key=lambda x: x[1]):
    if v in seen:
        continue
    seen.add(v)
    ok = '  (落在文件内)' if 0 <= fo < len(D) else '  (>文件长度)'
    w("    0x%08X -> 文件 0x%05X%s   出现在固件 0x%05X" % (v, fo & 0xFFFFF, ok, off))

# ---------- D. 关键地址处的字节（看是否像函数入口：PUSH） ----------
w()
w("### D. 上面每个落点处的字节（判断是否函数入口）")
for v in sorted(seen):
    fo = v - 0x08000000
    if 0 <= fo < len(D) - 4:
        bs = D[fo:fo+4]
        hw = bs[0] | (bs[1] << 8)
        kind = 'Thumb PUSH' if (0xB400 <= hw <= 0xB5FF) else ('BL/BLX(32bit)' if bs[1] in (0xF0, 0xF4, 0xF7, 0xF8) else '普通')
        w("    0x%08X -> 0x%05X  %-11s  %s" % (v, fo, ' '.join('%02x'%b for b in bs), kind))

# ---------- E. 调试/命令面关键词（放宽到大小写不敏感 + 部分词） ----------
w()
w("### E. 调试/命令面关键词（全文件，不区分大小写）")
kws = [b'cmd', b'CMD', b'uart', b'UART', b'debug', b'DEBUG', b'log', b'LOG',
       b'err', b'ERR', b'fail', b'FAIL', b'test', b'TEST', b'test_', b'_fw',
       b'ver', b'VER', b'calib', b'CALIB', b'self', b'report', b'REPORT',
       b'isp', b'ISP', b'burn', b'download', b'CRC', b'crc']
for kw in kws:
    n = D.count(kw)
    if n:
        locs = []
        s = 0
        while True:
            i = D.find(kw, s)
            if i < 0: break
            locs.append(i); s = i + 1
        w("    %-10s x%-3d  %s" % (kw.decode(), n, ','.join('0x%05X'%l for l in locs[:8])))

# ---------- F. printf 格式串 ----------
w()
w("### F. 全部 printf 风格格式串（% 开头，>=2 字符）")
pat = re.compile(rb'%[-+ #0-9.]*[diouxXeEfgGcsprb%][^\x00]{0,6}')
fs = []
for m in pat.finditer(D):
    s = m.group()
    if len(s) >= 2 and s[:2] != b'%%':
        fs.append((m.start(), s))
w("  共 %d 处" % len(fs))
for off, s in fs[:60]:
    w("    0x%05X  %r" % (off, s))

open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cfg_parsed', 'tail_ptrtable.txt'), 'w', encoding='utf-8').write('\n'.join(OUT))
print('\n'.join(OUT))
