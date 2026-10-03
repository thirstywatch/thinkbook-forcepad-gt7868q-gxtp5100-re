"""Col02 写入语义对照实验（读 → 写回 → 再读）

目的：判定 Col02 的**写（SetFeature）是否按 RID 路由**（读已知不按）。
  - RID 2：读得到 `02 15`（1 字节参数）。先"同值回写"，再"改 +1"，看能否读回变化。
  - RID 9：项目认定它是 Haptics Intensity（曾写入过）。同值回写 10，再看 RID2/RID6 是否变化。
  - **不写 RID 6 那 256 字节页**（内容像签名/密钥，乱写风险不可控）。

安全设计：禁用设备前先读基线；每步写后立刻读回；**结尾把所有已知值恢复**；`finally` 里无条件恢复设备。
需要管理员权限。执行期间触控板不可用。
"""
import ctypes, sys, time, os, json, hashlib, traceback
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
hid.HidD_GetFeature.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
hid.HidD_GetFeature.restype = wintypes.BOOL
hid.HidD_SetFeature.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
hid.HidD_SetFeature.restype = wintypes.BOOL
hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]

DIF_PROPERTYCHANGE = 0x12
DICS_ENABLE, DICS_DISABLE = 0x01, 0x02
DICS_FLAG_GLOBAL = 0x01
GENERIC_RW = 0xC0000000
MAXLEN = 737

KNOWN_PATH = None
LOG = []


def log(msg):
    print(msg)
    LOG.append(msg)


def load_known_path():
    try:
        j = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hid_devices.json")
        for r in json.load(open(j, encoding="utf-8")):
            p = r.get("path", "")
            if "gxtp5100" in p.lower() and "col02" in p.lower():
                return p
    except Exception:
        pass
    return None


def is_col02(p):
    low = p.lower()
    if KNOWN_PATH:
        return low == KNOWN_PATH.lower()
    return ("gxtp5100" in low) and ("col02" in low)


def enum_col02():
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


def change_state(enable):
    g = GUID(); hid.HidD_GetHidGuid(ctypes.byref(g))
    hdev = setupapi.SetupDiGetClassDevsW(ctypes.byref(g), None, None, 0x12)
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
        if not is_col02(p):
            continue
        ps = PCH(); ps.cbSize = 8  # sizeof(SP_CLASSINSTALL_HEADER); ps.InstallFunction = DIF_PROPERTYCHANGE
        ps.StateChange = DICS_ENABLE if enable else DICS_DISABLE
        ps.Scope = DICS_FLAG_GLOBAL; ps.HwProfile = 0
        if not setupapi.SetupDiSetClassInstallParamsW(hdev, ctypes.byref(di), ctypes.byref(ps), ctypes.sizeof(ps)):
            e = ctypes.get_last_error(); setupapi.SetupDiDestroyDeviceInfoList(hdev); return False, e
        if not setupapi.SetupDiCallClassInstaller(DIF_PROPERTYCHANGE, hdev, ctypes.byref(di)):
            e = ctypes.get_last_error(); setupapi.SetupDiDestroyDeviceInfoList(hdev); return False, e
        setupapi.SetupDiDestroyDeviceInfoList(hdev)
        return True, 0
    setupapi.SetupDiDestroyDeviceInfoList(hdev)
    return False, -1


def open_h(path):
    for acc in (GENERIC_RW, 0x40000000, 0):
        h = k32.CreateFileW(path, acc, 3, None, 3, 0, None)
        if h and h != 0xFFFFFFFFFFFFFFFF:
            return h, acc
    return None, None


def rd(h, rid, L=MAXLEN):
    buf = (ctypes.c_ubyte * L)()
    for i in range(L): buf[i] = 0xEE
    buf[0] = rid
    ctypes.set_last_error(0)
    ok = hid.HidD_GetFeature(h, buf, L)
    return (bytes(buf), None) if ok else (None, ctypes.get_last_error())


def wr(h, rid, payload):
    """payload 不含 RID"""
    L = 1 + len(payload)
    buf = (ctypes.c_ubyte * L)()
    buf[0] = rid
    for i, v in enumerate(payload): buf[1 + i] = v
    ctypes.set_last_error(0)
    ok = hid.HidD_SetFeature(h, buf, L)
    return ok, ctypes.get_last_error()


def main():
    global KNOWN_PATH
    KNOWN_PATH = load_known_path()
    here = os.path.dirname(os.path.abspath(__file__))
    outdir = os.path.join(here, "col02-writeprobe")
    os.makedirs(outdir, exist_ok=True)
    log("输出目录: %s" % outdir)

    if not enum_col02():
        log("未找到 Col02"); return

    log("\n[1/4] 禁用设备 …")
    ok, err = change_state(enable=False)
    log("      %s%s" % ("成功" if ok else "失败(err=%d)" % err, ""))
    time.sleep(2.0)

    result = {}
    try:
        h, acc = open_h((enum_col02() or [(None, None)])[0][0] if enum_col02() else "")
        log("      句柄: %s access=0x%X" % ("OK" if h else "失败", acc or 0))
        if not h:
            return

        log("\n[2/4] 读基线（RID 2 / 6 / 9）")
        base = {}
        for rid in (2, 6, 9):
            d, e = rd(h, rid)
            base[rid] = d
            log("      RID=%-3d %s" % (rid, ("md5=%s 头8=%s" % (hashlib.md5(d).hexdigest()[:12],
                                                              " ".join("%02X" % c for c in d[:8]))) if d else "err=%d" % e))

        log("\n[3/4] 写入对照")
        # --- RID 2：先同值回写，再改 +1 ---
        v = base[2][1] if base[2] else 0x15
        log("      RID=2 原值 0x%02X" % v)
        okw, ew = wr(h, 2, [v])
        log("        同值回写 [0x%02X] → %s err=%d" % (v, "True" if okw else "False", ew))
        time.sleep(0.3)
        d2, _ = rd(h, 2)
        log("        读回: %s%s" % (" ".join("%02X" % c for c in d2[:4]) if d2 else "读失败",
                                    "  ← 与基线相同" if d2 and d2[:2] == base[2][:2] else "  ← ★ 与基线不同"))
        result["rid2_same_write"] = {"ok": bool(okw), "err": ew, "readback": d2[:4].hex() if d2 else None}

        newv = (v + 1) & 0xFF
        okw2, ew2 = wr(h, 2, [newv])
        log("        改值写入 [0x%02X] → %s err=%d" % (newv, "True" if okw2 else "False", ew2))
        time.sleep(0.3)
        d3, _ = rd(h, 2)
        changed = bool(d3 and d3[1] == newv)
        log("        读回: %s   %s" % (" ".join("%02X" % c for c in d3[:4]) if d3 else "读失败",
                                       "★★ 写入生效（RID 2 是可写参数！）" if changed else "未变化（写入未生效）"))
        result["rid2_changed_write"] = {"ok": bool(okw2), "err": ew2, "readback": d3[:4].hex() if d3 else None,
                                        "effective": changed}
        # 恢复
        okw3, ew3 = wr(h, 2, [v])
        log("        恢复 [0x%02X] → %s" % (v, "True" if okw3 else "False"))
        time.sleep(0.2)
        d4, _ = rd(h, 2)
        log("        恢复后读回: %s" % (" ".join("%02X" % c for c in d4[:4]) if d4 else "读失败"))
        result["rid2_restore"] = {"ok": bool(okw3), "readback": d4[:4].hex() if d4 else None}

        # --- RID 9：按项目用法写 1 字节（已知良好值 10），看别处是否变化 ---
        okw9, ew9 = wr(h, 9, [10])
        log("      RID=9 写入 [0x0A]（项目已知良好值）→ %s err=%d" % ("True" if okw9 else "False", ew9))
        time.sleep(0.3)
        for rid in (2, 6, 9):
            d, e = rd(h, rid)
            if d:
                same = (base[rid] is not None and d[:257] == base[rid][:257])
                log("        写后 RID=%-3d md5=%s %s" % (rid, hashlib.md5(d).hexdigest()[:12],
                                                        "（与基线相同）" if same else "（★ 与基线不同！）"))
            else:
                log("        写后 RID=%-3d err=%d" % (rid, e))
        result["rid9_write"] = {"ok": bool(okw9), "err": ew9}
        k32.CloseHandle(h)
    except Exception:
        log(traceback.format_exc())
    finally:
        log("\n[4/4] 恢复设备 …")
        ok2, err2 = change_state(enable=True)
        log("      %s%s" % ("成功" if ok2 else "失败(err=%d)" % err2, ""))
        time.sleep(1.0)
        log("      复查: %s" % ("接口已回来 ✔" if enum_col02() else "接口未回来 ✘（请手动启用）"))

    open(os.path.join(outdir, "writeprobe_result.json"), "w", encoding="utf-8").write(
        json.dumps(result, ensure_ascii=False, indent=1))
    open(os.path.join(outdir, "writeprobe_log.txt"), "w", encoding="utf-8").write("\n".join(LOG))
    log("\n完成。结果目录: %s" % outdir)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        input("按回车退出…")
