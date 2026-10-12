#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
lab__r41_ram_followtest_bl.py — 在【bootloader 态】测 follow 语义（★ 仍不碰 flash）

★ 为什么要这步
  r40 在【正常模式】测 0xC000：两种 follow 都写不进去（回读全 0x00）。
  假设：0xC000（FLASH_BUFFER_ADDR）只有在【进入 bootloader】后才映射为 ISP RAM 缓冲
        （官方 fw_update 正是先 0E 10 → 等 0xDD → 0E 11，然后才写 0xC000）。
  ⇒ 本脚本进入 bootloader 后重做同样的 RAM 写入/回读判定。

★ 风险界定
  · 会调用：0E 10（切 patch）、{33}（关坐标）、0E 11（启动更新）、0E 13（复位）
  · **不会调用 0E 12** ⇒ **全程不写 flash、不擦除**
  · 目标只有 0xC000（RAM 暂存）+ 收尾复位
  · 异常时 finally 强制走恢复路径（0E 13 + {34} + {32}）
  · 设备侧安全网：docs/09-safety/RECOVERY.md（BIOS 自动重刷）

用法
  python lab__r41_ram_followtest_bl.py            # dry
  python lab__r41_ram_followtest_bl.py --go       # 执行
  python lab__r41_ram_followtest_bl.py --go --skip-exit   # 进了就不退出（不推荐）
"""
import sys, os, time, argparse, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gxmem

RAM_BUF = 0xC000
CMD_ADDR, BL_STATE, FLASH_RES = 0x4160, 0x5095, 0x5096
BL_READY = 0xDD
CHUNK = 55
LOG = []
STATE = {"in_bl": False}


def log(s):
    line = "[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), s)
    print(line, flush=True); LOG.append(line)


def flush():
    try:
        open(os.path.join(HERE, "_r41_log.txt"), "a", encoding="utf-8").write("\n".join(LOG) + "\n")
    except Exception:
        pass


def hx(b, n=None):
    b = bytes(b)
    if n: b = b[:n]
    return " ".join("%02X" % x for x in b)


def cmd6(c): return bytes([0x0E, c, 0x00, 0x00, 0x01, 0x01])


def cmdreg(c, hi=0, lo=0):
    ck = (c + hi + lo) & 0xFFFF
    return bytes([c, hi, lo, (ck >> 8) & 0xFF, ck & 0xFF])


def rd(g, a, n=1):
    for _ in range(3):
        d, _ = g.read(a, n)
        if d and len(d) >= n: return bytes(d[:n])
        time.sleep(0.03)
    return None


def read_chunked(g, addr, total, chunk=256):
    out = bytearray()
    while len(out) < total:
        n = min(chunk, total - len(out))
        d = rd(g, addr + len(out), n)
        if not d or len(d) < n: return None
        out += d; time.sleep(0.02)
    return bytes(out)


def write_pkt(g, addr, data, follow_mode):
    pos = 0; pkg = 0; cur = addr & 0xFFFF; total = len(data)
    npkt = (total + CHUNK - 1) // CHUNK
    while pos < total:
        n = min(CHUNK, total - pos)
        follow = (0x01 if (pos + n) < total else 0x00) if follow_mode == 'official' else 0x00
        pkt = [0x0E, 0x20, follow, pkg & 0xFF, n + 5, 0x00,
               (cur >> 8) & 0xFF, cur & 0xFF, (n >> 8) & 0xFF, n & 0xFF] + list(data[pos:pos + n])
        if not g._send(pkt): return False, pkg, npkt
        pos += n; cur = (cur + n) & 0xFFFF; pkg += 1; time.sleep(0.002)
    return True, npkt, npkt


def bl_stable(g, need=5, tries=40, gap=0.03):
    seq = []
    for _ in range(tries):
        b = rd(g, BL_STATE)
        if b: seq.append(b[0])
        if len(seq) >= need and all(x == seq[-1] for x in seq[-need:]):
            return seq[-1], True, seq
        time.sleep(gap)
    return (seq[-1] if seq else None), False, seq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--skip-exit", action="store_true")
    a = ap.parse_args()

    log("=" * 84)
    log("r41 · bootloader 态下测 follow（★ 不发 0E12、不碰 flash）· %s"
        % ("COMMIT" if a.go else "DRY"))
    log("=" * 84)
    log("")
    log("将调用：0E 10 → {33} → 等 0x5095==0xDD → 0E 11 → [写/读 0xC000] → {34} → 0E 13 → {32}")
    log("★ 不会调用 0E 12；不写 flash、不擦除")
    if not a.go:
        log("")
        log("[DRY] 未加 --go ⇒ 未打开设备。")
        return 0

    g = gxmem.Gx()
    if not g.open():
        log("[FATAL] 打开 Col04 失败"); return 3
    failed = False
    try:
        log("")
        log("── 0) 基线 ──")
        base = rd(g, 0x96F8, 32)
        log("  0x96F8: %s" % hx(base))
        for ad, nm in [(CMD_ADDR, 'CMD_ADDR'), (BL_STATE, 'BL_STATE'), (FLASH_RES, 'FLASH_RESULT')]:
            v = rd(g, ad, 1)
            log("  0x%04X %-13s = %s" % (ad, nm, ("0x%02X" % v[0]) if v else "<空>"))

        log("")
        log("── 1) 0E 10 切 patch ──")
        if not g._send(list(cmd6(0x10))):
            log("  ❌ 发送失败"); return 4
        STATE["in_bl"] = True
        log("  ✅ 已发，等 250 ms"); time.sleep(0.25)
        for _ in range(3):
            g.write(CMD_ADDR, cmdreg(0x33)); time.sleep(0.01)
        log("  ✅ {33} 关坐标 ×3")

        log("── 2) 等 0x5095 == 0xDD ──")
        v, stable, seq = bl_stable(g)
        log("  末值 %s 稳定=%s  最近: %s" % (("0x%02X" % v) if v is not None else "None",
              stable, " ".join("%02X" % x for x in seq[-10:])))
        if v != BL_READY or not stable:
            log("  ❌ 未进入 bootloader ⇒ 终止"); failed = True; return 5
        log("  ✅ 已进入 bootloader 态")

        log("── 3) 0E 11 启动更新 ──")
        if not g._send(list(cmd6(0x11))):
            log("  ❌ 发送失败"); failed = True; return 6
        time.sleep(0.1)
        log("  ✅ 已发")

        A = bytes([0xAA] * 4096)
        B = bytes([0x55] * 4096)

        log("")
        log("── 4) ★ 写 0xAA×4096，follow=0x01（官方语义）──")
        ok, done, tot = write_pkt(g, RAM_BUF, A, 'official')
        log("  发送 %s（%d/%d 包）" % ("✅" if ok else "❌", done, tot))
        time.sleep(0.3)
        rb = read_chunked(g, RAM_BUF, 4096)
        if rb:
            m = sum(1 for i in range(4096) if rb[i] == A[i])
            log("  回读：%d/4096 匹配 = %.2f%%  %s" % (m, m/4096*100, "★落地" if m>4000 else "⚠️不匹配"))
            log("  前 32B: %s" % hx(rb, 32))
        else:
            log("  回读失败")

        log("")
        log("── 5) ★ 写 0x55×4096，follow=0x00（项目旧用法）──")
        ok, done, tot = write_pkt(g, RAM_BUF, B, 'zero')
        log("  发送 %s（%d/%d 包）" % ("✅" if ok else "❌", done, tot))
        time.sleep(0.3)
        rb2 = read_chunked(g, RAM_BUF, 4096)
        if rb2:
            m = sum(1 for i in range(4096) if rb2[i] == B[i])
            log("  回读：%d/4096 匹配 = %.2f%%  %s" % (m, m/4096*100, "★落地" if m>4000 else "⚠️不匹配"))
            log("  前 32B: %s" % hx(rb2, 32))
        else:
            log("  回读失败")

        log("")
        log("── 6) 长写/短写对照：写 55 B 与写 110 B ──")
        for n in (55, 110, 256):
            pat = bytes([0x3C] * n)
            ok, _, _ = write_pkt(g, RAM_BUF, pat, 'official')
            time.sleep(0.15)
            r = read_chunked(g, RAM_BUF, n)
            mm = sum(1 for i in range(n) if r and i < len(r) and r[i] == pat[i]) if r else -1
            log("  写 %3d B: 发送=%s  匹配=%s" % (n, "✅" if ok else "❌",
                  ("%d/%d" % (mm, n)) if mm >= 0 else "<读失败>"))

        log("")
        log("★ 结论：见上面各【回读】行")
        return 0
    finally:
        if STATE["in_bl"] and not a.skip_exit:
            log("")
            log("★ 收尾（已进 bootloader，必须退出）")
            try:
                g.write(CMD_ADDR, cmdreg(0x34)); log("  → {34} 开坐标")
            except Exception as e:
                log("  → {34} 异常 %r" % e)
            try:
                if g._send(list(cmd6(0x13))):
                    log("  → 0E13 复位"); time.sleep(0.3)
            except Exception as e:
                log("  → 0E13 异常 %r" % e)
            try:
                g.write(CMD_ADDR, cmdreg(0x32)); log("  → {32} 切 PTP")
            except Exception as e:
                log("  → {32} 异常 %r" % e)
            log("")
            log("── 收尾核查 ──")
            b2 = rd(g, 0x96F8, 32)
            log("  0x96F8: %s" % hx(b2))
            log("  ⇒ 与基线一致：%s" % ("✅" if b2 == base else "⚠️ 不一致"))
            for ad, nm in [(CMD_ADDR, 'CMD_ADDR'), (BL_STATE, 'BL_STATE'), (FLASH_RES, 'FLASH_RESULT')]:
                v = rd(g, ad, 1)
                log("  0x%04X %-13s = %s" % (ad, nm, ("0x%02X" % v[0]) if v else "<空>"))
        g.close()
        flush()
        log("日志 → _r41_log.txt")


if __name__ == "__main__":
    raise SystemExit(main())
