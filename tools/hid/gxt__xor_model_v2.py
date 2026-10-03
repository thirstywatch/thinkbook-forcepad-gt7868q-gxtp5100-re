# -*- coding: utf-8 -*-
"""
实验 B：给 C = P XOR T[i mod 1024] 一个决定性判决。

上一轮（实验 A）失败的原因：判据选错了。
  "ASCII 串数"在 4 KB 尺度上噪声极大，随机 T 都能到 17，真 T 才 18 —— 无判别力。

本轮改判据 —— 用"结构同构"而不是"看起来像文本"：
  B1. 块内自相似：同相位组（i mod 1024 相同）的字节，其"异或差分"应稳定。
      若 C = P XOR T，则 P 相同 ⇒ C 相同。因此统计"同相位字节的众数占比"。
      （这一条上轮已做，是 T 存在的证据；本轮作为正向确认重跑）
  B2. ★关键判据：对候选解密结果，统计 64 B 窗口的低熵比例。
      真明文固件（tpfw 头部、固件头部）低熵窗口 ~0.8-1.0；
      加扰数据 ~0.0-0.3。这是有量纲的、可对照的判据。
  B3. ★更强判据：解出的数据里，"递增表 / 指针表 / 零填充段"的比例。
      真固件含大量 0x00 填充段和 0xFFFFFFFF、单调递增 u16 表 —— 随机数据没有。
  B4. 负对照升级：随机 T 跑同一套判据，看分位数。
  B5. 若 B2/B3 仍阴性 ⇒ 明确宣布模型被证伪，转向其他假设。
"""
import os, struct, math, collections, random, json

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'cfg_parsed')
os.makedirs(OUT, exist_ok=True)
FW = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
T_PATH = os.path.join(HERE, 'K_gt7868q.bin')

L = []
def w(s=''):
    L.append(s); print(s)

def entropy(b):
    if not b: return 0.0
    c = collections.Counter(b); n = len(b)
    return -sum((v/n)*math.log2(v/n) for v in c.values())

def ascii_runs(b, minlen=6):
    runs, cur = [], 0
    for x in b:
        if 32 <= x < 127: cur += 1
        else:
            if cur >= minlen: runs.append(cur)
            cur = 0
    if cur >= minlen: runs.append(cur)
    return len(runs), sum(runs)

def low_ent_frac(b, win=64, thresh=6.5, step=32):
    """低熵窗口占比：真固件很高，随机数据很低"""
    if len(b) < win: return 0.0
    n = hit = 0
    for k in range(0, len(b)-win, step):
        n += 1
        if entropy(b[k:k+win]) < thresh: hit += 1
    return hit/n if n else 0.0

def run_props(b, win=64, step=32):
    """
    结构性质：
      zero_frac  全 0 窗口比
      ff_frac    全 FF 窗口比
      mono_frac  单调 u16 窗口比（递增表特征）
      const_frac 常量窗口比（重复同一字节）
    """
    if len(b) < win: return (0,0,0,0)
    n=z=ff=mono=const=0
    for k in range(0, len(b)-win, step):
        n += 1
        ch = b[k:k+win]
        if all(x==0 for x in ch): z += 1; continue
        if all(x==0xFF for x in ch): ff += 1; continue
        if len(set(ch)) <= 3: const += 1; continue
        v = struct.unpack('<%dH' % (win//2), ch)
        d = [v[i+1]-v[i] for i in range(len(v)-1)]
        if all(0 <= x <= 4 for x in d) or all(-4 <= x <= 0 for x in d): mono += 1
    return (z/n, ff/n, mono/n, const/n)

def score(b):
    ar_n, ar_len = ascii_runs(b)
    z, ff, mono, const = run_props(b)
    return {'ascii_runs': ar_n, 'ascii_ratio': ar_len/len(b) if b else 0,
            'low_ent': low_ent_frac(b), 'zero': z, 'ff': ff,
            'mono': mono, 'const': const,
            'struct': mono + const + z + ff, 'H': entropy(b)}

def fmt(sc):
    return ('ASCII %4d(%.4f) | 低熵 %.3f | 0段 %.3f | FF段 %.3f | 单调表 %.3f | 常量 %.3f | 结构分 %.3f | H %.3f'
            % (sc['ascii_runs'], sc['ascii_ratio'], sc['low_ent'], sc['zero'],
               sc['ff'], sc['mono'], sc['const'], sc['struct'], sc['H']))

def main():
    w('='*80); w('实验 B：C = P XOR T[i mod 1024] 的决定性判决'); w('='*80)
    fw = open(FW,'rb').read(); T = open(T_PATH,'rb').read()
    yi = fw.find(b'YELSTO')
    start = yi if yi>=0 else 0x1400
    seg = fw[start:]
    w(); w('- 固件 %d B · 加扰段 0x%04X..0x%04X (%d B) · T %d B' % (len(fw), start, len(fw), len(seg), len(T)))

    # ---------- 参照物 ----------
    w(); w('### 0. 参照物（真固件该有的样子）'); w('```')
    w('固件头 0..0x100   ' + fmt(score(fw[:0x100])))
    w('固件头 0..0x1000  ' + fmt(score(fw[:0x1000])))
    tp = open(os.path.join(HERE,'tpfw_86272_PNOR_G1_7863.bin'),'rb').read()
    w('tpfw 头 0..0x100  ' + fmt(score(tp[:0x100])))
    w('tpfw 头 0..0x1000 ' + fmt(score(tp[:0x1000])))
    w('随机数据 4KB      ' + fmt(score(bytes(random.randrange(256) for _ in range(4096)))))
    w('全零 4KB          ' + fmt(score(bytes(4096))))
    w('```')

    # ---------- B1: 同相位组众数（正向确认 T 存在） ----------
    w(); w('### B1. 同相位组众数占比（i mod 1024 相同的字节）')
    w('若 C = P XOR T ⇒ 明文相同处密文相同 ⇒ 众数占比应远高于 1/256')
    w('```')
    for name, data in [('加扰段', seg)]:
        for step in [1024]:
            groups = collections.defaultdict(list)
            for k, x in enumerate(data):
                groups[k % step].append(x)
            shares = []
            for g in groups.values():
                if len(g) < 8: continue
                c = collections.Counter(g)
                shares.append(c.most_common(1)[0][1]/len(g))
            shares.sort()
            w('%s mod %d：组数 %d，众数占比 中位 %.4f 均值 %.4f max %.4f（随机基线 %.4f）'
              % (name, step, len(groups), shares[len(shares)//2], sum(shares)/len(shares),
                 shares[-1], 1/256))
    w('```')

    # ---------- B2/B3: 解密结果的结构分 ----------
    w(); w('### B2. 256 相位 × 变体 —— 按「结构分」排序')
    def bitrev(x): return int('{:08b}'.format(x)[::-1], 2)
    variants = {
        '原样': lambda t: bytes(t),
        '取反': lambda t: bytes((~x)&0xFF for x in t),
        '逆序': lambda t: bytes(t[::-1]),
        '位反转': lambda t: bytes(bitrev(x) for x in t),
    }
    results = []
    for vn, vf in variants.items():
        Tv = vf(T)
        for ph in range(256):
            key = Tv[ph:] + Tv[:ph]
            dec = bytes(a ^ key[k & 1023] for k,a in enumerate(seg))
            sc = score(dec)
            results.append((sc['struct'], sc['low_ent'], vn, ph, sc))
    results.sort(key=lambda r: (-r[0], -r[1]))
    w(); w('**Top 10**'); w()
    w('| 变体 | 相位 | 结构分 | 低熵 | ASCII | 单调表 | 常量 | 0段 | H |')
    w('|---|---|---|---|---|---|---|---|---|')
    for st, le, vn, ph, sc in results[:10]:
        w('| %s | %d | %.4f | %.3f | %d | %.3f | %.3f | %.3f | %.3f |'
          % (vn, ph, st, sc['low_ent'], sc['ascii_runs'], sc['mono'], sc['const'], sc['zero'], sc['H']))

    # ---------- B4: 随机 T 对照 ----------
    w(); w('### B4. 🎯 随机 T 对照（同套判据）')
    random.seed(20260930)
    ctrl_struct, ctrl_low = [], []
    for _ in range(20):
        rt = bytes(random.randrange(256) for _ in range(1024))
        for ph in range(0, 256, 16):
            key = rt[ph:] + rt[:ph]
            dec = bytes(a ^ key[k & 1023] for k,a in enumerate(seg))
            sc = score(dec)
            ctrl_struct.append(sc['struct']); ctrl_low.append(sc['low_ent'])
    ctrl_struct.sort(); ctrl_low.sort()
    n = len(ctrl_struct)
    w('```')
    w('随机 T 结构分：min %.4f · 中位 %.4f · p90 %.4f · max %.4f'
      % (ctrl_struct[0], ctrl_struct[n//2], ctrl_struct[int(n*0.9)], ctrl_struct[-1]))
    w('随机 T 低熵  ：min %.4f · 中位 %.4f · p90 %.4f · max %.4f'
      % (ctrl_low[0], ctrl_low[n//2], ctrl_low[int(n*0.9)], ctrl_low[-1]))
    w('真实 T 最优：结构分 %.4f · 低熵 %.4f（变体 %s 相位 %d）'
      % (results[0][0], results[0][1], results[0][2], results[0][3]))
    w('```')

    # ---------- B5: 判决 ----------
    best = results[0]
    z90 = ctrl_struct[int(n*0.9)]
    w(); w('### B5. 判决'); w('```')
    if best[0] <= z90:
        w('❌ 证伪：真实 T 的最优结构分 (%.4f) 未超过随机 T 的 p90 (%.4f)' % (best[0], z90))
        w('   ⇒ C = P XOR T[i mod 1024]（及取反/逆序/位反转变体）不能解出明文固件')
    else:
        w('✅ 可能成立：真实 T 结构分 (%.4f) > 随机 p90 (%.4f)' % (best[0], z90))
        w('   需进一步人眼核对输出')
    w('```')

    # ---------- 输出最优结果前 256 B ----------
    vn, ph = best[2], best[3]
    key = variants[vn](T); key = key[ph:] + key[:ph]
    dec = bytes(a ^ key[k & 1023] for k,a in enumerate(seg))
    w(); w('### 最优组合输出（前 256 B）—— 变体 %s 相位 %d' % (vn, ph)); w('```')
    for k in range(0, 256, 32):
        ch = dec[k:k+32]
        w('%04X  %-95s |%s|' % (k, ch.hex(' '), ''.join(chr(c) if 32<=c<127 else '.' for c in ch)))
    w('```')

    open(os.path.join(OUT,'xor_model_v2.txt'),'w',encoding='utf-8').write('\n'.join(L))
    w(); w('写入 cfg_parsed/xor_model_v2.txt')

main()
