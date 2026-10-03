// VendorListen.cs — 只读监听 Goodix 厂商通道 (Col04) 的输入报文
// 安全约束：仅 CreateFile(GENERIC_READ) + ReadFile，绝不写入任何数据
#pragma warning disable 0649, 0169
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

public static class VendorListen
{
    public static readonly ConcurrentQueue<string> Log = new ConcurrentQueue<string>();
    static void L(string s) { Log.Enqueue(s); }

    [StructLayout(LayoutKind.Sequential)]
    struct RAWINPUTDEVICELIST { public IntPtr hDevice; public uint dwType; }

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
    struct OVERLAPPED { public IntPtr Internal; public IntPtr InternalHigh; public uint Offset; public uint OffsetHigh; public IntPtr hEvent; }

    [DllImport("user32.dll")]
    static extern uint GetRawInputDeviceList([Out] RAWINPUTDEVICELIST[] pRawInputDeviceList, ref uint puiNumDevices, uint cbSize);
    [DllImport("user32.dll", EntryPoint = "GetRawInputDeviceInfoW", CharSet = CharSet.Unicode)]
    static extern uint GetRawInputDeviceInfoStr(IntPtr hDevice, uint uiCommand, StringBuilder pData, ref uint pcbSize);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern IntPtr CreateFileW(string lpFileName, uint dwDesiredAccess, uint dwShareMode,
        IntPtr lpSecurityAttributes, uint dwCreationDisposition, uint dwFlagsAndAttributes, IntPtr hTemplateFile);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool ReadFile(IntPtr hFile, byte[] lpBuffer, uint nNumberOfBytesToRead, IntPtr lpNumberOfBytesRead, ref OVERLAPPED lpOverlapped);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool GetOverlappedResult(IntPtr hFile, ref OVERLAPPED lpOverlapped, out uint lpNumberOfBytesTransferred, bool bWait);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool CancelIo(IntPtr hFile);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern IntPtr CreateEvent(IntPtr lpEventAttributes, bool bManualReset, bool bInitialState, string lpName);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern uint WaitForSingleObject(IntPtr hHandle, uint dwMilliseconds);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool CloseHandle(IntPtr hObject);
    [DllImport("hid.dll")]
    static extern bool HidP_GetCaps(IntPtr pp, ref HIDP_CAPS caps);
    [DllImport("hid.dll")]
    static extern bool HidD_GetPreparsedData(IntPtr h, out IntPtr pp);
    [DllImport("hid.dll")]
    static extern bool HidD_FreePreparsedData(IntPtr pp);

    const uint GENERIC_READ = 0x80000000;
    const uint FILE_SHARE_READ = 1, FILE_SHARE_WRITE = 2, OPEN_EXISTING = 3;
    const uint FILE_FLAG_OVERLAPPED = 0x40000000;
    const uint ERROR_IO_PENDING = 997;
    const uint WAIT_OBJECT_0 = 0, WAIT_TIMEOUT = 258;

    static Thread _th;
    static volatile bool _run;
    static IntPtr _h = IntPtr.Zero;
    public static int ReportCount;
    public static int TimeoutCount;
    public static string DevicePath = "";

    public static string Start(string filter, string collection)
    {
        uint n = 0, sz = (uint)Marshal.SizeOf(typeof(RAWINPUTDEVICELIST));
        GetRawInputDeviceList(null, ref n, sz);
        if (n == 0) return "no-devices";
        var arr = new RAWINPUTDEVICELIST[n];
        GetRawInputDeviceList(arr, ref n, sz);
        string path = null;
        foreach (var d in arr)
        {
            if (d.dwType != 2) continue;
            uint s = 0;
            GetRawInputDeviceInfoStr(d.hDevice, 0x20000007, null, ref s);
            if (s == 0) continue;
            var sb = new StringBuilder((int)s + 2);
            uint s2 = s;
            GetRawInputDeviceInfoStr(d.hDevice, 0x20000007, sb, ref s2);
            string p = sb.ToString();
            if (p.IndexOf(filter, StringComparison.OrdinalIgnoreCase) >= 0 &&
                p.IndexOf(collection, StringComparison.OrdinalIgnoreCase) >= 0) { path = p; break; }
        }
        if (path == null) return "device-not-found";
        DevicePath = path;

        _h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, IntPtr.Zero, OPEN_EXISTING, FILE_FLAG_OVERLAPPED, IntPtr.Zero);
        if (_h == IntPtr.Zero || _h.ToInt64() == -1)
        {
            int e = Marshal.GetLastWin32Error(); _h = IntPtr.Zero;
            return "open-failed err=" + e;
        }
        L("opened READ-ONLY: " + path);

        IntPtr pp;
        if (HidD_GetPreparsedData(_h, out pp))
        {
            var caps = new HIDP_CAPS(); caps.Reserved = new ushort[17];
            if (HidP_GetCaps(pp, ref caps))
                L(string.Format("caps: inLen={0} outLen={1} featLen={2} topUsagePage=0x{3:X2} topUsage=0x{4:X2}",
                    caps.InputReportByteLength, caps.OutputReportByteLength, caps.FeatureReportByteLength, caps.UsagePage, caps.Usage));
            HidD_FreePreparsedData(pp);
        }

        _run = true;
        _th = new Thread(Loop);
        _th.IsBackground = true;
        _th.Start();
        return "listening";
    }

    public static void Stop() { _run = false; }

    static void Loop()
    {
        IntPtr ev = CreateEvent(IntPtr.Zero, false, false, null);
        var ov = new OVERLAPPED(); ov.hEvent = ev;
        var buf = new byte[256];
        var sw = System.Diagnostics.Stopwatch.StartNew();
        double lastIdleLog = 0;
        while (_run)
        {
            bool ok = ReadFile(_h, buf, (uint)buf.Length, IntPtr.Zero, ref ov);
            int err = Marshal.GetLastWin32Error();
            if (!ok && err != ERROR_IO_PENDING) { L("ReadFile failed err=" + err); break; }

            uint w = WaitForSingleObject(ev, 1000);
            if (w == WAIT_TIMEOUT)
            {
                CancelIo(_h);
                WaitForSingleObject(ev, 500);
                TimeoutCount++;
                double t = sw.Elapsed.TotalSeconds;
                if (t - lastIdleLog >= 30.0)
                {
                    L(string.Format("[idle {0:F0}s] reports={1} 累计空闲秒数={2}", t, ReportCount, TimeoutCount));
                    lastIdleLog = t;
                }
                continue;
            }
            if (w != WAIT_OBJECT_0) { L("wait failed w=" + w); break; }
            uint got;
            if (!GetOverlappedResult(_h, ref ov, out got, false)) { L("GetOverlappedResult failed err=" + Marshal.GetLastWin32Error()); break; }
            if (got == 0) continue;

            ReportCount++;
            var sb = new StringBuilder();
            uint lim = got > 80 ? 80 : got;
            for (uint i = 0; i < lim; i++) sb.Append(buf[i].ToString("X2")).Append(' ');
            L(string.Format("[VENDOR #{0}] t={1:F3}s len={2} :: {3}", ReportCount, sw.Elapsed.TotalSeconds, got, sb.ToString().Trim()));
        }
        if (_h != IntPtr.Zero) { CloseHandle(_h); _h = IntPtr.Zero; }
        CloseHandle(ev);
        L("loop exited");
    }

    public static string[] Drain()
    {
        var list = new List<string>();
        string s;
        while (Log.TryDequeue(out s)) list.Add(s);
        return list.ToArray();
    }
}
