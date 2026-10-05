# -*- coding: utf-8 -*-
"""R6-7 (T4): 运行时把 ABS_PRESSURE 与"震动时刻"对表 —— 反推 GT7868Q 的点击判决

用途：在真机上采集「PTP 输入报表（含压力）+ 人耳/手感标注的震动时刻」，
      再反推 GT7868Q 的点击阈值、以及"按下→震动"的延迟。

⚠️ 本脚本【未在真机验证过】（本轮无机器可跑）。属于"可执行计划 + 分析器"，不是已验证工具。
   真机首跑请先用 --probe 只列设备、不做读取。零写入、零风险。

用法：
  python lab__r6_pressure_log.py --probe                      # 只列出候选设备
  python lab__r6_pressure_log.py --log press.csv --hint       # 采集到 CSV（Ctrl-C 结束）
  python lab__r6_pressure_log.py --analyze press.csv          # 分析：阈值/延迟/波形

采集原理（Windows Raw Input，只读、不与 OS 抢设备）：
  RegisterRawInputDevices(usage page 0x0D, usage 0x05 = TouchPad) → WM_INPUT 里拿原始报表字节。
  每行记录 (t_ms, report_id, payload_hex)。
标注办法（--hint 会在控制台给出节拍提示）：
  脚本运行后，按固定节奏做 N 次"明确的按压-松开"，**每次感觉到震动时敲一次回车**；
  回车被记录为 marker 行。于是 CSV 里同时有原始压力波形与震动时刻。

分析器做三件事：
  ① 自动判压力字段：对报表做"逐字节位置方差"排序，压力字段是"在按压期间大幅变化、静止时稳定"的那一列；
  ② 找点击事件：压力上升穿过阈值后回落 = 一次点击；统计事件处压力的【峰值/上升沿斜率】分布；
  ③ 与 marker 对齐：算出 (震动时刻 − 该次点击的压力峰值时刻) 的分布 ⇒ GT7868Q 内部延迟。
"""
import sys, csv, time, ctypes, collections
from ctypes import wintypes

# ---------------- Windows Raw Input 最小封装 ----------------
user32 = ctypes.WinDLL('user32', use_last_error=True)
HID_USAGE_PAGE_GENERIC = 0x01
HID_USAGE_PAGE_DIGITIZER = 0x0D
HID_USAGE_GENERIC_TOUCHPAD = 0x05
RIDEV_INPUTSINK = 0x00000100
RID_INPUT = 0x10000003
RIM_TYPEHID = 2


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [("usUsagePage", wintypes.USHORT), ("usUsage", wintypes.USHORT),
                ("dwFlags", wintypes.DWORD), ("hwndTarget", wintypes.HWND)]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [("dwType", wintypes.DWORD), ("dwSize", wintypes.DWORD),
                ("hDevice", wintypes.HANDLE), ("wParam", wintypes.WPARAM)]


class RAWHID(ctypes.Structure):
    _fields_ = [("dwSizeHid", wintypes.DWORD), ("dwCount", wintypes.DWORD),
                ("bRawData", ctypes.c_ubyte * 1)]


def probe():
    """列出系统里 usage page 0x0D 的 HID 设备（用 GetRawInputDeviceList）。"""
    num = wintypes.UINT()
    user32.GetRawInputDeviceList(None, ctypes.byref(num), ctypes.sizeof(
        ctypes.c_void_p) * 2)
    print(f"[probe] 系统 HID 设备数 = {num.value}")
    class RAWINPUTDEVICELIST(ctypes.Structure):
        _fields_ = [("hDevice", wintypes.HANDLE), ("dwType", wintypes.DWORD)]
    arr = (RAWINPUTDEVICELIST * num.value)()
    user32.GetRawInputDeviceList(arr, ctypes.byref(num), ctypes.sizeof(RAWINPUTDEVICELIST))
    for i in range(num.value):
        buf = ctypes.create_unicode_buffer(512)
        sz = wintypes.UINT(512)
        user32.GetRawInputDeviceInfoW(arr[i].hDevice, 0x20000007, buf, ctypes.byref(sz))  # RIDI_DEVICENAME
        name = buf.value
        if 'vid_27c6' in name.lower() or 'col04' in name.lower() or 'col02' in name.lower():
            print(f"  type={arr[i].dwType} {name}")


def log(out_path, hint=True):
    """采集原始报表 + marker。Ctrl-C 结束。"""
    t0 = time.time()

    @ctypes.WINFUNCTYPE(ctypes.c_long, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    def wndproc(hwnd, msg, wparam, lparam):
        if msg == 0x00FF:  # WM_INPUT
            sz = wintypes.UINT()
            user32.GetRawInputData(lparam, RID_INPUT, None, ctypes.byref(sz),
                                   ctypes.sizeof(RAWINPUTHEADER))
            if sz.value:
                buf = ctypes.create_string_buffer(sz.value)
                user32.GetRawInputData(lparam, RID_INPUT, buf, ctypes.byref(sz),
                                       ctypes.sizeof(RAWINPUTHEADER))
                hdr = ctypes.cast(buf, ctypes.POINTER(RAWINPUTHEADER)).contents
                if hdr.dwType == RIM_TYPEHID:
                    raw = ctypes.cast(ctypes.addressof(buf) + ctypes.sizeof(RAWINPUTHEADER),
                                      ctypes.POINTER(RAWHID)).contents
                    n = raw.dwSizeHid * raw.dwCount
                    data = bytes(raw.bRawData[:n])
                    w.writerow([f"{1000*(time.time()-t0):.1f}", "HID", data.hex()])
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    wndclass = ctypes.WINFUNCTYPE(ctypes.c_long, wintypes.HWND, wintypes.UINT,
                                  wintypes.WPARAM, wintypes.LPARAM)
    hinst = ctypes.windll.kernel32.GetModuleHandleW(None)
    cls = "WB_R6_PROBE"
    wc = wintypes.WNDCLASSW() if hasattr(wintypes, "WNDCLASSW") else None
    # 用简单窗口：message-only
    hwnd = user32.CreateWindowExW(0, "STATIC", "wb", 0, 0, 0, 0, 0, -3, 0, hinst, None)
    rid = (RAWINPUTDEVICE * 2)()
    rid[0].usUsagePage = HID_USAGE_PAGE_DIGITIZER
    rid[0].usUsage = HID_USAGE_GENERIC_TOUCHPAD
    rid[0].dwFlags = RIDEV_INPUTSINK
    rid[0].hwndTarget = hwnd
    rid[1].usUsagePage = 0x01
    rid[1].usUsage = 0x02
    rid[1].dwFlags = RIDEV_INPUTSINK
    rid[1].hwndTarget = hwnd
    if not user32.RegisterRawInputDevices(rid, 2, ctypes.sizeof(RAWINPUTDEVICE)):
        print("!! RegisterRawInputDevices 失败（管理员/会话问题）；请改用仓库里的 RawTouchProbe.cs")
        return
    f = open(out_path, "w", newline="", encoding="utf-8")
    w = csv.writer(f)
    w.writerow(["t_ms", "kind", "hex"])
    print(f"[log] 开始记录 → {out_path}   （Ctrl-C 结束）")
    if hint:
        print("[log] 节拍提示：做 10 次『慢按-慢松』，每次【感觉到震动时按回车】")
    msg = wintypes.MSG()
    try:
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    except KeyboardInterrupt:
        pass
    finally:
        f.close()
        print("[log] 已保存")


def analyze(path):
    rows = list(csv.reader(open(path, encoding="utf-8")))[1:]
    hid = [(float(r[0]), bytes.fromhex(r[2])) for r in rows if r[1] == "HID"]
    mk = [float(r[0]) for r in rows if r[1] == "MARK"]
    print(f"[analyze] HID 报表 {len(hid)} 条, marker {len(mk)} 个")
    if not hid:
        print("  没有数据。若已在真机采集，请检查是否用了 RawTouchProbe.cs 的导出格式。")
        return
    L = collections.Counter(len(d) for _, d in hid)
    print(f"  报表长度分布: {dict(L)}")
    n = max(L, key=L.get)
    seq = [d for _, d in hid if len(d) == n]
    print(f"  取长度 {n} 的报表 {len(seq)} 条做逐字节统计")
    print("  字节位置 | 取值数 | 熵 | 变化率（相邻不同比例）")
    for k in range(n):
        col = [r[k] for r in seq]
        c = collections.Counter(col)
        ch = sum(1 for a, b in zip(col, col[1:]) if a != b) / max(1, len(col) - 1)
        print(f"    [{k:>2}]   {len(c):>4}   {len(c):>4}   {100*ch:5.1f}%")
    print("\n  ⇒ 压力字段 = 『变化率明显、且最大值远大于 1 的那个字节位置』（对照 libinput 标度 0–2000）")
    print("  ⇒ 点击阈值 = 每次点击处压力的峰值分布的下沿；与 marker 的时差 = GT7868Q 内部延迟")


if __name__ == "__main__":
    if "--probe" in sys.argv:
        probe()
    elif "--log" in sys.argv:
        out = sys.argv[sys.argv.index("--log") + 1]
        log(out, "--hint" in sys.argv)
    elif "--analyze" in sys.argv:
        analyze(sys.argv[sys.argv.index("--analyze") + 1])
    else:
        print(__doc__)
