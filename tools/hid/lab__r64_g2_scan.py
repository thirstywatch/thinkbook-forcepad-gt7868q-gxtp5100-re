#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lab__r64_g2_scan.py —— G2 E 面逐袋扫描**驱动器**（需 sounddevice 解释器）

对每个 (袋, 填充)：① 走官方 cfg 会话写 0x96F8（调 lab__r62 --commit --bag N --fill X）
                  ② 立即录 `--window` 秒音频，用 J1（180–220 Hz 带内能量）数出"震动事件"
                  ③ 记结果码 + J1 指标；每轮做健康签名检查，异常即中止

只写会话 RAM（0x7D 后 IC 从 flash 重载）⇒ 易失。所有行增量写盘，崩了也不丢。

用法：
  python lab__r64_g2_scan.py --bags 1-27 --fills 00,ff --window 8 --tag g2scan
  python lab__r64_g2_scan.py --bags 1-3  --fills 00 --window 6 --tag pilot   # 小样先跑
"""
import os, sys, re, time, json, subprocess, argparse, datetime

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
R62 = os.path.join(ROOT, "tools", "hid", "lab__r62_cfg_legal_write.py")
PY = sys.executable          # 本驱动器（音频）用
PY_TOOLS = r"C:\\Users\\XIXINGLU\\.dsh\\dsh-runtimes\\dsh-primary-runtime\\dependencies\\python\\python.exe"   # ★ 设备工具必须用这个（3.12；3.13 下 HID 读回垃圾）
SR = 48000
LRA_LO, LRA_HI = 180.0, 220.0
ENV = dict(os.environ); ENV["PYTHONIOENCODING"] = "utf-8"   # ★ 子进程统一 UTF-8（否则中文行变乱码，结果码解析失败）
BASE_RMS = 0.000049      # 2026-10-14 本底 p95（vib_probe baseline）
EVENT_MULT = 3.0         # 事件判据：带内 RMS > 本底 p95 × 3
DEV = 5                  # 输入设备（可被 --dev 覆盖）
THR = None               # 自适应阈值（标定后填）


def parse_bags(s):
    out = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def write_bag(bag, fill):
    p = subprocess.run([PY_TOOLS, R62, "--commit", "--bag", str(bag), "--fill", "0x%02X" % fill],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT, env=ENV)
    out = (p.stdout or "") + (p.stderr or "")
    code = None
    for ln in out.splitlines():
        mm = re.search(r"结果\s*=\s*([0-9A-Fa-f ]+)", ln)
        if mm:
            code = mm.group(1).strip()
    ok = bool(code) and code.startswith("7F")
    return code, ok, out


def record_and_analyze(secs):
    import numpy as np
    import sounddevice as sd
    x = sd.rec(int(secs * SR), samplerate=SR, channels=1, dtype="float32", device=DEV)
    sd.wait()
    x = x[:, 0]
    win = 1024
    n = len(x) // win
    rms = np.sqrt(np.mean((x[:n * win].reshape(n, win)) ** 2, axis=1) + 1e-20)
    # 带内能量：对每帧做 FFT，取 180–220 Hz
    band = []
    f = np.fft.rfftfreq(win, 1.0 / SR)
    m = (f >= LRA_LO) & (f <= LRA_HI)
    for k in range(n):
        X = np.abs(np.fft.rfft(x[k * win:(k + 1) * win] * np.hanning(win)))
        band.append(float(np.sqrt(np.mean(X[m] ** 2))))
    band = np.array(band)
    thr = THR if THR else (BASE_RMS * EVENT_MULT)
    above = band > thr
    runs, cur = [], 0
    for v in above:
        if v:
            cur += 1
        elif cur:
            runs.append(cur); cur = 0
    if cur:
        runs.append(cur)
    frame_ms = win * 1000.0 / SR
    cnt = {}
    for th in (0.0005, 0.001, 0.002, 0.004):
        c, cur2 = 0, 0
        for v in band:
            if v > th:
                cur2 += 1
            elif cur2:
                c += 1; cur2 = 0
        if cur2:
            c += 1
        cnt["%.4f" % th] = c
    return dict(frames=n, band_p50=float(np.percentile(band, 50)), band_p95=float(np.percentile(band, 95)),
                band_max=float(band.max()), thr=thr, events=len(runs),
                counts=cnt, dur_ms=[round(r * frame_ms, 1) for r in runs])


def _rd(addr, n):
    p = subprocess.run([PY_TOOLS, os.path.join(ROOT, "tools", "hid", "gxmem.py"), "read", addr, str(n)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT, env=ENV)
    out = (p.stdout or "") + (p.stderr or "")
    for ln in out.splitlines():
        if "->" in ln:
            return ln.split("->", 1)[1].strip()
    return ""


def health():
    """健康判据 = 与 gxmem selftest 同款：0x4000 前缀 A7 E0 ED + 0x96F8[2] ∈ {1B,11}。
    2026-10-14：不再用 0x5096（该状态页在扫描中途整体变成 FF，见 B73）。"""
    lv = _rd("0x4000", 4).split()
    ch = _rd("0x96F8", 4).split()
    ok_live = len(lv) >= 3 and lv[0] == "A7" and lv[1] == "E0" and lv[2] == "ED"
    ok_bag = len(ch) >= 3 and ch[2] in ("1B", "11")
    return "liveness=%s bag=%s (%s)" % ("OK" if ok_live else "BAD", ch[2] if len(ch) >= 3 else "??",
                                        "正常" if (ok_live and ok_bag) else "异常"), (ok_live and ok_bag)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bags", default="1-27")
    ap.add_argument("--fills", default="00,ff")
    ap.add_argument("--window", type=float, default=8.0)
    ap.add_argument("--tag", default="g2scan")
    ap.add_argument("--wait-taps", action="store_true", help="先等用户开始按压（检到连续震动事件）再开跑")
    ap.add_argument("--dev", type=int, default=5, help="输入设备索引（默认 5；2026-10-14 实测 dev5 带内最强）")
    ap.add_argument("--calib", type=float, default=0.0, help="开跑前静默标定秒数（0=不做，用固定阈值）")
    ap.add_argument("--delay", type=float, default=20.0, help="启动后等待秒数（给你时间开始按压）")
    ap.add_argument("--controls", type=int, default=1, help="对照行重复次数（写原 cfg）")
    ap.add_argument("--no-bags", action="store_true", help="只跑对照行，不跑袋")
    ap.add_argument("--no-restore", action="store_true", help="结束时【不】回写原 cfg（默认会回写）")
    a = ap.parse_args()
    bags = parse_bags(a.bags)
    fills = [int(x, 16) for x in a.fills.split(",")]
    outdir = os.path.join(ROOT, "data", "logs")
    os.makedirs(outdir, exist_ok=True)
    path_out = os.path.join(outdir, "lab__%s_%s.json" % (a.tag, datetime.datetime.now().strftime("%Y%m%d_%H%M%S")))
    rows = []
    global THR, DEV
    DEV = a.dev
    import numpy as np, sounddevice as sd
    if a.calib > 0:
        print("=== 静默标定 %.1f s（请先别按）===" % a.calib)
        xc = sd.rec(int(a.calib * SR), samplerate=SR, channels=2, dtype="float32", device=DEV)[:, :1]
        sd.wait()
        win = 1024; nn = len(xc) // win
        ff = np.fft.rfftfreq(win, 1.0 / SR); mm = (ff >= LRA_LO) & (ff <= LRA_HI)
        vals = [float(np.sqrt(np.mean(np.abs(np.fft.rfft(xc[k * win:(k + 1) * win, 0] * np.hanning(win)))[mm] ** 2))) for k in range(nn)]
        p95 = float(np.percentile(vals, 95)) if vals else 0.0
        THR = max(p95 * EVENT_MULT, 0.0005)
        print("  本底 p95=%.6f ⇒ 事件阈值 THR=%.6f" % (p95, THR))
    else:
        THR = BASE_RMS * EVENT_MULT
    if a.wait_taps:
        print("=== 等待用户开始按压（每秒约 1 次）… ===")
        thr = BASE_RMS * EVENT_MULT
        need, got = 3, 0
        while got < need:
            x = sd.rec(int(0.5 * SR), samplerate=SR, channels=1, dtype="float32", device=9)
            sd.wait()
            x = x[:, 0]
            win = 1024; n = len(x) // win
            f = np.fft.rfftfreq(win, 1.0 / SR); m = (f >= LRA_LO) & (f <= LRA_HI)
            hit = 0
            for k in range(n):
                X = np.abs(np.fft.rfft(x[k * win:(k + 1) * win] * np.hanning(win)))
                if float(np.sqrt(np.mean(X[m] ** 2))) > thr:
                    hit += 1
            if hit:
                got += 1
                print("  检到震动事件 %d/%d" % (got, need))
        print("  ⇒ 已检到你开始按压，正式开跑！")
    if a.delay > 0:
        print("=== 请现在开始按压：%.0f 秒后正式开跑 ===" % a.delay)
        time.sleep(a.delay)
    print("=== G2 扫描开始 ===")
    print("袋: %s · 填充: %s · 每轮窗口 %.1f s · 输出 %s" % (bags, [hex(x) for x in fills], a.window, path_out))
    print("健康签名(前): 0x5096 =", health())
    t0 = time.time()
    # 对照行（协议 §3 步骤 1）：原样写回 + J1 参考窗（可重复 N 次以标定噪声）
    for _ci in range(a.controls):
        pr0 = subprocess.run([PY_TOOLS, R62, "--commit", "--cases", "A"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", cwd=ROOT, env=ENV)
        code0 = None
        for ln in ((pr0.stdout or "") + (pr0.stderr or "")).splitlines():
            mm0 = re.search(r"结果\s*=\s*([0-9A-Fa-f ]+)", ln)
            if mm0:
                code0 = mm0.group(1).strip()
        print("\n--- [%d] 对照：原样写回 ---\n  结果码: %s" % (_ci, code0))
        m0 = record_and_analyze(a.window)
        print("  J1(对照): p50=%.6f p95=%.6f max=%.6f · %s" % (m0["band_p50"], m0["band_p95"], m0["band_max"], m0["counts"]))
        hh, hh_ok = health()
        rows.append(dict(idx=_ci, bag=0, fill=0, code=code0, accepted=bool(code0) and code0.startswith("7F"), j1=m0, health=hh, health_ok=hh_ok, t=round(time.time() - t0, 1)))
        with open(path_out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(dict(tag=a.tag, window=a.window, base_rms=BASE_RMS, rows=rows), fh, ensure_ascii=False, indent=1)
    if a.no_bags:
        pass
    else:
        pass
    for i, bag in enumerate([] if a.no_bags else bags):
        for fill in fills:
            n = len(rows) + 1
            print("\n--- [%d] bag=%d fill=0x%02X ---" % (n, bag, fill))
            code, ok, raw = write_bag(bag, fill)
            print("  写入结果码:", code, "(OK)" if ok else "(非 0x7F)")
            m = record_and_analyze(a.window)
            print("  J1: p50=%.6f p95=%.6f max=%.6f · 多阈值事件数 %s" % (m["band_p50"], m["band_p95"], m["band_max"], m["counts"]))
            h, h_ok = health()
            row = dict(idx=n, bag=bag, fill=fill, code=code, accepted=ok, j1=m, health=h, health_ok=h_ok,
                       t=round(time.time() - t0, 1))
            rows.append(row)
            with open(path_out, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(dict(tag=a.tag, window=a.window, base_rms=BASE_RMS, rows=rows), fh, ensure_ascii=False, indent=1)
            if not h_ok:
                print("  ⚠️ 健康判据失败（%s）⇒ 按协议中止！" % h)
                abort = True
                break
            if not ok:
                print("  ⚠️ 结果码非 0x7F（记录后继续，但该轮判为无效）")
        if abort:
            print("  ⇒ 已中止：跳到回写原 cfg")
            break
    if not a.no_restore:
        print("\n=== 回写原 cfg（恢复基线）===")
        pr = subprocess.run([PY_TOOLS, R62, "--commit", "--cases", "A"], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", cwd=ROOT, env=ENV)
        for ln in ((pr.stdout or "") + (pr.stderr or "")).splitlines():
            if "结果" in ln or "读回" in ln or "restore" in ln:
                print("  " + ln.strip()[:120])
        h2, h2ok = health()
        print("  健康判据(后): %s ⇒ %s" % (h2, "正常" if h2ok else "异常"))
    print("\n=== 扫描结束：%d 轮，用时 %.1f s ===" % (len(rows), time.time() - t0))
    print("输出:", path_out)
    ev = [r for r in rows if r["j1"]["events"] > 0]
    print("有 J1 事件的轮数: %d / %d" % (len(ev), len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
