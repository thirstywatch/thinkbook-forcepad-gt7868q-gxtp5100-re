#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lab__dedup_check.py —— 【开工前查重】工具（2026-10-14 立规）

规则（纪律 177）：**任何新目标/新任务开工前，必须先在档案里查重。**

查三处：
  1) 文档正文（docs/ method/ gaps/ vendor-refs/ README*）
  2) 登记表 B1–B<n>（结论与推翻）
  3) 工具与日志（tools/ data/logs/）

用法：
  python lab__dedup_check.py 关键词1 [关键词2 ...]
  python lab__dedup_check.py --file tasks.txt     # 每行一个任务/关键词

输出：每个关键词的命中数、命中文件（前若干）、样例行 —— 命中多 ⇒ 很可能已做过。
"""
import os, re, sys

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIRS = ["docs", "method", "gaps", "vendor-refs", "tools", "data/logs", "reproduce"]
ROOTS = ["README.md", "README.en.md", "NOTICE.md", "CONTRIBUTING.md"]


def iter_files():
    for f in ROOTS:
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            yield p
    for d in DIRS:
        base = os.path.join(ROOT, d)
        for dp, dn, fn in os.walk(base):
            dn[:] = [x for x in dn if x != "__pycache__"]
            for f in fn:
                if f.lower().endswith((".md", ".txt", ".py", ".json", ".csv", ".ps1", ".c", ".h", ".asm")):
                    yield os.path.join(dp, f)


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    if args[0] == "--file":
        keys = [l.strip() for l in open(args[1], encoding="utf-8") if l.strip()]
    else:
        keys = args
    files = list(iter_files())
    print("扫描 %d 个文件（docs/method/gaps/vendor-refs/tools/data-logs/reproduce + 根 README）" % len(files))
    verdict = []
    for k in keys:
        try:
            rx = re.compile(re.escape(k), re.I)
        except re.error:
            rx = re.compile(k, re.I)
        hits = 0
        fhits = {}
        samples = []
        for p in files:
            try:
                t = open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            n = len(rx.findall(t))
            if n:
                hits += n
                fhits[os.path.relpath(p, ROOT)] = n
                if len(samples) < 2:
                    for i, line in enumerate(t.splitlines(), 1):
                        if rx.search(line):
                            samples.append("%s:%d %s" % (os.path.relpath(p, ROOT), i, line.strip()[:110]))
                            break
        top = sorted(fhits.items(), key=lambda x: -x[1])[:5]
        mark = "🔴 已做过?" if hits >= 3 else ("🟡 部分?" if hits else "🟢 未见")
        verdict.append((k, hits, mark))
        print("\n=== [%s] %s（命中 %d / %d 文件）===" % (mark, k, hits, len(fhits)))
        for f, n in top:
            print("   %-58s %d" % (f, n))
        for s in samples:
            print("   · " + s)
    print("\n===== 结论 =====")
    for k, hits, mark in verdict:
        print("   %-46s %s (%d)" % (k, mark, hits))
    return 0


if __name__ == "__main__":
    sys.exit(main())
