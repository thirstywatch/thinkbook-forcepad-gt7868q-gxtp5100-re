#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
lab__r33_fw_update_sim.py — 官方 fw_update 的【离线模拟器】（不碰设备）

目的
----
把官方 `goodix/gdix_hid_firmware_update` 的 `GT7868QUpdate::fw_update()` 对【我们的固件】
会发出的**每一条命令、每一个字节**离线算出来。用途：

  1. ★ **把地址算术钉死**（不依赖任何设备读回）—— 见 §A
  2. ★ **逐字节可对照官方源码**（`gtx2_update.cpp:139-213` / `gt7868q_update.cpp:122-311`）
  3. ★ 将来实机执行时**照单发**，不需任何猜测
  4. ★ 预先算出"这套序列会把 flash 写成什么"（按官方**表序覆盖**规则）—— 见 §C
  5. ★ 标出"哪一块最适合做首次实机目标"—— 见 §D

★ 地址算术（§A，这是本脚本的核心）
--------------------------------
官方代码：
    sub_fw_flash_addr = (fw_data[pos+5] << 8 | fw_data[pos+6]) << 8;   // u16BE 再 <<8
    buf_load_flash[7] = (flash_addr >> 16) & 0xFF;
    buf_load_flash[8] = (flash_addr >>  8) & 0xFF;
⇒ 代入后：  [7] = 表内 addr_u16 的高字节
            [8] = 表内 addr_u16 的低字节
⇒ **`0E 12` 的 [7][8] 两个字节，恰好逐字节等于容器表里 addr 字段的原始 u16（大端）。**
⇒ 这是一个"纯离线可验证"的地址算术链条，不需要读设备。

用法
----
  python lab__r33_fw_update_sim.py <container.bin> [--payload-offset 0x113C] [--flash-flag 0x0C]
  python lab__r33_fw_update_sim.py <container.bin> --emit-flash out.bin    # 导出"会被写成什么"

⚠️ 只读。不打开设备、不写设备。
"""
import sys, os, argparse

RAM_BUFFER_SIZE = 4096
CMD_ADDR        = 0x4160


def ck16be_word_sum(data):
    """官方 load_sub_firmware 的校验和：按【大端 16 位字】累加，uint16 回绕"""
    s = 0
    for i in range(0, len(data) - 1, 2):
        s = (s + ((data[i] << 8) + data[i + 1])) & 0xFFFF
    return s


def parse_gtx3(A):
    size = int.from_bytes(A[0:4], 'big')
    ck = int.from_bytes(A[4:6], 'big')
    calc = sum(A[6:size + 6]) & 0xFFFF
    N = A[0x1B]
    ents = []
    cur = 0x100
    for i in range(N):
        p = 0x20 + i * 8
        t = A[p]
        ln = int.from_bytes(A[p + 1:p + 5], 'big')
        rawa = int.from_bytes(A[p + 5:p + 7], 'big')
        ents.append({'i': i, 'type': t, 'len': ln, 'rawa': rawa,
                     'fa': rawa << 8, 'off': cur, 'tbl_off': p})
        cur += ln
    return {'size': size, 'ck': ck, 'calc': calc, 'ok': (ck == calc and size + 6 == len(A)),
            'magic': A[6:0x0F], 'pid': A[0x0F:0x17], 'cid': A[0x17],
            'vid': int.from_bytes(A[0x18:0x1B], 'big'), 'n': N, 'ents': ents,
            'data_off': 0x100, 'data_end': cur}


def frames_for(A, info, flash_flag):
    """产出官方 fw_update 的完整命令序列（按官方表序）"""
    seq = []
    seq.append(('命令帧', '0E10 切patch', '0E 10 00 00 01 01', '-', '-'))
    seq.append(('寄存器写', '0x4160 <- {33} 关坐标', f'0E 20 00 00 0A 00 41 60 00 05 33 00 00 00 33', hex(CMD_ADDR), '5B'))
    seq.append(('等待', '轮询 0x5095 == 0xDD', '—', '0x5095', '—'))
    seq.append(('命令帧', '0E11 启动更新', '0E 11 00 00 01 01', '-', '-'))

    for e in info['ents']:
        if not (flash_flag & (0x01 << e['type'])):
            seq.append(('跳过', f"idx{e['i']} type=0x{e['type']:02X} 不在 flash_flag(0x{flash_flag:02X}) 内", '-', '-', '-'))
            continue
        remain = e['len']
        off = e['off']
        ifa = e['fa']
        n_chunk = 0
        while remain > 0:
            n = min(RAM_BUFFER_SIZE, remain)
            ch = A[off:off + n]
            ck = ck16be_word_sum(ch)
            fr = bytes([0x0E, 0x12, 0x00, 0x00, 0x06,
                        (n >> 8) & 0xFF, n & 0xFF,
                        (ifa >> 16) & 0xFF, (ifa >> 8) & 0xFF,
                        (ck >> 8) & 0xFF, ck & 0xFF])
            seq.append(('0E12', f"idx{e['i']} 第{n_chunk+1}块",
                        fr.hex(' ').upper(),
                        f"0x{ifa:06X}",
                        f"{n} B (文件 0x{off:05X}) ck=0x{ck:04X}"))
            off += n; ifa += n; remain -= n; n_chunk += 1

    seq.append(('寄存器写', '0x4160 <- {34} 开坐标', '0E 20 00 00 0A 00 41 60 00 05 34 00 00 00 34', hex(CMD_ADDR), '5B'))
    seq.append(('命令帧', '0E13 复位', '0E 13 00 00 01 01', '-', '-'))
    seq.append(('寄存器写', '0x4160 <- {32} 切PTP', '0E 20 00 00 0A 00 41 60 00 05 32 00 00 00 32', hex(CMD_ADDR), '5B'))
    return seq


def emit_flash(A, info, flash_flag):
    """按官方【表序覆盖】规则，算出最终 flash 内容（只覆盖表内触及的地址）"""
    lo = min(e['fa'] for e in info['ents'])
    hi = max(e['fa'] + e['len'] for e in info['ents'])
    buf = bytearray(b'\xFF' * (hi - lo))
    touched = [False] * (hi - lo)
    for e in info['ents']:
        if not (flash_flag & (0x01 << e['type'])):
            continue
        st = e['fa'] - lo
        buf[st:st + e['len']] = A[e['off']:e['off'] + e['len']]
        for i in range(st, st + e['len']):
            touched[i] = True
    return lo, bytes(buf), touched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--payload-offset", type=lambda x: int(x, 0), default=0x113C)
    ap.add_argument("--payload-size", type=lambda x: int(x, 0), default=100608)
    ap.add_argument("--flash-flag", type=lambda x: int(x, 0), default=0x0C,
                    help="官方 main.cpp 对本机用 0x0C（注释 update type:0x02,0x03）")
    ap.add_argument("--emit-flash", default=None, help="把'会被写成什么'导出到该文件")
    a = ap.parse_args()

    d = open(a.file, 'rb').read()
    A = d[a.payload_offset:a.payload_offset + a.payload_size]
    info = parse_gtx3(A)

    print("=" * 96)
    print("官方 fw_update 离线模拟 · %s" % os.path.basename(a.file))
    print("=" * 96)
    print("容器: 偏移 0x%05X 长度 %d" % (a.payload_offset, len(A)))
    print("  长度字段 %d (+6=%d) 校验 0x%04X/实算 0x%04X  %s"
          % (info['size'], info['size'] + 6, info['ck'], info['calc'],
             "✅ 通过" if info['ok'] else "❌"))
    print("  IC代号=%r  PID=%r  CID=0x%02X  VID=0x%06X  子固件数=%d"
          % (info['magic'], info['pid'], info['cid'], info['vid'], info['n']))
    print("  flash_flag = 0x%02X ⇒ 下发的 type：%s"
          % (a.flash_flag, [hex(t) for t in sorted({e['type'] for e in info['ents']})
                            if (a.flash_flag & (0x01 << t))]))

    # ── §A 地址算术链条 ──
    print()
    print("§A 地址算术（★ 不依赖设备读回的纯离线链条）")
    print("-" * 96)
    print("  官方:  flash_addr = (表内u16be) << 8 ;  [7]=(fa>>16)&FF ; [8]=(fa>>8)&FF")
    print("  ⇒     [7][8] ≡ 表内 u16be 的两个字节")
    print()
    print("  %-4s %-5s %-8s %-10s %-12s %-8s %s" % ("idx", "type", "len", "表内u16be", "flash_addr", "[7][8]", "数据(file)"))
    for e in info['ents']:
        mark = "★" if (a.flash_flag & (0x01 << e['type'])) else " "
        print("  %s%-3d 0x%02X  %-8d 0x%04X     0x%06X      %02X %02X    0x%05X"
              % (mark, e['i'], e['type'], e['len'], e['rawa'], e['fa'],
                 (e['fa'] >> 16) & 0xFF, (e['fa'] >> 8) & 0xFF, e['off']))
    print()
    print("  ★ 自查：对每一行，(fa>>16)&0xFF == (表内u16be>>8)，(fa>>8)&0xFF == (表内u16be&0xFF)")
    bad = [e['i'] for e in info['ents']
           if ((e['fa'] >> 16) & 0xFF) != (e['rawa'] >> 8) or ((e['fa'] >> 8) & 0xFF) != (e['rawa'] & 0xFF)]
    print("  ⇒ 不一致的行：%s" % (bad if bad else "无（全部自洽 ✅）"))

    # ── §B 完整命令序列 ──
    seq = frames_for(A, info, a.flash_flag)
    print()
    print("§B 官方 fw_update 对本机会发的完整序列（共 %d 步，其中 0E12 共 %d 条）"
          % (len(seq), sum(1 for s in seq if s[0] == '0E12')))
    print("-" * 96)
    for i, (kind, desc, frame, addr, extra) in enumerate(seq):
        print("  %3d [%-6s] %-46s %s" % (i, kind, desc, frame if frame != '-' else ''))
        if extra != '-':
            print("            └ 目标 %-10s %s" % (addr, extra))

    # ── §C 会被写成什么 ──
    lo, buf, touched = emit_flash(A, info, a.flash_flag)
    print()
    print("§C 这套序列会把 flash 写成什么（按官方【表序覆盖】规则）")
    print("-" * 96)
    print("  覆盖地址范围：0x%06X – 0x%06X（共 %d B）" % (lo, lo + len(buf), len(buf)))
    nt = sum(touched)
    print("  其中被覆盖 %d B，未覆盖（保持原值）%d B" % (nt, len(buf) - nt))
    # 找重叠
    cnt = [0] * len(buf)
    for e in info['ents']:
        if not (a.flash_flag & (0x01 << e['type'])):
            continue
        for i in range(e['fa'] - lo, e['fa'] - lo + e['len']):
            cnt[i] += 1
    ov = [i for i, c in enumerate(cnt) if c > 1]
    if ov:
        # 归并区间
        runs = []
        st = ov[0]; pv = ov[0]
        for p in ov[1:]:
            if p == pv + 1:
                pv = p
            else:
                runs.append((st, pv)); st = p; pv = p
        runs.append((st, pv))
        print("  ⚠️ 被多次写入的区域（后者覆盖前者）：")
        for s, e2 in runs:
            print("      0x%06X – 0x%06X (%d B)" % (lo + s, lo + e2 + 1, e2 - s + 1))
    else:
        print("  无重叠")
    if a.emit_flash:
        open(a.emit_flash, 'wb').write(buf)
        print("  已导出 → %s" % a.emit_flash)

    # ── §D 首次实机目标安全性排序 ──
    print()
    print("§D 哪个子固件最适合做【首次实机目标】")
    print("-" * 96)
    print("  评估维度：① 是否整块 4096 的整数倍（避免半块）② 是否被别的块覆盖 ③ 是否碰关键地址（0x000000 最敏感）")
    print()
    print("  %-4s %-6s %-8s %-10s %-9s %-9s %s"
          % ("idx", "type", "len", "flash_addr", "4096整倍", "被覆盖", "结论"))
    for e in info['ents']:
        if not (a.flash_flag & (0x01 << e['type'])):
            continue
        aligned = (e['len'] % RAM_BUFFER_SIZE == 0)
        st = e['fa'] - lo
        covered = any(cnt[i] > 1 for i in range(st, st + e['len']))
        crit = e['fa'] == 0
        verdict = []
        if crit:
            verdict.append("❌ 碰 0x000000")
        if not aligned:
            verdict.append("⚠️ 非 4096 整倍")
        if covered:
            verdict.append("⚠️ 被覆盖")
        if not verdict:
            verdict.append("✅ 首选候选")
        print("  %-4d 0x%02X   %-8d 0x%06X   %-9s %-9s %s"
              % (e['i'], e['type'], e['len'], e['fa'],
                 "是" if aligned else "否", "是" if covered else "否", " ".join(verdict)))

    print()
    print("⚠️ 本脚本【不做任何设备操作】。以上仅为离线推演，实机执行前仍需解决：")
    print("   · 地址算术虽已逐字节自洽，但 IC 内部对 [7][8] 的解释只能实机验证")
    print("   · 官方【无独立 erase】（擦除隐含在 0E12 内）⇒ 错地址 = 静默毁掉一片")
    print("   · 官方【不读回 flash】⇒ 写错时没有任何回读层能发现")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
