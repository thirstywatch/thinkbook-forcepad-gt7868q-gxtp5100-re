# -*- coding: utf-8 -*-
"""feat_read.py — 读 Col02 全部 Feature 报告（只读实验）

背景：
  haptic_caps.py 测出 Col02（PTP 顶层集合, UP=0x0D/U=0x05）有 6 个 Feature 报告：
     RID=2  0x000D/0x0059 + 0x000D/0x0055   ->  2 字节
     RID=9  0x000E/0x0023 (Haptic Intensity) ->  2 字节
     RID=6  0xFF00/0x00C5  256 B x u8       -> 257 字节
     RID=11 0xFF00/0x00C7   66 B x u8       ->  67 字节   (= 65 + RID，与 Col04 载荷等长)
     RID=12 0xFF00/0x00C6  736 B x u8       -> 737 字节   (= FeatureReportByteLength)
     RID=13 0xFF00/0x00C4    4 B x u8       ->   5 字节
  AllCaps.cs 注释承认：RID 6/7/11/12/13 【从未被看过内容】。
  usage 0xC4..0xC7 连续编号 = 很可能是「命令 / 数据窗口 / 状态」一整套私有通道。

本脚本只做 GET_FEATURE（只读），不写任何东西。
用法： python feat_read.py
"""
import ctypes, sys, os, time
from ctypes import wintypes

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
INVALID = ctypes.c_void_p(-1).value
GUID_STR = "{4d1e55b2-f16f-11cf-88cb-001111000030}"

COL02 = ("\\\\?\\HID#GXTP5100&Col02#5&52a7aed&0&0001#" + GUID_STR)
COL03 = ("\\\\?\\HID#GXTP5100&Col03#5&52a7aed&0&0002#" + GUID_STR)
COL04 = ("\\\\?\\HID#GXTP5100&Col04#5&52a7aed&0&0003#" + GUID_STR)

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
hid = ctypes.WinDLL('hid', use_last_error=True)
k32.CreateFileW.restype = wintypes.HANDLE
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
hid.HidD_GetFeature.argtypes = [wintypes.HANDLE, ctypes.c_char_p, wintypes.ULONG]
hid.HidD_GetFeature.restype = wintypes.BOOLEAN
hid.HidD_SetFeature.argtypes = [wintypes.HANDLE, ctypes.c_char_p, wintypes.ULONG]
hid.HidD_SetFeature.restype = wintypes.BOOLEAN


def openp(path):
    """Col02 被 Windows PTP 驱动独占 (err=32) => 必须用 access=0 打开。
       HidD_GetFeature 走 IOCTL_HID_GET_FEATURE (FILE_ANY_ACCESS)，不需要读权限。"""
    for acc, sh, tag in (
        (0, 3, "acc=0"),
        (GENERIC_READ, 3, "acc=RD"),
        (GENERIC_READ | GENERIC_WRITE, 3, "acc=RW"),
    ):
        h = k32.CreateFileW(path, acc, sh, None, OPEN_EXISTING, 0, None)
        if h and h != INVALID:
            print("  [open] %s ok" % tag)
            return h
        print("  [open] %s err=%d" % (tag, ctypes.get_last_error()))
    return None


def hx(d, per=32):
    if not d:
        return ""
    return "\n".join("    " + " ".join("%02X" % b for b in d[i:i + per])
                     for i in range(0, len(d), per)) if len(d) > per else "    " + " ".join("%02X" % b for b in d)


def asc(d):
    return "".join(chr(b) if 32 <= b < 127 else "." for b in d)


def get_feature(h, rid, total, label):
    buf = ctypes.create_string_buffer(total)
    ctypes.memset(buf, 0, total)
    buf[0] = bytes([rid])
    t0 = time.time()
    ok = hid.HidD_GetFeature(h, ctypes.cast(buf, ctypes.c_char_p), total)
    err = ctypes.get_last_error()
    ms = (time.time() - t0) * 1000
    raw = buf.raw[:total]
    print("  RID=%-3d %-34s len=%-4d -> %s err=%-3d  %.0fms" % (
        rid, label, total, "OK" if ok else "FAIL", err, ms))
    if ok:
        print(hx(raw))
        print("    ascii: %s" % asc(raw))
    else:
        print("    %s" % hx(raw))
    print()
    return ok, raw


def main():
    print("=" * 78)
    print("Col02 Feature 读取（只读）")
    print("=" * 78)
    h = openp(COL02)
    if not h:
        print("open Col02 FAILED err=%d" % ctypes.get_last_error())
        return 1
    print("Col02 opened.\n")

    plan = [
        (2, 2, "0x0D/0x0059 + 0x0D/0x0055"),
        (9, 2, "0x0E/0x0023 HapticIntensity"),
        (13, 5, "0xFF00/0x00C4 (4B)"),
        (11, 67, "0xFF00/0x00C7 (66B)"),
        (6, 257, "0xFF00/0x00C5 (256B)"),
        (12, 737, "0xFF00/0x00C6 (736B)"),
    ]
    results = {}
    for rid, ln, lbl in plan:
        try:
            ok, raw = get_feature(h, rid, ln, lbl)
            results[rid] = raw if ok else None
        except Exception as e:
            print("  RID=%d EXCEPTION %r\n" % (rid, e))
        time.sleep(0.05)

    # 保存
    outdir = os.path.dirname(os.path.abspath(__file__))
    for rid, raw in results.items():
        if raw:
            fn = os.path.join(outdir, "feat_rid%02d.bin" % rid)
            with open(fn, "wb") as f:
                f.write(raw)
            print("  saved %s (%d B)" % (os.path.basename(fn), len(raw)))

    k32.CloseHandle(h)

    # Col03 RID 3
    print()
    print("=" * 78)
    print("Col03 Feature RID=3 (0x0D/0x0052, 2 bytes)")
    print("=" * 78)
    h3 = openp(COL03)
    if h3:
        get_feature(h3, 3, 3, "0x0D/0x0052 (2B)")
        k32.CloseHandle(h3)
    else:
        print("open Col03 FAILED err=%d" % ctypes.get_last_error())

    return 0


if __name__ == "__main__":
    sys.exit(main())
