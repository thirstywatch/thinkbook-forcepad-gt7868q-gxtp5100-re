"""Col02 feature 精确读取（禁用 PTP 驱动 → 按声明长度逐 RID 读 → 自动恢复设备）

背景：write-only 句柄能打开 Col02 且 GET_FEATURE 成功，但读到的内容与请求的 RID 无关
     （疑似被 PTP/类驱动路由到同一 feature 页）。
     本脚本临时禁用该 HID 设备，让驱动松手后再按各 RID 的声明长度精确读取，最后**必定**恢复。

需要管理员权限。执行期间触控板不可用，脚本结束会自动恢复。
"""
import ctypes, sys, time, os, hashlib, json, traceback
from ctypes import wintypes

setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
hid = ctypes.WinDLL("hid", use_last_error=True)
k32 = ctypes.WinDLL("kernel32", use_last_error=True)


class GUID(ctypes.Structure):
    _fields_ = [("D1", ctypes.c_ulong), ("D2", ctypes.c_ushort), ("D3", ctypes.c_ushort),
                ("D4", ctypes.c_ubyte * 8)]


class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("ClassGuid", GUID), ("DevInst", wintypes.DWORD),
                ("Reserved", ctypes.c_void_p)]


class SP_DID(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("InterfaceClassGuid", GUID), ("Flags", wintypes.DWORD),
                ("R", ctypes.c_void_p)]


class PCH(ctypes.Structure):
    """SP_PROPCHANGE_PARAMS"""
    _fields_ = [("cbSize", wintypes.DWORD), ("InstallFunction", wintypes.DWORD),
                ("StateChange", wintypes.DWORD), ("Scope", wintypes.DWORD), ("HwProfile", wintypes.DWORD)]


setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), ctypes.c_wchar_p, ctypes.c_void_p, wintypes.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID),
                                                 wintypes.DWORD, ctypes.POINTER(SP_DID)]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DID), ctypes.c_void_p,
                                                      wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                                      ctypes.POINTER(SP_DEVINFO_DATA)]
setupapi.SetupDiSetClassInstallParamsW.restype = wintypes.BOOL
setupapi.SetupDiSetClassInstallParamsW.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DEVINFO_DATA),
                                                   ctypes.POINTER(PCH), wintypes.DWORD]
setupapi.SetupDiCallClassInstaller.restype = wintypes.BOOL
setupapi.SetupDiCallClassInstaller.argtypes = [wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(SP_DEVINFO_DATA)]
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
k32.CreateFileW.restype = ctypes.c_void_p
k32.CreateFileW.argtypes = [ctypes.c_wchar_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                            wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
k32.CloseHandle.argtypes = [ctypes.c_void_p]
k32.GetCurrentProcess.restype = ctypes.c_void_p
hid.HidD_GetFeature.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
hid.HidD_GetFeature.restype = wintypes.BOOL
hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]

DIF_PROPERTYCHANGE = 0x12
DICS_ENABLE, DICS_DISABLE = 0x01, 0x02
DICS_FLAG_GLOBAL = 0x01
GENERIC_RW = 0xC0000000

DECLARED = {2: 1, 6: 256, 9: 1, 11: 66, 12: 736, 13: 4}   # RID -> 声明数据长度
UNKNOWN = {7: None}                                        # 长度未知 → 扫描


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


KNOWN_PATH = None


def load_known_path():
    """从 hid_devices.json 里取 gxtp5100 col02 的精确路径（更稳）"""
    try:
        j = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hid_devices.json")
        for r in json.load(open(j, encoding="utf-8")):
            p = r.get("path", "")
            if "gxtp5100" in p.lower() and "col02" in p.lower():
                return p
    except Exception:
        pass
    return None


def is_col02(path):
    """必须同时含 gxtp5100 与 col02（避免误伤 intc816&col02）"""
    low = path.lower()
    if KNOWN_PATH:
        return low == KNOWN_PATH.lower()
    return ("gxtp5100" in low) and ("col02" in low)


def enum_col02():
    """返回 [(path, SP_DEVINFO_DATA)]"""
    g = GUID(); hid.HidD_GetHidGuid(ctypes.byref(g))
    hdev = setupapi.SetupDiGetClassDevsW(ctypes.byref(g), None, None, 0x12)
    out = []
    i = 0
    while True:
        d = SP_DID(); d.cbSize = ctypes.sizeof(d)
        if not setupapi.SetupDiEnumDeviceInterfaces(hdev, None, ctypes.byref(g), i, ctypes.byref(d)):
            break
        i += 1
        need = wintypes.DWORD(0)
        setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(d), None, 0, ctypes.byref(need), None)
        buf = ctypes.create_string_buffer(need.value)
        ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0] = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
        di = SP_DEVINFO_DATA(); di.cbSize = ctypes.sizeof(di)
        if not setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(d), buf, need.value, None, ctypes.byref(di)):
            continue
        p = ctypes.wstring_at(ctypes.addressof(buf) + 4)
        if is_col02(p):
            out.append((p, di))
    setupapi.SetupDiDestroyDeviceInfoList(hdev)
    return out


def change_state(pair, enable):
    path, di = pair
    g = GUID(); hid.HidD_GetHidGuid(ctypes.byref(g))
    hdev = setupapi.SetupDiGetClassDevsW(ctypes.byref(g), None, None, 0x12)
    # 必须传与 hdev 同源的 DevInfoData：重新枚举取一份
    i = 0
    while True:
        d = SP_DID(); d.cbSize = ctypes.sizeof(d)
        if not setupapi.SetupDiEnumDeviceInterfaces(hdev, None, ctypes.byref(g), i, ctypes.byref(d)):
            break
        i += 1
        need = wintypes.DWORD(0)
        setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(d), None, 0, ctypes.byref(need), None)
        buf = ctypes.create_string_buffer(need.value)
        ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0] = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
        di2 = SP_DEVINFO_DATA(); di2.cbSize = ctypes.sizeof(di2)
        if not setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(d), buf, need.value, None, ctypes.byref(di2)):
            continue
        p = ctypes.wstring_at(ctypes.addressof(buf) + 4)
        if not is_col02(p):
            continue
        ps = PCH()
        ps.cbSize = 8  # sizeof(SP_CLASSINSTALL_HEADER); ps.InstallFunction = DIF_PROPERTYCHANGE
        ps.StateChange = DICS_ENABLE if enable else DICS_DISABLE
        ps.Scope = DICS_FLAG_GLOBAL; ps.HwProfile = 0
        if not setupapi.SetupDiSetClassInstallParamsW(hdev, ctypes.byref(di2), ctypes.byref(ps), ctypes.sizeof(ps)):
            e = ctypes.get_last_error(); setupapi.SetupDiDestroyDeviceInfoList(hdev); return False, e
        if not setupapi.SetupDiCallClassInstaller(DIF_PROPERTYCHANGE, hdev, ctypes.byref(di2)):
            e = ctypes.get_last_error(); setupapi.SetupDiDestroyDeviceInfoList(hdev); return False, e
        setupapi.SetupDiDestroyDeviceInfoList(hdev)
        return True, 0
    setupapi.SetupDiDestroyDeviceInfoList(hdev)
    return False, -1


def open_any(path):
    for acc in (GENERIC_RW, 0x40000000, 0x80000000, 0):
        h = k32.CreateFileW(path, acc, 3, None, 3, 0, None)
        if h and h != 0xFFFFFFFFFFFFFFFF:
            return h, acc
    return None, None


def main():
    global KNOWN_PATH
    KNOWN_PATH = load_known_path()
    here = os.path.dirname(os.path.abspath(__file__))
    outdir = os.path.join(here, "col02-precise")
    os.makedirs(outdir, exist_ok=True)
    print("输出目录: %s" % outdir)
    print("管理员: %s" % is_admin())

    pairs = enum_col02()
    if not pairs:
        print("未找到 Col02 接口"); return
    path, _ = pairs[0]
    print("Col02: %s" % path.split("#")[1])

    print("\n[1/3] 禁用设备 …")
    ok, err = change_state(pairs[0], enable=False)
    print("      %s%s" % ("成功" if ok else "失败(err=%d)" % err,
                          "" if ok else "  ← 若失败，请手动在设备管理器里禁用「HID-compliant touch pad」的 Col02 设备后重跑"))
    time.sleep(2.0)

    try:
        print("\n[2/3] 读取 …")
        pairs2 = enum_col02()
        p2 = pairs2[0][0] if pairs2 else path
        h, acc = open_any(p2)
        print("      句柄: %s access=0x%X" % ("OK" if h else "失败", acc or 0))
        if not h:
            print("      → 读不到（可能设备真的消失了，属正常）"); return
        summary = {}
        # 全 RID 扫描：RID 0..24 × 缓冲 {2, 257, 737}
        for rid in range(0, 25):
            for L in (2, 257, 737):
                buf = (ctypes.c_ubyte * 737)()
                for i in range(737): buf[i] = 0xEE
                buf[0] = rid
                ctypes.set_last_error(0)
                r = hid.HidD_GetFeature(h, buf, L)
                e = ctypes.get_last_error()
                if r:
                    d = bytes(buf[:L])
                    md5 = hashlib.md5(d).hexdigest()[:12]
                    # 有效数据长度 = 连续非 0xEE 前缀长度
                    eff = 0
                    while eff < len(d) and d[eff] != 0xEE: eff += 1
                    open(os.path.join(outdir, "rid%02d_len%d.bin" % (rid, L)), "wb").write(d)
                    print("      RID=%-3d len=%-4d OK 有效%3d md5=%s 头12: %s" % (
                        rid, L, eff, md5, " ".join("%02X" % c for c in d[:12])))
                    key = "%d_%d" % (rid, L)
                    summary[key] = {"rid": rid, "len": L, "eff": eff, "md5": md5, "head": d[:16].hex()}
                else:
                    print("      RID=%-3d len=%-4d -- err=%d" % (rid, L, e))
        open(os.path.join(outdir, "summary.json"), "w", encoding="utf-8").write(
            json.dumps(summary, ensure_ascii=False, indent=1))
        k32.CloseHandle(h)
    except Exception:
        traceback.print_exc()
    finally:
        print("\n[3/3] 恢复设备（必定执行）…")
        ok2, err2 = change_state(pairs[0], enable=True)
        print("      %s%s" % ("成功" if ok2 else "失败(err=%d)" % err2, ""))
        time.sleep(1.0)
        print("      复查: %s" % ("接口已回来 ✔" if enum_col02() else "接口未回来 ✘（请手动在设备管理器启用）"))

    print("\n完成。结果在: %s" % outdir)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        input("按回车退出…")
