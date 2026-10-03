# -*- coding: utf-8 -*-
"""
A-13 最终定案：**子记录语法**。

铁证（raw 对齐）：
  sid0 @0x0336  TAG=0x0E LEN=0x59
     0e 59 | 00 99 66 1e 10 02 0c 19 14 0c 03 5a 1a 5a 14 18 1e 28 18 1e 28
             18 1e 28 18 1e 28 03 40 00 08 04 0f 00 00 00 0a 15 10 5b 00 80
             00 20 00 a0 00 00 00 00 00 00 00 00
           | 30 5c |
             0a 00 14 00 50 00 20 03 e8 03 d0 07 40 1f 10 27 58 02 2d 00 90 01
             00 00 88 13 00 00 10 27 00 00
           | f4 01 00 00 | a0 0f 00 00 | 40 1f 00 00 | 08 00 |
           | 0c 5d | 20 00 40 00 c0 00 02 02 | 00 00 |
           | 0c 5e | 06 ...
  sid3 @0x051E 附近同类块
           ... 0a 0a 04 | 30 5c | 00 00 00 00 |
           | 30 5c | 0a 00 14 00 ... (同样的值阶梯)
           | f4 01 00 00 | a0 0f 00 00 | 40 1f 00 00 | 08 00 |
           | 0c 5d | 40 00 80 00 c0 00 02 02 | 01 00 |
           | 0c 5e | 06 3c 00 50 00 3c 00 50 00 | 00 16 5f | ...
           | 10 00 00 00 ... 00 e8 03 e8 03 | 00 9e 60 00 80

由此得到的语法（sub-record = u16 tag + u16 len + payload）：
  - 0x5C30: 值阶梯（含 400/600 时长常量）  -> **时长/系数阶**
  - 0x5D0C: 4×u16                      -> 某组参数
  - 0x5E0C: n×u16                      -> 某组参数
  - 0x5F16: 全 0
  - 0x5F0A ... 

⚠️ 但 K5 已证 0x5C..0x5F 家族频次 ≈ 随机基线 —— 所以这些「subtag」需要
   在**跨文件重复**的基础上才能认定为真。本脚本对每个候选子 tag 做该检验。
"""
import os, struct, json
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_DIR = os.path.join(HERE, 'cfg')
OUT = os.path.join(HERE, 'cfg_parsed')
os.makedirs(OUT, exist_ok=True)

FILES = ['sid0.bin', 'sid2.bin', 'sid3.bin']

L = []
def w(s=''):
    L.append(s)
    print(s)


# 从两处对齐中提取的「公共骨架」——必须逐字节相同才算真结构
SKELETONS = {
    'A_阶梯头部': bytes.fromhex('30 5c 0a 00 14 00 50 00 20 03 e8 03 d0 07 40 1f 10 27 58 02 2d 00 90 01 00 00 88 13 00 00 10 27 00 00'),
    'B_阶梯尾': bytes.fromhex('f4 01 00 00 a0 0f 00 00 40 1f 00 00 08 00'),
    'C_5D0C': bytes.fromhex('0c 5d'),
    'D_5E0C': bytes.fromhex('0c 5e'),
    'E_5F16': bytes.fromhex('16 5f'),
    'F_5F0A': bytes.fromhex('0a 55'),
}

# 时长常量
NAMES = {0x0190: '400', 0x0258: '600', 0x03E8: '1000', 0x012C: '300',
         0x01F4: '500', 0x0064: '100', 0x00C8: '200', 0x001E: '30',
         0x0032: '50', 0x0014: '20', 0x000A: '10', 0x1388: '5000',
         0x2710: '10000', 0x1F40: '8000', 0x07D0: '2000', 0x0320: '800'}


def main():
    w('=' * 78)
    w('A-13 最终定案：跨厂商公共骨架 + 值阶梯')
    w('=' * 78)

    dat = {}
    for fn in FILES:
        p = os.path.join(CFG_DIR, fn)
        if not os.path.exists(p):
            p = os.path.join(HERE, fn)
        dat[fn] = open(p, 'rb').read()

    # ---------- S1 骨架验证：是否两文件都有、且位置关系一致 ----------
    w()
    w('### S1 公共骨架验证（跨文件逐字节相同）')
    w()
    w('| 骨架 | 长度 | 内容 | sid0 位置 | sid2 | sid3 | 结论 |')
    w('|---|---|---|---|---|---|---|')
    for name, sk in SKELETONS.items():
        locs = {}
        for fn in FILES:
            i = dat[fn].find(sk)
            locs[fn] = i
        nf = sum(1 for fn in FILES if locs[fn] >= 0)
        # 只算 sid0 / sid3 是否都有
        ok = '✅ 跨厂商共用' if (locs['sid0.bin'] >= 0 and locs['sid3.bin'] >= 0) else \
             ('仅一份' if nf == 1 else '❌ 缺失')
        w('| %s | %d | `%s` | %s | %s | %s | %s |'
          % (name, len(sk), sk[:20].hex(' ') + ('…' if len(sk) > 20 else ''),
             '0x%04X' % locs['sid0.bin'] if locs['sid0.bin'] >= 0 else '—',
             '0x%04X' % locs['sid2.bin'] if locs['sid2.bin'] >= 0 else '—',
             '0x%04X' % locs['sid3.bin'] if locs['sid3.bin'] >= 0 else '—', ok))

    # ---------- S2 值阶梯解剖 ----------
    w()
    w('### S2 🎯 值阶梯完整解剖（骨架 A）')
    w()
    for fn in ('sid0.bin', 'sid3.bin'):
        i = dat[fn].find(SKELETONS['A_阶梯头部'])
        if i < 0:
            w('- %s：无' % fn)
            continue
        sk = SKELETONS['A_阶梯头部']
        w('#### %s @0x%04X' % (fn, i))
        w()
        w('| 相对偏移 | 原始 hex | u16 | 含义 |')
        w('|---|---|---|---|')
        for k in range(0, len(sk) - 1, 2):
            v = struct.unpack_from('<H', sk, k)[0]
            w('| +%d | `%s` | %d | %s |' % (k, sk[k:k + 2].hex(' '), v, NAMES.get(v, '')))
        w()

    # ---------- S3 阶梯上下文更长片段 ----------
    w()
    w('### S3 阶梯前后各 32 字节（更长上下文）')
    w()
    for fn in ('sid0.bin', 'sid3.bin'):
        i = dat[fn].find(SKELETONS['A_阶梯头部'])
        if i < 0:
            continue
        w('```')
        w('%s @0x%04X' % (fn, i))
        w('  前 32: %s' % dat[fn][max(0, i - 32):i].hex(' '))
        w('  阶梯 : %s' % dat[fn][i:i + 36].hex(' '))
        w('  后 32: %s' % dat[fn][i + 36:i + 36 + 32].hex(' '))
        w('```')
        w()

    # ---------- S4 跨文件相同 u16 序列搜索 ----------
    w()
    w('### S4 跨文件相同的 u16 序列（≥4 项连续相同）')
    w()
    def u16seq(data):
        return [struct.unpack_from('<H', data, k)[0] for k in range(0, len(data) - 1, 2)]
    for fa, fb in (('sid0.bin', 'sid2.bin'), ('sid0.bin', 'sid3.bin'), ('sid2.bin', 'sid3.bin')):
        A, B = u16seq(dat[fa]), u16seq(dat[fb])
        idx = defaultdict(list)
        for k in range(0, len(B) - 3):
            idx[tuple(B[k:k + 4])].append(k)
        found = []
        seen = set()
        for k in range(0, len(A) - 3):
            key = tuple(A[k:k + 4])
            if key in idx and key not in seen:
                seen.add(key)
                found.append((k * 2, idx[key][0] * 2, key))
        w('**%s ↔ %s**：%d 个 ≥4 项相同的 u16 序列' % (fa, fb, len(found)))
        w()
        w('| %s 偏移 | %s 偏移 | u16 序列 | 标注 |' % (fa, fb))
        w('|---|---|---|---|')
        for (x, y, key) in sorted(found, key=lambda t: -sum(1 for v in t[2] if v in NAMES))[:20]:
            ann = ', '.join('%d%s' % (v, '(%s)' % NAMES[v] if v in NAMES else '') for v in key)
            w('| 0x%04X | 0x%04X | %s | %s |' % (x, y, ann,
                                                '★ 含时长常量' if any(v in NAMES for v in key) else ''))
        w()

    txt = '\n'.join(L)
    open(os.path.join(OUT, 'skeleton_final.txt'), 'w', encoding='utf-8').write(txt)
    w()
    w('写入：cfg_parsed/skeleton_final.txt')


main()
