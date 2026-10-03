// HidWatch.cs — 同时只读监听同一设备的所有 HID 集合的输入报文
// 安全约束：仅 CreateFile(GENERIC_READ) + ReadFile，绝不写入任何数据
#pragma warning disable 0649, 0169
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

public static class HidWatch
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

    class Reader
    {
        public string Name; public IntPtr H; public Thread T; public volatile bool Run;
        public int Count; public int Timeouts; public double LastIdleLog;
    }

    static readonly List<Reader> _readers = new List<Reader>();
    static readonly System.Diagnostics.Stopwatch _sw = System.Diagnostics.Stopwatch.StartNew();

    static List<string> EnumPaths(string filter)
    {
        var res = new List<string>();
        uint n = 0, sz = (uint)Marshal.SizeOf(typeof(RAWINPUTDEVICELIST));
        GetRawInputDeviceList(null, ref n, sz);
        if (n == 0) return res;
        var arr = new RAWINPUTDEVICELIST[n];
        GetRawInputDeviceList(arr, ref n, sz);
        foreach (var d in arr)
        {
            // dwType: 0=鼠标 1=键盘 2=HID。触控板的鼠标集合(Col01)是 0，不能只匹配 2
            uint s = 0;
            GetRawInputDeviceInfoStr(d.hDevice, 0x20000007, null, ref s);
            if (s == 0) continue;
            var sb = new StringBuilder((int)s + 2);
            uint s2 = s;
            GetRawInputDeviceInfoStr(d.hDevice, 0x20000007, sb, ref s2);
            string p = sb.ToString();
            if (p.IndexOf(filter, StringComparison.OrdinalIgnoreCase) >= 0) res.Add(p);
        }
        return res;
    }

    /// <summary>对指定设备的每个集合各开一个只读句柄并起一个读取线程</summary>
    public static string StartMany(string filter, string[] collections)
    {
        var paths = EnumPaths(filter);
        var sb = new StringBuilder();
        foreach (var col in collections)
        {
            string path = null;
            foreach (var p in paths)
                if (p.IndexOf(col, StringComparison.OrdinalIgnoreCase) >= 0) { path = p; break; }

            if (path == null) { L("[W " + col + "] 原始输入枚举里没有这个集合"); sb.Append(col + ":not-found "); continue; }

            IntPtr h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
                IntPtr.Zero, OPEN_EXISTING, FILE_FLAG_OVERLAPPED, IntPtr.Zero);
            if (h == IntPtr.Zero || h.ToInt64() == -1)
            {
                int e = Marshal.GetLastWin32Error();
                L("[W " + col + "] 只读打开失败 err=" + e + (e == 32 ? " (ERROR_SHARING_VIOLATION: 被系统独占)" : ""));
                sb.Append(col + ":fail" + e + " ");
                continue;
            }

            IntPtr pp;
            if (HidD_GetPreparsedData(h, out pp))
            {
                var caps = new HIDP_CAPS(); caps.Reserved = new ushort[17];
                if (HidP_GetCaps(pp, ref caps))
                    L(string.Format("[W {0}] 已打开并监听  inLen={1} outLen={2} featLen={3} topUp=0x{4:X2} topU=0x{5:X2}",
                        col, caps.InputReportByteLength, caps.OutputReportByteLength, caps.FeatureReportByteLength, caps.UsagePage, caps.Usage));
                HidD_FreePreparsedData(pp);
            }
            else L("[W " + col + "] 已打开并监听（caps 读取失败）");

            var r = new Reader { Name = col, H = h, Run = true };
            _readers.Add(r);
            r.T = new Thread(() => Loop(r));
            r.T.IsBackground = true;
            r.T.Start();
            sb.Append(col + ":ok ");
        }
        return sb.ToString();
    }

    public static void StopAll() { foreach (var r in _readers) r.Run = false; }
    public static int TotalReports { get { int t = 0; foreach (var r in _readers) t += r.Count; return t; } }

    static void Loop(Reader r)
    {
        IntPtr ev = CreateEvent(IntPtr.Zero, false, false, null);
        var ov = new OVERLAPPED(); ov.hEvent = ev;
        var buf = new byte[256];
        while (r.Run)
        {
            bool ok = ReadFile(r.H, buf, (uint)buf.Length, IntPtr.Zero, ref ov);
            int err = Marshal.GetLastWin32Error();
            if (!ok && err != ERROR_IO_PENDING) { L("[W " + r.Name + "] ReadFile 失败 err=" + err); break; }

            uint w = WaitForSingleObject(ev, 1000);
            if (w == WAIT_TIMEOUT)
            {
                CancelIo(r.H);
                WaitForSingleObject(ev, 500);
                r.Timeouts++;
                double t = _sw.Elapsed.TotalSeconds;
                if (t - r.LastIdleLog >= 30.0)
                {
                    L(string.Format("[W {0}] [idle {1:F0}s] reports={2}", r.Name, t, r.Count));
                    r.LastIdleLog = t;
                }
                continue;
            }
            if (w != WAIT_OBJECT_0) { L("[W " + r.Name + "] wait 失败 w=" + w); break; }
            uint got;
            if (!GetOverlappedResult(r.H, ref ov, out got, false)) { L("[W " + r.Name + "] GetOverlappedResult 失败 err=" + Marshal.GetLastWin32Error()); break; }
            if (got == 0) continue;

            r.Count++;
            if (r.Count <= 200)
            {
                var sb = new StringBuilder();
                uint lim = got > 80 ? 80 : got;
                for (uint i = 0; i < lim; i++) sb.Append(buf[i].ToString("X2")).Append(' ');
                L(string.Format("[W {0} #{1}] t={2:F3}s len={3} :: {4}", r.Name, r.Count, _sw.Elapsed.TotalSeconds, got, sb.ToString().Trim()));
            }
            else if (r.Count == 201) L("[W " + r.Name + "] 后续报文只计数（前 200 条已完整记录）");
            else if (r.Count % 500 == 0) L(string.Format("[W {0}] 累计 {1} 条报文 (t={2:F1}s)", r.Name, r.Count, _sw.Elapsed.TotalSeconds));
        }
        if (r.H != IntPtr.Zero) { CloseHandle(r.H); r.H = IntPtr.Zero; }
        CloseHandle(ev);
        L("[W " + r.Name + "] 读取线程结束");
    }

    public static string[] Drain()
    {
        var list = new List<string>();
        string s;
        while (Log.TryDequeue(out s)) list.Add(s);
        return list.ToArray();
    }
}
