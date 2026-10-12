#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
lab__r48_header_write_test.py — ★ 幂等写测试：写路径能否到达 0x4000（固件头）

★ 为什么是幂等写
  目标 0x4000-0x4007 是【固件头】。**若写入不完整 ⇒ 反而会造成退化**。
  因此本脚本【只写回它当前的原值】⇒ 结果与现状等价 ⇒ 即使完整成功也不改变任何东西，
  但能验证：① 写路径够不够得到 0x4000 ② 写后读回是否一致

★ 安全
  · 默认 dry；--go 才执行
  · 写前必须【先读回原值】并在写后【逐字节校验】
  · 写入长度 = 8 字节（单包，走已验证的多包路径）
  · 不调用任何 0E 10/0E 11/0E 12/0E 13
  · 异常时不做任何额外动作（因为没进 bootloader，无非常态）
"""
import sys, os, time, argparse, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gxmem

TARGET = 0x4000
LEN = 8
LOG = []


def log(s):
    line = "[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), s)
    print(line, flush=True); LOG.append(line)


def flush():
    try:
        open(os.path.join(HERE, "_r48_log.txt"), "a", encoding="utf-8").write("\n".join(LOG) + "\n")
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
        time.sleep(0.1)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()

    log("=" * 78)
    log("r48 · 幂等写 0x4000 固件头（写回原值）· %s" % ("COMMIT" if a.go else "DRY"))
    log("=" * 78)
    log("目标: 0x%04X 长度 %d B（单包）" % (TARGET, LEN))
    log("★ 将写回它【当前的原值】⇒ 幂等 ⇒ 即使成功也不改变任何东西")

    if not a.go:
        log("")
        log("[DRY] 未加 --go ⇒ 未打开设备。")
        return 0

    g = gxmem.Gx()
    if not g.open():
        log("[FATAL] 打开 Col04 失败"); return 3
    try:
        log("")
        log("── 1) 读回原值 ──")
        orig = rd(g, TARGET, LEN)
        if orig is None:
            log("  ❌ 读不到 0x%04X ⇒ 终止（不写）" % TARGET); return 4
        log("  0x%04X 原值: %s" % (TARGET, hx(orig)))

        # 参考：正常态应为 A7 E0 E5 B1 F5 9D D8 DC
        NORMAL = bytes.fromhex('A7E0E5B1F59DD8DC')
        log("  ⇒ 是否为已知正常态值: %s" % ("✅ 是（与刚 dump 的正常态一致）" if orig == NORMAL else "⚠️ 否"))

        # 上下文（确认我们在固件头区）
        ctx = rd(g, TARGET, 0x40)
        if ctx:
            log("  0x4000-0x403F: %s" % hx(ctx))
            log("  ⇒ YELSTO 在 0x4018: %s" % ("✅" if ctx[0x18:0x1E] == b'YELSTO' else "⚠️"))

        log("")
        log("── 2) 幂等写（写回同一 8 字节）──")
        log("  将写 0x%04X ← %s" % (TARGET, hx(orig)))
        ok = g.write(TARGET, orig)
        log("  写入调用返回: %s" % ("✅" if ok else "❌"))
        time.sleep(0.3)

        log("")
        log("── 3) 写后校验 ──")
        after = rd(g, TARGET, LEN)
        log("  写后 0x%04X: %s" % (TARGET, hx(after) if after else "<读失败>"))
        same = (after == orig)
        log("  ⇒ 与写前一致: %s" % ("✅ 是（幂等成立，数据未变）" if same else "❌ 否"))

        # 校验整块头
        ctx2 = rd(g, TARGET, 0x40)
        if ctx2 and ctx:
            n = sum(1 for i in range(0x40) if ctx2[i] != ctx[i])
            log("  ⇒ 固件头 0x4000-0x403F 前后差异: %d/64 字节" % n)
            if n:
                for i in range(0x40):
                    if ctx2[i] != ctx[i]:
                        log("     0x%04X: %02X -> %02X" % (TARGET + i, ctx[i], ctx2[i]))

        log("")
        log("── 4) 结论 ──")
        if same:
            log("  ★ 写路径【够得到】0x%04X（写入后读回一致）" % TARGET)
            log("  ⇒ 这意味着：将来在退化态下，可以直接把正常态值写回这个头来尝试定点修复")
        else:
            log("  ⚠️ 写后与写前不一致 ⇒ 该地址【不是】可正常读写的普通内存")
            log("  （可能是 flash 或只读影子区；或写路径不覆盖该地址）")
        return 0
    finally:
        g.close()
        flush()
        log("日志 → _r48_log.txt")


if __name__ == "__main__":
    raise SystemExit(main())
