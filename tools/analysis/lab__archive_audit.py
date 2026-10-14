#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lab__archive_audit.py —— 档案一致性审计（离线、只读、可复现）

为什么需要：本项目有 6 处会写"口径数字"的入口文档（README / README.en / REPO-STRUCTURE /
START-HERE / docs/INDEX / 全书 §20.0+§20.10），多轮编辑后极易漂移（2026-10-14 实测漂了 27 处）。

检查两类东西：
  1) 度量口径：入库文件数 / MiB / 工作区文件数 / md 数 / 🔴 数 / 全书行数·KB / 脚本数
  2) 范围口径：登记表 B 范围 · 纪律条数 · 全书 §19 轮次范围

用法：
  python lab__archive_audit.py            # 只报告（有漂移则退出码 1）
  python lab__archive_audit.py --quiet    # 只打印结论
"""
import os, re, subprocess, sys

try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BOOK = os.path.join(ROOT, "docs", "00-软件逆向全书-芯片固件主机控制.md")
REG = os.path.join(ROOT, "docs", "08-findings", "00-矛盾与推翻登记表.md")
ENTRY = ["README.md", "README.en.md", "docs/REPO-STRUCTURE.md", "docs/00-START-HERE.md",
         "docs/INDEX.md", "docs/en/HANDBOOK-SUMMARY.en.md", BOOK]
SCRIPT_EXT = (".py", ".ps1", ".bat", ".js", ".mjs", ".c", ".h", ".cs", ".sh")


def walk():
    mds, allf = [], []
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d != ".git"]
        for f in fn:
            p = os.path.join(dp, f)
            allf.append(p)
            if f.endswith(".md"):
                mds.append(p)
    return mds, allf


def metrics():
    mds, allf = walk()
    # ⚠️ 必须 core.quotepath=false + -z：否则非 ASCII 路径会被 C 转义，导致体积严重少算
    raw = subprocess.run(["git", "-C", ROOT, "-c", "core.quotepath=false", "ls-files", "-z"],
                         capture_output=True).stdout.decode("utf-8", "replace")
    tracked = [x for x in raw.split("\0") if x.strip()]
    tb = sum(os.path.getsize(os.path.join(ROOT, t)) for t in tracked if os.path.exists(os.path.join(ROOT, t)))
    book = open(BOOK, encoding="utf-8").read()
    red = 0
    for f in mds:
        red += open(f, encoding="utf-8", errors="replace").read().count("🔴")
    return {
        "tracked": len(tracked), "mib": round(tb / 1048576, 2),
        "disk": len(allf), "md": len(mds), "red": red,
        "book_lines": book.count("\n"), "book_kb": round(os.path.getsize(BOOK) / 1024),
        "scripts": sum(1 for f in allf if f.endswith(SCRIPT_EXT)),
    }


def declared_ranges():
    reg = open(REG, encoding="utf-8").read()
    bs = [int(m) for m in re.findall(r"^### B(\d+)", reg, re.M)]
    book = open(BOOK, encoding="utf-8").read()
    secs = [int(m) for m in re.findall(r"^#{1,3} §19\.(\d+)", book, re.M)]
    disc = [int(m) for m in re.findall(r"\*\*第 1[–-](\d+) 条\*\*", book)]
    return max(bs) if bs else 0, max(secs) if secs else 0, max(disc) if disc else 0


def main():
    quiet = "--quiet" in sys.argv
    M = metrics()
    bmax, smax, dmax = declared_ranges()
    problems = []
    if not quiet:
        print("== 度量口径 ==")
        for k, v in M.items():
            print("   %-12s %s" % (k, v))
        print("== 实际范围 == 登记表 B1–B%d · 全书 §19.0–§19.%d · 纪律 1–%d" % (bmax, smax, dmax))
    tokens = {
        "入库文件数": [str(M["tracked"]), "{:,}".format(M["tracked"])],
        "MiB": ["%.2f MiB" % M["mib"]],
        "md 数": ["%d 份 md" % M["md"]],
        "🔴 数": ["{:,} 处".format(M["red"]), "**%d** 🔴" % M["red"]],
        "全书行数": ["{:,} 行".format(M["book_lines"])],
        "B 范围": ["B1–B%d" % bmax],
        "纪律": ["第 1–%d 条" % dmax],
        "轮次": ["§19.0–§19.%d" % smax],
    }
    # 只在【声明性上下文】里比对范围，避免历史叙述/子集表述的假阳性
    stale_patterns = [
        (r"(\d{3,4}) 个入库文件", lambda v: v == M["tracked"], r"规模|Size"),
        (r"\*\*(\d{3,4}) 份 md\*\*", lambda v: v == M["md"], r"规模|UpdateLog|更正标记"),
        (r"B 类已累计 B1[–-]B(\d+)", lambda v: v == bmax, r"."),
        (r"B1[–-]B(\d+).{0,12}已推翻", lambda v: v == bmax, r"."),
        (r"complete discipline set is (\d+) rules", lambda v: v == dmax, r"."),
        (r"完整纪律体系共 (\d+) 条", lambda v: v == dmax, r"."),
        (r"^\| \*\*纪律\*\* \| \*\*第 1[–-](\d+) 条", lambda v: v == dmax, r"."),
        (r"^\| 全书轮次 \| \*\*§19\.0[–-]§19\.(\d+)\*\*", lambda v: v == smax, r"."),
        (r"§19\.0[–-]§19\.(\d+) \+ \*\*第二十部", lambda v: v == smax, r"."),
        # 2026-10-14 扩充：覆盖 REPO-STRUCTURE §五 表与全书 §20.13.3 的口径行
        (r"文件总数（工作区，不含 \.git） \| \*\*(\d+)\*\*", lambda v: v == M["disk"], r"."),
        (r"git 跟踪 (\d+) 文件", lambda v: v == M["tracked"], r"."),
        (r"md (\d+)\*\* / 脚本", lambda v: v == M["md"], r"."),
        (r"脚本 \*\*(\d+)\*\*", lambda v: v == M["scripts"], r"."),
        (r"\*\*git 跟踪文件\*\* \| \*\*(\d+) 个", lambda v: v == M["tracked"], r"."),
        (r"更正标记 \*\*(\d+) 处\*\*", lambda v: v == M["red"], r"."),
        # 2026-10-14 扩充：全书行数 / KB（自指数字，最易漂）
        (r"\| 全书 \| \*\*([\d,]+) 行", lambda v: v == M["book_lines"], r"."),
        (r"\*\*([\d,]+) 行 / ~[\d.]+ MB\*\*", lambda v: v == M["book_lines"], r"."),
    ]

    for rel in ENTRY:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            continue
        for i, line in enumerate(open(p, encoding="utf-8", errors="replace"), 1):
            if re.search(r"历史快照|旧复印|2026-10-01|12,6\d\d|整理轮\*\*（文档层", line):
                continue
            for pat, ok, ctx in stale_patterns:
                if ctx != "." and not re.search(ctx, line):
                    continue
                m = re.search(pat, line)
                if m and not ok(int(m.group(1).replace(",", ""))):
                    problems.append("%s:%d  %s ≠ %s :: %s" % (rel, i, pat, m.group(1), line.strip()[:100]))
    if problems:
        print("\n❌ 发现 %d 处口径漂移：" % len(problems))
        for x in problems:
            print("   " + x)
        return 1
    print("\n✅ 口径一致（登记表 B1–B%d · 纪律 1–%d · §19.0–§19.%d · 入库 %d 文件 / %.2f MiB · md %d · 全书 %d 行）" % (bmax, dmax, smax, M["tracked"], M["mib"], M["md"], M["book_lines"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
