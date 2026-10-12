#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lab__r15_newton_status.py —— 照搬 edimetia3d/GoodixNewtonTouchpad 的 status 逻辑

来源（逐字照搬其判据，不改动）：
    edimetia3d/GoodixNewtonTouchpad / Hid.cs
      - Enumerate()      : SetupDiGetClassDevs(DIGCF_PRESENT|DEVICEINTERFACE) + HidD_GetHidGuid
      - ReadDescriptor() : CreateFile(path, access=0, share=3, OPEN_EXISTING)  ← 只查询，不申请读写
                           HidD_GetAttributes + HidD_GetPreparsedData + HidP_GetCaps
      - IsTarget()       : Vid==0x27C6 && Pid==0x0F9A
                           && UsagePage==0xFF00 && Usage==1
                           && InputLength==9 && OutputLength==9 && FeatureLength==0
      - SelectTarget()   : matches.Count() 必须 == 1，否则抛异常
      - status 子命令    : 只枚举 + 打印，hardwareState = "unverified-no-readback"

★ 本工具是【纯只读】：
    - 不发 Output Report
    - 不调 HidD_SetFeature
    - 不写任何设备
  仅把 Newton 的匹配判据套到本机所有 HID 集合上，输出"像不像 / 差在哪"。

用法：
    python lab__r15_newton_status.py            # 人类可读
    python lab__r15_newton_status.py --json     # 机器可读
"""

import ctypes
import json
import sys
from ctypes import wintypes

hid = ctypes.WinDLL("hid.dll")
setupapi = ctypes.WinDLL("setupapi.dll")
kernel32 = ctypes.WinDLL("kernel32.dll")

# ---- Newton 的常量（逐字照搬） ----
PRESENT_DEVICE_INTERFACES = 0x12          # DIGCF_PRESENT | DIGCF_DEVICEINTERFACE
SHARE_READ_WRITE = 3
OPEN_EXISTING = 3
HID_SUCCESS = 0x110000                    # HIDP_STATUS_SUCCESS
NO_MORE_ITEMS = 259                       # ERROR_NO_MORE_ITEMS
INSUFFICIENT_BUFFER = 122

# ---- Newton 的 IsTarget 判据（逐字照搬，含其 0F9A） ----
NEWTON_VID = 0x27C6
NEWTON_PID = 0x0F9A
NEWTON_USAGE_PAGE = 0xFF00
NEWTON_USAGE = 0x0001
NEWTON_REPORT_LEN = 9
NEWTON_FEATURE_LEN = 0


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Size", wintypes.ULONG), ("VendorID", wintypes.USHORT),
                ("ProductID", wintypes.USHORT), ("VersionNumber", wintypes.USHORT)]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", wintypes.USHORT), ("UsagePage", wintypes.USHORT),
        ("InputReportByteLength", wintypes.USHORT),
        ("OutputReportByteLength", wintypes.USHORT),
        ("FeatureReportByteLength", wintypes.USHORT),
        ("Reserved", wintypes.USHORT * 17),
        ("NumberLinkCollectionNodes", wintypes.USHORT),
        ("NumberInputButtonCaps", wintypes.USHORT),
        ("NumberInputValueCaps", wintypes.USHORT),
        ("NumberInputDataIndices", wintypes.USHORT),
        ("NumberOutputButtonCaps", wintypes.USHORT),
        ("NumberOutputValueCaps", wintypes.USHORT),
        ("NumberOutputDataIndices", wintypes.USHORT),
        ("NumberFeatureButtonCaps", wintypes.USHORT),
        ("NumberFeatureValueCaps", wintypes.USHORT),
        ("NumberFeatureDataIndices", wintypes.USHORT),
    ]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("InterfaceClassGuid", GUID),
                ("Flags", wintypes.DWORD), ("Reserved", ctypes.POINTER(wintypes.ULONG))]


hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]
hid.HidD_GetAttributes.argtypes = [wintypes.HANDLE, ctypes.POINTER(HIDD_ATTRIBUTES)]
hid.HidD_GetAttributes.restype = wintypes.BOOL
hid.HidD_GetPreparsedData.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
hid.HidD_GetPreparsedData.restype = wintypes.BOOL
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
hid.HidP_GetCaps.restype = ctypes.c_long
hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
hid.HidD_FreePreparsedData.restype = wintypes.BOOL

setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), wintypes.LPCWSTR,
                                        ctypes.c_void_p, wintypes.DWORD]
setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID),
    wintypes.DWORD, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
    ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
    ctypes.c_void_p]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL

kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                ctypes.c_void_p]
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


def read_descriptor(path):
    """照搬 Newton ReadDescriptor()：access=0 只查询，不申请读写。"""
    h = kernel32.CreateFileW(path, 0, SHARE_READ_WRITE, None, OPEN_EXISTING, 0, None)
    if not h or h == INVALID_HANDLE_VALUE:
        return None
    try:
        attrs = HIDD_ATTRIBUTES()
        attrs.Size = ctypes.sizeof(attrs)
        if not hid.HidD_GetAttributes(h, ctypes.byref(attrs)):
            return None
        pp = ctypes.c_void_p()
        if not hid.HidD_GetPreparsedData(h, ctypes.byref(pp)):
            return None
        try:
            caps = HIDP_CAPS()
            if hid.HidP_GetCaps(pp, ctypes.byref(caps)) != HID_SUCCESS:
                return None
            return {
                "path": path,
                "vid": attrs.VendorID,
                "pid": attrs.ProductID,
                "usage_page": caps.UsagePage,
                "usage": caps.Usage,
                "in_len": caps.InputReportByteLength,
                "out_len": caps.OutputReportByteLength,
                "feat_len": caps.FeatureReportByteLength,
                "n_in_vcaps": caps.NumberInputValueCaps,
                "n_out_vcaps": caps.NumberOutputValueCaps,
                "n_feat_vcaps": caps.NumberFeatureValueCaps,
            }
        finally:
            hid.HidD_FreePreparsedData(pp)
    finally:
        kernel32.CloseHandle(h)


def enumerate_all():
    """照搬 Newton Enumerate()。"""
    guid = GUID()
    hid.HidD_GetHidGuid(ctypes.byref(guid))
    info = setupapi.SetupDiGetClassDevsW(ctypes.byref(guid), None, None,
                                         PRESENT_DEVICE_INTERFACES)
    if not info or info == INVALID_HANDLE_VALUE:
        raise OSError("SetupDiGetClassDevs failed")
    out = []
    try:
        idx = 0
        while True:
            did = SP_DEVICE_INTERFACE_DATA()
            did.cbSize = ctypes.sizeof(did)
            if not setupapi.SetupDiEnumDeviceInterfaces(info, None, ctypes.byref(guid),
                                                       idx, ctypes.byref(did)):
                err = ctypes.get_last_error() if hasattr(ctypes, "get_last_error") else 0
                if err == NO_MORE_ITEMS or idx > 0:
                    break
                break
            idx += 1
            needed = wintypes.DWORD(0)
            setupapi.SetupDiGetDeviceInterfaceDetailW(info, ctypes.byref(did), None, 0,
                                                      ctypes.byref(needed), None)
            if needed.value < 8:
                continue
            buf = ctypes.create_string_buffer(needed.value)
            ctypes.memmove(buf, ctypes.byref(wintypes.DWORD(8)), 4)
            if not setupapi.SetupDiGetDeviceInterfaceDetailW(info, ctypes.byref(did), buf,
                                                            needed.value,
                                                            ctypes.byref(needed), None):
                continue
            path = ctypes.wstring_at(ctypes.addressof(buf) + 4)
            d = read_descriptor(path)
            if d:
                # Newton 的 ReadDescriptor 只收 HID 集合；这里同样只保留能读出 caps 的
                d["is_target"] = newton_is_target(d)
                out.append(d)
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(info)
    return out


def newton_is_target(d):
    """照搬 Newton IsTarget() —— 判据一字不改。"""
    return (d["vid"] == NEWTON_VID and d["pid"] == NEWTON_PID
            and d["usage_page"] == NEWTON_USAGE_PAGE and d["usage"] == NEWTON_USAGE
            and d["in_len"] == NEWTON_REPORT_LEN
            and d["out_len"] == NEWTON_REPORT_LEN
            and d["feat_len"] == NEWTON_FEATURE_LEN)


def diff_report(d):
    """给出"差在哪"——这不是 Newton 的代码，是本工具加的诊断。"""
    diffs = []
    if d["vid"] != NEWTON_VID:
        diffs.append("VID %04X != %04X" % (d["vid"], NEWTON_VID))
    if d["pid"] != NEWTON_PID:
        diffs.append("PID %04X != %04X" % (d["pid"], NEWTON_PID))
    if d["usage_page"] != NEWTON_USAGE_PAGE:
        diffs.append("UsagePage %04X != %04X" % (d["usage_page"], NEWTON_USAGE_PAGE))
    if d["usage"] != NEWTON_USAGE:
        diffs.append("Usage %04X != %04X" % (d["usage"], NEWTON_USAGE))
    if d["in_len"] != NEWTON_REPORT_LEN:
        diffs.append("InputLen %d != %d" % (d["in_len"], NEWTON_REPORT_LEN))
    if d["out_len"] != NEWTON_REPORT_LEN:
        diffs.append("OutputLen %d != %d" % (d["out_len"], NEWTON_REPORT_LEN))
    if d["feat_len"] != NEWTON_FEATURE_LEN:
        diffs.append("FeatureLen %d != %d" % (d["feat_len"], NEWTON_FEATURE_LEN))
    return diffs


def main():
    as_json = "--json" in sys.argv
    devices = enumerate_all()

    goodix = [d for d in devices if d["vid"] == NEWTON_VID]
    targets = [d for d in devices if d["is_target"]]

    if as_json:
        print(json.dumps({
            "total_hid_collections": len(devices),
            "goodix_27C6_collections": len(goodix),
            "newton_is_target_matches": len(targets),
            "select_target_would_throw": len(targets) != 1,
            "hardware_state": "unverified-no-readback",
            "goodix": goodix,
        }, ensure_ascii=False, indent=2))
        return

    print("=" * 88)
    print("### Newton status 照搬 —— 只读，不发包")
    print("=" * 88)
    print("  来源：edimetia3d/GoodixNewtonTouchpad / Hid.cs")
    print("  IsTarget 判据：VID/PID 27C6/0F9A · UP/Usage FF00/0001 · In/Out 9/9 · Feature 0")
    print()
    print("  本机 HID 集合总数            = %d" % len(devices))
    print("  本机 VID==27C6 的集合数      = %d" % len(goodix))
    print("  ★ 满足 Newton IsTarget 的数量 = %d" % len(targets))
    print()
    print("  Newton SelectTarget() 要求 count == 1：")
    if len(targets) == 1:
        print("    => 通过（本机恰有 1 个匹配）")
    else:
        print("    => ★ 会抛异常：Expected exactly one compatible Goodix HID collection; "
              "found %d" % len(targets))
    print()
    print("  hardwareState = unverified-no-readback   （Newton 原文，无读回命令）")
    print()

    if not goodix:
        print("  ⚠ 本机没有 VID==27C6 的 HID 集合")
        return

    print("-" * 88)
    print("### 本机 27C6 集合逐条对照 Newton 判据")
    print("-" * 88)
    for i, d in enumerate(goodix, 1):
        tag = "✅ target" if d["is_target"] else "❌ 不匹配"
        print("  [%d] %s  PID=%04X  UP/Usage=%04X/%04X  In/Out/Feat=%d/%d/%d"
              % (i, tag, d["pid"], d["usage_page"], d["usage"],
                 d["in_len"], d["out_len"], d["feat_len"]))
        print("      vcaps In/Out/Feat = %d/%d/%d"
              % (d["n_in_vcaps"], d["n_out_vcaps"], d["n_feat_vcaps"]))
        if not d["is_target"]:
            for line in diff_report(d):
                print("      ✗ 差在：%s" % line)
        print()
    print("=" * 88)
    print("★ 本工具未发送任何数据。Newton 的成功指标也只是『传输完成』，")
    print("  它自己写明：does not prove that the hardware retained the value。")
    print("=" * 88)


if __name__ == "__main__":
    main()
