#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vib_probe.py —— ★★★ 触控板「震动探针」：把"震没震"从【手感】变成【客观数字】

为什么需要它（本项目纪律 109 的直接后果）
------------------------------------------------
`docs/00-...全书` 纪律 109：**主观感受（"更强/更软"）不能单独支撑字段定名**。
而"暴力扫描"（扫 256 个命令码 / 扫 32 KB 地址 / 扫几百个 cfg 字段）会产生**几百次判断** ——
靠手摸做几百次判断 = 纯噪声。

⇒ **任何暴力扫描的前置件 = 一个客观、可自动化、可复现的"震动判据"。**

本探针给出**两个互相独立的客观判据**：
  J1（声学）  笔记本自带 4 通道麦克风阵列：录 RMS 时间线 + 频谱，找 LRA 特征频率
  J2（力学）  触控板的力通道：LRA 振动会机械耦合进力传感器（若该通道可读）

LRA 特征频率的已知值
--------------------
本项目已确证 **`PA0` 常驻 200 Hz PWM = LRA 谐振频率**（§1.2 / §20.11）。
⇒ **判据 = 在 180–220 Hz 带内出现显著能量峰**（比宽带 RMS 更有分辨力）。

用法
----
  python vib_probe.py baseline            # 只测本底（零风险，先跑这个）
  python vib_probe.py calibrate           # 校准：提示你按 5 次触控板，看能否检出
  python vib_probe.py watch [秒数]        # 连续监测，实时打印带内能量
  python vib_probe.py record <秒> <out.wav>
"""
import sys, os, time, json, argparse, datetime

# Windows 控制台默认 GBK：打印 emoji / 生僻字会让 print 抛 UnicodeEncodeError（2026-10-14 实测）
try:  # 只把不可编码字符降级为 '?'，不改变可读内容
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

try:
    import numpy as np
    import sounddevice as sd
except ImportError as e:
    print("[FATAL] 需要 numpy + sounddevice：%r" % e)
    print("        C:/Users/<USER>/.workbuddy/binaries/python/envs/default/Scripts/python.exe -m pip install sounddevice numpy")
    raise SystemExit(2)

SR = 48000          # 采样率
LRA_LO, LRA_HI = 180.0, 220.0   # LRA 谐振带（项目已证 200 Hz）
BLOCK = 1024        # ~21 ms（事件检测用）
SPEC_N = 8192       # 频谱分析窗（~171 ms）⇒ 频率分辨率 5.9 Hz，可分辨 187/200/210
DEV = None          # None = 默认输入设备
CH = None           # None = 用设备全部通道（≤4）


def pick_device():
    """优先选【采样率 48000 且多通道】的输入设备（Intel 智音麦克风阵列）"""
    best = None
    for i, d in enumerate(sd.query_devices()):
        if d['max_input_channels'] < 1:
            continue
        sr = int(d['default_samplerate'])
        ch = d['max_input_channels']
        score = (sr == 48000) * 2 + (ch >= 2)
        if '麦克风阵列' in d['name'] or 'Microphone' in d['name'] or 'Array' in d['name']:
            score += 3
        if best is None or score > best[0]:
            best = (score, i, d)
    return best


def band_energy(x, sr, lo=LRA_LO, hi=LRA_HI):
    """返回 (总RMS, 带内RMS, 峰值频率)。x 最好 ≥ SPEC_N 才有足够频率分辨率。"""
    if len(x) < 64:
        return 0.0, 0.0, 0.0
    x = np.asarray(x, dtype=np.float64)
    x = x - x.mean()
    rms = float(np.sqrt(np.mean(x ** 2)))
    n = min(len(x), SPEC_N)
    seg = x[-n:]
    w = np.hanning(len(seg))
    X = np.fft.rfft(seg * w)
    f = np.fft.rfftfreq(len(seg), 1.0 / sr)
    P = np.abs(X) ** 2
    m = (f >= lo) & (f <= hi)
    be = float(np.sqrt(np.sum(P[m]) / len(seg)))
    pk = float(f[m][int(np.argmax(P[m]))]) if m.any() and P[m].size else 0.0
    return rms, be, pk


def open_stream(channels, sr):
    return sd.InputStream(device=DEV, samplerate=sr, channels=channels,
                          blocksize=BLOCK, dtype='float32')


def resolve_dev_ch():
    """解析设备/通道并设置全局 DEV / CUR_CH / CUR_SR（只打印一次）"""
    global DEV, CUR_CH, CUR_SR
    sc, idx, d = pick_device()
    if DEV is None:
        DEV = idx
    info = sd.query_devices(DEV)
    CUR_CH = CH if CH is not None else min(4, info['max_input_channels'])
    CUR_SR = int(info['default_samplerate'])
    print("输入设备 [%d] %s  in=%d  → 用 %d ch @ %d Hz  (频谱窗 %d 点 ⇒ %.1f Hz/格)"
          % (DEV, info['name'], info['max_input_channels'], CUR_CH, CUR_SR, SPEC_N, CUR_SR / SPEC_N))


def iter_frames(secs, sr, ch):
    """产出 (t, rms[], band[], peak[])，每通道一个值；内部维护 SPEC_N 长的滚动缓冲"""
    ring = np.zeros((SPEC_N, ch), dtype=np.float32)
    filled = 0
    t0 = time.time()
    with sd.InputStream(device=DEV, samplerate=sr, channels=ch,
                        blocksize=BLOCK, dtype='float32') as st:
        while True:
            t = time.time() - t0
            if t >= secs:
                return
            blk, _ = st.read(BLOCK)
            k = min(len(blk), SPEC_N)
            if filled + k <= SPEC_N:
                ring[filled:filled + k] = blk[:k]
            else:
                ring = np.roll(ring, -k, axis=0)
                ring[SPEC_N - k:] = blk[:k]
            filled = min(SPEC_N, filled + k)
            n = filled
            rms, be, pk = [], [], []
            for c in range(ch):
                r, b, p = band_energy(ring[SPEC_N - n:, c], sr)
                rms.append(r); be.append(b); pk.append(p)
            yield t, rms, be, pk


def cmd_baseline(secs=3.0):
    print("\n记录 %.1f s 本底…\n" % secs)
    acc = []
    for t, rms, be, pk in iter_frames(secs, CUR_SR, CUR_CH):
        acc.append((rms, be, pk))
    A = {k: np.array([row[k] for row in acc]) for k in range(3)}
    for c in range(CUR_CH):
        for j, nm in enumerate(["总RMS", "带内RMS(180-220Hz)", "峰值频率"]):
            v = A[j][:, c]
            print("  ch%d %-20s 中位=%.6f  p95=%.6f  max=%.6f%s"
                  % (c, nm, float(np.median(v)), float(np.percentile(v, 95)), v.max(),
                     "  Hz" if j == 2 else ""))
    bb = A[1].reshape(-1)
    p95 = float(np.percentile(bb, 95))
    print("\n★ 判据基线：带内RMS 中位=%.6f  p95=%.6f  max=%.6f"
          % (float(np.median(bb)), p95, bb.max()))
    print("  ⇒ 事件判据建议：带内RMS > p95×3 = %.6f" % (p95 * 3))
    return p95


def cmd_calibrate():
    p95 = cmd_baseline(3.0)
    print("\n" + "=" * 72)
    print("现在请【连续轻按触控板 5 次】，每次间隔约 1 秒。开始…")
    print("=" * 72)
    events = 0
    hist = []
    thr = max(2e-5, p95 * 3)
    for t, rms, be, pk in iter_frames(8.0, CUR_SR, CUR_CH):
        hist.append(float(np.median(be)))
        base = float(np.median(hist)) if hist else 0.0
        if max(be) > thr:
            events += 1
            c = int(np.argmax(be))
            print("  ⚡ 事件 %2d  t=%.2fs  ch%d 带内=%.6f (本底中位 %.6f)  峰值=%.1f Hz"
                  % (events, t, c, be[c], base, pk[c]))
    print("\n阈值=%.6f  检出 %d 次 ⇒ %s"
          % (thr, events, "**声学判据成立，探针可用**" if events >= 3
             else "未检出；改用 J2（力通道）或换设备/增益"))


def cmd_watch(secs=10.0):
    print("监测 %.0f s（Ctrl+C 停）…" % secs)
    for t, rms, be, pk in iter_frames(secs, CUR_SR, CUR_CH):
        c = int(np.argmax(be))
        print("  t=%6.2fs  总RMS=%.6f  带内(ch%d)=%.6f  峰值=%5.1f Hz"
              % (t, rms[c], c, be[c], pk[c]))


def cmd_record(secs, out):
    print("录 %.1f s -> %s" % (secs, out))
    buf = []
    with sd.InputStream(device=DEV, samplerate=CUR_SR, channels=CUR_CH,
                        blocksize=BLOCK, dtype='float32') as st:
        t0 = time.time()
        while time.time() - t0 < secs:
            blk, _ = st.read(BLOCK)
            buf.append(blk.copy())
    x = np.concatenate(buf, axis=0)
    import wave
    with wave.open(out, 'wb') as w:
        w.setnchannels(CUR_CH); w.setsampwidth(2); w.setframerate(CUR_SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype('<i2').tobytes())
    print("已写 %d 帧 × %d ch @ %d Hz" % (x.shape[0], CUR_CH, CUR_SR))


def cmd_selftest():
    """自检：先用扬声器放一段 200 Hz（LRA 谐振频率），同时录音，验证"能否检出 200 Hz"。
    这不证明"触控板声音能被听到"，只证明【判据本身有分辨力】。"""
    print("自检：播放 200 Hz（低幅度）1.2 s，同时录音…")
    dur, f0, amp = 1.2, 200.0, 0.04
    t = np.arange(int(dur * CUR_SR)) / CUR_SR
    tone = (amp * np.sin(2 * np.pi * f0 * t)).astype('float32')
    try:
        od = sd.query_devices(kind='output')
    except Exception:
        od = None
    print("  输出设备：%s" % (od['name'] if od else 'default'))
    out_ch = min(2, od['max_output_channels']) if od else 2
    mono = (amp * np.sin(2 * np.pi * f0 * t)).astype('float32')
    tone = np.repeat(mono[:, None], out_ch, axis=1)      # 补齐到输出通道数
    rec = []
    with sd.OutputStream(samplerate=CUR_SR, channels=out_ch,
                         blocksize=BLOCK, dtype='float32') as out:
        with sd.InputStream(device=DEV, samplerate=CUR_SR, channels=CUR_CH,
                            blocksize=BLOCK, dtype='float32') as inp:
            st = out.write(tone)
            while True:
                blk, _ = inp.read(BLOCK)
                rec.append(blk.copy())
                if len(rec) * BLOCK >= len(tone) + CUR_SR // 2:
                    break
    x = np.concatenate(rec, axis=0)
    n = min(len(x), SPEC_N)
    rms, be, pk = band_energy(x[-n:, 0], CUR_SR)
    print("  录到 %d 帧；带内RMS=%.6f  峰值频率=%.1f Hz" % (len(x), be, pk))
    ok = (LRA_LO <= pk <= LRA_HI) and be > 5e-5
    print("  ⇒ %s：峰值频率落在 %.0f–%.0f Hz ⇒ **判据有分辨力**" % (
        "✅ 通过" if ok else "⚠️ 未通过", LRA_LO, LRA_HI))
    print("     注意：这一步只验证【探针能识别 200 Hz】，不验证【触控板声音可被听到】。")
    print("     后者需要你跑 `calibrate`（按 5 次触控板）。")


CUR_SR, CUR_CH = SR, 2

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="触控板震动探针（客观判据）")
    ap.add_argument("cmd", choices=["devices", "baseline", "calibrate", "watch", "record", "selftest"])
    ap.add_argument("arg", nargs="*")
    ap.add_argument("--dev", type=int, default=None, help="输入设备索引")
    ap.add_argument("--ch", type=int, default=None, help="通道数（≤4）")
    a = ap.parse_args()
    DEV, CH = a.dev, a.ch
    if a.cmd == "devices":
        for i, d in enumerate(sd.query_devices()):
            if d['max_input_channels'] > 0:
                print("  [%2d] %-52s IN%d sr=%d"
                      % (i, d['name'][:52], d['max_input_channels'], int(d['default_samplerate'])))
        raise SystemExit(0)
    resolve_dev_ch()
    if a.cmd == "baseline":
        cmd_baseline(float(a.arg[0]) if a.arg else 3.0)
    elif a.cmd == "calibrate":
        cmd_calibrate()
    elif a.cmd == "watch":
        cmd_watch(float(a.arg[0]) if a.arg else 10.0)
    elif a.cmd == "record":
        cmd_record(float(a.arg[0]), a.arg[1])
    elif a.cmd == "selftest":
        cmd_selftest()
