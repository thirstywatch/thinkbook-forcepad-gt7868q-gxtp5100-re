#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Goodix YELLOWSTONE / NOR 家族触控固件 —— 官方容器解析 + 1024 周期 XOR 解扰
2026-10-02 定案版

用法:
    python decrypt.py <firmware.bin> [K.bin]
    python decrypt.py --scan-phase <firmware.bin>

约定（四份独立固件验证一致）:
    plain[i] = raw[i] ^ K[(i + PHASE) % 1024]      i = 容器相对偏移
    PHASE = 316      <=> 等价于  raw ^ rot_left(K, 316)
    数据区相对写法则为 572（= 316 + 0x100）

官方容器结构（goodix_gtx8_update.c: struct firmware_info, #pragma pack(1)）:
    u32 BE size | u16 BE checksum | hw_pid[6] | hw_vid[3] | fw_pid[8] |
    u8 cid | u8 vid[3] | u8 subsys_num | u8 chip_type | u8 protocol_ver | u8 rsv[2] |
    8B x N 子固件表 @ +0x20 | 数据区 @ +0x100
    子固件表项: type(u8) | size(u32 BE) | flash_addr(u16 BE)<<8 | pad(1)
"""
import sys, os, struct, collections, math

PHASE = 316          # 容器相对相位（= K[(container_rel + 316) % 1024]）
DATA_OFF = 0x100     # 数据区相对容器起点
TBL_OFF = 0x20       # 子固件表相对容器起点
HDR = 0x100          # FW_HEADER_SIZE
PREFIX = 6           # 容器前缀: u32 size + u16 checksum
# 数据区相对相位 = PHASE + DATA_OFF = 572

# ============================================================================
# ★ K 的出处（可复现性声明 —— 2026-10-02 追清）
# ----------------------------------------------------------------------------
# 文件  : K_gt7868q.bin（1024 B）
#         MD5     d2f24a3f7141991be9c35d757baea26d
#         SHA256  1a4847391f429a6b233df317bdf4c0b9...
#         仓库内别名 GT7868Q_scramble_key.bin（同一 md5）
# 提取  : 从【本机 GT7868Q 固件】bios-re/GT7868Q_native_fw.bin 的
#         file 偏移 0x08800 处原样切出 1024 字节。
#         已验证：K == raw[0x8800:0x8C00] == raw[0x8C00:0x9000]（同一份重复 4 次）
#         ⇒ 这就是本书旧称为「纯区 / 常量填充段」的那 4 KB。
#
# ⚠️ 为什么这不算"自我循环"（必须写清，否则复现者会卡在这里）：
#   1) K 在【另一个型号、另一份固件】tpfw_86272_PNOR_G1_7863.bin（PID=7863，
#      与本机 7868Q 只共享 0.3% 字节）里同样逐字节出现 —— 10 处，且形态是
#      rot_left(K,316)（因为该文件容器起点在偏移 0，相位基准不同）。
#   2) 相位规则 (容器相对 + 316) mod 1024 在【四份固件】上全部成立，
#      四份各自穷举 1024 相位的全局最优都是 316 ⇒ 过拟合概率 ~1/1024³。
#   3) K 的字节直方图【卡方 = 0.00】（256 个值各恰好 4 次）—— 天然数据表
#      不会刻意把 256 个值配平；这是 keystream / 白化表的指纹。
#   4) 解出的明文里，K 的副本数归零（100352 B 中 0 处）⇒ 相位正确。
#   若只想自己复现，不需要信任上面任何一条：直接跑
#       python decrypt.py <固件> K.bin --scan-phase
#   看最优相位是否落在容器相对 316 即可。
# ============================================================================


def entropy(b):
    if not b:
        return 0.0
    c = collections.Counter(b)
    n = len(b)
    return -sum(v / n * math.log2(v / n) for v in c.values())


def bigram_entropy(b):
    if len(b) < 2:
        return 0.0
    c = collections.Counter(zip(b, b[1:]))
    n = len(b) - 1
    return -sum(v / n * math.log2(v / n) for v in c.values())


def longest_zero_run(b):
    best = cur = 0
    for x in b:
        cur = cur + 1 if x == 0 else 0
        if cur > best:
            best = cur
    return best


def rot_left(k, n):
    n %= len(k)
    return k[n:] + k[:n]


def find_container(buf, limit=65536):
    """按官方校验和定位容器起点（大小写皆试）"""
    for o in range(0, min(len(buf) - HDR, limit)):
        size = struct.unpack('>I', buf[o:o + 4])[0]
        if not (1000 < size <= len(buf) - o):
            continue
        ck = struct.unpack('>H', buf[o + 4:o + 6])[0]
        if sum(buf[o + 6:o + 6 + size]) & 0xFFFF == ck:
            return o
    return None


def parse_container(buf, o):
    """解析官方 firmware_info"""
    size = struct.unpack('>I', buf[o:o + 4])[0]
    ck = struct.unpack('>H', buf[o + 4:o + 6])[0]
    info = dict(
        size=size,
        checksum=ck,
        checksum_ok=(sum(buf[o + 6:o + 6 + size]) & 0xFFFF == ck),
        hw_pid=buf[o + 6:o + 12],
        hw_vid=buf[o + 12:o + 15],
        fw_pid=buf[o + 15:o + 23],
        cid=buf[o + 23],
        fw_vid=buf[o + 24:o + 27],
        subsys_num=buf[o + 27],
        chip_type=buf[o + 28],
        protocol_ver=buf[o + 29],
        reserved=buf[o + 30:o + 32],
    )
    subs = []
    for i in range(28):                       # FW_SUBSYS_MAX_NUM
        q = o + TBL_OFF + i * 8
        t = buf[q]
        ln = int.from_bytes(buf[q + 1:q + 5], 'big')
        if t == 0 and ln == 0:
            break
        fa = int.from_bytes(buf[q + 5:q + 7], 'big') << 8
        subs.append(dict(idx=i, type=t, size=ln, flash_addr=fa))
    info['subsys'] = subs
    return info


def scan_phase(raw, K):
    """穷举 1024 相位，按熵最小（=结构最多）排序返回前若干"""
    prof = []
    for p in range(1024):
        d = bytes(v ^ K[(i + p) % 1024] for i, v in enumerate(raw))
        prof.append((entropy(d), p))
    prof.sort()
    return prof


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = sys.argv[1]
    Kpath = sys.argv[2] if len(sys.argv) > 2 else None
    buf = open(path, 'rb').read()

    o = find_container(buf)
    if o is None:
        print("[!] 未找到通过官方校验和的容器。")
        print("    文件头:", buf[:32].hex(' '))
        return 2
    info = parse_container(buf, o)
    print("=" * 74)
    print("固件      :", os.path.basename(path), "(%d B)" % len(buf))
    print("容器起点  : 0x%X   数据区起点: 0x%X" % (o, o + DATA_OFF))
    print("size      : %d (0x%X)   checksum: 0x%04X  %s"
          % (info['size'], info['size'], info['checksum'],
             "OK" if info['checksum_ok'] else "FAIL"))
    print("hw_pid    : %r" % info['hw_pid'])
    print("fw_pid    : %r" % info['fw_pid'])
    print("cid=0x%02X  fw_vid=%s  subsys_num=%d  chip_type=0x%02X  proto=0x%02X"
          % (info['cid'], info['fw_vid'].hex(' '), info['subsys_num'],
             info['chip_type'], info['protocol_ver']))
    tot = sum(s['size'] for s in info['subsys'])
    data_len = info['size'] + PREFIX - HDR      # 容器总长 = size + 6
    print("子固件 %d 条，合计 0x%X (%d)   数据区长度 0x%X (%d)   %s"
          % (len(info['subsys']), tot, tot, data_len, data_len,
             "★相等" if tot == data_len else "✗不等"))

    raw = buf[o + DATA_OFF:o + DATA_OFF + tot]
    print("-" * 74)
    print("raw  : H0=%.4f  H2=%.3f  零%6.2f%%  最长零串=%d"
          % (entropy(raw), bigram_entropy(raw),
             100 * raw.count(0) / len(raw), longest_zero_run(raw)))

    if not Kpath:
        print("\n[提示] 未提供 K，跳过解扰。可用 --scan-phase 自检相位。")
        return 0
    K = open(Kpath, 'rb').read()
    assert len(K) == 1024, "K 必须是 1024 字节"

    if '--scan-phase' in sys.argv:
        prof = scan_phase(raw, K)
        print("\n相位剖面（按熵升序）: 最优=%d 熵=%.4f ；次优=%d ；均值=%.4f"
              % (prof[0][1], prof[0][0], prof[1][1],
                 sum(p[0] for p in prof) / 1024))
        print("换算容器相对相位 = (数据区相对 - 0x100) %% 1024 = %d"
              % ((prof[0][1] - DATA_OFF) % 1024))

    k2 = rot_left(K, PHASE)
    # 数据区相对偏移 i  ⇒  容器相对偏移 = i + DATA_OFF
    dec = bytes(v ^ k2[(i + DATA_OFF) % 1024] for i, v in enumerate(raw))
    print("plain: H0=%.4f  H2=%.3f  零%6.2f%%  最长零串=%d   ΔH0=%+.4f"
          % (entropy(dec), bigram_entropy(dec),
             100 * dec.count(0) / len(dec), longest_zero_run(dec),
             entropy(dec) - entropy(raw)))

    print("-" * 74)
    print("%-4s %-6s %-8s %-9s %-9s %-8s %-8s %-9s %-7s"
          % ("#", "type", "size", "flash", "明文H0", "零%", "最长0串", "file_off", "ASCII%"))
    off = 0
    for s in info['subsys']:
        x = dec[off:off + s['size']]
        off += s['size']
        asc = 100.0 * sum(1 for c in x if 32 <= c < 127) / len(x)
        print("%-4d 0x%02X   0x%05X  0x%05X   %-9.4f %-8.2f %-9d 0x%06X  %-7.1f"
              % (s['idx'], s['type'], s['size'], s['flash_addr'],
                 entropy(x), 100 * x.count(0) / len(x),
                 longest_zero_run(x), o + DATA_OFF + off - s['size'], asc))

    out = os.path.join(os.path.dirname(os.path.abspath(path)),
                       os.path.basename(path) + ".plain_data.bin")
    open(out, 'wb').write(dec)
    print("-" * 74)
    print("已写出明文:", out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
