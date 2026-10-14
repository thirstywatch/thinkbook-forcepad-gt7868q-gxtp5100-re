#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lab__r65_bag2_probe.py -- 【bag 2 语义校验圈定】探针（2026-10-14 新增）

pass-1 实测：bag 2 数据全零 ⇒ `7E 00 03` (DATA_ERR) ⇒ bag 2 的内容被 IC 语义校验。
本脚本用**客观判据（结果码）**圈出"到底哪一个字节被校验"：
  ① 对照：原样写回（期望 7E 00 07 DATA_EQU）
  ② 整袋填充扫描：{0x01,0x02,0x7F,0x80,0xFF}（看哪些值合法）
  ③ **逐字节清零**：bag 2 的每个数据字节单独置 0，其余保持原值 ⇒ 触发 DATA_ERR 的就是被校验字节
  ④ 收尾：回写原 cfg（全程仅会话 RAM）

用法： python lab__r65_bag2_probe.py [--only fill|byte|all] [--commit]
"""
import os, sys, re, json, time, subprocess, argparse, datetime

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
R62 = os.path.join(ROOT, "tools", "hid", "lab__r62_cfg_legal_write.py")
PY_TOOLS = r"C:\\Users\\XIXINGLU\\.dsh\\dsh-runtimes\\dsh-primary-runtime\\dependencies\\python\\python.exe"
ENV = dict(os.environ); ENV["PYTHONIOENCODING"] = "utf-8"
BAG2_OFF, BAG2_END = 0x0D, 0x30          # bag 2：起点 0x0D，止点 0x30 ⇒ 数据区 0x0F..0x2D（31 B）
DATA_FROM, DATA_TO = BAG2_OFF + 2, BAG2_END - 2


def run_r62(args):
    p = subprocess.run([PY_TOOLS, R62] + args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=ROOT, env=ENV)
    out = (p.stdout or "") + (p.stderr or "")
    code = None
    for ln in out.splitlines():
        m = re.search(r"结果\s*=\s*([0-9A-Fa-f ]+)", ln)
        if m:
            code = m.group(1).strip()
    return code, out


def health():
    def rd(addr, n):
        p = subprocess.run([PY_TOOLS, os.path.join(ROOT, "tools", "hid", "gxmem.py"), "read", addr, str(n)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT, env=ENV)
        for ln in ((p.stdout or "") + (p.stderr or "")).splitlines():
            if "->" in ln:
                return ln.split("->", 1)[1].split()
        return []
    lv = rd("0x4000", 4); ch = rd("0x96F8", 4)
    ok = len(lv) >= 3 and lv[0] == "A7" and lv[1] == "E0" and lv[2] == "ED" and len(ch) >= 3 and ch[2] in ("1B", "11")
    return ok, "liveness=%s bag=%s" % (lv[:3], ch[2] if len(ch) >= 3 else "??")


def cls(code):
    if not code:
        return "无结果"
    c = code.replace(" ", "")
    return {"7F": "✅ 接受", "7E0007": "＝ 与当前相同", "7E0003": "🔴 DATA_ERR", "7E0002": "🔴 CHKSUM", "7E0001": "🔴 PKGS"}.get(c[:6], "? " + c)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="all", choices=["all", "fill", "byte"])
    ap.add_argument("--commit", action="store_true")
    a = ap.parse_args()
    out = os.path.join(ROOT, "data", "logs", "lab__bag2probe_%s.json" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    rows = []
    t0 = time.time()
    def probe(label, args, expect=None):
        if not a.commit:
            print("  [DRY] %-34s %s" % (label, " ".join(args)))
            return True
        code, raw = run_r62(args)
        ok, h = health()
        rows.append(dict(label=label, args=args, code=code, cls=cls(code), health=h, t=round(time.time() - t0, 1)))
        print("  %-34s → %-16s %s | %s" % (label, str(code), cls(code), h))
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(rows, fh, ensure_ascii=False, indent=1)
        if not ok:
            print("  ⚠️ 健康判据失败 ⇒ 中止并回写")
            return False
        return True
    print("=== bag 2 探针（数据区 0x%X..0x%X，%d 字节）===" % (DATA_FROM, DATA_TO - 1, DATA_TO - DATA_FROM))
    try:
        probe("对照：原样写回", ["--commit", "--cases", "A"])
        if a.only in ("all", "fill"):
            for f in (0x01, 0x02, 0x7F, 0x80, 0xFF):
                if not probe("整袋填充 0x%02X" % f, ["--commit", "--bag", "2", "--fill", "0x%02X" % f]):
                    break
        if a.only in ("all", "byte"):
            for off in range(DATA_FROM, DATA_TO):
                if not probe("单字节清零 0x%03X" % off, ["--commit", "--set-byte", "0x%X=0x00" % off]):
                    break
    finally:
        if a.commit:
            print("=== 收尾：回写原 cfg ===")
            code, _ = run_r62(["--commit", "--cases", "A"])
            ok, h = health()
            print("  回写结果码 %s · %s ⇒ %s" % (code, h, "正常" if ok else "异常"))
    hits = [r for r in rows if r["code"] and r["code"].replace(" ", "").startswith("7E0003")]
    print("")
    print("触发 DATA_ERR 的探针：%d 个" % len(hits))
    for r in hits:
        print("   " + r["label"])
    print("输出:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
