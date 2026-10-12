#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
lab__r49_header_restore_test.py — ★★ 定点修复实验
  进 bootloader 使设备退化 → 回到正常模式 → 写回固件头 → 看功能是否恢复

★ 实验设计（关键）
  1. 基线：读 0x4000-0x403F（正常态全量，作为"要写回的正确值"）
  2. 进 bootloader 并退出（0E10→等0xDD→0E11→{34}→0E13→{32}）⇒ 设备退化
  3. **在正常模式下**读 0x4000-0x403F ⇒ 确认退化（应为 00×8 + CID/VID 被改）
  4. **在正常模式下**把第 1 步的 64 B 写回 0x4000
  5. 读回校验
  6. ⇒ 请喆测试触控板：若触觉/按压点击恢复 ⇒ ★ 定点修复成立

★ 为什么写回放在【正常模式】
  已由 lab__r48 证明：正常模式下 0x4000 可写且幂等。
  （bootloader 态下的可写性未知，且退出时的收尾可能覆盖它。）

★ 安全
  · 默认 dry；--go 执行
  · 写回的是【本机的正常态原值】⇒ 与设备固件版本匹配（不是外部容器内容）—— 纪律 139
  · 失败时：仅提示重启（BIOS 重刷路径）
"""
import sys, os, time, argparse, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gxmem

HDR = 0x4000
HDRLEN = 0x40
CMD_ADDR, BL_STATE, FLASH_RES = 0x4160, 0x5095, 0x5096
BL_READY = 0xDD
LOG = []
STATE = {"in_bl": False}


def log(s):
    line = "[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), s)
    print(line, flush=True); LOG.append(line)


def flush():
    try:
        open(os.path.join(HERE, "_r49_log.txt"), "a", encoding="utf-8").write("\n".join(LOG) + "\n")
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


def rd(g, a, n, tries=8):
    for _ in range(tries):
        d, _ = g.read(a, n)
        if d and len(d) >= n:
            return bytes(d[:n])
        time.sleep(0.1)
    return None


def bl_stable(g, need=5, tries=40, gap=0.03):
    seq = []
    for _ in range(tries):
        b = rd(g, BL_STATE, 1)
        if b:
            seq.append(b[0])
        if len(seq) >= need and all(x == seq[-1] for x in seq[-need:]):
            return seq[-1], True
        time.sleep(gap)
    return (seq[-1] if seq else None), False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()

    log("=" * 82)
    log("r49 · 定点修复实验（进 bootloader 退化 → 写回固件头 → 看功能）· %s"
        % ("COMMIT" if a.go else "DRY"))
    log("=" * 82)
    log("将调用：0E10 → {33} → 等0x5095==0xDD → 0E11 → {34} → 0E13 → {32}   （★ 不发 0E12）")
    log("然后：在正常模式下写回 0x4000 的 64 B 正常态原值")
    if not a.go:
        log("")
        log("[DRY] 未加 --go ⇒ 未打开设备。")
        return 0

    g = gxmem.Gx()
    if not g.open():
        log("[FATAL] 打开 Col04 失败"); return 3
    try:
        # ── 1) 基线（正常态）──
        log("")
        log("── 1) 基线：读取正常态固件头（这就是要写回的正确值）──")
        base_hdr = rd(g, HDR, HDRLEN)
        if base_hdr is None:
            log("  ❌ 读不到 ⇒ 终止"); return 4
        log("  0x4000-0x403F: %s" % hx(base_hdr))
        if base_hdr[0:8] == b'\x00' * 8:
            log("  ⚠️ 前 8 字节已是全零 ⇒ 设备【现在就是退化态】")
            log("      ⇒ 无法用它作为'正常态正确值'的基准 ⇒ 终止")
            return 5
        log("  ✅ 前 8 字节非零 ⇒ 当前是正常态，可作为正确值基准")

        # ── 2) 进+退 bootloader ⇒ 退化 ──
        log("")
        log("── 2) 进 bootloader 并退出（这一步会造成退化）──")
        if not g._send(list(cmd6(0x10))):
            log("  ❌ 0E10 失败"); return 6
        STATE["in_bl"] = True
        log("  ✅ 0E10 已发，等 250 ms"); time.sleep(0.25)
        for _ in range(3):
            g.write(CMD_ADDR, cmdreg(0x33)); time.sleep(0.01)
        log("  ✅ {33} 关坐标")
        v, stable = bl_stable(g)
        log("  0x5095 末值 %s 稳定=%s" % (("0x%02X" % v) if v is not None else "None", stable))
        if v != BL_READY or not stable:
            log("  ❌ 未进 bootloader ⇒ 终止"); return 7
        if not g._send(list(cmd6(0x11))):
            log("  ❌ 0E11 失败"); return 8
        log("  ✅ 0E11 已发，等 100 ms"); time.sleep(0.1)
        g.write(CMD_ADDR, cmdreg(0x34)); log("  ✅ {34}")
        if g._send(list(cmd6(0x13))):
            log("  ✅ 0E13 复位，等 300 ms"); time.sleep(0.3)
        g.write(CMD_ADDR, cmdreg(0x32)); log("  ✅ {32}")
        STATE["in_bl"] = False

        # ── 3) 确认退化 ──
        log("")
        log("── 3) 确认退化（正常模式下读固件头）──")
        deg_hdr = rd(g, HDR, HDRLEN)
        if deg_hdr is None:
            log("  ❌ 读不到 ⇒ 终止"); return 9
        log("  0x4000-0x403F: %s" % hx(deg_hdr))
        nzero = all(x == 0 for x in deg_hdr[0:8])
        log("  ⇒ 前 8 字节是否全零: %s" % ("★ 是（已退化）" if nzero else "否（未退化？）"))
        ndiff = sum(1 for i in range(HDRLEN) if base_hdr[i] != deg_hdr[i])
        log("  ⇒ 与基线差异: %d/%d 字节" % (ndiff, HDRLEN))
        if ndiff:
            for i in range(HDRLEN):
                if base_hdr[i] != deg_hdr[i]:
                    log("     0x%04X: %02X -> %02X" % (HDR + i, base_hdr[i], deg_hdr[i]))

        # ── 4) 写回固件头 ──
        log("")
        log("── 4) ★ 写回固件头（正常模式下，64 B）──")
        log("  将写 0x%04X ← %s" % (HDR, hx(base_hdr)))
        ok = g.write(HDR, base_hdr)
        log("  写入调用返回: %s" % ("✅" if ok else "❌"))
        time.sleep(0.4)

        # ── 5) 校验 ──
        log("")
        log("── 5) 写后校验 ──")
        after = rd(g, HDR, HDRLEN)
        log("  0x4000-0x403F: %s" % hx(after) if after else "  <读失败>")
        if after:
            n = sum(1 for i in range(HDRLEN) if after[i] != base_hdr[i])
            log("  ⇒ 与基线差异: %d/%d 字节  %s" % (n, HDRLEN, "★ 完全一致" if n == 0 else ""))
            log("  ⇒ 前 8 字节: %s" % ("★ 已恢复非零" if after[0:8] != b'\x00' * 8 else "仍全零"))

        log("")
        log("═" * 62)
        log("★ 请立刻测试触控板：滑动 / 按压点击 / 触觉")
        log("   若触觉+按压点击恢复 ⇒ ★★★ 定点修复【成立】")
        log("   若未恢复 ⇒ 固件头不是（唯一）根因；重启即可恢复")
        log("═" * 62)
        return 0
    finally:
        if STATE["in_bl"]:
            log("")
            log("★ 恢复路径（仍在 bootloader）")
            try:
                g.write(CMD_ADDR, cmdreg(0x34))
                if g._send(list(cmd6(0x13))):
                    time.sleep(0.3)
                g.write(CMD_ADDR, cmdreg(0x32))
                log("  → {34} / 0E13 / {32} 已发")
            except Exception as e:
                log("  → 异常 %r" % e)
        g.close()
        flush()
        log("日志 → _r49_log.txt")


if __name__ == "__main__":
    raise SystemExit(main())
