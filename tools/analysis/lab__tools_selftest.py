#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lab__tools_selftest.py -- 【谁来审计审计者】两个完整性闸门的正/负对照自测（2026-10-14 新增）

为什么需要它：本项目每轮都以「✅ 口径一致 / ✅ 索引一致」作为收工判据；
但【判据本身没被标定过】——如果闸门失灵，✅ 就是空的。本脚本用【阳性对照 + 阴性对照】标定它们：

  第一部分 lab__index_check.py：在临时树里造 9 种情形，逐条断言它该报/不该报
    clean / 孤儿 / 幽灵 / 计数漂移 / 大小漂移 / 重复行 / 失效链接 /
    ★ 反斜杠行名（应【不】误报 —— 2026-10-14 我在此踩过坑）/ --fix 幂等收敛
  第二部分 lab__archive_audit.py：在真仓库上做一次【注入漂移 -> 应报 -> 还原 -> 应过】的活体对照
    （默认跳过；用 --live-audit 打开。注入前备份 + sha256 校验还原）

用法：
  python lab__tools_selftest.py                # 只跑索引闸门对照（零风险）
  python lab__tools_selftest.py --live-audit   # 追加口径闸门活体对照
退出码：0 = 全部对照通过；1 = 有对照失败（或注入未还原）
"""
import os, sys, shutil, tempfile, subprocess, hashlib

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL_INDEX = os.path.join(HERE, "lab__index_check.py")
TOOL_AUDIT = os.path.join(HERE, "lab__archive_audit.py")
PY = sys.executable
PASS, FAIL = [], []


def note(ok, name, extra="", extra_out=""):
    (PASS if ok else FAIL).append(name)
    print(("  [PASS] " if ok else "  [FAIL] ") + name + (("  " + extra) if extra else ""))


def build_fixture(subdir=False):
    root = tempfile.mkdtemp(prefix="ixfix_")
    os.makedirs(os.path.join(root, "tools", "analysis"))
    os.makedirs(os.path.join(root, "docs", "01-overview"))
    shutil.copy(TOOL_INDEX, os.path.join(root, "tools", "analysis", "lab__index_check.py"))
    if subdir:
        os.makedirs(os.path.join(root, "docs", "01-overview", "sub"))
        open(os.path.join(root, "docs", "01-overview", "sub", "a.md"), "w", encoding="utf-8").write("A" * 1200)
        rows = ["| `sub\\a.md` | %d KB |" % max(1, round(len("A" * 1200) / 1024))]
        cnt = 1
    else:
        open(os.path.join(root, "docs", "01-overview", "a.md"), "w", encoding="utf-8").write("A" * 1200)
        open(os.path.join(root, "docs", "01-overview", "b.md"), "w", encoding="utf-8").write("B" * 1200)
        rows = ["| `a.md` | %d KB |" % max(1, round(len("A" * 1200) / 1024)), "| `b.md` | %d KB |" % max(1, round(len("B" * 1200) / 1024))]
        cnt = 2
    open(os.path.join(root, "docs", "INDEX.md"), "w", encoding="utf-8").write(
        "# 文档索引\n\n## `01-overview/`（%d 个）\n\n| 文件 | 大小 |\n|---|---|\n%s\n" % (cnt, "\n".join(rows)))
    open(os.path.join(root, "tools", "INDEX.md"), "w", encoding="utf-8").write(
        "# 工具索引\n\n## `tools/analysis/`（2 个）\n\n| 脚本 | 大小 |\n|---|---|\n| `lab__index_check.py` | %d KB |\n| `x.py` | %d KB |\n" % (max(1, round(os.path.getsize(os.path.join(root, "tools", "analysis", "lab__index_check.py")) / 1024)), max(1, round(len("#" + "x" * 1200) / 1024))))
    open(os.path.join(root, "tools", "analysis", "x.py"), "w", encoding="utf-8").write("#" + "x" * 1200)
    return root


def run_check(root):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    p = subprocess.run([PY, os.path.join(root, "tools", "analysis", "lab__index_check.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def mutate(root, kind):
    idx = os.path.join(root, "docs", "INDEX.md")
    t = open(idx, encoding="utf-8").read()
    sizes = {"a": "1 KB", "b": "1 KB"}
    if kind == "orphan":
        t = "\n".join([l for l in t.split("\n") if not l.startswith("| `a.md` |")])
    elif kind == "ghost":
        lines = t.split("\n")
        last = max(i for i, l in enumerate(lines) if l.startswith("| `"))
        lines.insert(last + 1, "| `zz.md` | 1 KB |")
        t = "\n".join(lines)
    elif kind == "count":
        t = t.replace("（2 个）", "（3 个）")
    elif kind == "size":
        t = "\n".join(["| `a.md` | 99 KB |" if l.startswith("| `a.md` |") else l for l in t.split("\n")])
    elif kind == "dup":
        b = [l for l in t.split("\n") if l.startswith("| `b.md` |")][0]
        t = t.replace(b, b + "\n" + b)
    elif kind == "link":
        open(os.path.join(root, "docs", "01-overview", "a.md"), "a", encoding="utf-8").write("\n[x](nope.md)\n")
    open(idx, "w", encoding="utf-8", newline="\n").write(t)


def part1():
    print("== 第一部分：lab__index_check.py 正/负对照（临时树）==")
    for kind, want in [("clean", 0), ("orphan", 1), ("ghost", 1), ("count", 1), ("size", 1), ("dup", 1), ("link", 1)]:
        root = build_fixture()
        if kind != "clean":
            mutate(root, kind)
        rc, out = run_check(root)
        hit = {"clean": "✅", "orphan": "孤儿", "ghost": "幽灵", "count": "计数", "size": "大小", "dup": "重复行", "link": "失效"}[kind]
        ok = (rc == want) and (hit in out)
        note(ok, "case=%s 期望 rc=%d 关键词=%s" % (kind, want, hit), "实际 rc=%d" % rc, out)
        shutil.rmtree(root, ignore_errors=True)
    # 反斜杠行名：应【不】误报
    root = build_fixture(subdir=True)
    rc, out = run_check(root)
    note(rc == 0, "反斜杠行名不误报（回归：2026-10-14 曾误报 45 处）", "实际 rc=%d" % rc, out)
    shutil.rmtree(root, ignore_errors=True)
    # --fix 幂等
    root = build_fixture()
    mutate(root, "orphan")
    subprocess.run([PY, os.path.join(root, "tools", "analysis", "lab__index_check.py"), "--fix"], capture_output=True)
    rc, out = run_check(root)
    note(rc == 0, "--fix 收敛后复检通过（幂等）", "实际 rc=%d" % rc)
    shutil.rmtree(root, ignore_errors=True)


def part2():
    print("== 第二部分：lab__archive_audit.py 活体对照（注入 -> 应报 -> 还原 -> 应过）==")
    repo = os.path.dirname(os.path.dirname(HERE))
    readme = os.path.join(repo, "README.md")
    if not os.path.exists(TOOL_AUDIT) or not os.path.exists(readme):
        note(False, "活体对照前置文件缺失")
        return
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
    if st:
        print("  [SKIP] 工作区有未提交文件（共 %d 项）—— audit 会把未提交文件计入口径，故先跳过活体对照" % len(st.splitlines()))
        return
    original = open(readme, "rb").read()
    h0 = hashlib.sha256(original).hexdigest()
    try:
        env2 = dict(os.environ); env2["PYTHONIOENCODING"] = "utf-8"
        p0 = subprocess.run([PY, TOOL_AUDIT, "--quiet"], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=repo, env=env2)
        if p0.returncode != 0:
            print("  [SKIP] 基线未通过（仓库当前存在真实口径漂移）—— 活体对照要求绿色基线；请先跑 archive_audit 修好再试")
            print("         " + (p0.stdout or "").strip().splitlines()[-1] if (p0.stdout or "").strip() else "")
            return
        note(True, "基线：真仓库通过（绿色基线）", "rc=0")
        mut = original.replace("B1–B65".encode("utf-8"), "B1–B99".encode("utf-8"))
        if mut == original:
            note(False, "注入点未找到（README 里没有 B1–B65）")
        else:
            open(readme, "wb").write(mut)
            p1 = subprocess.run([PY, TOOL_AUDIT, "--quiet"], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=repo, env=env2)
            out = (p1.stdout or "") + (p1.stderr or "")
            note(p1.returncode != 0 and "B1" in out, "阳性对照：注入 B1–B99 应被判漂移", "rc=%d" % p1.returncode)
    finally:
        open(readme, "wb").write(original)
    h1 = hashlib.sha256(open(readme, "rb").read()).hexdigest()
    note(h0 == h1, "还原校验：sha256 与注入前一致", h1[:16])
    p2 = subprocess.run([PY, TOOL_AUDIT, "--quiet"], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=repo, env=env2)
    note(p2.returncode == 0, "还原后：真仓库重新通过", "rc=%d" % p2.returncode)


def main():
    part1()
    if "--live-audit" in sys.argv:
        part2()
    else:
        print("== 第二部分跳过（用 --live-audit 打开活体对照）==")
    print("\n对照结果：通过 %d / 失败 %d" % (len(PASS), len(FAIL)))
    if FAIL:
        print("失败项：" + "; ".join(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
