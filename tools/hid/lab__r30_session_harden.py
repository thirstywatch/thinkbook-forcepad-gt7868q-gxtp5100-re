#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
lab__r30_session_harden.py — 会话初始化强化（elgato 方法学移植）

来源：schlarpc/elgato-cam-link-4k-firmware-re 的 docs/12-method.md 第 6 步实战笔记：
  "An I2C address that no device acknowledges makes the transfer fail with EPIPE.
   This is the presence test for a bus scan, and without it every address appears to
   answer, because the read buffer keeps the previous transfer. Sweep the bus several
   times: about one address per sweep acknowledges spuriously and returns all zeros.
   Keep only what answers every time."

本条与本项目已知病灶**精确同型**：
  第 18 轮记录："先前看到的 `0E 20 00 00` 是【复用缓冲区残留】，非真实回读"
  —— 即 Gx._recv() 会读到上一次事务的残留 Input Report。

三条对策（本工具实现）：
  ① DRAIN   ：每次事务前，把 Input Report 循环读干净（等价 elgato 的 empty_buffer()）
  ② SWEEP   ：同一事务重复 N 轮，要求**每一轮结果一致**
  ③ DROP-Z  ：丢弃"全 0x00"的结果（假应答）

另有 EXIST 判据：本通道没有 EPIPE 这种显式错误码，改用
  "**多轮一致 + 非全零 + 长度符合**" 三者同时成立 作为"真的应答了"的判据。

用法
----
  # 只读探测（默认 dry，不碰设备）
  python lab__r30_session_harden.py --plan probe

  # 实际执行（会打开设备；只做【读】，绝不写）
  python lab__r30_session_harden.py --plan probe --go

  # 自定义地址表
  python lab__r30_session_harden.py --plan addrs --addrs 0x96F8,0x9807,0x9000 --go

⚠️ 安全声明
  - 本工具**只调用 Gx.read()**，不含任何写路径（不调用 Gx.write / SetFeature）。
  - 只开 COL04（`GENERIC_READ|GENERIC_WRITE`，与 gxmem.py 一致）；**不碰 COL02 / 0x09 / 0x0D / 0x0E 以外的任何通道**。
  - 默认 dry：不加 `--go` 不打开设备。
"""
import sys, os, time, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

try:
    import gxmem
except Exception as e:
    print("[FATAL] 无法导入 gxmem.py（需与本脚本同目录）: %r" % e)
    raise SystemExit(2)


# ────────────────────────────── 核心：三对策 ──────────────────────────────

def drain(g, max_rounds=32, quiet_gap=0.05):
    """① DRAIN：把残留 Input Report 读干净。

    返回 (读到的残留条数, 残留内容列表)。
    判据：连续 quiet_gap 秒内读不到新数据 ⇒ 认为已空。
    注：HidD_GetInputReport 是同步调用，无超时语义；这里用"连续 N 次返回相同/失败"近似。
    """
    residues = []
    prev = None
    same = 0
    for _ in range(max_rounds):
        r = g._recv()
        if r is None:
            break
        body = r[1:11]
        if body == prev:
            same += 1
            if same >= 3:          # 连续 3 次完全一样 ⇒ 视为稳定/空
                break
        else:
            same = 0
            residues.append(body)
        prev = body
        time.sleep(quiet_gap)
    return len(residues), residues


def one_sweep(g, addr, size, drain_first=True):
    """单轮事务：可选先清残留，再读。返回 (data|None, info dict)。"""
    info = {"drained": 0}
    if drain_first:
        n, _ = drain(g)
        info["drained"] = n
    d, log = g.read(addr, size)
    info["log"] = log
    return d, info


def hardened_read(g, addr, size, sweeps=4, drain_first=True):
    """② SWEEP + ③ DROP-Z + EXIST 判据。

    返回 dict：
      ok        : 是否通过全部判据（= "真的应答了"）
      data      : 全部轮次一致时的数据
      all_zero  : 是否全 0x00
      consistent: 多轮是否一致
      results   : 每轮结果（hex 字符串或 None）
      drained   : 每轮清掉的残留条数
    """
    results = []
    raws = []
    drained = []
    for i in range(sweeps):
        d, info = one_sweep(g, addr, size, drain_first)
        drained.append(info["drained"])
        raws.append(d)
        results.append(d.hex().upper() if d else None)

    non_null = [r for r in raws if r]
    found = bool(non_null)

    # 判据 3：丢弃全零
    if found:
        first = non_null[0]
        all_zero = all(b == 0 for b in first)
    else:
        all_zero = False

    # 判据 2：多轮一致（以非空轮次为准；全部非空且完全相同才算一致）
    consistent = (len(non_null) == sweeps) and all(r == non_null[0] for r in non_null)

    # 判据 4：长度符合
    len_ok = bool(non_null) and len(non_null[0]) >= min(size, 1) if size else bool(non_null)

    ok = found and (not all_zero) and consistent and len_ok

    return {
        "addr": addr, "size": size,
        "ok": ok,
        "data": non_null[0] if non_null else None,
        "all_zero": all_zero,
        "consistent": consistent,
        "len_ok": len_ok,
        "drained": drained,
        "results": results,
    }


def hx(d, per=32):
    if not d:
        return "<null>"
    return " ".join("%02X" % b for b in d[:per]) + ("…(+%d)" % (len(d) - per) if len(d) > per else "")


# ────────────────────────────── 计划 ──────────────────────────────

PLANS = {
    # 已知可读点（来自 gxmem.py 的 selftest 与既往结论）
    "probe": [
        (0x96F8, 4,   "配置区（既往期望 22 01 1B 00）"),
        (0x96F8, 32,  "配置区 32B 窗口"),
        (0x9807, 4,   "既往判为【不可读/自相矛盾】—— 本工具应把它剔掉"),
        (0x0000, 4,   "对照：地址 0（预期无有效应答）"),
    ],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default="probe", choices=list(PLANS) + ["addrs"])
    ap.add_argument("--addrs", default="", help="逗号分隔的 16 位地址（配合 --plan addrs）")
    ap.add_argument("--size", type=int, default=32)
    ap.add_argument("--sweeps", type=int, default=4, help="重复轮数（默认 4）")
    ap.add_argument("--go", action="store_true", help="★ 实际打开设备（只读）")
    args = ap.parse_args()

    if args.plan == "addrs":
        if not args.addrs:
            print("[ERR] --plan addrs 需要 --addrs 0x...,0x...")
            return 2
        plan = [(int(x, 0), args.size, "自定义") for x in args.addrs.split(",") if x.strip()]
    else:
        plan = PLANS[args.plan]

    print("=" * 74)
    print("会话强化读探测（elgato 方法学：DRAIN + SWEEP + DROP-Z + 一致性存在判据）")
    print("  计划 %d 项 · 每项 %d 轮 · 只读 · 不含任何写路径" % (len(plan), args.sweeps))
    print("=" * 74)

    if not args.go:
        print("\n[DRY] 未加 --go，不打开设备。将要执行的操作：")
        for addr, size, note in plan:
            print("  read(0x%04X, %d)  ×%d 轮（每轮先 DRAIN）   # %s" % (addr, size, args.sweeps, note))
        print("\n去掉 --dry 影响：本工具默认就是 dry，加 --go 即实际执行。")
        return 0

    g = gxmem.Gx()
    if not g.open():
        print("[FATAL] 打开 COL04 失败。检查设备是否在位。")
        return 3
    print("\n[OK] COL04 已打开（只读）。\n")

    try:
        # 全局先清一次残留
        n, res = drain(g)
        print("全局 DRAIN：清掉 %d 条残留" % n)
        for i, r in enumerate(res[:4]):
            print("   残留[%d] %s" % (i, " ".join("%02X" % b for b in r)))
        print()

        rows = []
        for addr, size, note in plan:
            r = hardened_read(g, addr, size, sweeps=args.sweeps)
            rows.append((r, note))
            flag = "★通过" if r["ok"] else "  剔除"
            why = []
            if not r["data"]:
                why.append("无应答")
            if r["all_zero"]:
                why.append("全零(假应答)")
            if not r["consistent"]:
                why.append("多轮不一致")
            if not r["len_ok"]:
                why.append("长度不符")
            print("%s  0x%04X len=%-3d drained=%-2d  %s" %
                  (flag, addr, size, max(r["drained"]) if r["drained"] else 0,
                   (";".join(why) if why else "")))
            print("        数据: %s" % hx(r["data"]))
            print("        各轮: %s" % " | ".join(x or "<null>" for x in r["results"]))
            print("        备注: %s" % note)
            print()

        print("=" * 74)
        keep = [r for r, _ in rows if r["ok"]]
        drop = [r for r, _ in rows if not r["ok"]]
        print("★通过存在判据（多轮一致 + 非全零 + 长度符合）：%d 项" % len(keep))
        for r in keep:
            print("   0x%04X len=%d  %s" % (r["addr"], r["size"], hx(r["data"])))
        print("被剔除：%d 项" % len(drop))
        for r in drop:
            print("   0x%04X  reason: %s" % (r["addr"],
                  ("all_zero" if r["all_zero"] else ("inconsistent" if not r["consistent"] else "no-answer"))))
        print("\n⇒ 只有【★通过】的地址才可被后续实验当作可信基线。")
        return 0
    finally:
        g.close()


if __name__ == "__main__":
    raise SystemExit(main())
