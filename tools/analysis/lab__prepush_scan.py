#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lab__prepush_scan.py —— 推送前密钥/邮箱扫描器（2026-10-14 新增，纪律 187）

为什么需要它：2026-10-14 的清理发现 `gaps/GAPS.md` 里**残留过一个 API Token 的截断前缀**，
而一个**含完整 Token 的悬空 blob** 还留在本地对象库（该 blob 不可达 ⇒ 未推送，但很险）。
当时的常规扫描**漏掉了它**，原因是：① 只匹配"完整长密钥"、漏掉截断前缀；② **只按 UTF-8 解码**，
而该 blob 是 **UTF-16LE**。本工具把这两条都补上。

检查三层：
  ① 当前工作树（tracked 文件）
  ② 全历史 blob（`git cat-file --batch-all-objects`，含**不可达**对象）
  ③ 提交身份（author/committer email —— 这一层最容易被忽略）
编码：每个 blob 同时按 **UTF-8** 与 **UTF-16LE** 解码后匹配。

用法：
  python lab__prepush_scan.py --tree-only     # 快（秒级），适合放进日常闸门
  python lab__prepush_scan.py                 # 全量（含历史 + 不可达对象）
  python lab__prepush_scan.py --json out.json
"""
import os, re, sys, json, argparse, subprocess

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

# 完整密钥样式（>=16 位随机串）
FULL = [
    ("OpenAI/DeepSeek sk-", re.compile(r"sk-[A-Za-z0-9_-]{16,}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}")),
    ("Google AIza", re.compile(r"AIza[0-9A-Za-z_-]{30,}")),
    ("AWS AKIA", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Slack xox", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("私钥块", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("Bearer 长串", re.compile(r"Bearer\s+[A-Za-z0-9._-]{30,}")),
]
# 截断前缀（曾经漏掉的那一类）：sk- 后跟 4–15 位 + 省略号/…
PARTIAL = [
    ("密钥截断前缀", re.compile(r"sk-[A-Za-z0-9]{4,15}(?:…|\.\.\.)")),
]
PERSONAL_MAIL = re.compile(r"[\w.+-]+@(?:gmail|qq|163|126|outlook|hotmail|foxmail|icloud|sina|sohu|yahoo|protonmail|live|msn)\.[A-Za-z]{2,}", re.I)


def git(*a, **kw):
    return subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, **kw)


def scan_bytes(b: bytes):
    """返回 (完整命中, 截断命中, 个人邮箱命中)"""
    full, part, mail = [], [], []
    for enc in ("utf-8", "utf-16-le"):
        try:
            t = b.decode(enc, errors="ignore")
        except Exception:
            continue
        for name, rx in FULL:
            m = rx.search(t)
            if m:
                full.append("%s [%s]: %s" % (name, enc, m.group(0)[:24] + "…"))
        for name, rx in PARTIAL:
            m = rx.search(t)
            if m:
                part.append("%s [%s]: %s" % (name, enc, m.group(0)[:24]))
        for m in PERSONAL_MAIL.finditer(t):
            mail.append("%s [%s]" % (m.group(0).lower(), enc))
    return full, part, mail


def selftest():
    """★ 正负对照：每条控制独立计数（tot 动态），任一失败都会拉低分母 ⇒ 不能"静默通过"。"""
    ok = tot = 0
    fake = "sk-" + "A1b2C3d4E5f6G7h8I9j0K1l2"
    partial = "sk-6268\u2026"          # 真正的省略号字符
    controls = [
        ("完整密钥 UTF-8", fake.encode("utf-8"), "full"),
        ("完整密钥 UTF-16LE", fake.encode("utf-16-le"), "full"),
        ("截断前缀 UTF-8", partial.encode("utf-8"), "part"),
        ("截断前缀 UTF-16LE", partial.encode("utf-16-le"), "part"),
        ("个人邮箱", "someone@gmail.com".encode("utf-8"), "mail"),
        ("干净内容（负对照）", "这是一份干净的文件，只有普通中文与技术文本。".encode("utf-8"), "clean"),
    ]
    for name, data, kind in controls:
        tot += 1
        f, p, m = scan_bytes(data)
        got = {"full": bool(f), "part": bool(p), "mail": bool(m), "clean": not (f or p or m)}[kind]
        if got:
            ok += 1
        else:
            print("  SELFTEST FAIL: %s 未达预期" % name)
    return ok, tot

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree-only", action="store_true")
    ap.add_argument("--json", default=None)
    ap.add_argument("--limit", type=int, default=6000)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--allowlist", default=os.path.join(HERE, "prepush_allowlist.txt"))
    a = ap.parse_args()
    ok, tot = selftest()
    print("自测（正负对照）: %d/%d %s" % (ok, tot, "✅" if ok == tot else "❌"))
    report = {"full": [], "partial": [], "mail": [], "identity": []}
    # ① 当前树
    files = git("-c", "core.quotepath=false", "ls-files").stdout.decode("utf-8", "replace").split("\n")
    for rel in files:
        rel = rel.strip()
        if not rel:
            continue
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p) or os.path.getsize(p) > 8 * 1024 * 1024:
            continue
        with open(p, "rb") as fh:
            b = fh.read()
        f, part, mail = scan_bytes(b)
        for x in f:
            report["full"].append("tree %s :: %s" % (rel, x))
        for x in part:
            report["partial"].append("tree %s :: %s" % (rel, x))
        for x in mail:
            report["mail"].append("tree %s :: %s" % (rel, x))
    # ② 历史（含不可达对象）
    if not a.tree_only:
        out = git("cat-file", "--batch-all-objects", "--batch-check=%(objecttype) %(objectname)").stdout.decode("utf-8", "replace")
        blobs = [l.split(" ")[1] for l in out.split("\n") if l.startswith("blob ")]
        blobs = blobs[: a.limit]
        B = 200
        for i in range(0, len(blobs), B):
            chunk = blobs[i:i + B]
            r = git("cat-file", "--batch", input=("\n".join(chunk) + "\n").encode())
            data = r.stdout
            pos = 0
            while pos < len(data):
                nl = data.find(b"\n", pos)
                if nl < 0:
                    break
                head = data[pos:nl].decode("latin1")
                mm = re.match(r"^([0-9a-f]{40}) (\w+) (\d+)$", head)
                if not mm:
                    pos = nl + 1
                    continue
                size = int(mm.group(3))
                start = nl + 1
                end = min(start + size, len(data))
                f, part, mail = scan_bytes(data[start:end])
                for x in f:
                    report["full"].append("blob %s :: %s" % (mm.group(1)[:10], x))
                for x in part:
                    report["partial"].append("blob %s :: %s" % (mm.group(1)[:10], x))
                pos = end + 1
        print("已扫描历史 blob: %d" % len(blobs))
    # ③ 提交身份
    ids = git("log", "--all", "--format=%an <%ae>|%cn <%ce>").stdout.decode("utf-8", "replace")
    for x in sorted(set(l for l in ids.split("\n") if l.strip())):
        report["identity"].append(x)
        if PERSONAL_MAIL.search(x):
            report["mail"].append("identity :: " + x)
    # 豁免清单（只豁免已知且已处置的命中；新泄露不受影响）
    allow = []
    if a.allowlist and os.path.isfile(a.allowlist):
        for line in open(a.allowlist, encoding="utf-8"):
            line = line.split("#")[0].strip()
            if line:
                allow.append(line)
    # 汇总
    uniq = {k: sorted(set(v)) for k, v in report.items()}
    waived = []
    for key in ("full", "partial"):
        keep = []
        for x in uniq[key]:
            if any(w in x for w in allow):
                waived.append(x)
            else:
                keep.append(x)
        uniq[key] = keep
    if waived:
        print("已豁免（allowlist）: %d 处 —— 见 tools/analysis/prepush_allowlist.txt" % len(waived))
    print("")
    print("完整密钥命中: %d" % len(uniq["full"]))
    for x in uniq["full"][:20]:
        print("   🔴 " + x)
    print("截断前缀命中: %d" % len(uniq["partial"]))
    if not a.quiet:
        for x in uniq["partial"][:20]:
            print("   ⚠️ " + x)
    print("个人邮箱命中: %d（注意：厂商源码/邮件列表里的第三方邮箱属正常，需人工确认是否为你本人）" % len(uniq["mail"]))
    print("提交身份: " + " | ".join(uniq["identity"]))
    if a.json:
        with open(a.json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(uniq, fh, ensure_ascii=False, indent=1)
    bad = len(uniq["full"]) + len(uniq["partial"])
    print("")
    print(("❌ 有 %d 处需要处理后才能推送" % bad) if bad else "✅ 未发现密钥（可推送）")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
