// RawTouchProbe.cs — 用户态 Raw Input 精确式触控板探针
// 目的：验证 Windows 精确式触控板(PTP)的原始多点报文能否被普通用户态程序读取
// 用法：Add-Type 加载后 RawTouchProbe.Start(); RawTouchProbe.Pump(ms); RawTouchProbe.Drain();
#pragma warning disable 0649, 0169
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;

public static class RawTouchProbe
{
    public static readonly ConcurrentQueue<string> Log = new ConcurrentQueue<string>();
    static void L(string s) { Log.Enqueue(s); }

    const int WM_INPUT = 0x00FF;
    const uint RIDEV_INPUTSINK = 0x00000100;
    const uint RID_INPUT = 0x10000003;
    const uint RIDI_DEVICENAME = 0x20000007;
    const uint RIDI_DEVICEINFO = 0x2000000b;
    const uint RIDI_PREPARSEDDATA = 0x20000005;
    const int HIDP_INPUT = 0;
    const int HIDP_STATUS_SUCCESS = 0x00110000;

    [StructLayout(LayoutKind.Sequential)]
    public struct RAWINPUTDEVICE { public ushort usUsagePage; public ushort usUsage; public uint dwFlags; public IntPtr hwndTarget; }

    [StructLayout(LayoutKind.Sequential)]
    struct RAWINPUTHEADER { public uint dwType; public uint dwSize; public IntPtr hDevice; public IntPtr wParam; }

    [StructLayout(LayoutKind.Sequential)]
    struct MSG { public IntPtr hwnd; public uint message; public IntPtr wParam; public IntPtr lParam; public uint time; public int ptX; public int ptY; }

    [StructLayout(LayoutKind.Sequential)]
    struct HIDP_CAPS
    {
        public ushort Usage, UsagePage, InputReportByteLength, OutputReportByteLength, FeatureReportByteLength;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 17)] public ushort[] Reserved;
        public ushort NumberLinkCollectionNodes, NumberInputButtonCaps, NumberInputValueCaps, NumberInputDataIndices;
        public ushort NumberOutputButtonCaps, NumberOutputValueCaps, NumberOutputDataIndices;
        public ushort NumberFeatureButtonCaps, NumberFeatureValueCaps, NumberFeatureDataIndices;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct HIDP_VALUE_CAPS
    {
        public ushort UsagePage; public byte ReportID; public byte IsAlias; public ushort BitField;
        public ushort LinkCollection, LinkUsage, LinkUsagePage;
        public byte IsRange, IsStringRange, IsDesignatorRange, IsAbsolute, HasNull, Reserved;
        public ushort BitSize, ReportCount;
        public ushort R1, R2, R3, R4, R5;
        public uint UnitsExp, Units;
        public int LogicalMin, LogicalMax, PhysicalMin, PhysicalMax;
        public ushort UsageMin, UsageMax, StringMin, StringMax, DesignatorMin, DesignatorMax, DataIndexMin, DataIndexMax;
    }

    [DllImport("user32.dll", SetLastError = true)]
    static extern bool RegisterRawInputDevices(RAWINPUTDEVICE[] pRawInputDevices, uint uiNumDevices, uint cbSize);
    [DllImport("user32.dll")]
    static extern uint GetRawInputData(IntPtr hRawInput, uint uiCommand, IntPtr pData, ref uint pcbSize, uint cbSizeHeader);
    [DllImport("user32.dll", EntryPoint = "GetRawInputDeviceInfoW", CharSet = CharSet.Unicode)]
    static extern uint GetRawInputDeviceInfo(IntPtr hDevice, uint uiCommand, IntPtr pData, ref uint pcbSize);
    [DllImport("user32.dll", EntryPoint = "GetRawInputDeviceInfoW", CharSet = CharSet.Unicode)]
    static extern uint GetRawInputDeviceInfoStr(IntPtr hDevice, uint uiCommand, StringBuilder pData, ref uint pcbSize);
    [DllImport("user32.dll")]
    static extern bool PeekMessage(out MSG msg, IntPtr hWnd, uint min, uint max, uint remove);
    [DllImport("user32.dll")]
    static extern bool TranslateMessage(ref MSG msg);
    [DllImport("user32.dll")]
    static extern IntPtr DispatchMessage(ref MSG msg);
    [DllImport("hid.dll")]
    static extern bool HidP_GetCaps(IntPtr pp, ref HIDP_CAPS caps);
    [DllImport("hid.dll")]
    static extern bool HidP_GetValueCaps(int reportType, [Out] HIDP_VALUE_CAPS[] caps, ref ushort len, IntPtr pp);
    [DllImport("hid.dll")]
    static extern int HidP_GetUsageValue(int reportType, ushort usagePage, ushort linkCollection, ushort usage,
        out uint value, IntPtr pp, IntPtr report, uint reportLength);
    [DllImport("hid.dll")]
    static extern int HidP_GetUsageValueArray(int reportType, ushort usagePage, ushort linkCollection, ushort usage,
        [Out] byte[] value, ushort valueLength, IntPtr pp, IntPtr report, uint reportLength);

    // ---- 自建隐藏窗口（不依赖 WinForms） ----
    delegate IntPtr WndProcDelegate(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct WNDCLASSEX
    {
        public uint cbSize; public uint style; public IntPtr lpfnWndProc; public int cbClsExtra; public int cbWndExtra;
        public IntPtr hInstance; public IntPtr hIcon; public IntPtr hCursor; public IntPtr hbrBackground;
        [MarshalAs(UnmanagedType.LPWStr)] public string lpszMenuName;
        [MarshalAs(UnmanagedType.LPWStr)] public string lpszClassName;
        public IntPtr hIconSm;
    }

    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern ushort RegisterClassEx(ref WNDCLASSEX lpwcx);
    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern IntPtr CreateWindowEx(uint dwExStyle, string lpClassName, string lpWindowName, uint dwStyle,
        int x, int y, int w, int h, IntPtr hWndParent, IntPtr hMenu, IntPtr hInstance, IntPtr lpParam);
    [DllImport("user32.dll")]
    static extern IntPtr DefWindowProc(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    static extern IntPtr GetModuleHandle(string lpModuleName);

    static WndProcDelegate _wndProc;   // 必须保持引用，防止 GC
    static IntPtr _hwnd = IntPtr.Zero;

    static IntPtr WndProcImpl(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam)
    {
        if (msg == WM_INPUT)
        {
            try { HandleRawInput(lParam); } catch (Exception ex) { L("EX " + ex.Message); }
            return IntPtr.Zero;
        }
        return DefWindowProc(hWnd, msg, wParam, lParam);
    }

    static readonly Dictionary<IntPtr, DevInfo> _devs = new Dictionary<IntPtr, DevInfo>();
    static int _lastContacts = -1;   // 用于与厂商通道报文对齐
    public static bool TraceMode = false;   // 轨迹模式：只输出紧凑触点轨迹，不输出原始报文
    public static int RawLimit = 200;       // 原始报文记录条数上限（可调）
    static int _lastTraceCount = -1;
    static long _lastTraceMs = 0;
    static int _maxPressureSeen = 0;
    static readonly Stopwatch _traceSw = Stopwatch.StartNew();

    class DevInfo
    {
        public string Path;
        public ushort UsagePage, Usage;
        public HIDP_CAPS Caps;
        public HIDP_VALUE_CAPS[] VCaps;
        public bool CapsLogged;
        public int Reports;
    }

    public static string Start(bool includeTouchscreen, bool includeMouse)
    {
        if (_hwnd != IntPtr.Zero) return "already-started";

        _wndProc = new WndProcDelegate(WndProcImpl);
        var wc = new WNDCLASSEX();
        wc.cbSize = (uint)Marshal.SizeOf(typeof(WNDCLASSEX));
        wc.style = 0;
        wc.lpfnWndProc = Marshal.GetFunctionPointerForDelegate(_wndProc);
        wc.hInstance = GetModuleHandle(null);
        wc.lpszClassName = "RawTouchProbeWnd";
        ushort atom = RegisterClassEx(ref wc);
        int rcErr = Marshal.GetLastWin32Error();
        L("RegisterClassEx atom=" + atom + " err=" + rcErr);

        _hwnd = CreateWindowEx(0x00000080 /*WS_EX_TOOLWINDOW*/, "RawTouchProbeWnd", "probe",
            0x80000000 /*WS_POPUP*/, -32000, -32000, 1, 1, IntPtr.Zero, IntPtr.Zero, wc.hInstance, IntPtr.Zero);
        L("CreateWindowEx hwnd=0x" + _hwnd.ToInt64().ToString("X") + " err=" + Marshal.GetLastWin32Error());
        if (_hwnd == IntPtr.Zero) return "no-window";

        var list = new List<RAWINPUTDEVICE>();
        if (includeTouchscreen)
        {
            list.Add(new RAWINPUTDEVICE { usUsagePage = 0x0D, usUsage = 0x05, dwFlags = RIDEV_INPUTSINK, hwndTarget = _hwnd }); // Touch Pad
            list.Add(new RAWINPUTDEVICE { usUsagePage = 0x0D, usUsage = 0x04, dwFlags = RIDEV_INPUTSINK, hwndTarget = _hwnd }); // Touch Screen
            list.Add(new RAWINPUTDEVICE { usUsagePage = 0x0D, usUsage = 0x02, dwFlags = RIDEV_INPUTSINK, hwndTarget = _hwnd }); // Pen
        }
        if (includeMouse)
            list.Add(new RAWINPUTDEVICE { usUsagePage = 0x01, usUsage = 0x02, dwFlags = RIDEV_INPUTSINK, hwndTarget = _hwnd });
        var devs = list.ToArray();
        bool ok = RegisterRawInputDevices(devs, (uint)devs.Length, (uint)Marshal.SizeOf(typeof(RAWINPUTDEVICE)));
        L("RegisterRawInputDevices ok=" + ok + " err=" + Marshal.GetLastWin32Error() + " count=" + devs.Length);
        return ok ? "registered" : "failed";
    }

    static DevInfo GetDev(IntPtr h)
    {
        DevInfo d;
        if (_devs.TryGetValue(h, out d)) return d;
        d = new DevInfo();
        _devs[h] = d;

        // device path
        uint sz = 0;
        GetRawInputDeviceInfo(h, RIDI_DEVICENAME, IntPtr.Zero, ref sz);
        if (sz > 0)
        {
            var sb = new StringBuilder((int)sz + 2);
            uint sz2 = sz;
            GetRawInputDeviceInfoStr(h, RIDI_DEVICENAME, sb, ref sz2);
            d.Path = sb.ToString();
        }
        if (string.IsNullOrEmpty(d.Path)) d.Path = "<unknown>";

        // usage page / usage
        uint infoSize = 0;
        GetRawInputDeviceInfo(h, RIDI_DEVICEINFO, IntPtr.Zero, ref infoSize);
        IntPtr ib = Marshal.AllocHGlobal((int)infoSize);
        try
        {
            Marshal.WriteInt32(ib, (int)infoSize);
            uint got = infoSize;
            if (GetRawInputDeviceInfo(h, RIDI_DEVICEINFO, ib, ref got) != unchecked((uint)-1))
            {
                d.UsagePage = (ushort)Marshal.ReadInt16(ib, 16);
                d.Usage = (ushort)Marshal.ReadInt16(ib, 18);
            }
        }
        finally { Marshal.FreeHGlobal(ib); }

        // preparsed data + caps
        uint ppSize = 0;
        GetRawInputDeviceInfo(h, RIDI_PREPARSEDDATA, IntPtr.Zero, ref ppSize);
        IntPtr pp = Marshal.AllocHGlobal((int)ppSize);
        try
        {
            uint got = ppSize;
            if (GetRawInputDeviceInfo(h, RIDI_PREPARSEDDATA, pp, ref got) != unchecked((uint)-1))
            {
                var caps = new HIDP_CAPS();
                caps.Reserved = new ushort[17];
                if (HidP_GetCaps(pp, ref caps))
                {
                    d.Caps = caps;
                    ushort n = caps.NumberInputValueCaps;
                    if (n > 0)
                    {
                        var arr = new HIDP_VALUE_CAPS[n];
                        if (HidP_GetValueCaps(HIDP_INPUT, arr, ref n, pp)) d.VCaps = arr;
                    }
                }
            }
        }
        finally { Marshal.FreeHGlobal(pp); }

        L("DEV hDevice=0x" + h.ToInt64().ToString("X") + " up=0x" + d.UsagePage.ToString("X2") + " u=0x" + d.Usage.ToString("X2"));
        L("    path=" + d.Path);
        if (d.Caps.Usage != 0 || d.Caps.UsagePage != 0)
        {
            L(string.Format("    caps: up=0x{0:X2} u=0x{1:X2} inLen={2} outLen={3} featLen={4} linkNodes={5} inValCaps={6}",
                d.Caps.UsagePage, d.Caps.Usage, d.Caps.InputReportByteLength, d.Caps.OutputReportByteLength,
                d.Caps.FeatureReportByteLength, d.Caps.NumberLinkCollectionNodes, d.Caps.NumberInputValueCaps));
        }
        if (d.VCaps != null)
        {
            foreach (var c in d.VCaps)
            {
                ushort usage = c.UsageMin;
                L(string.Format("    VCAP rid={0} up=0x{1:X2} u=0x{2:X2} lc={3}(up=0x{4:X2},u=0x{5:X2}) bits={6} cnt={7} log=[{8},{9}] abs={10}",
                    c.ReportID, c.UsagePage, usage, c.LinkCollection, c.LinkUsagePage, c.LinkUsage,
                    c.BitSize, c.ReportCount, c.LogicalMin, c.LogicalMax, c.IsAbsolute));
            }
        }
        return d;
    }

    static void HandleRawInput(IntPtr lParam)
    {
        uint size = 0;
        uint hdrSize = (uint)Marshal.SizeOf(typeof(RAWINPUTHEADER));
        GetRawInputData(lParam, RID_INPUT, IntPtr.Zero, ref size, hdrSize);
        if (size == 0) { L("GetRawInputData size=0 err=" + Marshal.GetLastWin32Error()); return; }
        IntPtr buf = Marshal.AllocHGlobal((int)size);
        try
        {
            uint got = size;
            if (GetRawInputData(lParam, RID_INPUT, buf, ref got, hdrSize) != size) { L("GetRawInputData mismatch"); return; }
            var hdr = (RAWINPUTHEADER)Marshal.PtrToStructure(buf, typeof(RAWINPUTHEADER));
            if (hdr.dwType != 2) { return; } // only RIM_TYPEHID
            int off = Marshal.SizeOf(typeof(RAWINPUTHEADER));
            uint sizeHid = (uint)Marshal.ReadInt32(buf, off);
            uint count = (uint)Marshal.ReadInt32(buf, off + 4);
            byte[] data = new byte[sizeHid];
            Marshal.Copy(buf + off + 8, data, 0, (int)sizeHid);

            var d = GetDev(hdr.hDevice);
            d.Reports++;

            if (!TraceMode)
            {
                if (d.Reports <= RawLimit)
                {
                    var hex = new StringBuilder();
                    foreach (byte b in data) hex.Append(b.ToString("X2")).Append(' ');
                    L(string.Format("RPT dev=0x{0:X} up=0x{1:X2} u=0x{2:X2} len={3} cnt={4} data= {5}",
                        hdr.hDevice.ToInt64(), d.UsagePage, d.Usage, sizeHid, count, hex.ToString().Trim()));
                }
                else if (d.Reports == RawLimit + 1) L("... (raw dumps truncated)");
            }

            if (d.Path != null && d.Path.IndexOf("Col04", StringComparison.OrdinalIgnoreCase) >= 0) return;
            Decode(d, data, hdr.hDevice, d.Reports <= RawLimit || d.Reports % 20 == 0);
        }
        finally { Marshal.FreeHGlobal(buf); }
    }

    static void Decode(DevInfo d, byte[] data, IntPtr hDevice, bool verbose)
    {
        // 重新取 preparsed data（解码用）
        uint ppSize = 0;
        GetRawInputDeviceInfo(hDevice, RIDI_PREPARSEDDATA, IntPtr.Zero, ref ppSize);
        if (ppSize == 0) return;
        IntPtr pp = Marshal.AllocHGlobal((int)ppSize);
        IntPtr rep = Marshal.AllocHGlobal(data.Length);
        try
        {
            uint got = ppSize;
            if (GetRawInputDeviceInfo(hDevice, RIDI_PREPARSEDDATA, pp, ref got) == unchecked((uint)-1)) return;
            Marshal.Copy(data, 0, rep, data.Length);
            if (d.VCaps == null) return;
            byte rid = data.Length > 0 ? data[0] : (byte)0;
            // 按 link collection 归组
            // key = (usagePage<<16)|usageId —— 必须带 page，否则 0x01/0x30(X) 与 0x0D/0x30(压力) 会互相覆盖
            var lc = new SortedDictionary<ushort, Dictionary<int, int>>();
            int nOk = 0, nFail = 0;
            foreach (var c in d.VCaps)
            {
                if (c.ReportID != 0 && c.ReportID != rid) continue;
                if (c.IsRange != 0) continue;
                uint v;
                int st = HidP_GetUsageValue(HIDP_INPUT, c.UsagePage, c.LinkCollection, c.UsageMin, out v, pp, rep, (uint)data.Length);
                if (st == HIDP_STATUS_SUCCESS)
                {
                    nOk++;
                    if (!lc.ContainsKey(c.LinkCollection)) lc[c.LinkCollection] = new Dictionary<int, int>();
                    lc[c.LinkCollection][(c.UsagePage << 16) | c.UsageMin] = (int)v;
                }
                else nFail++;
            }
            if (verbose && nFail > 0) L("    decode: ok=" + nOk + " fail=" + nFail + " rid=" + rid);
            // —— 轨迹模式：输出紧凑触点轨迹（接触数变化 或 有接触且距上次 ≥40ms）——
            if (TraceMode)
            {
                int tc = 0;
                if (lc.ContainsKey(0)) lc[0].TryGetValue((0x0D << 16) | 0x54, out tc);
                long now = _traceSw.ElapsedMilliseconds;
                bool changed = tc != _lastTraceCount;
                if (changed || (tc > 0 && now - _lastTraceMs >= 40))
                {
                    _lastTraceCount = tc;
                    _lastTraceMs = now;
                    var sb2 = new StringBuilder();
                    sb2.Append("[TRACE] t=").Append(_traceSw.Elapsed.TotalSeconds.ToString("F3")).Append("s n=").Append(tc);
                    for (ushort k = 1; k <= 5; k++)
                    {
                        Dictionary<int, int> m;
                        if (!lc.TryGetValue(k, out m)) continue;
                        int x, y, p, id;
                        m.TryGetValue((0x01 << 16) | 0x30, out x);
                        m.TryGetValue((0x01 << 16) | 0x31, out y);
                        m.TryGetValue((0x0D << 16) | 0x30, out p);
                        m.TryGetValue((0x0D << 16) | 0x51, out id);
                        if (x == 0 && y == 0 && p == 0) continue;
                        sb2.Append(" [").Append(id).Append(":x").Append(x).Append(" y").Append(y).Append(" p").Append(p).Append(']');
                        if (p > _maxPressureSeen)
                        {
                            _maxPressureSeen = p;
                            L("[MAXP] 压力峰值 p=" + p + " @" + _traceSw.Elapsed.TotalSeconds.ToString("F3") + "s");
                        }
                    }
                    L(sb2.ToString());
                }
                return;
            }

            // 接触数变化 → 输出一行，便于和厂商通道报文按时间对齐
            int cc;
            if (lc.ContainsKey(0) && lc[0].TryGetValue((0x0D << 16) | 0x54, out cc) && cc != _lastContacts)
            {
                _lastContacts = cc;
                L("[TOUCH] contacts=" + cc);
            }

            var parts = new List<string>();
            foreach (var kv in lc)
            {
                var sb = new StringBuilder("LC" + kv.Key + "(");
                foreach (var u in kv.Value)
                {
                    sb.Append("0x").Append((u.Key >> 16).ToString("X2")).Append('/')
                      .Append((u.Key & 0xFFFF).ToString("X2")).Append('=').Append(u.Value).Append(' ');
                }
                sb.Append(')');
                parts.Add(sb.ToString());
            }
            L("    -> " + string.Join(" | ", parts.ToArray()));
        }
        finally { Marshal.FreeHGlobal(pp); Marshal.FreeHGlobal(rep); }
    }

    public static int Pump(int ms)
    {
        var sw = Stopwatch.StartNew();
        int n = 0; MSG m;
        while (sw.ElapsedMilliseconds < ms)
        {
            while (PeekMessage(out m, IntPtr.Zero, 0, 0, 1)) { TranslateMessage(ref m); DispatchMessage(ref m); n++; }
            System.Threading.Thread.Sleep(1);
        }
        return n;
    }

    public static string[] Drain()
    {
        var list = new List<string>();
        string s;
        while (Log.TryDequeue(out s)) list.Add(s);
        return list.ToArray();
    }
}

