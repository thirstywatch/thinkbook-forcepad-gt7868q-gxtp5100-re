#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
lab__r34_first_write.py — ★ 首次实机 `0E 12` 单块写入（最小风险）

★ 本脚本【只发一条】0E 12（不是 24 条）。目标与参数：
    目标子固件  : idx1 第 1 块
    flash 地址  : 0x016000        ← 非关键地址（不碰 0x000000）
    长度        : 4096 B
    数据来源    : 官方容器 file 0x00900 起 4096 B（★ 与设备现版本相同 ⇒ 幂等）
    校验和      : 0xFB48（大端 16 位字和，官方算法）

★ 官方依据
    命令帧 = 0E 12 00 00 06 <len16BE> <addrHi> <addrMid> <ckHi> <ckLo>
    流程   = 0E10 → {33} → 等 0x5095==0xDD → 0E11 → [0xC000<-data, 0E12, 轮询0x5096==0xAA] → {34} → 0E13 → {32}
    出处   : goodix/gdix_hid_firmware_update  gtx2/gtx2_update.cpp:139-213 · gt7868q/gt7868q_update.cpp:122-311

★ 已知风险（如实列出）
    ① 本通道【读不回 flash】⇒ 写错时没有任何回读层能发现（静默）
    ② 官方【无独立 erase】⇒ 擦除隐含在 0E12 内 ⇒ 地址算错 = 静默毁掉一片
    ③ IC 对 [7][8] 的字节序解释只能在本次实机中确认
    ④ 过程中触控板会【停止工作】（已进 bootloader）；收尾会复位并恢复

用法
  python lab__r34_first_write.py             # 只打印将要发送的每个字节（dry）
  python lab__r34_first_write.py --go        # ★ 真正执行
"""
import sys, os, time, argparse, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gxmem

IMAGE = r"<WORKSPACE>\_ext\fw\gt7868q_scrambled.bin"   # 已脱敏（原为本机绝对路径；见 _local-tools/redact.py）
PAYLOAD_OFF, PAYLOAD_SIZE = 0x0113C, 100608

TARGET_FA   = 0x016000
TARGET_LEN  = 4096
DATA_OFF_IN_IMAGE = 0x0113C + 0x00900     # 官方容器内 idx1 第 1 块位置

CMD_ADDR, BL_STATE, FLASH_RES, FLASH_BUF = 0x4160, 0x5095, 0x5096, 0xC000
BL_READY, RES_OK = 0xDD, 0xAA

LOG = []
STATE = {"in_bootloader": False}


def log(s):
    line = "[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), s)
    print(line, flush=True)
    LOG.append(line)


def flush():
    try:
        open(os.path.join(HERE, "_r34_log.txt"), "a", encoding="utf-8").write("\n".join(LOG) + "\n")
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


def cmd6(code):
    return bytes([0x0E, code, 0x00, 0x00, 0x01, 0x01])


def cmdreg(cmd, hi=0, lo=0):
    ck = (cmd + hi + lo) & 0xFFFF
    return bytes([cmd, hi, lo, (ck >> 8) & 0xFF, ck & 0xFF])


def rd(g, addr, n=1, tries=1):
    for _ in range(tries):
        d, _ = g.read(addr, n)
        if d:
            return bytes(d[:n])
        time.sleep(0.02)
    return None


def bl_state_stable(g, need=5, tries=40, gap=0.03):
    seq = []
    for _ in range(tries):
        b = rd(g, BL_STATE)
        if b is None:
            time.sleep(gap); continue
        seq.append(b[0])
        if len(seq) >= need and all(x == seq[-1] for x in seq[-need:]):
            return seq[-1], True, seq
        time.sleep(gap)
    return (seq[-1] if seq else None), False, seq


def health(g, tag):
    log("  [健康 %s] 0x4160=%s 0x5095=%s 0x5096=%s 0x96F8=%s"
        % (tag,
           hx(rd(g, CMD_ADDR) or b"\x00"),
           hx(rd(g, BL_STATE) or b"\x00"),
           hx(rd(g, FLASH_RES) or b"\x00"),
           hx(rd(g, 0x96F8, 8) or b"", )))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true", help="★ 真正执行")
    a = ap.parse_args()

    log("=" * 84)
    log("r34 · 首次实机 0E12 单块写入 · %s" % ("★★★ COMMIT" if a.go else "DRY"))
    log("=" * 84)

    # ── 准备数据（离线，先打印）──
    d = open(IMAGE, "rb").read()
    A = d[PAYLOAD_OFF:PAYLOAD_OFF + PAYLOAD_SIZE]
    size = int.from_bytes(A[0:4], "big")
    ckf = int.from_bytes(A[4:6], "big")
    calc = sum(A[6:size + 6]) & 0xFFFF
    log("官方镜像校验：长度 %d(+6=%d) %s ；校验 0x%04X/实算 0x%04X %s"
        % (size, size + 6, "✅" if size + 6 == len(A) else "❌", ckf, calc,
           "✅" if ckf == calc else "❌"))
    data = A[DATA_OFF_IN_IMAGE - PAYLOAD_OFF: DATA_OFF_IN_IMAGE - PAYLOAD_OFF + TARGET_LEN]
    if len(data) != TARGET_LEN:
        log("[ABORT] 取数据失败"); return 2
    ck = ck16be(data)
    frame = bytes([0x0E, 0x12, 0x00, 0x00, 0x06,
                   (TARGET_LEN >> 8) & 0xFF, TARGET_LEN & 0xFF,
                   (TARGET_FA >> 16) & 0xFF, (TARGET_FA >> 8) & 0xFF,
                   (ck >> 8) & 0xFF, ck & 0xFF])
    log("")
    log("★ 将要发送的完整序列（逐字节）")
    log("  [1] 0E10 切patch      : %s" % hx(cmd6(0x10)))
    log("  [2] 写 0x4160 ← {33}  : %s" % hx(cmdreg(0x33)))
    log("  [3] 轮询 0x5095 == 0xDD（连续 5 次相同才认可）")
    log("  [4] 0E11 启动更新     : %s" % hx(cmd6(0x11)))
    log("  [5] 写 RAM 0xC000 ← 4096 B 数据（file 0x%05X）" % DATA_OFF_IN_IMAGE)
    log("      数据前 32 B: %s" % hx(data, 32))
    log("      数据校验和 = 0x%04X" % ck)
    log("  [6] ★ 0E12 提交       : %s" % hx(frame))
    log("  [7] 轮询 0x5096 == 0xAA")
    log("  [8] 写 0x4160 ← {34}  : %s" % hx(cmdreg(0x34)))
    log("  [9] 0E13 复位         : %s" % hx(cmd6(0x13)))
    log("  [10] 写 0x4160 ← {32} : %s" % hx(cmdreg(0x32)))
    log("")
    log("⚠️ 过程中触控板会停止工作（[1] 之后到 [9] 之间）")

    if not a.go:
        log("")
        log("[DRY] 未加 --go ⇒ 未打开设备。核对上方每个字节后，用 --go 执行。")
        return 0

    g = gxmem.Gx()
    if not g.open():
        log("[FATAL] 打开 Col04 失败"); return 3
    failed = False
    try:
        log("")
        log("── 0. 基线 ──")
        health(g, "写前")
        b96 = rd(g, 0x96F8, 32)
        log("  0x96F8 基线 32B: %s" % hx(b96 or b""))

        v0, st0, seq0 = bl_state_stable(g, need=5, tries=10)
        log("  0x5095 进 bootloader 前：末值 %s（连续5次稳定=%s）"
            % ("0x%02X" % v0 if v0 is not None else "None", st0))

        log("── 1. 0E10 切 patch ──")
        if not g._send(list(cmd6(0x10))):
            log("  ❌ 发送失败 ⇒ 终止（未改动）"); return 4
        STATE["in_bootloader"] = True
        log("  ✅ 已发 %s，等待 250 ms" % hx(cmd6(0x10)))
        time.sleep(0.25)

        log("── 2. 关坐标上报 {33} ──")
        g.write(CMD_ADDR, cmdreg(0x33))
        log("  ✅ 已写 0x4160 ← %s" % hx(cmdreg(0x33)))

        log("── 3. 等 0x5095 == 0xDD ──")
        v, stable, seq = bl_state_stable(g, need=5, tries=40, gap=0.03)
        log("  末值 %s ；最近 12 次读值: %s"
            % ("0x%02X" % v if v is not None else "None",
               " ".join("%02X" % x for x in seq[-12:])))
        if v != BL_READY or not stable:
            log("  ❌ 未稳定到 0xDD ⇒ **不继续**（立即走恢复路径）")
            failed = True
            return 5
        log("  ✅ 已进入 bootloader 态（0x5095 == 0xDD，连续5次）")

        log("── 4. 0E11 启动更新 ──")
        if not g._send(list(cmd6(0x11))):
            log("  ❌ 发送失败"); failed = True; return 6
        log("  ✅ 已发 %s，等待 100 ms" % hx(cmd6(0x11)))
        time.sleep(0.1)

        log("── 5. 写 RAM 暂存 0xC000 ← %d B ──" % TARGET_LEN)
        if not g.write(FLASH_BUF, data):
            log("  ❌ 写 0xC000 失败 ⇒ 未发 0E12"); failed = True; return 7
        log("  ✅ 已写入 0xC000")

        log("── 6. ★ 0E12 提交（本脚本唯一一条）──")
        log("      帧: %s" % hx(frame))
        if not g._send(list(frame)):
            log("  ❌ 0E12 发送失败"); failed = True; return 8
        log("  ✅ 已发出 0E12")

        log("── 7. 轮询 0x5096 == 0xAA ──")
        ok = False
        seen = []
        for i in range(100):
            time.sleep(0.002)
            b = rd(g, FLASH_RES)
            if b:
                seen.append(b[0])
                if b[0] == RES_OK:
                    ok = True
                    log("  第 %d 次 = 0xAA ⇒ ★ 本块成功" % (i + 1))
                    break
        if not ok:
            log("  100 次未见 0xAA ；最近值: %s" % " ".join("%02X" % x for x in seen[-16:]))
            log("  ❌ 记阴性 ⇒ 走恢复路径，不再做任何进一步动作")
            failed = True
        else:
            g.write(FLASH_RES, b"\x00")
            log("  ✅ 已清零 0x5096")

        log("── 8-10. 收尾：{34} → 0E13 → {32} ──")
        g.write(CMD_ADDR, cmdreg(0x34)); log("  ✅ {34} 开坐标")
        if g._send(list(cmd6(0x13))):
            log("  ✅ 0E13 复位已发"); time.sleep(0.3)
        else:
            log("  ⚠️ 0E13 发送失败")
        g.write(CMD_ADDR, cmdreg(0x32)); log("  ✅ {32} 切 PTP")
        STATE["in_bootloader"] = False

        log("")
        log("── 写后核查 ──")
        health(g, "写后")
        b96b = rd(g, 0x96F8, 32)
        log("  0x96F8 32B: %s" % hx(b96b or b""))
        log("  ⇒ 与写前一致：%s" % ("✅" if b96b == b96 else "⚠️ 不一致"))
        log("")
        if failed:
            log("★★★ 结论：0E12 未报成功（见 [7]）。设备已复位回正常态。")
        else:
            log("★★★★★ 结论：0E12 被接受且结果寄存器报 0xAA。")
            log("   ⇒ 这【不等价于】落盘已验：本通道读不回 flash，只能靠【功能表现】判断。")
            log("   ⇒ 请**立刻试触控板**（移动/点击/滑动）确认仍正常工作。")
        return 0 if not failed else 1
    finally:
        if failed and STATE["in_bootloader"]:
            log("")
            log("★ 恢复路径（已进 bootloader，必须收尾）")
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
            health(g, "恢复后")
        elif failed:
            log("(未进 bootloader ⇒ 不触发恢复路径)")
        g.close()
        flush()
        log("日志 → _r34_log.txt")


if __name__ == "__main__":
    raise SystemExit(main())
