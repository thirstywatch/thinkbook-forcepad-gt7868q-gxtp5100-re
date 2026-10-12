#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""lab__r54_rid9_sweep.py —— ★ 直接实验：HID Feature RID 9 / usage 0x0E·0x23 "Haptic Intensity"

★★ 结论先行（登记表 B14，2026-10-08 第 22 轮已实证）
     **`0x09`（Col02 的 Feature Report RID 9，HID 触觉页 0x0E / usage 0x23 Intensity，取值 0–100）
       = 这块板唯一的"震动强度/开关"主机控制面。**
       · `0`  = 完全静音（用户体感："没震动反馈了"）
       · `100` = 满档
       · Windows 设置里那个「触觉点击」开关，联动写的**就是它**（关=0 / 开=100）
       · 不落盘（易失）：外部改写后 Windows UI 会与硬件脱钩，UI 里"关一下再开"即可复原

★ 本脚本是这条结论的**可复现实测**（而不是新发现）。
  ⚠️ 纪律 114：测"开关型"字段**必须包含 `0 = 关` 这一档**；
     只测 10 / 50 / 100 之类的中间档会得到**假的阴性**。

背景（全书 §10.5 / §11.9 / 追加十五）
  · 本机 4 个 HID 集合里，**唯一**跟触觉有关的 HID 面就是这个字段
    （缺 host-initiated haptics 那一整条：没有 `0x0E/0x21 Manual Trigger`、没有 `0x0E/0x20`）
  · ⇒ **改它能调"设备自主触发时用多大劲"，但仍不能"任意时刻主动拉扳机"**

本脚本做的事
  1. 打印 Windows 侧偏好（FeedbackEnabled / FeedbackIntensity / ClickForceSensitivity）
  2. 按【固定时间轴】依次跑：基线 → 100 → 0 → 100，每段 8 秒，屏幕同步倒计时
  3. 收尾无条件写回 100

★ 安全性
  · 只写 HID feature report（描述符正式声明的字段），**不碰固件、不碰 flash、不进 bootloader**
  · 回滚路径：Windows 设置 → 触控板 → 「触觉反馈强度」滑块拖一下（驱动会重写）；
    或重启电脑
  · 单变量：整个过程只改 RID 9 一个字段

用法
  python lab__r54_rid9_sweep.py            # 打印计划（DRY）
  python lab__r54_rid9_sweep.py --go       # 执行时间轴
  python lab__r54_rid9_sweep.py --set 64   # 只写一个值（十六进制）
"""
import ctypes
import sys
import time
import datetime
import winreg

HERE = None
try:
    import os
    HERE = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, HERE)
except Exception:
    pass
import hid_feature as hf

RID = 9
COL = "col02"
SEG = 8.0            # 每段秒数
# ★ 2026-10-11 修正：必须包含【0 = 关】这一档（登记表 B14 / 纪律 114）
#   只测 10 vs 50 vs 100 这种"中间档"会得到假的阴性 —— 开关型字段的可见效应在极端档。
# (要写入的值 or None=不写, 说明)
PLAN = [(None, '当前值（上一轮我写过的 0x0A=10，属于"偏弱"档）—— 基线'),
        (0x64, '100  满档'),
        (0x00, '0    ★ 零档 = 完全静音（这是"能不能关掉震动"的硬判据）'),
        (0x64, '100  收尾恢复（纪律：开关型字段收尾必须写回满值）')]

LOG = []


def log(s):
    line = "[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), s)
    print(line, flush=True)
    LOG.append(line)


def flush():
    if HERE:
        try:
            open(os.path.join(HERE, "_r54_log.txt"), "a", encoding="utf-8").write("\n".join(LOG) + "\n")
        except Exception:
            pass


def win_prefs():
    out = {}
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r'Software\Microsoft\Windows\CurrentVersion\PrecisionTouchPad')
        i = 0
        while True:
            try:
                n, v, _ = winreg.EnumValue(k, i)
            except OSError:
                break
            out[n] = v
            i += 1
    except OSError:
        pass
    return out


def set_rid9(v, h=None):
    path = hf.find_path(COL)
    own = h is None
    if own:
        h = hf.open_dev(path)
        if not h:
            return False
    buf = ctypes.create_string_buffer(2)
    buf[0] = bytes([RID])
    buf[1] = bytes([v & 0xFF])
    ok = hf.hid.HidD_SetFeature(h, ctypes.cast(buf, ctypes.c_void_p), 2)
    err = ctypes.get_last_error()
    if own:
        hf.k32.CloseHandle(h)
    return bool(ok), err


def main():
    a = sys.argv[1:]
    log("=" * 78)
    log("r54 · HID RID9 (0x0E/0x23 Haptic Intensity) 直接实验")
    log("=" * 78)

    p = win_prefs()
    log("Windows 侧偏好（PrecisionTouchPad）:")
    for k in ('FeedbackEnabled', 'FeedbackIntensity', 'ClickForceSensitivity'):
        if k in p:
            log("   %-22s = %s (%s)" % (k, p[k], hex(p[k]) if isinstance(p[k], int) else ''))
    log("")

    if '--set' in a:
        v = int(a[a.index('--set') + 1], 16)
        log("单发写入 RID9 = 0x%02X (%d)" % (v, v))
        log("  结果: %s" % (set_rid9(v),))
        flush()
        return 0

    if '--go' not in a:
        log("[DRY] 计划（每段 %.0f 秒）：" % SEG)
        t = 0
        for v, lbl in PLAN:
            log("   T+%2.0fs ~ T+%2.0fs : RID9 = %s  %s"
                % (t, t + SEG, ("0x%02X" % v) if v is not None else "  --  ", lbl))
            t += SEG
        log("")
        log("★ 加 --go 执行。执行时请【持续用指腹按压 / 轻点触控板】并记住每段震感。")
        log("  ⚠ 运行前请先确认：现在【按下触控板】有没有震动反馈？（这是基线）")
        return 0

    path = hf.find_path(COL)
    log("目标: %s" % path)
    h = hf.open_dev(path)
    if not h:
        log("[FATAL] 打不开 Col02")
        return 3

    try:
        log("")
        log("★ 现在开始，请【持续按压 / 轻点触控板】。每段 8 秒，脚本会实时提示。")
        log("")
        t0 = time.time()
        for v, lbl in PLAN:
            if v is None:
                ok, err = True, 0
                wlbl = "—— 不写，用 Windows 当前值 ——"
            else:
                ok, err = set_rid9(v, h)
                wlbl = "写入 %s (err=%d)" % ("OK" if ok else "FAIL", err)
            log("  ──> RID9 = %s  %s   %s   [T+%.0fs]"
                % (("0x%02X" % v) if v is not None else " -- ", lbl, wlbl, time.time() - t0))
            seg_end = time.time() + SEG
            while time.time() < seg_end:
                left = seg_end - time.time()
                sys.stdout.write("\r      ... 本段还剩 %4.1f s (RID9=%s) "
                                 % (left, ("0x%02X" % v) if v is not None else "--"))
                sys.stdout.flush()
                time.sleep(0.25)
            sys.stdout.write("\r%s\r" % (" " * 50))
        log("")
        log("═" * 70)
        log("★ 请回报：这 5 段的【点击震动】强弱次序（哪段最强 / 哪段消失 / 哪段和平时一样）")
        log("  以及：整个过程中滑动/点击功能是否正常")
        log("═" * 70)
        log("回滚：若感觉异常，拖一下 Windows 触控板设置里的「触觉反馈强度」滑块，或重启电脑。")
        return 0
    finally:
        hf.k32.CloseHandle(h)
        flush()


if __name__ == '__main__':
    sys.exit(main())
