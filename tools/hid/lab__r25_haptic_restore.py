#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lab__r25_haptic_restore.py —— 触觉强度恢复工具（事故响应 2026-10-08）

背景：`lab__r24_haptic_ab.py` 测 `0x09` 时写入了 0/50 等值，喆反馈"没震动反馈了"。
      Windows 设置里「触觉点击」开关仍显示"开"，但硬件端强度被外部改写 ⇒ UI 与硬件脱钩。

本工具做三件事：
  A. 报告当前四个集合的权限/健康状态（只读）
  B. 把 `0x09` 按多种"可能被 Windows 认可的值"依次写入（默认 100 / 80 / 50）
  C. `--cycle` 模式：在 `0x09` 上做一个 关→开 的模拟（0 → 100），
     等价于 Windows 那个开关"关一下再开"

★ 只写 `0x09`，绝不碰 0x0E/0x0D/cfg。
★ 若本工具无效 ⇒ 下一步是 `pnputil /restart-device`（让 IC 从 flash 重载默认值）。

用法：
  python lab__r25_haptic_restore.py            # 写 100
  python lab__r25_haptic_restore.py 80         # 写指定值
  python lab__r25_haptic_restore.py --cycle    # 0 → 100（模拟开关 关/开）
  python lab__r25_haptic_restore.py --report   # 只报告不写
"""
import ctypes
import sys
import time
from ctypes import wintypes
import importlib.util
import os

_here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('r22', os.path.join(_here, 'lab__r22_feature_caps.py'))
r22 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r22)

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
hd = ctypes.WinDLL('hid', use_last_error=True)
k32.CreateFileW.restype = wintypes.HANDLE
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
k32.CloseHandle.argtypes = [wintypes.HANDLE]
hd.HidD_SetFeature.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
hd.HidD_SetFeature.restype = wintypes.BOOL

RID = 0x09
GW = 0x40000000
INVALID = ctypes.c_void_p(-1).value


def paths_by_col():
    return {r22.col_tag(p): p for p in r22.enum_paths() if 'gxtp5100' in p.lower()}


def report():
    print("=== 四集合状态（只读）===")
    ps = paths_by_col()
    for tag in ('COL01', 'COL02', 'COL03', 'COL04'):
        p = ps.get(tag)
        if not p:
            print("  %s  ✗ 未枚举到" % tag)
            continue
        row = []
        for acc, nm in ((0, 'Q'), (0x80000000, 'R'), (0x40000000, 'W')):
            h = k32.CreateFileW(p, acc, 3, None, 3, 0, None)
            ok = bool(h) and h != INVALID
            row.append('%s=%s' % (nm, 'OK' if ok else 'e%d' % ctypes.get_last_error()))
            if ok:
                k32.CloseHandle(h)
        print("  %s  %s" % (tag, '  '.join(row)))
    # RID 09 声明
    p02 = ps.get('COL02')
    if p02:
        info, err = r22.read_col(p02)
        if err:
            print("  COL02 caps 读取失败: %s" % err)
        else:
            for e in info.get('FEATURE', []):
                if e['RID'] == RID:
                    print("  COL02 RID 0x09 声明: logi[%d..%d] %dbit ×%d（存在）"
                          % (e['LogMin'], e['LogMax'], e['BitSize'], e['Count']))


def write9(value):
    ps = paths_by_col()
    p = ps.get('COL02')
    if not p:
        print("✗ 未找到 Col02")
        return False
    h = k32.CreateFileW(p, GW, 3, None, 3, 0, None)
    if not h or h == INVALID:
        print("✗ 打开 Col02 失败 err=%d" % ctypes.get_last_error())
        return False
    try:
        b = (ctypes.c_ubyte * 2)()
        b[0] = RID
        b[1] = value & 0xFF
        ctypes.set_last_error(0)
        ok = bool(hd.HidD_SetFeature(h, b, 2))
        print("  写 0x09 = %-3d -> %s" % (value, "✅ 被接受" if ok else "❌ e%d" % ctypes.get_last_error()))
        return ok
    finally:
        k32.CloseHandle(h)


def main():
    args = [a for a in sys.argv[1:]]
    report()
    print()
    if '--report' in args:
        return 0

    if '--cycle' in args:
        print("=== 模拟开关 关→开（0 → 100）===")
        write9(0)
        time.sleep(1.0)
        write9(100)
        time.sleep(0.3)
        write9(100)
        return 0

    val = 100
    for a in args:
        if a.isdigit():
            val = int(a)
    print("=== 恢复：写 0x09 = %d（连续 3 次确保被接受）===" % val)
    for i in range(3):
        write9(val)
        time.sleep(0.2)
    print()
    print("若仍无反馈 ⇒ 请执行（管理员 PowerShell）：")
    print('  pnputil /restart-device "HID\\GXTP5100&Col02\\5&52a7aed&0&0001"')
    print('  pnputil /restart-device "HID\\GXTP5100&Col03\\5&52a7aed&0&0002"')
    print('  pnputil /restart-device "HID\\GXTP5100&Col04\\5&52a7aed&0&0003"')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
