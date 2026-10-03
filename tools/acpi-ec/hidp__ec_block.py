#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ec_block.py -- 按 Delphi TCompressedBlockReader / Inno Setup 的 "CBlock" 格式解析 overlay。

依据（本轮从 .text 字符串+类型名确认，不是猜）：
  TCompressedBlockReader / TCompressedBlockReaderQ
  TDecompressorReadProc / TCustomDecompressorClassX
  TLZMA1SmallDecompressor / LZMADecompSmall / TLZMAInternalDecoderState
  TSetupCompressMethod => cmLZMA / cmLZMA2
  DecompressInto / ECompressDataError / ECompressInternalError
  ⇒ 说明 payload 是【分块 + 每块选一个压缩方法】的结构，不是"整块加密再 LZMA"。

Inno Setup 的 CBlock 布局（经典实现，Delphi 亦同）：
    StoredSize : LongWord;      // 压缩后长度
    Flags      : Byte;          // bit0-1 = 压缩方法(0=store,1=zlib,2=bzip2,3=lzma1)
                                  // bit2-7 = 保留
    CRC32      : LongWord;      // 原始数据 CRC32
  之后是 StoredSize 字节的压缩数据
块与块之间连续排列，读到文件尾为止。

★ 本脚本做三件事：
  1) 试各种"块头偏移"（0 / 4 / 8 / 12…）看能否自洽切出全文件
  2) 找到能切通的那个偏移后，逐块解压，打印块类型分布
  3) 输出解出的总字节数 + 首部预览 ⇒ 就是 EC 固件本体
"""
import struct, sys, zlib, lzma, collections

OVERLAY_OFF = 0x2C000
FN = 'NJME01WW.exe'
d = open(FN, 'rb').read()
ov = d[OVERLAY_OFF:]
print('overlay = %d B (0x%X)' % (len(ov), len(ov)))
print('前 64 B:', ov[:64].hex(' '))
print()

METHOD = {0: 'store', 1: 'zlib', 2: 'bzip2', 3: 'lzma1'}


def try_decompress(flags, payload):
    m = flags & 0x03
    if m == 0:
        return payload
    if m == 1:
        try:
            return zlib.decompress(payload)
        except Exception:
            try:
                return zlib.decompress(payload, -15)
            except Exception:
                return None
    if m == 2:
        import bz2
        try:
            return bz2.decompress(payload)
        except Exception:
            return None
    if m == 3:
        # LZMA1：Delphi 的 TLZMA1SmallDecompressor 用的是 5 字节 props 头
        try:
            return lzma.decompress(payload, format=lzma.FORMAT_ALONE)
        except Exception:
            pass
        try:
            return lzma.decompress(payload, format=lzma.FORMAT_RAW,
                                   filters=[{'id': lzma.FILTER_LZMA1}])
        except Exception:
            return None
    return None


def scan(start_skip):
    """从 start_skip 开始按 CBlock 切，检验能否自洽走到文件尾"""
    off = start_skip
    blocks = []
    n = len(ov)
    while off + 9 <= n:
        stored = struct.unpack_from('<I', ov, off)[0]
        flags = ov[off + 4]
        if stored == 0 or stored > n - off - 9:
            break
        payload = ov[off + 9: off + 9 + stored]
        blocks.append((off, stored, flags, payload))
        off += 9 + stored
        if len(blocks) > 200000:
            break
    consumed = off - start_skip
    return blocks, consumed, off


print('=' * 88)
print('A) 扫描 CBlock 结构：找能自洽切通的起始偏移')
print('=' * 88)
best = None
for skip in range(0, 40):
    blocks, consumed, endoff = scan(skip)
    if not blocks:
        continue
    ratio = consumed / (len(ov) - skip)
    # 判据：能吃掉文件的绝大部分，且块数合理
    if ratio > 0.98 and len(blocks) < 100000:
        print('  ★ skip=%-3d 块数=%-7d 吃掉 %.4f  结束@0x%X (剩 %d B 未吃)'
              % (skip, len(blocks), ratio, endoff, len(ov) - endoff))
        if best is None or ratio > best[1]:
            best = (skip, ratio, blocks, endoff)
    elif len(blocks) <= 3:
        print('    skip=%-3d 块数=%-3d 吃掉 %.4f' % (skip, len(blocks), ratio))

if best is None:
    print('\n  ✘ 没有一个起始偏移能让 CBlock 结构自洽走通')
    print('    ⇒ overlay 不是 Delphi TCompressedBlockReader 格式')
    print('    ⇒ 或块头不是 9 字节（可能有别的布局）')
    sys.exit(1)

skip, ratio, blocks, endoff = best
print()
print('=' * 88)
print('B) 用 skip=%d 逐块解压' % skip)
print('=' * 88)
meth_cnt = collections.Counter()
out = bytearray()
fail = 0
for i, (off, stored, flags, payload) in enumerate(blocks):
    m = flags & 0x03
    meth_cnt[METHOD.get(m, 'm%d' % m)] += 1
    r = try_decompress(flags, payload)
    if r is None:
        fail += 1
        if fail <= 5:
            print('  块 %d @0x%X 存 %d 字节 flags=0x%02X (方法 %s) 解压失败 头 16B=%s'
                  % (i, off, stored, flags, METHOD.get(m), payload[:16].hex(' ')))
        continue
    out += r
    if i < 6:
        print('  块 %-4d @0x%06X 存=%-8d flags=0x%02X(%-6s) -> 解出 %d 字节  头 16B=%s'
              % (i, off, stored, flags, METHOD.get(m, m), len(r), r[:16].hex(' ')))

print()
print('  块总数        :', len(blocks))
print('  压缩方法分布  :', dict(meth_cnt))
print('  解压失败      :', fail)
print('  解出总字节    : %d (%.2f MB)' % (len(out), len(out) / 1048576))
print('  压缩率        : %.4f' % (len(out) / max(1, sum(b[1] for b in blocks))))

if out:
    name = 'ec_payload.bin'
    open(name, 'wb').write(out)
    print('\n  ★ 已写出 %s' % name)
    print('  �� 32 B:', out[:32].hex(' '))
    import re
    s = re.findall(rb'[\x20-\x7e]{8,}', bytes(out[:400000]))
    print('  前 400KB 内可打印串(>=8) %d 个:' % len(s))
    for x in s[:20]:
        print('     %r' % x[:70])
