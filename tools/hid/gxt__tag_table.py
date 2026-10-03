# -*- coding: utf-8 -*-
"""
A-13: 把 tpcfgsid*.cfg 的 TLV 全量表解成 TAG 语义表。

方法（自证伪优先）：
  1. 用已确认的 [TAG][LEN][payload] 遍历器（LE16? 先测）解出全部块。
  2. 对每个 TAG 统计：出现次数 / LEN 集合 / 是否定长 / 载荷统计特征。
  3. 一致性检验：同一 TAG 在不同 sid 之间是否同长度、同语义倾向。
  4. 语义归类线索：
     - 载荷是 ASCII          -> 字符串/版本
     - 载荷是递增序列         -> 通道/引脚映射
     - 载荷是大端 u16 递减梯度 -> 时序/系数
     - 载荷含 0x80 附近值     -> 电容基线
     - 载荷长度 == 2*(行*列)弱 -> 通道表
  5. 交叉验证：LEN 字段是 1 字节还是 2 字节？遍历覆盖率是多少？
     -> 若 2 字节 LEN 也能走通且覆盖率更高，则前面的结论要改。
"""
import struct, json, os, sys
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_DIR = os.path.join(HERE, 'cfg')
OUT = os.path.join(HERE, 'cfg_parsed')
os.makedirs(OUT, exist_ok=True)

FILES = ['sid0.bin', 'sid2.bin', 'sid3.bin']
L = []
def w(s=''):
    L.append(s)
    print(s)


def ascii_ratio(b):
    if not b:
        return 0.0
    ok = sum(1 for x in b if 32 <= x < 127)
    return ok / len(b)


def walk(data, start, len_bytes=1, endian='little'):
    """[TAG][LEN][payload] 流遍历。返回 (blocks, coverage_bytes)."""
    blocks = []
    i = start
    n = len(data)
    while i < n:
        if i + 1 + len_bytes > n:
            break
        tag = data[i]
        if len_bytes == 1:
            ln = data[i + 1]
            hdr = 2
        elif len_bytes == 2:
            ln = struct.unpack_from('<H' if endian == 'little' else '>H', data, i + 1)[0]
            hdr = 3
        else:
            raise ValueError
        j = i + hdr + ln
        if j > n:
            blocks.append((i, tag, ln, None, 'TRUNC'))
            break
        blocks.append((i, tag, ln, data[i + hdr:j], None))
        i = j
    cov = sum(h + (l if p is not None else 0) for (_, _, l, p, e) in
              [(a, b, c, d, e) for (a, b, c, d, e) in blocks if e is None]
              for h in [0])  # placeholder, recomputed below
    cov = 0
    for (off, tag, ln, pay, err) in blocks:
        if err:
            continue
        cov += 1 + len_bytes + ln
    return blocks, cov


def main():
    w('=' * 78)
    w('A-13  tpcfgsid*.cfg  TAG 语义表')
    w('=' * 78)

    # ---------- 0. 先自证：LEN 宽度与起始偏移 ----------
    w()
    w('### 0. 遍历器自证（覆盖率对照）')
    w()
    w('| 文件 | 起始 | LEN宽 | 块数 | 覆盖字节 | 覆盖率 | 截断 | 备注 |')
    w('|---|---|---|---|---|---|---|---|')
    variants = {}
    rawdat = {}
    for fn in FILES:
        p = os.path.join(CFG_DIR, fn)
        if not os.path.exists(p):
            # 回退到工区根
            p2 = os.path.join(HERE, fn)
            p = p2 if os.path.exists(p2) else p
        data = open(p, 'rb').read()
        rawdat[fn] = data
        for start in (0x38, 0x3C, 0x40):
            for lb in (1, 2):
                try:
                    blk, cov = walk(data, start, lb)
                except Exception as ex:
                    w('| %s | 0x%02X | %d | - | - | - | - | %s |' % (fn, start, lb, ex))
                    continue
                trunc = sum(1 for x in blk if x[4])
                mark = ''
                if trunc == 0 and cov > 0.9 * len(data):
                    mark = '★'
                w('| %s | 0x%02X | %d | %d | %d | %.1f%% | %d | %s |'
                  % (fn, start, lb, len(blk), cov, 100.0 * cov / len(data), trunc, mark))
                variants[(fn, start, lb)] = (blk, cov)

    # 选最优：优先「无截断」，其次覆盖率最高；只有一个尾部截断块是正常的（EOF 处的零填充）
    best = {}
    for fn in FILES:
        cands = [(k, v) for k, v in variants.items() if k[0] == fn]
        if not cands:
            continue
        # 截断块数 <= 1 视为可接受（尾块）
        cands = [(k, v) for k, v in cands
                 if sum(1 for x in v[0] if x[4]) <= 1 and v[0]]
        if not cands:
            continue
        cands.sort(key=lambda kv: -kv[1][1])
        best[fn] = cands[0]

    w()
    w('**选定**：' + ' · '.join(
        '%s → start=0x%02X lenw=%d (cover %.1f%%)'
        % (fn, kv[0][1], kv[0][2], 100.0 * kv[1][1] / len(rawdat[fn]))
        for fn, kv in sorted(best.items())))

    json.dump({fn: {'start': kv[0][1], 'lenw': kv[0][2], 'cover': kv[1][1],
                    'size': len(rawdat[fn])} for fn, kv in best.items()},
              open(os.path.join(OUT, 'tag_walker_choice.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)

    # ---------- 1. 全量块表 ----------
    allblocks = {}
    for fn in FILES:
        if fn not in best:
            continue
        blk, cov = best[fn][1]
        allblocks[fn] = blk

    w()
    w('### 1. 全量 TAG 清单（跨三份 cfg 汇总）')
    w()
    tagstat = defaultdict(lambda: {'n': 0, 'lens': [], 'bytes': 0, 'files': Counter(),
                                   'sample': None, 'ascii': [], 'payloads': []})
    for fn, blk in allblocks.items():
        for (off, tag, ln, pay, err) in blk:
            s = tagstat[tag]
            s['n'] += 1
            s['lens'].append(ln)
            s['bytes'] += ln
            s['files'][fn] += 1
            if pay is not None:
                s['ascii'].append(ascii_ratio(pay))
                if len(s['payloads']) < 12:
                    s['payloads'].append((fn, off, pay))

    rows = []
    for tag, s in sorted(tagstat.items()):
        lens = sorted(set(s['lens']))
        fixed = '定长' if len(lens) == 1 else '变长'
        ar = sum(s['ascii']) / len(s['ascii']) if s['ascii'] else 0.0
        rows.append((tag, s['n'], lens, fixed, s['bytes'], dict(s['files']), ar))
    w('| TAG | 次数 | LEN 取值 | 定/变 | 总字节 | 分布(sid0/sid2/sid3) | ASCII率 |')
    w('|---|---|---|---|---|---|---|')
    for tag, n, lens, fixed, byt, files, ar in rows:
        w('| `0x%02X` | %d | %s | %s | %d | %d/%d/%d | %.2f |'
          % (tag, n, ','.join(str(x) for x in lens[:8]) + ('…' if len(lens) > 8 else ''),
             fixed, byt, files.get('sid0.bin', 0), files.get('sid2.bin', 0),
             files.get('sid3.bin', 0), ar))
    w()
    w('**统计**：共 %d 个不同 TAG，%d 个块。'
      % (len(tagstat), sum(s['n'] for s in tagstat.values())))

    # ---------- 2. 定长 TAG 的跨文件一致性（最强的语义线索） ----------
    w()
    w('### 2. 🎯 定长且跨文件复现的 TAG —— 最可能是「有明确语义的配置项」')
    w()
    w('判据：同一 TAG 在 **≥2 份不同厂商 cfg** 里出现，且 **LEN 完全一致**。')
    w()
    w('| TAG | LEN | 出现文件 | 出现次数 | 载荷样例（hex） | 语义猜测 |')
    w('|---|---|---|---|---|---|')
    strong = []
    for tag, s in sorted(tagstat.items()):
        lens = sorted(set(s['lens']))
        if len(lens) != 1:
            continue
        nf = sum(1 for k, v in s['files'].items() if v > 0)
        if nf < 2:
            continue
        sample = s['payloads'][0][2] if s['payloads'] else b''
        hexs = sample[:24].hex(' ')
        strong.append((tag, lens[0], s['files'], s['n'], sample))
        w('| `0x%02X` | %d | %s | %d | `%s`%s | ? |'
          % (tag, lens[0], ','.join(sorted(k[:4] for k in s['files'] if s['files'][k] > 0)),
             s['n'], hexs, '…' if len(sample) > 24 else ''))
    w()
    w('**强 TAG 数 = %d**' % len(strong))

    # ---------- 3. 按长度 = 通道数 的候选 ----------
    w()
    w('### 3. 通道/矩阵表候选（长度是偶数、载荷是递增或 0x80 附近）')
    w()
    w('| 文件 | 偏移 | TAG | LEN | 判定 | 首16字节 |')
    w('|---|---|---|---|---|---|')
    for fn, blk in allblocks.items():
        for (off, tag, ln, pay, err) in blk:
            if pay is None or ln < 8 or ln % 2:
                continue
            u = [struct.unpack_from('<H', pay, k)[0] for k in range(0, ln - 1, 2)]
            inc = sum(1 for k in range(1, len(u)) if u[k] == u[k - 1] + 1)
            near128 = sum(1 for x in u if 100 <= x <= 201)
            verdict = []
            if inc >= len(u) * 0.5:
                verdict.append('递增序列(%d/%d)' % (inc, len(u) - 1))
            if near128 >= len(u) * 0.5:
                verdict.append('128基准(%d/%d)' % (near128, len(u)))
            if verdict:
                w('| %s | 0x%04X | `0x%02X` | %d | %s | %s |'
                  % (fn, off, tag, ln, ' + '.join(verdict), pay[:16].hex(' ')))

    # ---------- 4. 每个 TAG 的详细 dump ----------
    w()
    w('### 4. 逐 TAG 详细表（含所有出现位点）')
    for tag, s in sorted(tagstat.items()):
        lens = sorted(set(s['lens']))
        w()
        w('#### TAG `0x%02X`  ·  次数 %d  ·  LEN {%s}  ·  总 %d B'
          % (tag, s['n'], ','.join(str(x) for x in lens), s['bytes']))
        w()
        w('| 文件 | 偏移 | LEN | 载荷 |')
        w('|---|---|---|---|')
        for fn, blk in allblocks.items():
            for (off, t2, ln, pay, err) in blk:
                if t2 != tag:
                    continue
                if pay is None:
                    w('| %s | 0x%04X | %d | (截断) |' % (fn, off, ln))
                elif ln <= 24:
                    w('| %s | 0x%04X | %d | `%s` |' % (fn, off, ln, pay.hex(' ')))
                else:
                    w('| %s | 0x%04X | %d | `%s` … `%s` |'
                      % (fn, off, ln, pay[:16].hex(' '), pay[-8:].hex(' ')))

    txt = '\n'.join(L)
    open(os.path.join(OUT, 'tag_table.txt'), 'w', encoding='utf-8').write(txt)

    # ---------- 5. 机器可读导出 ----------
    exp = {}
    for tag, s in tagstat.items():
        exp['%02X' % tag] = {
            'count': s['n'],
            'lens': sorted(set(s['lens'])),
            'files': dict(s['files']),
            'sites': [[fn, off, ln] for fn, blk in allblocks.items()
                      for (off, t2, ln, pay, err) in blk if t2 == tag],
        }
    json.dump(exp, open(os.path.join(OUT, 'tag_table.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    w()
    w('写入：cfg_parsed/tag_table.txt  ·  cfg_parsed/tag_table.json')


main()
