#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lab__g2_analyze.py -- G2 扫描结果分析器（2026-10-14 新增）

读 lab__r64_g2_scan.py 产出的 JSON，输出：
  ① 逐行表（袋/填充/结果码/J1 指标/多阈值事件数）
  ② 以【对照行 idx=0】为基准，标出 J1 指标偏离的**候选袋**（阈值：事件数或 p95 差 ≥ 2×）
  ③ **覆盖度**与**穷尽判据**：只有"27 袋 × {0x00,0xFF} 全部 0x7F 且无候选"才允许下"cfg 无事件层字段"

用法： python lab__g2_analyze.py --json data/logs/lab__g2scanB_xxx.json [--md out.md]
"""
import os, sys, json, argparse

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

THS = ["0.0005", "0.0010", "0.0020", "0.0040"]


def classify(code):
    """结果码语义（2026-10-14 实测修正）：7F=接受并应用 · 7E0007=与【当前已应用 cfg】相同(DATA_EQU)
       · 7E0003=DATA_ERR(语义非法) · 7E0002=CHKSUM_ERR · 7E0001=PKGS_ERR · None=会话未完成"""
    if not code:
        return "无结果(会话未完成)"
    c = code.replace(" ", "")
    if c.startswith("7F"):
        return "✅ 已应用"
    if c.startswith("7E0007"):
        return "＝ 与当前相同(DATA_EQU)"
    if c.startswith("7E0003"):
        return "🔴 DATA_ERR(语义非法)"
    if c.startswith("7E0002"):
        return "🔴 CHKSUM_ERR"
    if c.startswith("7E0001"):
        return "🔴 PKGS_ERR"
    return "? " + c


def fmt_row(r):
    j = r["j1"]
    return "%-4s %-5s 0x%-3s %-14s %-8s p50=%.6f p95=%.6f max=%.6f 事件%s" % (
        r["idx"], r["bag"], "%02X" % r["fill"], (r.get("code") or "-")[:14],
        classify(r.get("code")), j["band_p50"], j["band_p95"], j["band_max"],
        json.dumps(j["counts"], ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True)
    ap.add_argument("--md", default=None)
    ap.add_argument("--factor", type=float, default=2.0, help="候选判据倍数（默认 2×）")
    a = ap.parse_args()
    d = json.load(open(a.json, encoding="utf-8"))
    rows = d["rows"]
    ctrl = next((r for r in rows if r["idx"] == 0), None)
    print("文件: %s · tag=%s · 窗口 %.1fs · 行数 %d" % (os.path.basename(a.json), d.get("tag"), d.get("window", 0), len(rows)))
    print("")
    print("idx  bag   fill 结果码          accepted p50/p95/max/事件")
    for r in rows:
        r["accepted"] = bool(r.get("code")) and str(r["code"]).startswith("7F")   # ★ 从结果码重算，避免旧数据字段过期
        print(fmt_row(r))
    # 覆盖度
    cov = set((r["bag"], r["fill"]) for r in rows if r["bag"] != 0)
    bags = sorted(set(b for b, f in cov))
    fills = sorted(set(f for b, f in cov))
    acc = [r for r in rows if r["bag"] != 0]
    n_ok = sum(1 for r in acc if r.get("accepted"))
    print("")
    print("覆盖：袋 %d 个 %s · 填充 %s · 组合 %d" % (len(bags), bags if len(bags) <= 30 else "(>30)", [hex(f) for f in fills], len(cov)))
    from collections import Counter as _C
    cls = _C(classify(r.get("code")) for r in acc)
    print("结果码分类：" + " · ".join("%s×%d" % (k, v) for k, v in cls.most_common()))
    print("已应用(7F)：%d / %d" % (n_ok, len(acc)))
    # 候选袋
    if ctrl is None:
        print("⚠️ 无对照行（idx=0）⇒ 无法判定偏离，只列指标")
        return 0
    c = ctrl["j1"]
    cand = []
    for r in acc:
        j = r["j1"]
        reasons = []
        if j["band_p95"] > max(c["band_p95"], 1e-9) * a.factor:
            reasons.append("p95 %.6f > %.2f×对照" % (j["band_p95"], a.factor))
        for t in THS:
            if j["counts"][t] > max(1, c["counts"][t]) * a.factor:
                reasons.append("事件数(%s)=%d > %.2f×对照" % (t, j["counts"][t], a.factor))
        if reasons:
            cand.append((r["bag"], r["fill"], reasons))
    print("候选（偏移对照 ≥ %.2f×）：%d 个" % (a.factor, len(cand)))
    for b, f, rs in cand:
        print("   bag=%d fill=0x%02X: %s" % (b, f, "; ".join(rs)))
    # 穷尽判据
    complete = (len(bags) == 27) and (set(fills) == {0x00, 0xFF})
    print("")
    print("穷尽判据：覆盖 27 袋 × {0x00,0xFF} = %s · 全部 0x7F = %s · 无候选 = %s"
          % (complete, n_ok == len(acc), not cand))
    if complete and n_ok == len(acc) and not cand:
        print("⇒ ✅ 结论成立：**cfg 中不存在事件层/触觉触发字段**（E 面穷尽否定）")
    else:
        print("⇒ ⏳ 结论**不成立**：本轮不足以做穷尽否定（覆盖/结果码/候选 三项须全满足）")
    if a.md:
        lines = ["| idx | 袋 | 填充 | 结果码 | 接受 | p50 | p95 | max | 事件数 |", "|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            j = r["j1"]
            lines.append("| %s | %s | 0x%02X | `%s` | %s | %.6f | %.6f | %.6f | %s |" % (
                r["idx"], r["bag"], r["fill"], r.get("code") or "-", "✅" if r.get("accepted") else "❌",
                j["band_p50"], j["band_p95"], j["band_max"], json.dumps(j["counts"], ensure_ascii=False)))
        open(a.md, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
        print("已写表格 " + a.md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
