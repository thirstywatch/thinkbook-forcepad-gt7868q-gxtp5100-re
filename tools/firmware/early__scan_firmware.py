#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TF100A 同族固件扫描器
用途：扫描 fw-candidates 目录下的待检包（.cab / .msu / .exe / .bin / .zip），
      自动解包并查找「汇顶 GT7868Q + 钛方 TF100A」方案的固件特征。

用法：
    set PYTHONIOENCODING=utf-8
    python scan_firmware.py            # 扫描脚本所在目录
    python scan_firmware.py <目录>      # 扫描指定目录

判定依据（来自本机既有样本 TB14P_GT7868Q_14030522_20240202.BIN）：
    1. Cortex-M 向量表：初始 SP 落在 0x20000000 附近，复位向量形如 0x08xxxxxx 且最低位为 1
    2. 特征字符串：TF100A / Test_FW / 5.21.01.xxxxx
    3. 末尾浮点数据表（值约 0.15-0.2，字节模式 ?? ?? ?? 3E）
    4. 镜像尺寸约 56,480 字节（完整版可能略大）
"""
import os
import re
import sys
import math
import struct
import subprocess

SIGS = [b'TF100A', b'Test_FW', b'5.21.01', b'TF100', b'Taifang', b'FORCEPAD', b'ForcePad']

# 本机样本的关键指纹（用于比对）
REF_SP = 0x200076C8
REF_RESET = 0x08005165
REF_SIZE = 56480


def entropy(data):
    if not data:
        return 0.0
    cnt = [0] * 256
    for b in data:
        cnt[b] += 1
    n = len(data)
    e = 0.0
    for c in cnt:
        if c:
            p = c / n
            e -= p * math.log2(p)
    return e


def find_vector_tables(data, limit=8):
    """扫描可能的 Cortex-M 向量表起点"""
    hits = []
    n = len(data)
    for off in range(0, max(0, n - 64), 4):
        sp, rv = struct.unpack_from('<II', data, off)
        # SP 落在 SRAM 区、复位向量落在 flash 区且带 Thumb 位
        if not (0x20000000 <= sp < 0x20040000):
            continue
        if not (0x08000000 <= rv < 0x09000000 and (rv & 1)):
            continue
        # 再验几个中断向量：要么为 0（未用），要么是合法的 flash 地址
        good = 0
        for i in range(2, 18):
            if off + i * 4 + 4 > n:
                break
            v = struct.unpack_from('<I', data, off + i * 4)[0]
            if v == 0 or (0x08000000 <= v < 0x09000000 and (v & 1)):
                good += 1
        if good >= 13:
            hits.append((off, sp, rv))
            if len(hits) >= limit:
                break
    return hits


def tail_float_table(data, img_len):
    """检查镜像末尾 512 字节是否像浮点数据表（?? ?? ?? 3E 模式）"""
    if img_len < 512:
        return 0
    tail = data[img_len - 512:img_len]
    hits = 0
    for i in range(0, len(tail) - 3, 4):
        if tail[i + 3] == 0x3E:  # 小端单精度，指数接近 0.125~0.25
            val = struct.unpack_from('<f', tail, i)[0]
            if 0.10 <= val <= 0.30:
                hits += 1
    return hits


def analyze_blob(name, data):
    """分析一段二进制，返回是否疑似目标固件"""
    n = len(data)
    print(f'\n  [blob] {name}  ({n} 字节, 熵={entropy(data[:262144]):.2f})')

    found_sig = {}
    for s in SIGS:
        i = data.find(s)
        if i != -1:
            found_sig[s.decode()] = hex(i)
    if found_sig:
        print(f'        特征字符串命中: {found_sig}')

    # 版本号 5.21.01.xxxxx
    m = re.search(rb'(\d+\.\d+\.\d+\.\d{4,6})', data)
    if m:
        print(f'        疑似版本号: {m.group(1).decode(errors="ignore")}')

    vts = find_vector_tables(data)
    if vts:
        for off, sp, rv in vts[:4]:
            img_len = n - off
            print(f'        向量表 @ 0x{off:X}  SP=0x{sp:X}  Reset=0x{rv:X}  '
                  f'→ 镜像长 {img_len} 字节')
            if sp == REF_SP and rv == REF_RESET:
                print('        ★★★ SP/Reset 与本机样本完全一致！')
            fc = tail_float_table(data, img_len)
            if fc:
                print(f'        末尾浮点表命中 {fc} 项（疑似 TF100A 固件尾）')
            # 检查向量越界（判断是否完整）
            img_end = 0x08000000 + img_len
            over = []
            for i in range(0, 64):
                if off + i * 4 + 4 > n:
                    break
                v = struct.unpack_from('<I', data, off + i * 4)[0]
                if 0x08000000 <= v < 0x09000000 and (v & 1) and v > img_end:
                    over.append((i, v - img_end))
            if over:
                print(f'        ⚠ 向量越界 {len(over)} 处（镜像可能不完整）: '
                      + ', '.join(f'idx{i}(+{o}B)' for i, o in over[:4]))
            else:
                print('        ✓ 无向量越界 —— 镜像可能是完整的')
            if abs(img_len - REF_SIZE) < 4096:
                print(f'        ★ 尺寸与本机样本接近（{REF_SIZE}）')
    return bool(found_sig or vts)


def try_extract(path, workdir):
    """尝试解包，返回提取出的文件列表"""
    ext = os.path.splitext(path)[1].lower()
    outs = []
    if ext in ('.cab', '.msu'):
        cmd = ['expand', path, '-F:*', workdir]
        try:
            subprocess.run(cmd, capture_output=True, timeout=120)
        except Exception as e:
            print(f'    expand 失败: {e}')
    elif ext in ('.exe', '.zip'):
        # 试 7z
        for sevenzip in ('7z', '7za', r'C:\Program Files\7-Zip\7z.exe'):
            try:
                subprocess.run([sevenzip, 'x', '-y', f'-o{workdir}', path],
                               capture_output=True, timeout=180)
                break
            except Exception:
                continue
    for root, _, files in os.walk(workdir):
        for f in files:
            outs.append(os.path.join(root, f))
    return outs


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(root)
    print(f'扫描目录: {root}')

    targets = []
    for f in sorted(os.listdir(root)):
        p = os.path.join(root, f)
        if not os.path.isfile(p):
            continue
        if os.path.splitext(f)[1].lower() in ('.cab', '.msu', '.exe', '.zip', '.bin'):
            targets.append(p)

    if not targets:
        print('没找到待检包。请把下载的 .cab / .exe 放到本目录后重跑。')
        return

    print(f'找到 {len(targets)} 个待检文件\n')
    verdicts = []
    for p in targets:
        print('=' * 72)
        print(f'文件: {os.path.basename(p)}  ({os.path.getsize(p)} 字节)')
        ext = os.path.splitext(p)[1].lower()
        if ext == '.bin':
            data = open(p, 'rb').read()
            if analyze_blob(os.path.basename(p), data):
                verdicts.append(os.path.basename(p))
        else:
            workdir = os.path.join(root, '_x_' + os.path.splitext(os.path.basename(p))[0])
            os.makedirs(workdir, exist_ok=True)
            extracted = try_extract(p, workdir)
            if not extracted:
                print('    解包无产出（可能不是标准 cab/7z）')
            hit = False
            for e in extracted:
                try:
                    d = open(e, 'rb').read()
                except Exception:
                    continue
                if len(d) < 1024:
                    continue
                if analyze_blob(os.path.relpath(e, root), d):
                    hit = True
            if hit:
                verdicts.append(os.path.basename(p))

    print('\n' + '=' * 72)
    print('汇总：')
    if verdicts:
        print('  ★ 疑似同族/命中特征的文件：')
        for v in verdicts:
            print(f'    - {v}')
    else:
        print('  未命中任何 TF100A 特征。')


if __name__ == '__main__':
    main()
