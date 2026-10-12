#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
lab__r36_full_update.py — 完整复刻官方 fw_update（全部 12 个子固件 / 24 块连续写入）

★ 用途：恢复因"半更新"而退化的设备 —— 把官方固件的全部内容写回 flash。

★ 依据
  `goodix/gdix_hid_firmware_update`（官方，master）
  · gt7868q/gt7868q_update.cpp:122-311  fw_update
  · gtx2/gtx2_update.cpp:139-213        load_sub_firmware
  · gtx5/gtx5.cpp:227-309               传输原语
  · main.cpp:400-404                    flash_flag = 0x0C（type 0x02, 0x03）

★ 流程（与官方逐字对应）
  ① 0E 10 00 00 01 01                     切 patch          → 250 ms
  ② 写 0x4160 ← {33,00,00,00,33}          关坐标（×3）
  ③ 轮询 0x5095 == 0xDD（连续 5 次）      等 bootloader
  ④ 0E 11 00 00 01 01                     启动更新          → 100 ms
  ⑤ 按【表序】逐块：写 0xC000 ← 4096 B → 0E 12 → 轮询 0x5096 == 0xAA
     （跳过 type 不在 flash_flag 内的块）
  ⑥ 写 0x4160 ← {34,00,00,00,34}          开坐标
  ⑦ 0E 13 00 00 01 01                     复位              → 300 ms
  ⑧ 写 0x4160 ← {32,00,00,00,32}          切 PTP

★ 安全
  · 默认 dry；--commit 才真执行
  · 写入数据【全部来自官方容器】（设备当前跑的就是这份固件 ⇒ 幂等）
  · 任一块失败 ⇒ 立即走恢复路径（0E 13 + {34} + {32}）
"""
import sys, os, time, argparse, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gxmem

IMAGE = r"<WORKSPACE>\_ext\fw\gt7868q_scrambled.bin"   # 已脱敏（原为本机绝对路径；见 _local-tools/redact.py）
PAYLOAD_OFF, PAYLOAD_SIZE = 0x0113C, 100608
CMD_ADDR, BL_STATE, FLASH_RES, FLASH_BUF = 0x4160, 0x5095, 0x5096, 0xC000
RAM_BUFFER_SIZE = 4096
BL_READY, RES_OK = 0xDD, 0xAA
FLASH_FLAG = 0x0C

LOG = []


def log(s):
    line = "[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), s)
    print(line, flush=True); LOG.append(line)


def flush():
    try:
        open(os.path.join(HERE, "_r36_log.txt"), "a", encoding="utf-8").write("\n".join(LOG) + "\n")
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
    if not g.write(FLASH_BUF, data):
        log("      ❌ 写 0xC000 失败"); return False
    ck = ck16be(data)
    fr = bytes([0x0E, 0x12, 0x00, 0x00, 0x06,
                (len(data) >> 8) & 0xFF, len(data) & 0xFF,
                (addr >> 16) & 0xFF, (addr >> 8) & 0xFF,
                (ck >> 8) & 0xFF, ck & 0xFF])
    log("      0E12: %s" % hx(fr, 11))
    if not g._send(list(fr)):
        log("      ❌ 发送失败"); return False
    for i in range(100):
        time.sleep(0.002)
        b = rd(g, FLASH_RES)
        if b:
            if b[0] == RES_OK:
                log("      ✅ 0xAA（第 %d 次）" % (i + 1))
                g.write(FLASH_RES, b"\x00")
                return True
    b = rd(g, FLASH_RES)
    log("      ❌ 未报 0xAA（末值 %s）" % hx(b or b"", 1))
    return False


def parse_container(path):
    d = open(path, "rb").read()
    A = d[PAYLOAD_OFF:PAYLOAD_OFF + PAYLOAD_SIZE]
    size = int.from_bytes(A[0:4], "big")
    ck = int.from_bytes(A[4:6], "big")
    calc = sum(A[6:size + 6]) & 0xFFFF
    if not (size + 6 == len(A) and ck == calc):
        log("[ABORT] 官方容器校验失败"); return None
    N = A[0x1B]
    ents = []; cur = 0x100
    for i in range(N):
        p = 0x20 + i * 8
        t = A[p]; ln = int.from_bytes(A[p + 1:p + 5], "big")
        fa = int.from_bytes(A[p + 5:p + 7], "big") << 8
        ents.append({"i": i, "type": t, "len": ln, "fa": fa, "off": cur})
        cur += ln
    return {"A": A, "size": size, "ck": ck, "calc": calc, "ents": ents,
            "pid": A[0x0F:0x17], "magic": A[6:0x0F], "n": N}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="★ 真正执行")
    ap.add_argument("--image", default=IMAGE)
    a = ap.parse_args()

    log("=" * 84)
    log("r36 · 完整官方更新（12 子固件 / 24 块）· %s" % ("COMMIT" if a.commit else "DRY"))
    log("=" * 84)

    c = parse_container(a.image)
    if not c:
        return 2
    log("官方镜像：%s" % os.path.basename(a.image))
    log("  长度 %d(+6=%d) ✅  校验 0x%04X ✅  PID=%r  IC=%r  子固件 %d"
        % (c["size"], c["size"] + 6, c["ck"], c["pid"], c["magic"], c["n"]))

    todo = []
    for e in c["ents"]:
        if not (FLASH_FLAG & (0x01 << e["type"])):
            log("  跳过 idx%d (type 0x%02X，不在 flag 0x%02X 内)" % (e["i"], e["type"], FLASH_FLAG))
            continue
        nch = (e["len"] + RAM_BUFFER_SIZE - 1) // RAM_BUFFER_SIZE
        for c2 in range(nch):
            addr = e["fa"] + c2 * RAM_BUFFER_SIZE
            off = e["off"] + c2 * RAM_BUFFER_SIZE
            n = min(RAM_BUFFER_SIZE, e["len"] - c2 * RAM_BUFFER_SIZE)
            todo.append({"addr": addr, "data": c["A"][off:off + n],
                         "idx": e["i"], "chunk": c2, "ck": ck16be(c["A"][off:off + n])})
    log("  ⇒ 将写入 %d 块（覆盖 0x%06X – 0x%06X）"
        % (len(todo), min(t["addr"] for t in todo),
           max(t["addr"] + len(t["data"]) for t in todo)))

    if not a.commit:
        log("")
        log("[DRY] 未加 --commit。将执行：进 bootloader → 逐块 0E 12（%d 块）→ 复位" % len(todo))
        for t in todo[:6]:
            log("    0E12 0x%06X len=%d ck=0x%04X (idx%d-%d)"
                % (t["addr"], len(t["data"]), t["ck"], t["idx"], t["chunk"]))
        log("    … 共 %d 块" % len(todo))
        return 0

    g = gxmem.Gx()
    if not g.open():
        log("[FATAL] 打开 Col04 失败"); return 3
    in_bl = False
    failed = False
    try:
        log("")
        log("── ① 0E10 切 patch ──")
        if not g._send(list(cmd6(0x10))):
            log("  ❌ 失败"); return 4
        log("  ✅ 已发，等待 250 ms"); time.sleep(0.25)

        log("── ② {33} 关坐标（×3）──")
        for _ in range(3):
            g.write(CMD_ADDR, cmdreg(0x33)); time.sleep(0.01)
        log("  ✅ 已发 ×3")

        log("── ③ 轮询 0x5095 == 0xDD（连续 5 次）──")
        v, stable = bl_stable(g)
        log("  末值 %s 稳定=%s" % (("0x%02X" % v) if v is not None else "None", stable))
        if v != BL_READY or not stable:
            log("  ❌ 未进入 bootloader ⇒ 终止"); failed = True; return 5
        in_bl = True
        log("  ✅ 已进入 bootloader")

        log("── ④ 0E11 启动更新 ──")
        if not g._send(list(cmd6(0x11))):
            log("  ❌ 失败"); failed = True; return 6
        log("  ✅ 已发，等待 100 ms"); time.sleep(0.1)

        log("── ⑤ 逐块写入（%d 块）──" % len(todo))
        done = 0
        for t in todo:
            log("  [%d/%d] idx%d-%d → 0x%06X (ck=0x%04X)"
                % (done + 1, len(todo), t["idx"], t["chunk"], t["addr"], t["ck"]))
            if not load_chunk(g, t["addr"], t["data"]):
                log("  ❌ 本块失败 ⇒ 停止写入（已写 %d 块）" % done)
                failed = True
                break
            done += 1
        log("  ⇒ 完成 %d / %d 块" % (done, len(todo)))

        log("── ⑥⑦⑧ 收尾：{34} → 0E13 → {32} ──")
        g.write(CMD_ADDR, cmdreg(0x34)); log("  ✅ {34}")
        if g._send(list(cmd6(0x13))):
            log("  ✅ 0E13 复位"); time.sleep(0.3)
        else:
            log("  ⚠️ 0E13 失败")
        g.write(CMD_ADDR, cmdreg(0x32)); log("  ✅ {32}")

        log("")
        log("═" * 60)
        if not failed and done == len(todo):
            log("★★★★★ 完整更新序列执行完毕（%d/%d 块全部 0xAA）" % (done, len(todo)))
            log("  ⇒ 请测试触控板：滑动 / 按压点击 / 触觉")
        elif done > 0:
            log("🔴 部分完成：%d/%d 块。设备可能仍处于退化态。" % (done, len(todo)))
            log("  ⇒ 可重跑本脚本（会从头再写一遍全部块）")
        else:
            log("🔴 0 块成功。")
        log("═" * 60)
        return 0 if not failed else 1
    finally:
        if in_bl:
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
            log("  → 健康复查: 0x4160=%s 0x96F8=%s"
                % (hx(rd(g, CMD_ADDR) or b"\x00"), hx(rd(g, 0x96F8, 8) or b"")))
        g.close()
        flush()
        log("日志 → _r36_log.txt")


if __name__ == "__main__":
    raise SystemExit(main())
