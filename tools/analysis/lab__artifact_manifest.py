#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lab__artifact_manifest.py -- 【证据 sha256 清单】（2026-10-14 新增）

本项目的核心资产之一是**测量证据**（`data/reference/**` 的 .bin/.json，以及关键日志）。
但没有一份"清单+校验"机制：文件被误改、丢失、或换机恢复后不一致，都不会有人发现。

本脚本：
  generate  扫描 `data/reference/**`，写 `data/reference/SHA256SUMS.txt`（sha256 + 字节数 + 路径）
  verify    重算并与清单比对，报 缺失 / 多出 / 内容变化（退出码 1 = 有差异）

清单格式（每行）： <sha256>  <size>  <相对仓库根的路径>

用法：
  python lab__artifact_manifest.py generate
  python lab__artifact_manifest.py verify
"""
import os, sys, hashlib

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TARGET = "data/reference"
MANIFEST = os.path.join(ROOT, TARGET, "SHA256SUMS.txt")


def sha256(fp):
    h = hashlib.sha256()
    with open(fp, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan():
    base = os.path.join(ROOT, TARGET)
    out = {}
    for dp, dn, fn in os.walk(base):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for f in fn:
            if f == "SHA256SUMS.txt":
                continue
            fp = os.path.join(dp, f)
            out[os.path.relpath(fp, ROOT).replace("\\", "/")] = (os.path.getsize(fp), sha256(fp))
    return out


def do_generate():
    cur = scan()
    with open(MANIFEST, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# 证据 sha256 清单（lab__artifact_manifest.py generate 生成）\n")
        fh.write("# 格式: <sha256>  <size>  <path>\n")
        for p in sorted(cur):
            sz, h = cur[p]
            fh.write("%s  %d  %s\n" % (h, sz, p))
    print("已写 %s：%d 个文件，合计 %d B" % (os.path.relpath(MANIFEST, ROOT), len(cur), sum(v[0] for v in cur.values())))
    return 0


def read_manifest():
    old = {}
    if not os.path.exists(MANIFEST):
        return old
    for line in open(MANIFEST, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 2)
        if len(parts) == 3:
            old[parts[2]] = (int(parts[1]), parts[0])
    return old


def do_verify():
    old = read_manifest()
    if not old:
        print("❌ 清单不存在：先跑 generate")
        return 1
    cur = scan()
    missing = sorted(set(old) - set(cur))
    added = sorted(set(cur) - set(old))
    changed = sorted(p for p in (set(old) & set(cur)) if old[p][1] != cur[p][1])
    print("清单 %d · 实况 %d | 缺失 %d · 多出 %d · 变化 %d" % (len(old), len(cur), len(missing), len(added), len(changed)))
    for p in missing[:10]:
        print("   🔴 缺失: " + p)
    for p in changed[:10]:
        print("   🔴 变化: %s  (%s -> %s)" % (p, old[p][1][:12], cur[p][1][:12]))
    for p in added[:10]:
        print("   🟡 多出(未入清单): " + p)
    bad = len(missing) + len(changed)
    print("\n" + ("✅ 证据与清单一致" if bad == 0 else "❌ 证据有 %d 处不一致（新增项请跑 generate 收录）" % bad))
    return 1 if bad else 0


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if cmd == "generate":
        return do_generate()
    if cmd == "verify":
        return do_verify()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
