#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lab__ref_check.py -- 【悬挂引用】校验器（2026-10-14 新增；纪律 179 的自我标定内置）

问题：本项目有 278 份文档、3000+ 处交叉引用（`§19.x` / 登记表 `B<n>` / `纪律 <n>`）。
文件链接由 lab__index_check.py 管；但【编号引用】没人管 —— 若引用一个不存在的章节号，
读者会找不到东西（而链接检查看不见它）。

做法：先从档案里算出三个"上限"，再扫全文找越界引用：
  maxSec  = 全书里最大的 `§19.<N>` 标题号
  maxB    = 登记表里最大的 `### B<N>` 条号
  maxDisc = 全书/README 里声明的 `第 1–<N> 条` 中的 N

用法：
  python lab__ref_check.py                # 全库校验（退出码 1 = 有悬挂引用）
  python lab__ref_check.py --selftest     # 3 项自对照（阳性/阴性/上限推导）
  python lab__ref_check.py --ignore F1,F2 # 排除已知"故意越界"的夹具文档
"""
import os, re, sys

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BOOK = "docs/00-软件逆向全书-芯片固件主机控制.md"
REG = "docs/08-findings/00-矛盾与推翻登记表.md"
# 本文件自身与自测文档会故意写出越界编号（夹具），默认排除
DEFAULT_IGNORE = ("lab__ref_check.py", "lab__tools_selftest.py", "审计闸门自测")
SEC_RE = re.compile(r"§19\.(\d+)")
B_RE = re.compile(r"(?<![0-9A-Za-z_\-])B(\d{1,3})(?![0-9A-Fa-f_\-])")
DISC_RE = re.compile(r"纪律\s*(\d{1,3})")
RANGE_RE = re.compile(r"第\s*1\s*[–\-]\s*(\d{1,3})\s*条")


def read(rel):
    p = os.path.join(ROOT, rel)
    return open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else ""


def limits():
    book = read(BOOK)
    secs = [int(m.group(1)) for m in re.finditer(r"^#{1,4}\s*§19\.(\d+)", book, re.M)]
    disc = [int(m.group(1)) for m in RANGE_RE.finditer(book)] + [int(m.group(1)) for m in RANGE_RE.finditer(read("README.md"))]
    reg = read(REG)
    bs = [int(m.group(1)) for m in re.finditer(r"^###\s*B(\d+)", reg, re.M)]
    return (max(secs) if secs else 0), (max(bs) if bs else 0), (max(disc) if disc else 0)


def scan(ignore):
    max_sec, max_b, max_disc = limits()
    print("上限推导：§19.<%d> · B<%d> · 纪律<%d>" % (max_sec, max_b, max_disc))
    hits = {"sec": [], "b": [], "disc": []}
    for dp, dn, fn in os.walk(os.path.join(ROOT, "docs")):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for f in fn:
            if not f.endswith(".md"):
                continue
            fp = os.path.join(dp, f)
            rel = os.path.relpath(fp, ROOT)
            if any(x in rel for x in ignore):
                continue
            txt = open(fp, encoding="utf-8", errors="replace").read()
            txt = re.sub(r"```.*?```", " ", txt, flags=re.S)   # 跳过代码块
            for i, line in enumerate(txt.splitlines(), 1):
                for m in SEC_RE.finditer(line):
                    if int(m.group(1)) > max_sec:
                        hits["sec"].append("%s:%d %s" % (rel, i, m.group(0)))
                for m in B_RE.finditer(line):
                    if int(m.group(1)) > max_b:
                        hits["b"].append("%s:%d %s" % (rel, i, m.group(0)))
                for m in DISC_RE.finditer(line):
                    if int(m.group(1)) > max_disc:
                        hits["disc"].append("%s:%d %s" % (rel, i, m.group(0)))
    for k, name in (("sec", "§19.x 越界"), ("b", "B<n> 越界"), ("disc", "纪律 n 越界")):
        print("  %-14s %d" % (name, len(hits[k])))
        for s in hits[k][:12]:
            print("      " + s)
    return sum(len(v) for v in hits.values())


def selftest():
    import tempfile, subprocess, shutil
    print("== lab__ref_check.py 自对照（临时树）==")
    bad = 0
    root = tempfile.mkdtemp(prefix="reffix_")
    os.makedirs(os.path.join(root, "docs", "08-findings"))
    os.makedirs(os.path.join(root, "tools", "analysis"))
    shutil.copy(os.path.abspath(__file__), os.path.join(root, "tools", "analysis", "lab__ref_check.py"))
    book = "# §19.0\n# §19.5\n| 纪律 | **第 1–9 条** |\n"
    open(os.path.join(root, "docs", "00-软件逆向全书-芯片固件主机控制.md"), "w", encoding="utf-8").write(book)
    open(os.path.join(root, "docs", "08-findings", "00-矛盾与推翻登记表.md"), "w", encoding="utf-8").write("### B1\n### B7\n")
    open(os.path.join(root, "README.md"), "w", encoding="utf-8").write("x\n")
    # 阴性：引用都在范围内
    open(os.path.join(root, "docs", "ok.md"), "w", encoding="utf-8").write("见 §19.5 与 B7，纪律 9\n")
    # 阳性：三处越界
    open(os.path.join(root, "docs", "bad.md"), "w", encoding="utf-8").write("见 §19.99 与 B99，纪律 200\n")
    env = dict(os.environ); env["PYTHONIOENCODING"] = "utf-8"
    for f, want in (("ok.md", 0), ("bad.md", 3)):
        for other in ("ok.md", "bad.md"):
            q = os.path.join(root, "docs", other)
            if os.path.exists(q):
                os.remove(q)
        open(os.path.join(root, "docs", f), "w", encoding="utf-8").write(
            "见 §19.5 与 B7，纪律 9\n" if f == "ok.md" else "见 §19.99 与 B99，纪律 200\n")
        p = subprocess.run([sys.executable, os.path.join(root, "tools", "analysis", "lab__ref_check.py")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=root)
        got = sum(int(x) for x in re.findall(r"(?:越界)\s+(\d+)", p.stdout or ""))
        ok = got == want
        print(("  [PASS] " if ok else "  [FAIL] ") + "%s 期望越界 %d，实际 %d" % (f, want, got))
        bad += 0 if ok else 1
    shutil.rmtree(root, ignore_errors=True)
    print("对照结果：" + ("全部通过" if bad == 0 else "%d 项失败" % bad))
    return bad


def main():
    if "--selftest" in sys.argv:
        return 1 if selftest() else 0
    ignore = list(DEFAULT_IGNORE)
    if "--ignore" in sys.argv:
        ignore += sys.argv[sys.argv.index("--ignore") + 1].split(",")
    n = scan(ignore)
    print("\n" + ("✅ 无悬挂编号引用" if n == 0 else "❌ 发现 %d 处越界引用（见上；可能是历史/外部编号，需人工判定）" % n))
    return 0 if n == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
