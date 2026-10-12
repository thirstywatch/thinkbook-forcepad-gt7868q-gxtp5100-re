#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
lab__r40_ram_followtest.py — ★ 零风险：判定 follow(`[2]`) 语义（只在 RAM 0xC000 上）

★ 为什么要先做这个
  `follow`/`cont`（报文 `[2]` 字节）有两个互相矛盾的结论：
    · 官方 `GTx5Device::Write`（gtx5.cpp:227-276）：`[2]=0x01` 表示【还有后续包】
    · 项目 `lab__r13_cfgupdate.py` 注释：`[2]=1` 被判为序列错误 ⇒ 一律用 `[2]=0`
  ⇒ 在**真正写 flash 之前**，先在一个**不动 flash** 的目标上把语义问清。

★ 为什么零风险
  `0xC000` = `FLASH_BUFFER_ADDR`，是 IC 的 **RAM 暂存区**（官方每块 flash 数据都先写这里）。
  · 写它不是写 flash（不触发擦除/编程）
  · 它的内容本来就每次都被覆盖
  · **不调用 `0E 12`，不调用 `0E 10/0E 11/0E 13`** ⇒ 全程不进入任何升级态

★ 做法
  1. 基线记录（`0x96F8` / `0x4160` / `0x5095` / `0x5096`）
  2. 探 `0xC000` 的可读性与稳定性
  3. 写图案 A（0xAA ×4096）用 **follow=1**（官方语义）→ 回读比对
  4. 写图案 B（0x55 ×4096）用 **follow=0**（项目旧用法）→ 回读比对
  5. 结论：哪种 follow 能让数据完整落地

用法
  python lab__r40_ram_followtest.py            # dry
  python lab__r40_ram_followtest.py --go       # ★ 真正执行（仍为零风险）
"""
import sys, os, time, argparse, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gxmem

RAM_BUF = 0xC000
CMD_ADDR, BL_STATE, FLASH_RES = 0x4160, 0x5095, 0x5096
CHUNK = 55
LOG = []


def log(s):
    line = "[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), s)
    print(line, flush=True); LOG.append(line)


def flush():
    try:
        open(os.path.join(HERE, "_r40_log.txt"), "a", encoding="utf-8").write("\n".join(LOG) + "\n")
    except Exception:
        pass


def hx(b, n=None):
    b = bytes(b)
    if n: b = b[:n]
    return " ".join("%02X" % x for x in b)


def rd(g, a, n=1):
    for _ in range(3):
        d, _ = g.read(a, n)
        if d and len(d) >= n:
            return bytes(d[:n])
        time.sleep(0.03)
    return None


def read_chunked(g, addr, total, chunk=256):
    """分块读（每块短 ⇒ 可靠）。返回 bytes|None"""
    out = bytearray()
    while len(out) < total:
        n = min(chunk, total - len(out))
        d = rd(g, addr + len(out), n)
        if not d or len(d) < n:
            return None
        out += d
        time.sleep(0.02)
    return bytes(out)


def write_pkt(g, addr, data, follow_mode):
    """按指定 follow 模式拆包写。follow_mode: 'official' | 'zero'"""
    pos = 0; pkg = 0; cur = addr & 0xFFFF; total = len(data)
    npkt = (total + CHUNK - 1) // CHUNK
    while pos < total:
        n = min(CHUNK, total - pos)
        if follow_mode == 'official':
            follow = 0x01 if (pos + n) < total else 0x00
        else:
            follow = 0x00
        pkt = [0x0E, 0x20, follow, pkg & 0xFF, n + 5, 0x00,
               (cur >> 8) & 0xFF, cur & 0xFF,
               (n >> 8) & 0xFF, n & 0xFF] + list(data[pos:pos + n])
        if not g._send(pkt):
            return False, pkg, npkt
        pos += n; cur = (cur + n) & 0xFFFF; pkg += 1
        time.sleep(0.002)
    return True, npkt, npkt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()

    log("=" * 80)
    log("r40 · follow 语义判定 · ★ 零风险（只在 RAM 0xC000，不碰 flash、不进升级态）· %s"
        % ("COMMIT" if a.go else "DRY"))
    log("=" * 80)

    A = bytes([0xAA] * 4096)
    B = bytes([0x55] * 4096)
    log("")
    log("计划：")
    log("  1) 基线：0x96F8 / 0x4160 / 0x5095 / 0x5096")
    log("  2) 探 0xC000 可读性（256 B ×2）")
    log("  3) 写 0xC000 ← 0xAA×4096  【follow=0x01（官方语义）】→ 回读比对")
    log("  4) 写 0xC000 ← 0x55×4096  【follow=0x00（项目旧用法）】→ 回读比对")
    log("  ★ 全程不调用 0E 10 / 0E 11 / 0E 12 / 0E 13")

    if not a.go:
        log("")
        log("[DRY] 未加 --go ⇒ 未打开设备。")
        return 0

    g = gxmem.Gx()
    if not g.open():
        log("[FATAL] 打开 Col04 失败"); return 3
    try:
        log("")
        log("── 1) 基线 ──")
        base = rd(g, 0x96F8, 32)
        log("  0x96F8 32B: %s" % hx(base))
        for ad, nm in [(CMD_ADDR, 'CMD_ADDR'), (BL_STATE, 'BL_STATE'), (FLASH_RES, 'FLASH_RESULT')]:
            v = rd(g, ad, 1)
            log("  0x%04X %-13s = %s" % (ad, nm, ("0x%02X" % v[0]) if v else "<空>"))

        log("")
        log("── 2) 探 0xC000 可读性 ──")
        r1 = read_chunked(g, RAM_BUF, 256)
        time.sleep(0.2)
        r2 = read_chunked(g, RAM_BUF, 256)
        log("  第1次 256B: %s" % (hx(r1, 32) + " …" if r1 else "<空>"))
        log("  第2次 256B: %s" % (hx(r2, 32) + " …" if r2 else "<空>"))
        if not r1 or not r2:
            log("  ⚠️ 0xC000 读不到 ⇒ 无法用回读做判据（但写入本身仍零风险）")
        else:
            same = sum(1 for i in range(256) if r1[i] == r2[i])
            log("  两次相同 %d/256 %s" % (same, "✅ 稳定" if same == 256 else "⚠️ 不稳定"))

        log("")
        log("── 3) 写 0xAA×4096，follow=0x01（官方语义）──")
        ok, done, tot = write_pkt(g, RAM_BUF, A, 'official')
        log("  发送 %s（%d/%d 包）" % ("✅" if ok else "❌", done, tot))
        time.sleep(0.3)
        rb = read_chunked(g, RAM_BUF, 4096)
        if rb:
            m = sum(1 for i in range(4096) if rb[i] == A[i])
            log("  回读比对：%d/4096 匹配 = %.2f%%  %s" % (m, m / 4096 * 100,
                                                  "★ 数据完整落地" if m > 4000 else "⚠️ 不匹配"))
            log("  回读前 32B: %s" % hx(rb, 32))
        else:
            log("  回读失败（无法判定）")

        log("")
        log("── 4) 写 0x55×4096，follow=0x00（项目旧用法）──")
        ok, done, tot = write_pkt(g, RAM_BUF, B, 'zero')
        log("  发送 %s（%d/%d 包）" % ("✅" if ok else "❌", done, tot))
        time.sleep(0.3)
        rb2 = read_chunked(g, RAM_BUF, 4096)
        if rb2:
            m = sum(1 for i in range(4096) if rb2[i] == B[i])
            log("  回读比对：%d/4096 匹配 = %.2f%%  %s" % (m, m / 4096 * 100,
                                                  "★ 数据完整落地" if m > 4000 else "⚠️ 不匹配"))
            log("  回读前 32B: %s" % hx(rb2, 32))
        else:
            log("  回读失败（无法判定）")

        log("")
        log("── 5) 收尾核查（★ 未做任何 flash 操作）──")
        base2 = rd(g, 0x96F8, 32)
        log("  0x96F8 32B: %s" % hx(base2))
        log("  ⇒ 与基线一致：%s" % ("✅" if base2 == base else "⚠️ 不一致"))
        for ad, nm in [(CMD_ADDR, 'CMD_ADDR'), (BL_STATE, 'BL_STATE'), (FLASH_RES, 'FLASH_RESULT')]:
            v = rd(g, ad, 1)
            log("  0x%04X %-13s = %s" % (ad, nm, ("0x%02X" % v[0]) if v else "<空>"))
        log("")
        log("★ 结论请见上面两处【回读比对】")
        return 0
    finally:
        g.close()
        flush()
        log("日志 → _r40_log.txt")


if __name__ == "__main__":
    raise SystemExit(main())
