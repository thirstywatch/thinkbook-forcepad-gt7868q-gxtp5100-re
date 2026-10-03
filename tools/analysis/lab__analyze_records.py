# analyze_records.py - 分析固件容器前 105,148 字节 = 97 x 1084 记录区
import struct, collections, math

BIN = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
data = open(BIN, 'rb').read()
REC = 1084
N = 97
print('file=%d bytes; record region = %d x %d = %d' % (len(data), N, REC, N*REC))

recs = [data[i*REC:(i+1)*REC] for i in range(N)]

def ent(b):
    c = collections.Counter(b)
    n = len(b)
    return -sum((v/n)*math.log2(v/n) for v in c.values())

print('\n=== 每条记录的熵与前 16 字节 ===')
for i in (0,1,2,3,4,5,50,96):
    r = recs[i]
    print('  #%02d ent=%.2f  %s' % (i, ent(r), ' '.join('%02X'%x for x in r[:16])))

# 记录 0 像是容器头
print('\n=== 记录 0 (疑似容器头) 完整前 128 字节 ===')
for off in range(0, 128, 16):
    print('   %04X  %s' % (off, ' '.join('%02X'%x for x in recs[0][off:off+16])))

# 统计每条记录的特征：非零率、float32 合理率、首 4 字节
print('\n=== 各记录统计（前 24 条 + 最后 4 条）===')
print('   idx  nonzero%  floatOK%  first8')
for i in list(range(24)) + [93,94,95,96]:
    r = recs[i]
    nz = sum(1 for b in r if b) / len(r)
    # 按 4 字节对齐统计"像 float32"的比例（|v| in [1e-6, 1e6] 或 0）
    ok = 0; tot = 0
    for off in range(0, len(r)-3, 4):
        v = struct.unpack_from('<f', r, off)[0]
        tot += 1
        if v == 0 or (abs(v) > 1e-8 and abs(v) < 1e6 and not math.isnan(v) and not math.isinf(v)):
            ok += 1
    print('   %3d   %5.1f%%   %5.1f%%   %s' % (i, nz*100, ok/tot*100,
          ' '.join('%02X'%x for x in r[:8])))

# 记录之间是否只差一个小头部？比较记录 4/5 的差异分布
print('\n=== 记录间差异分布（4 vs 5, 5 vs 6, 50 vs 51）===')
for a, b in ((4,5),(5,6),(50,51),(95,96)):
    diff = sum(1 for x, y in zip(recs[a], recs[b]) if x != y)
    print('   #%d vs #%d: 不同字节 %d / %d' % (a, b, diff, REC))

# 记录内是否有重复的 3 字节/4 字节周期结构（波形特征）
print('\n=== 周期性检测（自相关前 3 个峰）===')
for i in (4, 5, 50, 96):
    r = recs[i]
    best = []
    for lag in range(2, 64):
        s = sum(1 for k in range(0, len(r)-lag) if r[k] == r[k+lag])
        best.append((s/(len(r)-lag), lag))
    best.sort(reverse=True)
    print('   #%02d 最相似周期: %s' % (i, ', '.join('lag=%d(%.2f)' % (l, v) for v, l in best[:3])))
