#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lab__r24_haptic_ab.py —— ★ `0x09` 触觉强度 A/B 交叉验证（goodhaptic 同一条通道）

动机（2026-10-08）：
  GitHub 命中 nwkyz/goodhaptic —— Linux 侧用 HID Feature Report `0x09`
  （Haptics 0x0E / Intensity 0x23，0–100）改震动力度，是其唯一成功路径。
  本项目已实测本机 Col02 **存在** RID 0x09（caps），且 **只写不可读**。
  但**从未在 Windows 上验证"写进去到底有没有效果"** ⇒ 本脚本就是那次验证。

设计（★ 全部为规避风险而设）：
  1. **只写 `0x09`** —— 绝不碰 `0x0E` 类、绝不碰 `0x0D`、绝不碰 cfg 通道
  2. **不禁用任何设备！** 实测 Col02 可用 `GENERIC_WRITE`(0x40000000) 打开（READ 被 Col03 占着，
     但 SetFeature 只需写权限）⇒ 无需 `pnputil /disable-device`
  3. **值域含"能证伪的极端档"**（满足纪律第 109 条）：
     100 = 强（应明显震）· 0 = 静音（**若 0 还震 ⇒ "强度旋钮"假说被否**）
  4. **顺序 100 → 50 → 0 → 100**：结尾回到强档，且给 3 个可分辨点看单调性
  5. **每步后等用户按键确认手感**（人机闭环）
  6. **收尾写回 100**（goodhaptic/Windows 默认档），并做健康复查

★ 安全：不落盘（HID 层本来就易失，与 B12 一致）；最坏情况 = 设置被重置，重启即恢复默认。
★ 全程不读回（本机 RID 9 读不到，已实测 err=122）—— 只有"写入是否被接受(BOOL)"这一个信号。

用法（需管理员权限？先试非管理员）：
  python lab__r24_haptic_ab.py --dry     # 只枚举 + 打印计划，不写
  python lab__r24_haptic_ab.py           # 正式跑（会提示你按回车）
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
hd.HidD_GetFeature.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
hd.HidD_GetFeature.restype = wintypes.BOOL

GENERIC_WRITE = 0x40000000
FILE_SHARE_RW = 3
OPEN_EXISTING = 3
INVALID = ctypes.c_void_p(-1).value

RID = 0x09
# ★ 方案：值 → 说明（满足"极端档可证伪"）
PLAN = [
    (100, "强档（goodhaptic/Windows 默认档）— 应先听到/感到『最明显』的震动"),
    (50,  "中档 — 应比 100 弱"),
    (0,   "★ 零档 — 若仍然照震 ⇒ 『强度旋钮』假说被【否】；若完全静音 ⇒ 假说【获强支持】"),
    (100, "回到强档 — 确认可逆"),
]


def find_col02():
    for p in r22.enum_paths():
        if 'gxtp5100' in p.lower() and 'col02' in p.lower():
            return p
    return None


def open_write(path):
    h = k32.CreateFileW(path, GENERIC_WRITE, FILE_SHARE_RW, None, OPEN_EXISTING, 0, None)
    if not h or h == INVALID:
        return None, ctypes.get_last_error()
    return h, 0


def set_haptic(h, value):
    """goodhaptic haptic_set() 的 Windows 等价：[0x09, value]"""
    buf = (ctypes.c_ubyte * 2)()
    buf[0] = RID
    buf[1] = value & 0xFF
    ctypes.set_last_error(0)
    ok = hd.HidD_SetFeature(h, buf, 2)
    return bool(ok), ctypes.get_last_error()


def health_check(tag):
    """健康三连：Col02 caps 可读 + Col04 存在 + 不崩"""
    ps = {r22.col_tag(p): p for p in r22.enum_paths() if 'gxtp5100' in p.lower()}
    ok02 = 'COL02' in ps
    ok04 = 'COL04' in ps
    info, err = r22.read_col(ps['COL02']) if ok02 else (None, 'missing')
    n9 = None
    if info:
        for e in info.get('FEATURE', []):
            if e['RID'] == RID:
                n9 = e
    print("    健康[%s]: COL02=%s COL04=%s  RID09声明=%s" %
          (tag, "在" if ok02 else "缺", "在" if ok04 else "缺",
           ("logi[%d..%d] %dbit×%d" % (n9['LogMin'], n9['LogMax'], n9['BitSize'], n9['Count'])) if n9 else "未读到"))


def main():
    dry = '--dry' in sys.argv

    print("=" * 92)
    print("### `0x09` 触觉强度 A/B 交叉验证（goodhaptic 通道在 Windows 上的首次实测）")
    print("=" * 92)

    path = find_col02()
    if not path:
        print("❌ 未找到 Col02")
        return 1
    print("目标集合：Col02")
    print("  路径：%s" % path)
    print()

    print("--- 前置健康检查 ---")
    health_check("前置")

    print()
    print("--- 计划（**只写 RID 0x09，不禁用任何设备，不碰 0x0E/0x0D**）---")
    for v, d in PLAN:
        print("  写 0x09 = %-3d   %s" % (v, d))
    print()

    if dry:
        print("[--dry] 未发任何报文。")
        return 0

    # 打开 WRITE-only 句柄
    h, err = open_write(path)
    if not h:
        print("❌ CreateFileW(WRITE) 失败 err=%d" % err)
        print("   提示：若 err=5（拒绝访问），需管理员权限重跑。")
        return 1
    print("✅ 已打开 Col02（WRITE-only）。开始。")

    results = []
    try:
        for i, (v, d) in enumerate(PLAN, 1):
            print()
            print("─" * 92)
            print("[%d/%d] 写入 0x09 = %d" % (i, len(PLAN), v))
            print("        %s" % d)
            ok, e = set_haptic(h, v)
            print("        SetFeature 返回：%s%s" % ("✅ 被接受" if ok else "❌ 失败", "" if ok else " err=%d" % e))
            results.append((v, ok, e))
            if not ok:
                print("        ⚠️ 写入未被接受 —— 后续步骤仍继续（以便观察是否部分生效）")
            print()
            try:
                ans = input("        ▶ 现在【用手指按压触控板】，然后描述感受 + 按回车继续：").strip()
            except EOFError:
                ans = ""
            if ans:
                print("        记录：%s" % ans)
    except KeyboardInterrupt:
        print("\n⚠️ 被中断 —— 立即进入收尾")
    finally:
        print()
        print("─" * 92)
        print("[收尾] 写回 0x09 = 100（强档），恢复默认手感")
        ok, e = set_haptic(h, 100)
        print("        SetFeature 返回：%s%s" % ("✅" if ok else "❌", "" if ok else " err=%d" % e))
        k32.CloseHandle(h)

    print()
    print("--- 后置健康检查 ---")
    health_check("后置")

    print()
    print("=" * 92)
    print("### 结果汇总")
    print("=" * 92)
    for v, ok, e in results:
        print("  0x09 = %-3d  写入%s%s" % (v, "被接受" if ok else "失败", "" if ok else " (err=%d)" % e))
    print()
    print("判读：")
    print("  · 若 0 档【完全静音】且 100 档【明显震】 ⇒ 『0x09 = 强度旋钮』在 Windows 上成立（把 2026-10-05 实证救回）")
    print("  · 若 0/50/100 三档【毫无区别】          ⇒ 本机 0x09 无效，与 goodhaptic 那台不同")
    print("  · 若 SetFeature 全部失败               ⇒ 写权限被拦（需管理员/需禁 Col03）")
    print()
    print("★ 本测试全程不落盘：最坏情况 = 设置被重置，重启设备即恢复默认。")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
