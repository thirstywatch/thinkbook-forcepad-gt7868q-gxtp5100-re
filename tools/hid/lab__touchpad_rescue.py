#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lab__touchpad_rescue.py —— 触控板急救（只发【官方文档化】的恢复命令）

背景：2026-10-14 13:50 的命令码扫描（`lab__brute.py cmdscan 0x01..0x2F`）之后
      用户报「触控板炸了」。本脚本按【官方更新器里出现过的命令】逐级恢复。

恢复序列（全部来自官方 `gtx8_gtx8_update.cpp` / 本项目 r13/r32 已验证过的写法）
--------------------------------------------------------------------------------
  R1  0x4160 ← {0x34,00,00,00,0x34}   官方「开坐标上报」（DisableReport 的反操作）
  R2  0x4160 ← {0x32,00,00,00,0x32}   官方「切 PTP 模式」（switch to ptp mode）
  R3  HID 0E 13 00 00 01 01           官方「复位 IC」（使配置生效 / 从 flash 重载）
  R4  再来一遍 R1+R2（复位后需要重新开上报 / 切模式）

安全
----
  · 只发上面 4 条【官方文档化】命令，**不发明任何新值**
  · **绝不碰** 0x1E000 / 0xC000 / 0E 10 / 0E 11 / 0E 12（flash 路径）
  · 全程只读快照 + 上述恢复命令；无副作用累积
  · 若 Col04 打不开 ⇒ 打印「需要设备级重启」的手动步骤
"""
import sys, os, time, json, argparse

# Windows 控制台默认 GBK：打印 emoji / 生僻字会让 print 抛 UnicodeEncodeError（2026-10-14 实测）
try:  # 只把不可编码字符降级为 '?'，不改变可读内容
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    import gxmem
except Exception as e:
    print("[FATAL] 需同目录 gxmem.py: %r" % e)
    raise SystemExit(2)

CMD = 0x4160
LIVE = 0x4000
BL = 0x5095
FR = 0x5096
CFG = 0x96F8


def hx(b):
    return b.hex(' ').upper() if b else '<FAIL>'


def snap(g, tag):
    r = {}
    for nm, a, n in [("0x4000", LIVE, 4), ("0x4160", CMD, 5),
                     ("0x5095", BL, 1), ("0x5096", FR, 1), ("0x96F8", CFG, 8)]:
        d, _ = g.read(a, n, rounds=6, delay=0.05)
        r[nm] = hx(d)
    print("  [%s] %s" % (tag, json.dumps(r, ensure_ascii=False)))
    return r


def mkc(cmd, data=0):
    hi, lo = (data >> 8) & 0xFF, data & 0xFF
    s = (cmd + hi + lo) & 0xFFFF
    return bytes([cmd, hi, lo, (s >> 8) & 0xFF, s & 0xFF])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true")
    a = ap.parse_args()
    if not a.commit:
        print("[DRY] 加 --commit 执行。将依次发：")
        print("  R1 0x4160 ← {34,00,00,00,34}  开坐标上报")
        print("  R2 0x4160 ← {32,00,00,00,32}  切 PTP 模式")
        print("  R3 HID 0E 13 00 00 01 01      复位 IC")
        print("  R4 再来一遍 R1+R2")
        return

    g = gxmem.Gx()
    ok = g.open()
    print("open(Col04) = %s" % ok)
    if not ok:
        print("\n❌ Col04 已打不开（设备句柄取不到）。")
        print("   ⇒ 走【设备级重启】（见脚本末尾提示），不要再发任何命令。")
        manual_steps()
        return

    try:
        print("\n--- 恢复前 ---")
        before = snap(g, "前")

        print("\n--- R1 开坐标上报 {34,00,00,00,34} ---")
        if g.write(CMD, mkc(0x34)):
            print("  已发"); time.sleep(0.25)
        snap(g, "R1后")

        print("\n--- R2 切 PTP 模式 {32,00,00,00,32} ---")
        if g.write(CMD, mkc(0x32)):
            print("  已发"); time.sleep(0.25)
        snap(g, "R2后")

        print("\n--- R3 复位 IC（HID 0E 13 00 00 01 01） ---")
        if g._send([0x0E, 0x13, 0x00, 0x00, 0x01, 0x01]):
            print("  已发"); time.sleep(1.2)
        else:
            print("  ⚠ 发送失败")
        snap(g, "R3后")

        print("\n--- R4 再来一遍 R1+R2（复位后需重开上报/切模式） ---")
        g.write(CMD, mkc(0x34)); time.sleep(0.25)
        g.write(CMD, mkc(0x32)); time.sleep(0.5)
        after = snap(g, "R4后")

        print("\n--- 对比 ---")
        ch = [k for k in before if before[k] != after[k]]
        print("  恢复前后不同的项: %s" % (ch if ch else "无"))
        print("  ★ 关键：0x4000 存活位 = %s （正常形如 A7 E0 xx B1）" % after["0x4000"])
        print("  ★ 关键：0x4160 命令寄存器 = %s （正常应含 FF）" % after["0x4160"])
    finally:
        g.close()

    print("\n=== 现在请你试试触控板 ===")
    print("  · 能动 + 能点 → ✅ 已恢复")
    print("  · 仍不动 → 跑一次【设备级重启】：")
    manual_steps()


def manual_steps():
    print(r"""
  ---------------------------------------------------------------
  设备级重启（按顺序试，第 1 步通常就够）
  ---------------------------------------------------------------
  1) 禁用再启用触控板（不需要管理员）：
     PowerShell（管理员）:
        Get-PnpDevice | Where-Object { $_.InstanceId -like '*GXTP5100*' } |
            Disable-PnpDevice -Confirm:$false
        Start-Sleep 2
        Get-PnpDevice | Where-Object { $_.InstanceId -like '*GXTP5100*' } |
            Enable-PnpDevice -Confirm:$false

  2) 若上面无效 ⇒ 重启设备（不用重启电脑）：
        pnputil /restart-device "HID\GXTP5100&Col01\<实例>"
     （实例号先用 `pnputil /enum-devices /class HIDClass` 查）

  3) 兜底：整机重启。**flash 全程未被改写**（我们只写过 0x4160 / 0x96F8 会话区），
     重启后 IC 会从 flash 重载，应当完全恢复。

  4) 若重启后仍不行 ⇒ 长按电源键 15 s 断电重来（EC 冷复位）。
  ---------------------------------------------------------------
""")


if __name__ == "__main__":
    main()
