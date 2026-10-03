// GoodixCmd.cs — 通过 Col04 (Report ID 14, 65 字节) 收发 Goodix GTX8 命令
// 协议来源: fwupd plugins/goodix-tp (Goodix 官方开源实现)
// 安全约束: 只实现「读内存」命令；写命令另行实现且必须先确认目标地址
#pragma warning disable 0649, 0169
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

public static class GoodixCmd
{
    [StructLayout(LayoutKind.Sequential)]
    struct RAWINPUTDEVICELIST { public IntPtr hDevice; public uint dwType; }

    [StructLayout(LayoutKind.Sequential)]
    struct OVERLAPPED { public IntPtr Internal; public IntPtr InternalHigh; public uint Offset; public uint OffsetHigh; public IntPtr hEvent; }

    [DllImport("user32.dll")]
    static extern uint GetRawInputDeviceList([Out] RAWINPUTDEVICELIST[] a, ref uint n, uint sz);
    [DllImport("user32.dll", EntryPoint = "GetRawInputDeviceInfoW", CharSet = CharSet.Unicode)]
    static extern uint GetRawInputDeviceInfoStr(IntPtr h, uint cmd, StringBuilder sb, ref uint sz);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern IntPtr CreateFileW(string p, uint acc, uint share, IntPtr sec, uint disp, uint flags, IntPtr t);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool WriteFile(IntPtr h, byte[] buf, uint len, out uint written, IntPtr ov);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool ReadFile(IntPtr h, byte[] buf, uint len, IntPtr read, ref OVERLAPPED ov);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool GetOverlappedResult(IntPtr h, ref OVERLAPPED ov, out uint transferred, bool wait);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool CancelIo(IntPtr h);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern IntPtr CreateEvent(IntPtr a, bool manual, bool init, string name);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern uint WaitForSingleObject(IntPtr h, uint ms);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool CloseHandle(IntPtr h);
    [DllImport("hid.dll", SetLastError = true)]
    static extern bool HidD_SetFeature(IntPtr h, byte[] buf, uint len);
    [DllImport("hid.dll", SetLastError = true)]
    static extern bool HidD_SetOutputReport(IntPtr h, byte[] buf, uint len);
    [DllImport("hid.dll")]
    static extern bool HidD_GetPreparsedData(IntPtr h, out IntPtr pp);
    [DllImport("hid.dll")]
    static extern bool HidD_FreePreparsedData(IntPtr pp);
    [DllImport("hid.dll")]
    static extern bool HidP_GetCaps(IntPtr pp, ref HIDP_CAPS caps);

    [StructLayout(LayoutKind.Sequential)]
    struct HIDP_CAPS
    {
        public ushort Usage, UsagePage, InputReportByteLength, OutputReportByteLength, FeatureReportByteLength;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 17)] public ushort[] Reserved;
        public ushort NumberLinkCollectionNodes, NumberInputButtonCaps, NumberInputValueCaps, NumberInputDataIndices;
        public ushort NumberOutputButtonCaps, NumberOutputValueCaps, NumberOutputDataIndices;
        public ushort NumberFeatureButtonCaps, NumberFeatureValueCaps, NumberFeatureDataIndices;
    }

    /// <summary>查询句柄上的真实报告长度</summary>
    public static string Caps()
    {
        if (_hw == IntPtr.Zero) return "not-open";
        IntPtr pp;
        if (!HidD_GetPreparsedData(_hw, out pp)) return "GetPreparsedData failed err=" + Marshal.GetLastWin32Error();
        var c = new HIDP_CAPS(); c.Reserved = new ushort[17];
        string s = "caps-failed";
        if (HidP_GetCaps(pp, ref c))
            s = string.Format("top=0x{0:X2}/0x{1:X2} inLen={2} outLen={3} featLen={4} outValCaps={5} featValCaps={6} inValCaps={7}",
                c.UsagePage, c.Usage, c.InputReportByteLength, c.OutputReportByteLength, c.FeatureReportByteLength,
                c.NumberOutputValueCaps, c.NumberFeatureValueCaps, c.NumberInputValueCaps);
        HidD_FreePreparsedData(pp);
        return s;
    }

    /// <summary>用指定长度试写（找正确的报告长度）</summary>
    public static string WriteLen(int len)
    {
        if (_hw == IntPtr.Zero) return "not-open";
        var buf = new byte[len];
        if (len > 0) buf[0] = REPORT_ID;
        uint written;
        bool w = WriteFile(_hw, buf, (uint)len, out written, IntPtr.Zero);
        return string.Format("WriteFile(len={0}) -> {1} written={2} err={3}", len, w, written, Marshal.GetLastWin32Error());
    }

    /// <summary>用 HidD_SetOutputReport 试写</summary>
    public static string SetOutputReport(int len)
    {
        if (_hw == IntPtr.Zero) return "not-open";
        var buf = new byte[len];
        if (len > 0) buf[0] = REPORT_ID;
        bool ok = HidD_SetOutputReport(_hw, buf, (uint)len);
        return string.Format("HidD_SetOutputReport(len={0}) -> {1} err={2}", len, ok, Marshal.GetLastWin32Error());
    }

    const uint GENERIC_READ = 0x80000000, GENERIC_WRITE = 0x40000000;
    const uint FILE_SHARE_READ = 1, FILE_SHARE_WRITE = 2, OPEN_EXISTING = 3;
    const uint FILE_FLAG_OVERLAPPED = 0x40000000;
    const uint ERROR_IO_PENDING = 997;
    const uint WAIT_OBJECT_0 = 0, WAIT_TIMEOUT = 258;
    const byte REPORT_ID = 0x0E;
    const int PKG = 65;

    static IntPtr _h = IntPtr.Zero;     // 读用（overlapped）
    static IntPtr _hw = IntPtr.Zero;    // 写用（同步）

    public static string Open(string filter, string col)
    {
        uint n = 0, sz = (uint)Marshal.SizeOf(typeof(RAWINPUTDEVICELIST));
        GetRawInputDeviceList(null, ref n, sz);
        var arr = new RAWINPUTDEVICELIST[n];
        GetRawInputDeviceList(arr, ref n, sz);
        string path = null;
        foreach (var d in arr)
        {
            uint s = 0;
            GetRawInputDeviceInfoStr(d.hDevice, 0x20000007, null, ref s);
            if (s == 0) continue;
            var sb = new StringBuilder((int)s + 2);
            uint s2 = s;
            GetRawInputDeviceInfoStr(d.hDevice, 0x20000007, sb, ref s2);
            string p = sb.ToString();
            if (p.IndexOf(filter, StringComparison.OrdinalIgnoreCase) >= 0 &&
                p.IndexOf(col, StringComparison.OrdinalIgnoreCase) >= 0) { path = p; break; }
        }
        if (path == null) return "device-not-found";
        _h = CreateFileW(path, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
                         IntPtr.Zero, OPEN_EXISTING, FILE_FLAG_OVERLAPPED, IntPtr.Zero);
        _hw = CreateFileW(path, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
                          IntPtr.Zero, OPEN_EXISTING, 0, IntPtr.Zero);
        if (_h == IntPtr.Zero || _h.ToInt64() == -1) { _h = IntPtr.Zero; return "open-failed(read) err=" + Marshal.GetLastWin32Error(); }
        if (_hw == IntPtr.Zero || _hw.ToInt64() == -1) { _hw = IntPtr.Zero; return "open-failed(write) err=" + Marshal.GetLastWin32Error(); }
        return "ok";
    }

    /// <summary>发送 65 字节命令包（output report 或 feature report 两种方式都试）</summary>
    public static string Send(byte[] pkt, bool useFeature)
    {
        if (_h == IntPtr.Zero && _hw == IntPtr.Zero) return "not-open";
        var buf = new byte[PKG];
        Array.Copy(pkt, buf, Math.Min(pkt.Length, PKG));
        buf[0] = REPORT_ID;
        if (useFeature)
        {
            bool ok = HidD_SetFeature(_h, buf, PKG);
            return "SetFeature -> " + ok + " err=" + Marshal.GetLastWin32Error();
        }
        bool w = HidD_SetOutputReport(_hw, buf, PKG);
        return "SetOutputReport(65) -> " + w + " err=" + Marshal.GetLastWin32Error();
    }

    /// <summary>等待并读取一个 65 字节输入报文</summary>
    public static byte[] Recv(int timeoutMs)
    {
        if (_h == IntPtr.Zero) return null;
        IntPtr ev = CreateEvent(IntPtr.Zero, false, false, null);
        var ov = new OVERLAPPED(); ov.hEvent = ev;
        var buf = new byte[PKG];
        bool ok = ReadFile(_h, buf, PKG, IntPtr.Zero, ref ov);
        int err = Marshal.GetLastWin32Error();
        if (!ok && err != ERROR_IO_PENDING) { CloseHandle(ev); return null; }
        uint w = WaitForSingleObject(ev, (uint)timeoutMs);
        if (w == WAIT_TIMEOUT) { CancelIo(_h); WaitForSingleObject(ev, 300); CloseHandle(ev); return null; }
        uint got;
        if (!GetOverlappedResult(_h, ref ov, out got, false)) { CloseHandle(ev); return null; }
        CloseHandle(ev);
        if (got == 0) return null;
        var res = new byte[got];
        Array.Copy(buf, res, (int)got);
        return res;
    }

    /// <summary>原样发送 65 字节（不强制改写第 0 字节）</summary>
    public static string SendRaw(byte[] buf65)
    {
        if (_hw == IntPtr.Zero) return "not-open";
        var b = new byte[PKG];
        Array.Copy(buf65, b, Math.Min(buf65.Length, PKG));
        bool w = HidD_SetOutputReport(_hw, b, PKG);
        return string.Format("SetOutputReport -> {0} err={1}  首4字节: {2:X2} {3:X2} {4:X2} {5:X2}",
            w, Marshal.GetLastWin32Error(), b[0], b[1], b[2], b[3]);
    }

    /// <summary>轮询读取，收集 windowMs 内收到的所有输入报文</summary>
    public static string[] RecvWindow(int windowMs)
    {
        var list = new System.Collections.Generic.List<string>();
        if (_h == IntPtr.Zero) return list.ToArray();
        var sw = System.Diagnostics.Stopwatch.StartNew();
        while (sw.ElapsedMilliseconds < windowMs)
        {
            byte[] r = Recv(300);
            if (r != null && r.Length > 0)
            {
                var sb = new StringBuilder();
                for (int i = 0; i < Math.Min(r.Length, 20); i++) sb.Append(r[i].ToString("X2")).Append(' ');
                list.Add(string.Format("t={0}ms len={1} :: {2}", sw.ElapsedMilliseconds, r.Length, sb.ToString().Trim()));
            }
        }
        return list.ToArray();
    }

    /// <summary>试读 feature report</summary>
    public static string GetFeature(int rid)
    {
        if (_hw == IntPtr.Zero) return "not-open";
        var buf = new byte[PKG]; buf[0] = (byte)rid;
        bool ok = HidD_GetFeature(_hw, buf, PKG);
        var sb = new StringBuilder();
        for (int i = 0; i < 8; i++) sb.Append(buf[i].ToString("X2")).Append(' ');
        return string.Format("GetFeature(rid={0}) -> {1} err={2} :: {3}", rid, ok, Marshal.GetLastWin32Error(), sb.ToString().Trim());
    }

    [DllImport("hid.dll", SetLastError = true)]
    static extern bool HidD_GetFeature(IntPtr h, byte[] buf, uint len);
    [DllImport("hid.dll", SetLastError = true)]
    static extern bool HidD_GetInputReport(IntPtr h, byte[] buf, uint len);

    /// <summary>用 HidD_GetInputReport 主动取输入报文（Hellcat 工具用它读响应）</summary>
    public static string GetInputReport(int handle, int rid, int len)
    {
        byte[] buf;
        return GetInputReport(handle, rid, len, out buf);
    }

    public static string GetInputReport(int handle, int rid, int len, out byte[] outBuf)
    {
        outBuf = null;
        IntPtr h = (handle == 3) ? _h3 : (handle == 4 ? _hw : _h);
        if (h == IntPtr.Zero) return "not-open";
        var buf = new byte[len];
        buf[0] = (byte)rid;
        bool ok = HidD_GetInputReport(h, buf, (uint)len);
        int err = Marshal.GetLastWin32Error();
        outBuf = buf;
        var sb = new StringBuilder();
        for (int i = 0; i < Math.Min(len, 65); i++) sb.Append(buf[i].ToString("X2")).Append(' ');
        return string.Format("Col{0} GetInputReport(rid={1}, len={2}) -> {3} err={4}\n        数据: {5}",
            handle, rid, len, ok, err, sb.ToString().Trim());
    }

    /// <summary>用 HidD_SetFeature 发送 65 字节包（Hellcat 工具的写方式）</summary>
    public static string SetFeaturePkt(int handle, byte[] pkt, int len)
    {
        IntPtr h = (handle == 3) ? _h3 : (handle == 4 ? _hw : _h);
        if (h == IntPtr.Zero) return "not-open";
        var buf = new byte[len];
        Array.Copy(pkt, buf, Math.Min(pkt.Length, len));
        buf[0] = REPORT_ID;
        bool ok = HidD_SetFeature(h, buf, (uint)len);
        return string.Format("Col%02d SetFeature(len={0}) -> {1} err={2}", handle, len, ok, Marshal.GetLastWin32Error());
    }

    static IntPtr _h3 = IntPtr.Zero;    // Col03 (mtconfig) 句柄，用于侧门发 feature 报文

    public static string OpenCol03()
    {
        uint n = 0, sz = (uint)Marshal.SizeOf(typeof(RAWINPUTDEVICELIST));
        GetRawInputDeviceList(null, ref n, sz);
        var arr = new RAWINPUTDEVICELIST[n];
        GetRawInputDeviceList(arr, ref n, sz);
        // Col03 不在原始输入枚举里，直接从已知路径前缀拼不出来；改用 SetupDi 太麻烦，
        // 这里复用 Col04 的打开流程：枚举所有 HID 原始输入设备不包含 Col03，
        // 因此用固定路径（GUID_DEVINTERFACE_HID）尝试。
        string path = @"\\?\HID#GXTP5100&Col03#5&52a7aed&0&0002#{4d1e55b2-f16f-11cf-88cb-001111000030}";
        _h3 = CreateFileW(path, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
                          IntPtr.Zero, OPEN_EXISTING, 0, IntPtr.Zero);
        if (_h3 == IntPtr.Zero || _h3.ToInt64() == -1) { _h3 = IntPtr.Zero; return "col03-open-failed err=" + Marshal.GetLastWin32Error(); }
        return "col03-ok";
    }

    /// <summary>通过 Col03 句柄发 feature 报文（侧门）：指定 report ID 与长度</summary>
    public static string SetFeatureVia(int handle, int rid, byte[] pkt, int len)
    {
        IntPtr h = (handle == 3) ? _h3 : _hw;
        if (h == IntPtr.Zero) return "not-open";
        var buf = new byte[len];
        Array.Copy(pkt, buf, Math.Min(pkt.Length, len));
        buf[0] = (byte)rid;
        bool ok = HidD_SetFeature(h, buf, (uint)len);
        return string.Format("Col%02d SetFeature(rid={0}, len={1}) -> {2} err={3}", handle, rid, len, ok, Marshal.GetLastWin32Error());
    }

    /// <summary>读内存（协议来源: fu_goodixtp_gtx8_device_read_pkg）</summary>
    public static byte[] ReadMem(ushort addr, ushort size, bool useFeature, out string log)
    {
        var pkt = new byte[10];
        pkt[0] = REPORT_ID;
        pkt[1] = 0x20;      // I2C_DIRECT_RW
        pkt[2] = 0x00;
        pkt[3] = 0x00;
        pkt[4] = 0x05;
        pkt[5] = 0x01;      // READ flag
        pkt[6] = (byte)(addr >> 8); pkt[7] = (byte)(addr & 0xFF);
        pkt[8] = (byte)(size >> 8); pkt[9] = (byte)(size & 0xFF);
        string s1 = Send(pkt, useFeature);
        byte[] rsp = Recv(800);
        if (rsp == null) { log = s1 + " | 无响应"; return null; }
        var hex = new StringBuilder();
        for (int i = 0; i < Math.Min(rsp.Length, 16); i++) hex.Append(rsp[i].ToString("X2")).Append(' ');
        if (rsp.Length < 6) { log = s1 + " | 响应过短 len=" + rsp.Length + " :: " + hex; return null; }
        int st = rsp[3], ln = rsp[4];
        if (st != 0 || ln != size)
        {
            log = s1 + string.Format(" | 响应异常 status={0} len={1} (期望 size={2}) :: {3}", st, ln, size, hex);
            return null;
        }
        var data = new byte[ln];
        Array.Copy(rsp, 5, data, 0, Math.Min(ln, rsp.Length - 5));
        log = s1 + string.Format(" | OK 读到 {0} 字节", ln);
        return data;
    }
}
