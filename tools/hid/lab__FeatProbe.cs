// FeatProbe.cs — 侧门测试：能否用「其它集合」的句柄，向 PTP 集合(Col02)的 Feature 报文写入
// 只做一次「写回原值」的探测（intensity 写回注册表里现有的 100），不改变任何实际设置
#pragma warning disable 0649, 0169
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public static class FeatProbe
{
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

    [DllImport("user32.dll")]
    static extern uint GetRawInputDeviceList([Out] RAWINPUTDEVICELIST[] pRawInputDeviceList, ref uint puiNumDevices, uint cbSize);
    [DllImport("user32.dll", EntryPoint = "GetRawInputDeviceInfoW", CharSet = CharSet.Unicode)]
    static extern uint GetRawInputDeviceInfoStr(IntPtr hDevice, uint uiCommand, StringBuilder pData, ref uint pcbSize);
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern IntPtr CreateFileW(string lpFileName, uint dwDesiredAccess, uint dwShareMode,
        IntPtr lpSecurityAttributes, uint dwCreationDisposition, uint dwFlagsAndAttributes, IntPtr hTemplateFile);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool CloseHandle(IntPtr hObject);
    [DllImport("hid.dll", SetLastError = true)]
    static extern bool HidD_GetFeature(IntPtr h, byte[] buf, uint len);
    [DllImport("hid.dll", SetLastError = true)]
    static extern bool HidD_SetFeature(IntPtr h, byte[] buf, uint len);
    [DllImport("hid.dll")]
    static extern bool HidD_GetPreparsedData(IntPtr h, out IntPtr pp);
    [DllImport("hid.dll")]
    static extern bool HidD_FreePreparsedData(IntPtr pp);
    [DllImport("hid.dll")]
    static extern bool HidP_GetCaps(IntPtr pp, ref HIDP_CAPS caps);
    [DllImport("hid.dll")]
    static extern bool HidP_GetValueCaps(int reportType, [Out] HIDP_VALUE_CAPS[] caps, ref ushort len, IntPtr pp);

    const uint GENERIC_READ = 0x80000000, GENERIC_WRITE = 0x40000000;
    const uint FILE_SHARE_READ = 1, FILE_SHARE_WRITE = 2, OPEN_EXISTING = 3;

    static string FindPath(string filter, string collection)
    {
        uint n = 0, sz = (uint)Marshal.SizeOf(typeof(RAWINPUTDEVICELIST));
        GetRawInputDeviceList(null, ref n, sz);
        if (n == 0) return null;
        var arr = new RAWINPUTDEVICELIST[n];
        GetRawInputDeviceList(arr, ref n, sz);
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
                p.IndexOf(collection, StringComparison.OrdinalIgnoreCase) >= 0) return p;
        }
        return null;
    }

    /// <summary>对 collection 的句柄，尝试 GET/SET report id = rid</summary>
    public static string[] Run(string filter, string collection, int rid, int value)
    {
        var o = new List<string>();
        string path = FindPath(filter, collection);
        if (path == null) { o.Add(collection + ": 未找到接口路径"); return o.ToArray(); }
        o.Add("接口: " + path);

        uint errRO;
        IntPtr h = CreateFileW(path, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, IntPtr.Zero, OPEN_EXISTING, 0, IntPtr.Zero);
        if (h == IntPtr.Zero || h.ToInt64() == -1)
        {
            errRO = (uint)Marshal.GetLastWin32Error();
            o.Add("  以 读写 方式打开失败 err=" + errRO);
            h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, IntPtr.Zero, OPEN_EXISTING, 0, IntPtr.Zero);
            if (h == IntPtr.Zero || h.ToInt64() == -1) { o.Add("  以 只读 方式打开也失败 err=" + Marshal.GetLastWin32Error()); return o.ToArray(); }
            o.Add("  以 只读 方式打开成功（无法写入，仅作能力查询）");
        }
        else o.Add("  以 读写 方式打开成功 ✔");

        IntPtr pp;
        if (HidD_GetPreparsedData(h, out pp))
        {
            var caps = new HIDP_CAPS(); caps.Reserved = new ushort[17];
            if (HidP_GetCaps(pp, ref caps))
            {
                o.Add(string.Format("  caps: in={0} out={1} feat={2} featValCaps={3}", caps.InputReportByteLength, caps.OutputReportByteLength, caps.FeatureReportByteLength, caps.NumberFeatureValueCaps));
                ushort fn = caps.NumberFeatureValueCaps;
                if (fn > 0)
                {
                    var fc = new HIDP_VALUE_CAPS[fn];
                    ushort f2 = fn;
                    if (HidP_GetValueCaps(2, fc, ref f2, pp))
                        for (int i = 0; i < f2; i++)
                            o.Add(string.Format("    FEAT rid={0} up=0x{1:X2} u=0x{2:X2} bits={3} log=[{4},{5}]",
                                fc[i].ReportID, fc[i].UsagePage, fc[i].UsageMin, fc[i].BitSize, fc[i].LogicalMin, fc[i].LogicalMax));
                }
            }
            HidD_FreePreparsedData(pp);
        }

        // GET（预期返回垃圾或失败，仅作参考）
        var g = new byte[128]; g[0] = (byte)rid;
        bool okGet = HidD_GetFeature(h, g, (uint)g.Length);
        o.Add(string.Format("  HidD_GetFeature(rid={0}) -> {1} err={2}  首字节: {3}", rid, okGet, Marshal.GetLastWin32Error(),
            BitConverter.ToString(g, 0, 8)));

        // SET：写回与原值相同的 intensity（100），不改动实际设置
        var s = new byte[128]; s[0] = (byte)rid; s[1] = (byte)value;
        bool okSet = HidD_SetFeature(h, s, (uint)s.Length);
        o.Add(string.Format("  HidD_SetFeature(rid={0}, value={1}) -> {2} err={3}", rid, value, okSet, Marshal.GetLastWin32Error()));

        CloseHandle(h);
        return o.ToArray();
    }
}
