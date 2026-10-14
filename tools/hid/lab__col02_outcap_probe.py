"""Col02 OUTPUT 能力实证 —— Windows 侧「到底能不能发出去」的**一次性实证**

背景（2026-10-14）：
  项目对 Col02 只做过 SET_FEATURE（HidD_SetFeature，RID 2/6/9）与 GET_FEATURE 读。
  **从未发过 OUTPUT 报告**（Col02 的 OutputReportByteLength = 0）。
  本工具把「Windows 侧到底拦不拦」这件事**用实测钉死**，而不是靠推理。

它做什么：
  1. 枚举 Col01–Col04，打印每个集合的 HidP_GetCaps（in/out/feat 长度、报告数）
  2. dump 每个集合的**原始报告描述符**（HidD_GetPreparsedData / HidP_GetReportDescriptor 不可用时退化为 caps）
  3. 【需显式开关】在 **Col02** 的句柄上逐个 RID 调 HidD_SetOutputReport，**载荷恒为全 0x00**，
     只记录 (返回值, GetLastError)。载荷全零 ⇒ **不携带任何命令语义**（不会被解释成 flash 操作）。

它【不做】什么：
  · 绝不向 Col04 发任何东西（Col04 是命令通道，本项目在此出过事故）
  · 绝不写 flash（0x0E 12 / 00 10 / 00 11 一律不碰）
  · 不做任何值变化扫描（那是 lab__brute.py 的事，且 cmdscan/classscan 已上锁）

风险等级：**零—低**。
  · 若 Windows 校验描述符（预期如此，因 out=0）⇒ 全部返回 FALSE / err=87，总线上什么都没发。
  · 即便 Windows 放行，载荷全零也只对应「命令码 0x00」，而 0x00 在厂商 DLL 的命令表里是**已声明合法**的条目。

用法：
    python lab__col02_outcap_probe.py                 # 只看 caps + 描述符（纯只读）
    python lab__col02_outcap_probe.py --try-output    # 追加 OUTPUT 报告实证（需管理员）
"""
import ctypes, os, sys, json, time
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


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", ctypes.c_ushort), ("UsagePage", ctypes.c_ushort),
        ("InputReportByteLength", ctypes.c_ushort), ("OutputReportByteLength", ctypes.c_ushort),
        ("FeatureReportByteLength", ctypes.c_ushort),
        ("Reserved", ctypes.c_ushort * 17),
        ("NumberLinkCollectionNodes", ctypes.c_ushort), ("NumberInputButtonCaps", ctypes.c_ushort),
        ("NumberInputValueCaps", ctypes.c_ushort), ("NumberInputDataIndices", ctypes.c_ushort),
        ("NumberOutputButtonCaps", ctypes.c_ushort), ("NumberOutputValueCaps", ctypes.c_ushort),
        ("NumberOutputDataIndices", ctypes.c_ushort), ("NumberFeatureButtonCaps", ctypes.c_ushort),
        ("NumberFeatureValueCaps", ctypes.c_ushort), ("NumberFeatureDataIndices", ctypes.c_ushort),
    ]


setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), ctypes.c_wchar_p, ctypes.c_void_p, wintypes.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID),
                                                 wintypes.DWORD, ctypes.POINTER(SP_DID)]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DID), ctypes.c_void_p,
                                                     wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                                     ctypes.POINTER(SP_DEVINFO_DATA)]
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
k32.CreateFileW.restype = ctypes.c_void_p
k32.CreateFileW.argtypes = [ctypes.c_wchar_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                            wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
k32.CloseHandle.argtypes = [ctypes.c_void_p]
hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]
hid.HidD_GetPreparsedData.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
hid.HidD_GetPreparsedData.restype = wintypes.BOOL
hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
hid.HidP_GetCaps.restype = ctypes.c_long
hid.HidD_SetOutputReport.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
hid.HidD_SetOutputReport.restype = wintypes.BOOL

GENERIC_RW = 0xC0000000
OPEN_EXISTING = 3
FILE_SHARE_RW = 3

OUT_PAYLOAD = 65          # Col04 是 65；Col02 若 out>0 也用这个做上界
LOG = []


def log(m):
    print(m)
    LOG.append(m)


def enum_hid():
    g = GUID(); hid.HidD_GetHidGuid(ctypes.byref(g))
    hdev = setupapi.SetupDiGetClassDevsW(ctypes.byref(g), None, None, 0x12)
    out, i = [], 0
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
        out.append(ctypes.wstring_at(ctypes.addressof(buf) + 4))
    setupapi.SetupDiDestroyDeviceInfoList(hdev)
    return out


def open_h(path, acc=GENERIC_RW):
    h = k32.CreateFileW(path, acc, FILE_SHARE_RW, None, OPEN_EXISTING, 0, None)
    if h and h != 0xFFFFFFFFFFFFFFFF:
        return h
    return None


def read_desc(path):
    """读原始报告描述符（HidD_GetPreparsedData 不含描述符本体，改读注册表/直接看 caps）。
    这里退化为：只报告 caps；若想拿原始字节请用项目已有的 poc/hid-dump。"""
    h = open_h(path, 0)
    if not h:
        return None
    pp = ctypes.c_void_p()
    caps = None
    if hid.HidD_GetPreparsedData(h, ctypes.byref(pp)):
        c = HIDP_CAPS()
        if hid.HidP_GetCaps(pp, ctypes.byref(c)) >= 0:
            caps = c
        hid.HidD_FreePreparsedData(pp)
    k32.CloseHandle(h)
    return caps


def main():
    want_try = "--try-output" in sys.argv
    here = os.path.dirname(os.path.abspath(__file__))
    outdir = os.path.join(here, "col02-outcap-probe")
    os.makedirs(outdir, exist_ok=True)

    paths = [p for p in enum_hid() if "gxtp5100" in p.lower()]
    if not paths:
        log("未找到 GXTP5100 的 HID 接口。"); return

    log("=" * 78)
    log("Col02 OUTPUT 能力实证 —— %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    log("=" * 78)

    targets = {}
    for p in paths:
        col = "?"
        low = p.lower()
        for c in ("col01", "col02", "col03", "col04"):
            if c in low:
                col = c.upper()
        caps = read_desc(p)
        if caps:
            log("\n[%s] %s" % (col, os.path.basename(p)))
            log("   usagePage=0x%04X usage=0x%04X" % (caps.UsagePage, caps.Usage))
            log("   IN=%d  OUT=%d  FEATURE=%d" % (caps.InputReportByteLength,
                                                  caps.OutputReportByteLength,
                                                  caps.FeatureReportByteLength))
            log("   report counts: inBtn=%d inVal=%d | outBtn=%d outVal=%d | featBtn=%d featVal=%d" % (
                caps.NumberInputButtonCaps, caps.NumberInputValueCaps,
                caps.NumberOutputButtonCaps, caps.NumberOutputValueCaps,
                caps.NumberFeatureButtonCaps, caps.NumberFeatureValueCaps))
            targets[col] = (p, caps)

    col02 = targets.get("COL02")
    if not col02:
        log("\n没有定位到 Col02（PTP 集合）。"); return
    p2, c2 = col02

    log("\n" + "-" * 78)
    log("Col02 的 OUT = %d  ⇒ %s" % (
        c2.OutputReportByteLength,
        "描述符里【没有任何输出报】⇒ Windows 预期会拒绝一切 SetOutputReport" if c2.OutputReportByteLength == 0
        else "存在输出报，值得解析 RID 归属"))

    if not want_try:
        log("\n（当前为只读模式。要追加 OUTPUT 报告实证，请加 --try-output 并以管理员运行。）")
        log("  实证内容：在 Col02 句柄上逐个 RID 调 HidD_SetOutputReport，载荷恒为全 0x00，")
        log("  只记录 (返回, GetLastError)，不改任何设备状态。")
    else:
        log("\n" + "-" * 78)
        log("OUTPUT 报告实证（载荷恒为全 0x00 —— 不携带命令语义）")
        # 待试 RID：已声明的 feature RID + Col04 的命令 RID + 未声明的低位
        rids = [0x02, 0x06, 0x09, 0x0B, 0x0C, 0x0D, 0x0E, 0x00, 0x01, 0x03, 0x0F, 0x10]
        h = open_h(p2)
        if not h:
            log("  打开 Col02 失败（需要管理员？）"); return
        results = {}
        for rid in rids:
            buf = (ctypes.c_ubyte * OUT_PAYLOAD)()
            buf[0] = rid                      # 载荷其余全 0
            ctypes.set_last_error(0)
            ok = hid.HidD_SetOutputReport(h, buf, OUT_PAYLOAD)
            err = ctypes.get_last_error()
            results["0x%02X" % rid] = {"ok": bool(ok), "err": err}
            log("   RID=0x%02X → %-5s  GetLastError=%d %s" % (
                rid, "OK" if ok else "FALSE", err,
                "(ERROR_INVALID_PARAMETER ⇒ Windows 按描述符拦下，报文未发出)" if err == 87 else ""))
            time.sleep(0.15)
        k32.CloseHandle(h)
        json.dump(results, open(os.path.join(outdir, "outcap_result.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

    open(os.path.join(outdir, "outcap_log.txt"), "w", encoding="utf-8").write("\n".join(LOG))
    log("\n完成。结果目录: %s" % outdir)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback; traceback.print_exc()
        input("按回车退出…")
