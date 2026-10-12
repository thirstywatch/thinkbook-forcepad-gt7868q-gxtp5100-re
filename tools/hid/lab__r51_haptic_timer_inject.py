#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
lab__r51_haptic_timer_inject.py — ★ 直接实验：写回 0x1800 触觉参数区（单变量）

假设：0x1800 区是触觉/LRA 驱动的定时器参数。退化态下被重置（0x0003FFFF -> 60/3968）
      ⇒ 写回正常值可能恢复震动。

★ 单变量：只改 0x1800-0x1813（20 B），其它一律不动。
★ 安全：设备当前已是退化态（触觉已关），写错不会更坏；重启即可恢复。
"""
import sys, os, time, argparse, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gxmem

ADDR = 0x1800
LEN = 0x14
# snapA/snapB 正常态值（两快照一致）
NORMAL = bytes.fromhex(
    'FF FF 03 00 FF FF 03 00 00 00 00 00 FF FF 03 00 FF FF 03 00 00 00 00 00'.replace(' ', ''))
LOG = []


def log(s):
    line = "[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), s)
    print(line, flush=True); LOG.append(line)


def flush():
    try:
        open(os.path.join(HERE, "_r51_log.txt"), "a", encoding="utf-8").write("\n".join(LOG) + "\n")
    except Exception:
        pass


def hx(b, n=None):
    b = bytes(b)
    if n: b = b[:n]
    return " ".join("%02X" % x for x in b)


def rd(g, a, n, tries=8):
    for _ in range(tries):
        d, _ = g.read(a, n)
        if d and len(d) >= n:
            return bytes(d[:n])
        time.sleep(0.12)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--restore", action="store_true", help="恢复：写回当前值（若有备份）")
    a = ap.parse_args()

    log("=" * 80)
    log("r51 · 写回 0x1800 触觉参数区（单变量）· %s" % ("COMMIT" if a.go else "DRY"))
    log("=" * 80)
    log("目标: 0x%04X 长度 %d B" % (ADDR, LEN))
    log("将写: %s" % hx(NORMAL))
    log("★ 只改这一处；不碰其它任何地址；不进 bootloader")

    if not a.go:
        log("")
        log("[DRY] 未加 --go")
        return 0

    g = gxmem.Gx()
    if not g.open():
        log("[FATAL] open fail"); return 3
    try:
        log("")
        log("── 1) 写前读取 ──")
        before = rd(g, ADDR, LEN)
        if before is None:
            log("  ❌ 读不到 ⇒ 终止"); return 4
        log("  0x%04X: %s" % (ADDR, hx(before)))
        log("  ⇒ 是否等于正常态值: %s" % ("✅ 是（原本就正常）" if before == NORMAL else "❌ 否"))

        log("")
        log("── 2) 写入正常态值 ──")
        ok = g.write(ADDR, NORMAL)
        log("  写入返回: %s" % ("✅" if ok else "❌"))
        time.sleep(0.4)

        log("")
        log("── 3) 写后校验 ──")
        after = rd(g, ADDR, LEN)
        log("  0x%04X: %s" % (ADDR, hx(after) if after else "<读失败>"))
        if after:
            n = sum(1 for i in range(LEN) if after[i] != NORMAL[i])
            log("  ⇒ 与目标差异 %d/%d  %s" % (n, LEN, "★ 写入成功" if n == 0 else ""))

        log("")
        log("═" * 60)
        log("★ 请立刻测触控板：")
        log("   ① 滑动 ② 按压点击 ③ 触觉（震动）")
        log("   若震动回来 ⇒ ★★★★★ 找到了'震动开关'就是 0x1800 区")
        log("═" * 60)
        return 0
    finally:
        g.close()
        flush()
        log("日志 → _r51_log.txt")


if __name__ == "__main__":
    raise SystemExit(main())
