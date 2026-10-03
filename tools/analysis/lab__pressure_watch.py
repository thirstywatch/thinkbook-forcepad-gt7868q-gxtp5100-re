# -*- coding: utf-8 -*-
"""pressure_watch.py — 连续采样 GT7868Q 的压力帧区，捕捉"按压事件"

背景：
  0x5F00 起是 60 字节/帧的环形缓冲，帧内可见 "通道数=4" 与静止值 0x28(=40)。
  本项目 TF100A 的判据是 |Δ压力| > 40（0x28）—— 两边数值吻合。
  本脚本连续读该区，把每次快照存成 JSONL，供事后分析"哪个字段在按压时跳变"。

用法：
  python pressure_watch.py <secs> <out.jsonl> [start] [len]
  默认读 0x5F00 区 240 字节（4 帧），每 0.5 秒一次。
"""
import ctypes, sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gxmem import Gx


def main():
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    out = sys.argv[2] if len(sys.argv) > 2 else "press.jsonl"
    start = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x5F00
    ln = int(sys.argv[4], 0) if len(sys.argv) > 4 else 240

    g = Gx()
    if not g.open():
        print("Col04 open FAILED err=%d" % ctypes.get_last_error())
        return 1
    print("open ok. 采样 0x%05X x%d B，持续 %.0f 秒 ..." % (start, ln, secs))
    t0 = time.time()
    n = 0
    fails = 0
    with open(out, "w") as f:
        while time.time() - t0 < secs:
            d, _ = g.read(start, ln)
            rec = {"t": round(time.time() - t0, 3), "d": d.hex() if d else None}
            if not d:
                fails += 1
            f.write(json.dumps(rec) + "\n")
            n += 1
            el = time.time() - t0
            if n % 20 == 0:
                print("  %d 采样, %.1fs, fail=%d" % (n, el, fails))
            # 目标 0.5 秒一个采样
            dt = 0.5 - ((time.time() - t0) - el)
            if dt > 0:
                time.sleep(dt)
    g.close()
    print("done. %d 采样 -> %s (%.1fs, fail=%d)" % (n, out, time.time() - t0, fails))
    return 0


if __name__ == "__main__":
    sys.exit(main())
