#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
lab__r35_chunk_write.py — 补写指定子固件的指定块（★ 修复用）

用途：r34 只写了 idx1 第 1 块（0x016000），导致 idx1 后半（0x017000）处于被擦除态。
     本脚本按官方流程补齐 idx1 的剩余块。

依据：goodix/gdix_hid_firmware_update  gtx2/gtx2_update.cpp:139-213 · gt7868q_update.cpp:122-311
"""
import sys, os, time, argparse, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gxmem

IMAGE = r"<WORKSPACE>\_ext\fw\gt7868q_scrambled.bin"   # 已脱敏（原为本机绝对路径；见 _local-tools/redact.py）
PAYLOAD_OFF, PAYLOAD_SIZE = 0x0113C, 100608
CMD_ADDR, BL_STATE, FLASH_RES, FLASH_BUF = 0x4160, 0x5095, 0x5096, 0xC000
BL_READY, RES_OK = 0xDD, 0xAA
RAM_BUFFER_SIZE = 4096

LOG = []


def log(s):
    line = "[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), s)
    print(line, flush=True); LOG.append(line)


def flush():
    try:
        open(os.path.join(HERE, "_r35_log.txt"), "a", encoding="utf-8").write("\n".join(LOG) + "\n")
    except Exception:
        pass


def ck16be(b):
    s = 0
    for i in range(0, len(b) - 1, 2):
        s = (s + ((b[i] << 8) + b[i + 1])) & 0xFFFF
    return s


def hx(b, n=None):
    b = bytes(b)
    if n: b = b[:n]
    return " ".join("%02X" % x for x in b)


def cmd6(c): return bytes([0x0E, c, 0x00, 0x00, 0x01, 0x01])


def cmdreg(c, hi=0, lo=0):
    ck = (c + hi + lo) & 0xFFFF
    return bytes([c, hi, lo, (ck >> 8) & 0xFF, ck & 0xFF])


def rd(g, a, n=1):
    for _ in range(2):
        d, _ = g.read(a, n)
        if d: return bytes(d[:n])
        time.sleep(0.03)
    return None


def bl_stable(g, need=5, tries=40, gap=0.03):
    seq = []
    for _ in range(tries):
        b = rd(g, BL_STATE)
        if b: seq.append(b[0])
        if len(seq) >= need and all(x == seq[-1] for x in seq[-need:]):
            return seq[-1], True
        time.sleep(gap)
    return (seq[-1] if seq else None), False


def load_chunk(g, addr, data):
    """官方单块：写 0xC000 → 0E 12 → 轮询 0x5096==0xAA → 清零。返回 True/False"""
    if not g.write(FLASH_BUF, data):
        log("      ❌ 写 0xC000 失败"); return False
    ck = ck16be(data)
    fr = bytes([0x0E, 0x12, 0x00, 0x00, 0x06,
                (len(data) >> 8) & 0xFF, len(data) & 0xFF,
                (addr >> 16) & 0xFF, (addr >> 8) & 0xFF,
                (ck >> 8) & 0xFF, ck & 0xFF])
    log("      → 0E12: %s" % hx(fr, 11))
    if not g._send(list(fr)):
        log("      ❌ 0E12 发送失败"); return False
    ok = False; seen = []
    for i in range(100):
        time.sleep(0.002)
        b = rd(g, FLASH_RES)
        if b:
            seen.append(b[0])
            if b[0] == RES_OK:
                log("      第 %d 次 = 0xAA ✅" % (i + 1)); ok = True; break
    if not ok:
        log("      ❌ 未报 0xAA；最近: %s" % " ".join("%02X" % x for x in seen[-12:]))
        return False
    g.write(FLASH_RES, b"\x00")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--idx", type=int, default=1, help="子固件 idx（默认 1）")
    ap.add_argument("--chunk", type=int, default=1, help="要补的块序号，0 起（默认 1 = 第 2 块）")
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()

    d = open(IMAGE, "rb").read()
    A = d[PAYLOAD_OFF:PAYLOAD_OFF + PAYLOAD_SIZE]
    size = int.from_bytes(A[0:4], "big")
    if (size + 6) != PAYLOAD_SIZE:
        log("[ABORT] 容器长度校验失败"); return 2
    N = A[0x1B]
    ents = []
    cur = 0x100
    for i in range(N):
        p = 0x20 + i * 8
        t = A[p]; ln = int.from_bytes(A[p + 1:p + 5], "big")
        fa = int.from_bytes(A[p + 5:p + 7], "big") << 8
        ents.append({"i": i, "type": t, "len": ln, "fa": fa, "off": cur})
        cur += ln
    e = ents[a.idx]
    nchunks = (e["len"] + RAM_BUFFER_SIZE - 1) // RAM_BUFFER_SIZE

    log("=" * 78)
    log("r35 · 子固件 idx%d（type 0x%02X, len %d, flash 0x%06X）共 %d 块"
        % (e["i"], e["type"], e["len"], e["fa"], nchunks))
    log("=" * 78)

    start = a.chunk
    todo = []
    for c in range(start, nchunks):
        addr = e["fa"] + c * RAM_BUFFER_SIZE
        off = e["off"] + c * RAM_BUFFER_SIZE
        todo.append((addr, A[off:off + RAM_BUFFER_SIZE], c))
    log("将补写 %d 块：从 chunk %d 到 %d" % (len(todo), start, nchunks - 1))
    for addr, ch, c in todo:
        log("  chunk %d → 0x%06X (4096 B, ck=0x%04X)" % (c, addr, ck16be(ch)))

    if not a.go:
        log("")
        log("[DRY] 未加 --go。核对上方清单后用 --go 执行。")
        return 0

    g = gxmem.Gx()
    if not g.open():
        log("[FATAL] 打开 Col04 失败"); return 3
    failed = False
    try:
        log("")
        log("── 基线 ──")
        b96 = rd(g, 0x96F8, 32)
        log("  0x96F8 32B: %s" % hx(b96 or b""))

        log("── 1. 0E10 切 patch ──")
        if not g._send(list(cmd6(0x10))):
            log("  ❌ 失败"); return 4
        STATE_OK = False
        log("  ✅ 已发，等待 250 ms"); time.sleep(0.25)
        g.write(CMD_ADDR, cmdreg(0x33)); log("  ✅ {33} 关坐标")

        log("── 2. 等 0x5095 == 0xDD（连续 5 次）──")
        v, stable = bl_stable(g, need=5)
        log("  末值 %s 稳定=%s" % (("0x%02X" % v) if v is not None else "None", stable))
        if v != BL_READY or not stable:
            log("  ❌ 未进 bootloader ⇒ 终止"); failed = True; return 5
        log("  ✅ 已进入 bootloader")
        STATE_OK = True

        log("── 3. 0E11 启动更新 ──")
        if not g._send(list(cmd6(0x11))):
            log("  ❌ 失败"); failed = True; return 6
        time.sleep(0.1)
        log("  ✅ 已发")

        log("── 4. 逐块补写 ──")
        for addr, ch, c in todo:
            log("  chunk %d → 0x%06X" % (c, addr))
            if not load_chunk(g, addr, ch):
                log("  ❌ 本块失败 ⇒ 停止"); failed = True; return 7
        log("  ✅ 全部补写完成")

        log("── 5. 收尾：{34} → 0E13 → {32} ──")
        g.write(CMD_ADDR, cmdreg(0x34)); log("  ✅ {34}")
        if g._send(list(cmd6(0x13))):
            log("  ✅ 0E13 复位"); time.sleep(0.3)
        else:
            log("  ⚠️ 0E13 失败")
        g.write(CMD_ADDR, cmdreg(0x32)); log("  ✅ {32} 切 PTP")

        log("")
        log("── 写后核查 ──")
        b96b = rd(g, 0x96F8, 32)
        log("  0x96F8 32B: %s" % hx(b96b or b""))
        log("  补写前 0x96F8: %s" % hx(b96 or b""))
        log("")
        if b96b == b96:
            log("  ✅ cfg 暂存区恢复到与补写前一致")
        else:
            log("  ⚠️ cfg 暂存区与补写前不同")
        log("")
        if failed:
            log("★★★ 本轮失败，请勿盲目重试。")
        else:
            log("★★★ idx1 已补齐（chunk %d..%d）。请立刻测试触控板：滑动、按压点击、触觉。" % (start, nchunks - 1))
        return 0 if not failed else 1
    finally:
        if STATE_OK:
            log("")
            log("★ 恢复路径（已进 bootloader）")
            try:
                g.write(CMD_ADDR, cmdreg(0x34)); log("  → {34}")
            except Exception as e:
                log("  → {34} 异常 %r" % e)
            try:
                if g._send(list(cmd6(0x13))): log("  → 0E13"); time.sleep(0.3)
            except Exception as e:
                log("  → 0E13 异常 %r" % e)
            try:
                g.write(CMD_ADDR, cmdreg(0x32)); log("  → {32}")
            except Exception as e:
                log("  → {32} 异常 %r" % e)
        g.close()
        flush()
        log("日志 → _r35_log.txt")


if __name__ == "__main__":
    raise SystemExit(main())
