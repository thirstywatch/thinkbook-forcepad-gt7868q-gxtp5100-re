#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lab__index_check.py -- 索引一致性检查 / 修复（2026-10-14 新增）

检查 docs/INDEX.md 与 tools/INDEX.md 是否与磁盘一致：孤儿 / 幽灵 / 计数 / 大小 / 重复 / 链接。

索引收录规则（checker 与 --fix 共用，写在索引前言里）：
  docs/  : 递归收录全部 .md（含 99-archived/old-line/），不收录 INDEX.md 自身
  tools/ : 只收录【脚本】扩展名 py/ps1/cs/bat/cmd/sh/js/mjs/c/h/asm，排除 *.bak* 与 __pycache__

用法：
  python lab__index_check.py            # 只检查（退出码 1 = 有漂移）
  python lab__index_check.py --fix      # 就地修复：更新计数/大小、补齐缺行（保留手写注释与行序）
  python lab__index_check.py --docs-only | --tools-only
"""
import os, re, sys

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SEC_RE = re.compile(r"^##\s+`?([^`（(]+?)/?`?\s*[（(](\d+)\s*个[）)]")
ROW_RE = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*([^|]*?)\s*\|")
ROOT_SEC = "主档案"
SCRIPT_EXT = (".py", ".ps1", ".cs", ".bat", ".cmd", ".sh", ".js", ".mjs", ".c", ".h", ".asm")


def excluded(name):
    return ".bak" in name or name.endswith(".pyc") or name.startswith("_") and name.endswith(".txt")


def walk(base, mode):
    out = []
    for dp, dn, fn in os.walk(base):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for f in fn:
            if excluded(f):
                continue
            if mode == "docs":
                if not f.endswith(".md"):
                    continue
            else:
                if not f.lower().endswith(SCRIPT_EXT):
                    continue
            out.append(os.path.relpath(os.path.join(dp, f), base).replace("\\", "/"))
    return out


def size_txt(fp, mode):
    n = os.path.getsize(fp)
    if mode == "tools" and n < 1024:
        return "%d B" % n
    return "%d KB" % round(n / 1024.0)


def parse_index(idx_path):
    lines = open(idx_path, encoding="utf-8", errors="replace").read().split("\n")
    secs = []
    starts = [i for i, l in enumerate(lines) if l.startswith("## ")]
    for k, i in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(lines)
        head = lines[i]
        m = SEC_RE.match(head)
        if m:
            dirname = m.group(1).strip().split("/")[-1]
            declared = int(m.group(2))
        elif ROOT_SEC in head:
            dirname, declared = "", None
        else:
            continue
        rows = []
        for j in range(i + 1, end):
            rm = ROW_RE.match(lines[j])
            if rm:
                rows.append((j, rm.group(1).strip().replace(chr(92), "/"), rm.group(2).strip()))
        secs.append({"head_i": i, "end": end, "dir": dirname, "declared": declared, "rows": rows})
    return lines, secs


def actual_for(base_dir, sec_dir, mode):
    files = walk(base_dir, mode)
    if sec_dir == "":
        return [p for p in files if "/" not in p]
    # 段头可能写 "tools/hid"，实际目录名取末段
    return [p for p in files if p.startswith(sec_dir + "/")]


def check_one(kind, base, mode, fix):
    base_dir = os.path.join(ROOT, base)
    idx_path = os.path.join(base_dir, "INDEX.md")
    lines, secs = parse_index(idx_path)
    lines = list(lines)
    declared_all = set()
    for s in secs:
        for (_, name, _sz) in s["rows"]:
            declared_all.add((s["dir"], name))
    actual = [p for p in walk(base_dir, mode) if p != "INDEX.md"]
    problems = {"orphan": [], "ghost": [], "count": [], "size": [], "dup": []}
    DELETE = "\x00DEL"
    for s in secs:
        seen = set()
        for (j, name, _sz) in s["rows"]:
            if name in seen:
                problems["dup"].append(name)
                if fix:
                    lines[j] = DELETE
                continue
            seen.add(name)
            if chr(92) in lines[j]:
                if fix:
                    lines[j] = lines[j].replace(chr(92), "/")
    decl_paths = set()
    for (sd, nm2) in declared_all:
        decl_paths.add(((sd + "/" + nm2) if sd else nm2).lstrip("/"))
    for p in actual:
        if p not in decl_paths:
            problems["orphan"].append(p)
    inserts = {}
    for s in secs:
        real = actual_for(base_dir, s["dir"], mode)
        names = set(r[1].rsplit("/", 1)[-1] for r in s["rows"])
        for (j, name, sz) in s["rows"]:
            rel = (s["dir"] + "/" + name) if s["dir"] else name
            rel = rel.lstrip("/")
            fp = os.path.join(base_dir, rel)
            if not os.path.exists(fp):
                # 幽灵行：若同基名文件存在于本段子目录中，视为【错前缀重复行】-> 可删
                base_name = name.rsplit("/", 1)[-1]
                sib = [q for q in actual_for(base_dir, s["dir"], mode) if q.rsplit("/", 1)[-1] == base_name]
                if sib:
                    problems["dup"].append(rel + "  (错前缀重复, 正确路径 " + sib[0] + ")")
                    if fix:
                        lines[j] = DELETE
                    continue
                problems["ghost"].append(rel)
                continue
            want = size_txt(fp, mode)
            if want != sz:
                problems["size"].append((rel, sz, want))
                if fix:
                    lines[j] = re.sub(r"(\|\s*`" + re.escape(name) + r"`\s*\|)\s*[^|]*?\s*(\|)", r"\1 " + want + r" \2", lines[j])
        missing = [p for p in real if p.rsplit("/", 1)[-1] not in names]
        if missing:
            inserts[s["head_i"]] = sorted(missing)
        if s["declared"] is not None and s["declared"] != len(real):
            problems["count"].append((s["dir"] or "(根)", s["declared"], len(real)))
            if fix:
                newn = len(real)
                lines[s["head_i"]] = re.sub(r"（\d+ 个）", "（%d 个）" % newn, lines[s["head_i"]])
    if fix and inserts:
        off = 0
        for head_i in sorted(inserts):
            s = [x for x in secs if x["head_i"] == head_i][0]
            body = lines[head_i + off:s["end"] + off]
            last_row = 0
            for k, l in enumerate(body):
                if ROW_RE.match(l):
                    last_row = k
            rows_new = []
            for p in inserts[head_i]:
                nm = p[len(s["dir"]) + 1:] if s["dir"] and p.startswith(s["dir"] + "/") else p
                rows_new.append("| `" + nm + "` | " + size_txt(os.path.join(base_dir, p), mode) + " |")
            if last_row == 0:
                body = body[:2] + rows_new + body[2:]
                add = len(rows_new)
            else:
                body = body[:last_row + 1] + rows_new + body[last_row + 1:]
                add = len(rows_new)
            lines = lines[:head_i + off] + body + lines[s["end"] + off:]
            off += add
            # 计数重算
            mm = SEC_RE.match(lines[head_i + (0 if off == add else 0)])
    if fix:
        lines = [l for l in lines if l != DELETE]
    total = sum(len(v) for v in problems.values())
    print("[%s] 实况 %d · 索引 %d 条 | 孤儿 %d · 幽灵 %d · 计数 %d · 大小 %d" % (kind, len(actual), len(declared_all), len(problems["orphan"]), len(problems["ghost"]), len(problems["count"]), len(problems["size"])))
    for d in problems["dup"][:10]:
        print("   🔴 重复行: " + d)
    for p in problems["orphan"][:10]:
        print("   🔴 孤儿: " + p)
    for t in problems["count"][:10]:
        print("   🔴 计数: %s 索引 %s -> 实际 %s" % t)
    for t in problems["size"][:10]:
        print("   🟡 大小: %s %s -> %s" % t)
    if fix:
        open(idx_path, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
        print("   ✍️ 已写回 " + idx_path)
    return total


def links_check():
    bad = 0
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in (".git", "__pycache__", "node_modules")]
        for f in fn:
            if not f.endswith(".md"):
                continue
            fp = os.path.join(dp, f)
            t = open(fp, encoding="utf-8", errors="replace").read()
            for m in re.finditer(r"\[[^\]]*\]\(([^)\s]+)\)", t):
                u = m.group(1)
                if u.startswith(("http:", "https:", "mailto:", "#")):
                    continue
                u = u.split("#")[0]
                if u and not os.path.exists(os.path.normpath(os.path.join(dp, u))):
                    bad += 1
    print("[链接] 失效 %d" % bad)
    return bad


def main():
    args = sys.argv[1:]
    fix = "--fix" in args
    bad = 0
    if "--tools-only" not in args:
        bad += check_one("docs", "docs", "docs", fix)
    if "--docs-only" not in args:
        bad += check_one("tools", "tools", "tools", fix)
    bad += links_check()
    print("\n" + ("✅ 索引/链接一致" if bad == 0 else "❌ 仍有 %d 处漂移" % bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
