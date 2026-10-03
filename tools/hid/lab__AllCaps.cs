// AllCaps.cs —— 把指定 HID 接口的【全部】value caps 打出来（不筛选）
//
// 为什么写它：项目此前的 haptic-capability 探测只打印"触觉页(0x0E)/压力页(0x0D)"的字段，
// 于是 Col02 的 Feature RID 6/7/11/12/13 从未被看过内容。
// 而 ArchWiki 显示连"有触觉"的 X9-14(Sensel) 也是用 FEATURE 报表(RID 0x0B 强度 / 0x0D 力度)
// 控制触觉 —— 所以"触发"有可能就藏在某个 feature 报表里。
//
// 用法：powershell -File dump-all-caps.ps1        （见同目录 ps1）
// 本文件只读，不写设备。

using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public static class AllCaps
{
    const int HIDP_STATUS_SUCCESS = 0x00110000;
    const int HIDP_INPUT = 0, HIDP_OUTPUT = 1, HIDP_FEATURE = 2;

    [StructLayout(LayoutKind.Sequential)]
    public struct HIDP_CAPS
    {
        public ushort Usage, UsagePage;
        public ushort InputReportByteLength, OutputReportByteLength, FeatureReportByteLength;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 17)] public ushort[] Reserved;
        public ushort NumberLinkCollectionNodes;
        public ushort NumberInputButtonCaps, NumberInputValueCaps, NumberInputDataIndices;
        public ushort NumberOutputButtonCaps, NumberOutputValueCaps, NumberOutputDataIndices;
        public ushort NumberFeatureButtonCaps, NumberFeatureValueCaps, NumberFeatureDataIndices;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct HIDP_VALUE_CAPS
    {
        public ushort UsagePage;
        public byte ReportID;
        public byte IsAlias;
        public ushort BitField;
        public ushort LinkCollection;
        public ushort LinkUsage, LinkUsagePage;
        public byte IsRange, IsStringRange, IsDesignatorRange, IsAbsolute;
        public byte HasNull;
        public byte Reserved;
        public ushort BitSize;
        public ushort ReportCount;
        public ushort Reserved2a, Reserved2b, Reserved2c, Reserved2d, Reserved2e;
        public uint UnitsExp, Units;
        public int LogicalMin, LogicalMax, PhysicalMin, PhysicalMax;
        public ushort UsageMin, UsageMax;
        public ushort StringMin, StringMax;
        public ushort DesignatorMin, DesignatorMax;
        public ushort DataIndexMin, DataIndexMax;
    }

    [DllImport("hid.dll")] static extern bool HidD_GetPreparsedData(IntPtr h, out IntPtr p);
    [DllImport("hid.dll")] static extern bool HidD_FreePreparsedData(IntPtr p);
    [DllImport("hid.dll")] static extern int HidP_GetCaps(IntPtr p, ref HIDP_CAPS c);
    [DllImport("hid.dll")] static extern int HidP_GetValueCaps(int kind, byte[] buf, ref ushort len, IntPtr p);

    [DllImport("setupapi.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr SetupDiGetClassDevs(ref Guid g, IntPtr e, IntPtr h, uint f);
    [DllImport("setupapi.dll", SetLastError = true)]
    static extern bool SetupDiEnumDeviceInterfaces(IntPtr s, IntPtr i, ref Guid g, uint n, ref SP_DEVICE_INTERFACE_DATA d);
    [DllImport("setupapi.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool SetupDiGetDeviceInterfaceDetail(IntPtr s, ref SP_DEVICE_INTERFACE_DATA d, IntPtr det, uint sz, out uint need, IntPtr info);

    [StructLayout(LayoutKind.Sequential)]
    struct SP_DEVICE_INTERFACE_DATA { public uint cbSize; public Guid InterfaceClassGuid; public uint Flags; public IntPtr Reserved; }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr CreateFileW(string n, uint acc, uint share, IntPtr sa, uint disp, uint fl, IntPtr t);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
    [DllImport("setupapi.dll")] static extern bool SetupDiDestroyDeviceInfoList(IntPtr s);

    static Guid HID = new Guid("4d1e55b2-f16f-11cf-88cb-001111000030");

    public static List<string> Paths()
    {
        var r = new List<string>();
        IntPtr s = SetupDiGetClassDevs(ref HID, IntPtr.Zero, IntPtr.Zero, 0x12);
        if (s == new IntPtr(-1)) return r;
        var d = new SP_DEVICE_INTERFACE_DATA(); d.cbSize = (uint)Marshal.SizeOf(d);
        for (uint i = 0; SetupDiEnumDeviceInterfaces(s, IntPtr.Zero, ref HID, i, ref d); i++)
        {
            uint need = 0;
            SetupDiGetDeviceInterfaceDetail(s, ref d, IntPtr.Zero, 0, out need, IntPtr.Zero);
            if (need == 0) continue;
            IntPtr buf = Marshal.AllocHGlobal((int)need);
            try
            {
                Marshal.WriteInt32(buf, IntPtr.Size == 8 ? 8 : 6);
                if (SetupDiGetDeviceInterfaceDetail(s, ref d, buf, need, out need, IntPtr.Zero))
                    r.Add(Marshal.PtrToStringUni(new IntPtr(buf.ToInt64() + 4)));
            }
            finally { Marshal.FreeHGlobal(buf); }
        }
        SetupDiDestroyDeviceInfoList(s);
        return r;
    }

    public static string Dump(string path, out string brief)
    {
        brief = null;
        var sb = new StringBuilder();
        IntPtr h = CreateFileW(path, 0, 3, IntPtr.Zero, 3, 0, IntPtr.Zero);
        if (h == new IntPtr(-1)) { brief = "打不开(access=0)"; return null; }
        IntPtr pp = IntPtr.Zero;
        try
        {
            if (!HidD_GetPreparsedData(h, out pp)) { brief = "GetPreparsedData 失败"; return null; }
            var c = new HIDP_CAPS();
            c.Reserved = new ushort[17];
            if (HidP_GetCaps(pp, ref c) != HIDP_STATUS_SUCCESS) { brief = "GetCaps 失败"; return null; }
            brief = string.Format("UP=0x{0:X4} U=0x{1:X4} In={2} Out={3} Feat={4} LinkColl={5}",
                c.UsagePage, c.Usage, c.InputReportByteLength, c.OutputReportByteLength,
                c.FeatureReportByteLength, c.NumberLinkCollectionNodes);
            sb.AppendLine("  " + brief);
            string[] kindName = { "Input", "Output", "Feature" };
            for (int kind = 0; kind < 3; kind++)
            {
                ushort n = kind == 0 ? c.NumberInputValueCaps : kind == 1 ? c.NumberOutputValueCaps : c.NumberFeatureValueCaps;
                if (n == 0) continue;
                ushort len = (ushort)(n + 8);
                int sz = Marshal.SizeOf(typeof(HIDP_VALUE_CAPS));
                byte[] buf = new byte[sz * len];
                if (HidP_GetValueCaps(kind, buf, ref len, pp) != HIDP_STATUS_SUCCESS) continue;
                for (int i = 0; i < len; i++)
                {
                    IntPtr p = Marshal.AllocHGlobal(sz);
                    try
                    {
                        Marshal.Copy(buf, i * sz, p, sz);
                        var v = (HIDP_VALUE_CAPS)Marshal.PtrToStructure(p, typeof(HIDP_VALUE_CAPS));
                        string usage = v.IsRange != 0
                            ? string.Format("0x{0:X4}/0x{1:X4}-0x{2:X4}", v.UsagePage, v.UsageMin, v.UsageMax)
                            : string.Format("0x{0:X4}/0x{1:X4}", v.UsagePage, v.UsageMin);
                        sb.AppendLine(string.Format("    {0,-7} RID={1,-3} {2,-22} bit={3,-3} cnt={4,-3} log={5}..{6} phys={7}..{8} units=0x{9:X8} exp={10} abs={11}",
                            kindName[kind], v.ReportID, usage, v.BitSize, v.ReportCount,
                            v.LogicalMin, v.LogicalMax, v.PhysicalMin, v.PhysicalMax, v.Units, v.UnitsExp, v.IsAbsolute));
                    }
                    finally { Marshal.FreeHGlobal(p); }
                }
            }
        }
        finally
        {
            if (pp != IntPtr.Zero) HidD_FreePreparsedData(pp);
            CloseHandle(h);
        }
        return sb.ToString();
    }
}
