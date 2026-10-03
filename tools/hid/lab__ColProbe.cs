// ColProbe.cs —— 枚举本机 Goodix 触控板所有 HID 集合，逐个尝试不同访问权限打开，
// 并在可读句柄上读取厂商 feature report（安全：只读，不写设备）。
// 编译: powershell Add-Type -Path .\ColProbe.cs
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public static class ColProbe
{
    [StructLayout(LayoutKind.Sequential)]
    struct SP_DEVICE_INTERFACE_DATA
    {
        public int cbSize;
        public Guid InterfaceClassGuid;
        public int Flags;
        public IntPtr Reserved;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct HIDP_CAPS
    {
        public ushort Usage, UsagePage;
        public ushort InputReportByteLength, OutputReportByteLength, FeatureReportByteLength;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 17)] public ushort[] Reserved;
        public ushort NumberLinkCollectionNodes, NumberInputButtonCaps, NumberInputValueCaps, NumberInputDataIndices;
        public ushort NumberOutputButtonCaps, NumberOutputValueCaps, NumberOutputDataIndices;
        public ushort NumberFeatureButtonCaps, NumberFeatureValueCaps, NumberFeatureDataIndices;
    }

    [DllImport("setupapi.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr SetupDiGetClassDevs(ref Guid g, IntPtr e, IntPtr h, uint f);
    [DllImport("setupapi.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool SetupDiEnumDeviceInterfaces(IntPtr h, IntPtr di, ref Guid g, uint i, ref SP_DEVICE_INTERFACE_DATA d);
    [DllImport("setupapi.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool SetupDiGetDeviceInterfaceDetail(IntPtr h, ref SP_DEVICE_INTERFACE_DATA d, IntPtr det, uint sz, ref uint req, IntPtr di);
    [DllImport("setupapi.dll")] static extern bool SetupDiDestroyDeviceInfoList(IntPtr h);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr CreateFileW(string p, uint acc, uint share, IntPtr sa, uint cd, uint fl, IntPtr t);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);

    [DllImport("hid.dll", SetLastError = true)] static extern bool HidD_GetFeature(IntPtr h, byte[] b, uint len);
    [DllImport("hid.dll", SetLastError = true)] static extern bool HidD_SetFeature(IntPtr h, byte[] b, uint len);
    [DllImport("hid.dll", SetLastError = true)] static extern bool HidD_GetInputReport(IntPtr h, byte[] b, uint len);
    [DllImport("hid.dll", SetLastError = true)] static extern bool HidD_GetPreparsedData(IntPtr h, out IntPtr pp);
    [DllImport("hid.dll")] static extern bool HidD_FreePreparsedData(IntPtr pp);
    [DllImport("hid.dll")] static extern int HidP_GetCaps(IntPtr pp, ref HIDP_CAPS caps);

    const uint GENERIC_READ = 0x80000000, GENERIC_WRITE = 0x40000000;
    const uint FILE_SHARE_READ = 1, FILE_SHARE_WRITE = 2, OPEN_EXISTING = 3;

    static readonly Guid HID_GUID = new Guid("4d1e55b2-f16f-11cf-88cb-001111000030");

    public static string[] EnumPaths(string filter)
    {
        var list = new List<string>();
        Guid g = HID_GUID;
        IntPtr set = SetupDiGetClassDevs(ref g, IntPtr.Zero, IntPtr.Zero, 0x12 /*PRESENT|DEVICEINTERFACE*/);
        if (set == IntPtr.Zero || set.ToInt64() == -1) return list.ToArray();
        try
        {
            var did = new SP_DEVICE_INTERFACE_DATA();
            did.cbSize = Marshal.SizeOf(typeof(SP_DEVICE_INTERFACE_DATA));
            for (uint i = 0; ; i++)
            {
                if (!SetupDiEnumDeviceInterfaces(set, IntPtr.Zero, ref g, i, ref did)) break;
                uint req = 0;
                SetupDiGetDeviceInterfaceDetail(set, ref did, IntPtr.Zero, 0, ref req, IntPtr.Zero);
                if (req == 0) continue;
                IntPtr buf = Marshal.AllocHGlobal((int)req);
                try
                {
                    Marshal.WriteInt32(buf, IntPtr.Size == 8 ? 8 : 6); // cbSize of detail struct
                    if (SetupDiGetDeviceInterfaceDetail(set, ref did, buf, req, ref req, IntPtr.Zero))
                    {
                        string p = Marshal.PtrToStringUni((IntPtr)(buf.ToInt64() + 4));
                        if (p != null && (filter == null || p.IndexOf(filter, StringComparison.OrdinalIgnoreCase) >= 0))
                            list.Add(p);
                    }
                }
                finally { Marshal.FreeHGlobal(buf); }
            }
        }
        finally { SetupDiDestroyDeviceInfoList(set); }
        return list.ToArray();
    }

    /// <summary>按完整路径打开（避免子串匹配打到别的设备上）</summary>
    public static IntPtr OpenPath(string path, bool read, bool write)
    {
        uint acc = 0;
        if (read) acc |= GENERIC_READ;
        if (write) acc |= GENERIC_WRITE;
        IntPtr h = CreateFileW(path, acc, FILE_SHARE_READ | FILE_SHARE_WRITE, IntPtr.Zero, OPEN_EXISTING, 0, IntPtr.Zero);
        return (h != IntPtr.Zero && h.ToInt64() != -1) ? h : IntPtr.Zero;
    }

    /// <summary>在 GXTP5100 里按集合名找完整路径</summary>
    public static string FindPath(string colName)
    {
        foreach (string p in EnumPaths("GXTP5100"))
            if (p.IndexOf(colName, StringComparison.OrdinalIgnoreCase) >= 0) return p;
        return null;
    }

    /// <summary>只读打开匹配 filter 的集合</summary>
    public static IntPtr OpenRO(string filter)
    {
        foreach (string p in EnumPaths(filter))
        {
            IntPtr h = CreateFileW(p, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, IntPtr.Zero, OPEN_EXISTING, 0, IntPtr.Zero);
            if (h != IntPtr.Zero && h.ToInt64() != -1) return h;
        }
        return IntPtr.Zero;
    }

    /// <summary>读 feature report</summary>
    public static byte[] GetFeat(IntPtr h, int rid, int len, out int err)
    {
        err = 0;
        if (h == IntPtr.Zero) { err = -1; return null; }
        var buf = new byte[len];
        buf[0] = (byte)rid;
        bool ok = HidD_GetFeature(h, buf, (uint)len);
        err = Marshal.GetLastWin32Error();
        return ok ? buf : null;
    }

    /// <summary>以只写权限打开匹配 filter 的集合（Col02 的独占只挡读，写是放行的）</summary>
    public static IntPtr OpenWrite(string filter)
    {
        foreach (string p in EnumPaths(filter))
        {
            IntPtr h = CreateFileW(p, GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, IntPtr.Zero, OPEN_EXISTING, 0, IntPtr.Zero);
            if (h != IntPtr.Zero && h.ToInt64() != -1) return h;
        }
        return IntPtr.Zero;
    }

    /// <summary>发 feature report：buf = [rid] + payload</summary>
    public static string SetFeat(IntPtr h, int rid, byte[] payload)
    {
        if (h == IntPtr.Zero) return "handle=null";
        var buf = new byte[1 + (payload == null ? 0 : payload.Length)];
        buf[0] = (byte)rid;
        if (payload != null) Array.Copy(payload, 0, buf, 1, payload.Length);
        bool ok = HidD_SetFeature(h, buf, (uint)buf.Length);
        return string.Format("SetFeature(rid={0}, len={1}) -> {2} err={3}", rid, buf.Length, ok, Marshal.GetLastWin32Error());
    }

    /// <summary>打开指定集合的读写句柄（Col04 用）</summary>
    public static IntPtr OpenRW(string filter)
    {
        foreach (string p in EnumPaths(filter))
        {
            IntPtr h = CreateFileW(p, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, IntPtr.Zero, OPEN_EXISTING, 0, IntPtr.Zero);
            if (h != IntPtr.Zero && h.ToInt64() != -1) return h;
        }
        return IntPtr.Zero;
    }

    public static void Close(IntPtr h) { if (h != IntPtr.Zero) CloseHandle(h); }

    public static byte[] GetInputReport65(IntPtr h, int rid)
    {
        var buf = new byte[65];
        buf[0] = (byte)rid;
        bool ok = HidD_GetInputReport(h, buf, 65);
        if (!ok) return null;
        return buf;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool DeviceIoControl(IntPtr h, uint code, byte[] inBuf, uint inSz, byte[] outBuf, uint outSz, out uint ret, IntPtr ov);
    const uint IOCTL_HID_GET_REPORT_DESCRIPTOR = 0x000B0000;

    /// <summary>读取当前生效的 HID 报表描述符（原始字节）</summary>
    public static byte[] GetDesc(IntPtr h)
    {
        var b = new byte[4096];
        uint ret;
        bool ok = DeviceIoControl(h, IOCTL_HID_GET_REPORT_DESCRIPTOR, null, 0, b, (uint)b.Length, out ret, IntPtr.Zero);
        if (!ok || ret == 0) return null;
        var r = new byte[ret];
        Array.Copy(b, r, (int)ret);
        return r;
    }

    public static string DescHex(IntPtr h)
    {
        byte[] d = GetDesc(h);
        if (d == null) return "(描述符读取失败)";
        var sb = new StringBuilder();
        for (int i = 0; i < d.Length; i++)
        {
            sb.Append(d[i].ToString("X2"));
            sb.Append((i % 32 == 31) ? "\n" : " ");
        }
        return "长度=" + d.Length + "\n" + sb.ToString();
    }

    /// <summary>打印任意句柄的 HIDP caps</summary>
    public static string CapsOf(IntPtr h)
    {
        IntPtr pp;
        if (!HidD_GetPreparsedData(h, out pp)) return "GetPreparsedData 失败 err=" + Marshal.GetLastWin32Error();
        try
        {
            var c = new HIDP_CAPS();
            int st = HidP_GetCaps(pp, ref c);
            if (st < 0) return "HidP_GetCaps 失败 status=0x" + st.ToString("X8");
            return string.Format("up=0x{0:X4} u=0x{1:X4} in={2} out={3} feat={4} | featVals={5} inVals={6} outVals={7}",
                c.UsagePage, c.Usage, c.InputReportByteLength, c.OutputReportByteLength, c.FeatureReportByteLength,
                c.NumberFeatureValueCaps, c.NumberInputValueCaps, c.NumberOutputValueCaps);
        }
        finally { HidD_FreePreparsedData(pp); }
    }

    static string Short(string path)
    {
        int a = path.IndexOf("HID#"); if (a < 0) a = 0;
        int b = path.IndexOf('#'); if (b < 0) b = path.Length;
        int c = path.IndexOf('{'); if (c < 0) c = path.Length;
        string s = path.Substring(a, c - a);
        return s.TrimEnd('#');
    }

    /// <summary>对每个集合尝试三种访问权限，并在成功的句柄上读 feature caps + 厂商报表</summary>
    public static string Run(string filter)
    {
        var sb = new StringBuilder();
        string[] paths = EnumPaths(filter);
        sb.AppendLine("找到 HID 接口: " + paths.Length);
        foreach (string p in paths)
        {
            sb.AppendLine();
            sb.AppendLine("=== " + Short(p));
            uint[] accs = { GENERIC_READ, GENERIC_WRITE, GENERIC_READ | GENERIC_WRITE };
            string[] names = { "READ ", "WRITE", "R+W  " };
            IntPtr ro = IntPtr.Zero;
            for (int k = 0; k < accs.Length; k++)
            {
                IntPtr h = CreateFileW(p, accs[k], FILE_SHARE_READ | FILE_SHARE_WRITE, IntPtr.Zero, OPEN_EXISTING, 0, IntPtr.Zero);
                bool ok = h != IntPtr.Zero && h.ToInt64() != -1;
                sb.AppendLine(string.Format("  open[{0}] share=RW -> {1} err={2}", names[k], ok, ok ? 0 : Marshal.GetLastWin32Error()));
                if (ok)
                {
                    if (k == 0 && ro == IntPtr.Zero) ro = h;
                    else CloseHandle(h);
                }
            }
            if (ro == IntPtr.Zero) { sb.AppendLine("  (无只读句柄，跳过读取)"); continue; }

            IntPtr pp;
            if (HidD_GetPreparsedData(ro, out pp))
            {
                var caps = new HIDP_CAPS();
                if (HidP_GetCaps(pp, ref caps) >= 0)
                    sb.AppendLine(string.Format("  caps: up=0x{0:X4} u=0x{1:X4} in={2} out={3} feat={4} featVals={5}",
                        caps.UsagePage, caps.Usage, caps.InputReportByteLength, caps.OutputReportByteLength,
                        caps.FeatureReportByteLength, caps.NumberFeatureValueCaps));
                HidD_FreePreparsedData(pp);
            }

            // 读 feature reports（只读，安全）
            int[][] rids = new int[][] {
                new int[]{ 2, 2 }, new int[]{ 9, 2 }, new int[]{ 13, 5 }, new int[]{ 11, 67 }, new int[]{ 6, 257 }, new int[]{ 12, 737 }
            };
            foreach (var r in rids)
            {
                byte[] buf = new byte[r[1]];
                buf[0] = (byte)r[0];
                bool ok = HidD_GetFeature(ro, buf, (uint)buf.Length);
                int err = Marshal.GetLastWin32Error();
                string hex = "";
                if (ok) { int n = Math.Min(buf.Length, 24); for (int i = 0; i < n; i++) hex += buf[i].ToString("X2") + " "; }
                sb.AppendLine(string.Format("  GetFeature(rid={0}, len={1}) -> {2} err={3} :: {4}", r[0], r[1], ok, err, hex.Trim()));
            }
            // 试读输入报表（Col04 专用；其他集合会失败，记录一下）
            {
                byte[] buf = new byte[65]; buf[0] = 0x0E;
                bool ok = HidD_GetInputReport(ro, buf, 65);
                int err = Marshal.GetLastWin32Error();
                string hex = "";
                if (ok) for (int i = 0; i < 16; i++) hex += buf[i].ToString("X2") + " ";
                sb.AppendLine(string.Format("  GetInputReport(rid=14,len=65) -> {0} err={1} :: {2}", ok, err, hex.Trim()));
            }
            CloseHandle(ro);
        }
        return sb.ToString();
    }
}
