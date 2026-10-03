# -*- coding: utf-8 -*-
"""
实验 A：验证 C = P XOR T[i mod 1024] 加扰模型。

方法（穷举 + 自证伪）：
  1. 取官方固件 TB14P_GT7868Q_*.BIN 的加扰段（YELSTO 之后）
  2. 取 T = GT7868Q_scramble_key.bin（1024 B）
  3. 尝试 T 的全部 256 个旋转相位 × 若干变体（原样/取反/字节反转/位反转）
  4. 对每个组合，计算解密结果的"可读性判据"：
       - ASCII 串数（>=6）
       - 低熵段（是否有连续 32 B 熵 < 4.0 的段）
       - 8051 操作码密度
       - 与 tpfw.bin 头部的同构度
  5. ★ 必须有阳性对照：随机 T 的基线是多少
     且必须有"已知明文对照"：拿 tpfw.bin 自己的加扰段做同样测试（如果 tpfw 体部也被加扰）
"""
import os, struct, math, collections, random, json

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'cfg_parsed')
os.makedirs(OUT, exist_ok=True)

FW = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
T_PATH = os.path.join(HERE, 'K_gt7868q.bin')

L = []
def w(s=''):
    L.append(s)
    print(s)


def entropy(b):
    if not b:
        return 0.0
    c = collections.Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def ascii_runs(b, minlen=6):
    """统计 >=minlen 的可打印 ASCII 连续串数量与总长"""
    runs, cur = [], 0
    for x in b:
        if 32 <= x < 127:
            cur += 1
        else:
            if cur >= minlen:
                runs.append(cur)
            cur = 0
    if cur >= minlen:
        runs.append(cur)
    return len(runs), sum(runs)


def opcode_density(b):
    op = {0x74, 0x75, 0x78, 0x79, 0x12, 0x02, 0x22, 0xC2, 0xD2, 0xE5, 0xF5}
    return sum(1 for x in b if x in op) / len(b) if b else 0


def low_entropy_fraction(b, win=64, thresh=5.0, step=16):
    """低熵窗口占比"""
    if len(b) < win:
        return 0.0
    n = 0
    hit = 0
    for k in range(0, len(b) - win, step):
        n += 1
        if entropy(b[k:k + win]) < thresh:
            hit += 1
    return hit / n if n else 0.0


def score(b, label=''):
    ar_n, ar_len = ascii_runs(b)
    return {
        'ascii_runs': ar_n,
        'ascii_len': ar_len,
        'ascii_ratio': ar_len / len(b) if b else 0,
        'opcode': opcode_density(b),
        'low_ent': low_entropy_fraction(b),
        'H': entropy(b),
    }


def fmt(sc):
    return ('ASCII串 %4d / 占比 %.4f | 操作码 %.4f | 低熵窗口 %.4f | H %.3f'
            % (sc['ascii_runs'], sc['ascii_ratio'], sc['opcode'], sc['low_ent'], sc['H']))


def main():
    w('=' * 80)
    w('实验 A：验证 C = P XOR T[i mod 1024]')
    w('=' * 80)

    fw = open(FW, 'rb').read()
    T = open(T_PATH, 'rb').read()
    w()
    w('- 固件：%s（%d B）' % (os.path.basename(FW), len(fw)))
    w('- T   ：%d B' % len(T))

    # 找加扰段
    yi = fw.find(b'YELSTO')
    w('- YELSTO 锚点：0x%04X' % yi if yi >= 0 else '- 无 YELSTO')
    start = yi if yi >= 0 else 0x1400
    seg = fw[start:]
    w('- 加扰段：0x%04X .. 0x%04X（%d B）' % (start, len(fw), len(seg)))

    w()
    w('### 0. 基线（不解密）')
    w('```')
    w('原始加扰段      ' + fmt(score(seg)))
    head = fw[:0x100]
    w('固件头部(0..0x100)' + fmt(score(head)))
    w('```')

    # ---------- 阳性对照：T 的自洽 ----------
    w()
    w('### 1. T 本身的性质')
    w('```')
    w('T 的熵 = %.4f  零占比 = %.4f  FF占比 = %.4f  不同值 = %d'
      % (entropy(T), T.count(0) / len(T), T.count(0xFF) / len(T), len(set(T))))
    w('```')

    # ---------- 主实验：256 相位 × 变体 ----------
    w()
    w('### 2. 主实验：256 相位 × 4 变体')
    w()
    w('变体：原样 / 逐字节取反 / 表逆序 / 位反转')

    def bitrev(x):
        return int('{:08b}'.format(x)[::-1], 2)

    variants = {
        '原样': lambda t: bytes(t),
        '取反': lambda t: bytes((~x) & 0xFF for x in t),
        '逆序': lambda t: bytes(t[::-1]),
        '位反转': lambda t: bytes(bitrev(x) for x in t),
    }

    results = []
    for vname, vfn in variants.items():
        Tv = vfn(T)
        for phase in range(256):
            # 循环左移 phase
            key = Tv[phase:] + Tv[:phase]
            # 只用前 4096 B 做快速评分
            probe = seg[:4096]
            dec = bytes(a ^ key[k & 1023] for k, a in enumerate(probe))
            sc = score(dec)
            results.append((sc['ascii_runs'], sc['ascii_ratio'], sc['low_ent'],
                            sc['opcode'], vname, phase, sc))

    # 排序：ASCII 串数优先，其次 ASCII 占比
    results.sort(key=lambda r: (-r[0], -r[1]))
    w()
    w('**Top 15（按 ASCII 串数降序）**')
    w()
    w('| 变体 | 相位 | ASCII串 | ASCII占比 | 操作码 | 低熵 | H |')
    w('|---|---|---|---|---|---|---|')
    for (an, ar, le, op, vn, ph, sc) in results[:15]:
        w('| %s | %d | %d | %.4f | %.4f | %.4f | %.3f |' % (vn, ph, an, ar, op, le, sc['H']))

    w()
    w('**分布统计（判断是否为真信号）**')
    w()
    ans = [r[0] for r in results]
    w('- ASCII 串数：min %d · 中位 %d · max %d' % (min(ans), sorted(ans)[len(ans)//2], max(ans)))
    w('- 若 max 只是略高于中位 ⇒ **无信号**；若 max 显著突出 ⇒ 有戏')

    # ---------- 随机 T 对照 ----------
    w()
    w('### 3. 🎯 随机 T 对照（决定性的阴性基线）')
    w()
    random.seed(20260930)
    rand_max = []
    for trial in range(30):
        rt = bytes(random.randrange(256) for _ in range(1024))
        best = 0
        for phase in range(0, 256, 8):   # 抽样
            key = rt[phase:] + rt[:phase]
            probe = seg[:4096]
            dec = bytes(a ^ key[k & 1023] for k, a in enumerate(probe))
            sc = score(dec)
            best = max(best, sc['ascii_runs'])
        rand_max.append(best)
    w('- 随机 T 的 ASCII 串数 max：min %d · 中位 %d · max %d'
      % (min(rand_max), sorted(rand_max)[len(rand_max)//2], max(rand_max)))
    w('- 真实 T 的最好成绩：%d' % results[0][0])
    w()

    # ---------- 4. 用 tpfw.bin 做"已知明文"对照 ----------
    w()
    w('### 4. tpfw.bin 体部做同样测试（它若也是加扰的，应为阴性）')
    w()
    tp = open(os.path.join(HERE, 'tpfw_86272_PNOR_G1_7863.bin'), 'rb').read()
    tpseg = tp[0x1000:0x1000 + 4096]
    w('```')
    w('tpfw 体部原始   ' + fmt(score(tpseg)))
    w('tpfw 头部 0..0x100 ' + fmt(score(tp[:0x100])))
    w('```')

    # ---------- 5. 若最好成绩突出，输出完整解密结果 ----------
    best = results[0]
    w()
    w('### 5. 最优组合的完整输出（前 512 B，看是否有结构）')
    w()
    vn, ph = best[4], best[5]
    key = variants[vn](T)
    key = key[ph:] + key[:ph]
    full = bytes(a ^ key[k & 1023] for k, a in enumerate(seg))
    w('变体 `%s` 相位 `%d`' % (vn, ph))
    w('```')
    for k in range(0, 512, 32):
        chunk = full[k:k + 32]
        hx = chunk.hex(' ')
        tx = ''.join(chr(c) if 32 <= c < 127 else '.' for c in chunk)
        w('%04X  %-95s |%s|' % (k, hx, tx))
    w('```')

    txt = '\n'.join(L)
    open(os.path.join(OUT, 'xor_model_test.txt'), 'w', encoding='utf-8').write(txt)
    json.dump({'best': {'variant': best[4], 'phase': best[5], 'score': best[6]},
               'all': [{'ascii_runs': r[0], 'ascii_ratio': r[1], 'variant': r[4], 'phase': r[5]}
                       for r in results]},
              open(os.path.join(OUT, 'xor_model_test.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    w()
    w('写入：cfg_parsed/xor_model_test.txt · xor_model_test.json')


main()
