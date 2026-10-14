#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lab__gate.py -- 【四闸门一键体检】统一运行器（2026-10-14 新增）

以前每轮收尾要手动依次跑 4 个工具 + 2 个自测；本脚本把它们合成一条命令，
并给出**单一退出码**与总表（任一闸门红 ⇒ 退出 1）。

闸门清单：
  1 自测      lab__tools_selftest.py         （索引 9 + 查重 6 + 口径 4 = 19 项对照）
  2 索引/链接 lab__index_check.py
  3 悬挂引用  lab__ref_check.py
  4 口径      lab__archive_audit.py --quiet

用法：
  python lab__gate.py            # 全部（默认不含活体审计对照）
  python lab__gate.py --all      # 追加 lab__tools_selftest.py --live-audit（需工作区干净）
  python lab__gate.py --quick    # 只跑闸门 2/3/4（跳过自测）
"""
import os, sys, subprocess

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def run(label, script, args):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    p = subprocess.run([PY, os.path.join(HERE, script)] + args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    out = ((p.stdout or "") + (p.stderr or "")).strip()
    tail = out.splitlines()[-1] if out else ""
    ok = p.returncode == 0
    print("  [%s] %-22s %s" % ("PASS" if ok else "FAIL", label, tail[:110]))
    if not ok:
        for ln in out.splitlines()[-12:]:
            print("        | " + ln[:150])
    return ok


def main():
    args = sys.argv[1:]
    results = []
    print("== 四闸门一键体检 ==")
    if "--quick" not in args:
        sa = ["--live-audit"] if "--all" in args else []
        results.append(run("自测(19 项对照)", "lab__tools_selftest.py", sa))
    results.append(run("索引/链接", "lab__index_check.py", []))
    results.append(run("悬挂编号引用", "lab__ref_check.py", []))
    results.append(run("口径审计", "lab__archive_audit.py", ["--quiet"]))
    n_ok = sum(1 for x in results if x)
    print("\n总表：%d/%d 闸门通过 %s" % (n_ok, len(results), "✅ 可收工" if n_ok == len(results) else "❌ 有闸门红"))
    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
