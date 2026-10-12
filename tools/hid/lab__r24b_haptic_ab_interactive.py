#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lab__r24b_haptic_ab_interactive.py —— `0x09` A/B 验证【交互版，逐步等你】

与 lab__r24 的区别：
  - 每一步 write 后**停住等你输入**（输入文字 = 你的感受，直接回车 = 跳过）
  - 加了一个 `r` 命令：重发当前值（方便反复体会）
  - 顺序改为 **盲测友好**：默认 100 → 0 → 100 → 0（**只跳两个极端档**，
    排除中间档的干扰，直接看"能不能关掉震动"这个最硬的判据）

用法：
  python lab__r24b_haptic_ab_interactive.py
  在提示处输入你的感受后回车；输入 r 重发；输入 q 退出并收尾。
"""
import ctypes
import sys
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

GENERIC_WRITE = 0x40000000
INVALID = ctypes.c_void_p(-1).value
RID = 0x09

# ★ 只跳两个极端档：这是"能不能关掉震动"的最硬判据
SEQ = [
    (100, "强档"),
    (0,   "★ 零档（若完全不震 = 强度旋钮成立）"),
    (100, "回强档（确认可逆）"),
    (0,   "再回零档（复现性检查）"),
]


def find_col02():
    for p in r22.enum_paths():
        if 'gxtp5100' in p.lower() and 'col02' in p.lower():
            return p
    return None


def set_haptic(h, value):
    buf = (ctypes.c_ubyte * 2)()
    buf[0] = RID
    buf[1] = value & 0xFF
    ctypes.set_last_error(0)
    return bool(hd.HidD_SetFeature(h, buf, 2)), ctypes.get_last_error()


def main():
    path = find_col02()
    if not path:
        print("❌ 未找到 Col02")
        return 1
    h = k32.CreateFileW(path, GENERIC_WRITE, 3, None, 3, 0, None)
    if not h or h == INVALID:
        print("❌ 打开 Col02 失败 err=%d（若 err=5 需管理员）" % ctypes.get_last_error())
        return 1
    print("=" * 88)
    print("### `0x09` A/B 交互验证   （Col02 已打开 · 只写 0x09 · 不禁用任何设备）")
    print("=" * 88)
    print("步骤：读到提示后，用手指【按压触控板】，把感受打进去再回车。")
    print("      （直接回车 = 无感受；输入 r = 重发当前值；输入 q = 收尾退出）")
    print()

    log = []
    try:
        for i, (v, d) in enumerate(SEQ, 1):
            while True:
                ok, e = set_haptic(h, v)
                print("─" * 88)
                print("[%d/%d] 已写 0x09 = %-3d  (%s)   SetFeature %s"
                      % (i, len(SEQ), v, d, "✅被接受" if ok else "❌失败 err=%d" % e))
                print("        ▶ 按压触控板试试 → 输入感受后回车：", end="", flush=True)
                try:
                    ans = input().strip()
                except (EOFError, KeyboardInterrupt):
                    ans = "q"
                if ans.lower() == 'r':
                    print("        （重发 …）")
                    continue
                if ans.lower() == 'q':
                    raise StopIteration
                log.append((v, ans))
                break
    except StopIteration:
        pass
    finally:
        set_haptic(h, 100)
        k32.CloseHandle(h)
        print()
        print("─" * 88)
        print("[收尾] 已写回 0x09 = 100")

    print()
    print("=" * 88)
    print("### 记录")
    for v, a in log:
        print("  0x09=%-3d  → %s" % (v, a if a else "(无输入)"))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
