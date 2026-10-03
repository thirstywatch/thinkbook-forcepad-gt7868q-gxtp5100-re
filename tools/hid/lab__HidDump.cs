// HidDump.cs — 枚举所有 HID 原始输入设备并 dump 其 usage 能力
// 重点：检查触控板是否实现 Haptics (Usage Page 0x0E) —— 微软 Haptic Touchpad 规范
#pragma warning disable 0649, 0169
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public static class HidDump
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

    [StructLayout(LayoutKind.Sequential)]
    struct HIDP_BUTTON_CAPS
    {
        public ushort UsagePage; public byte ReportID; public byte IsAlias; public ushort BitField;
        public ushort LinkCollection, LinkUsage, LinkUsagePage;
        public byte IsRange, IsStringRange, IsDesignatorRange, IsAbsolute;
        // 注意：HIDP_BUTTON_CAPS.Reserved 是 ULONG[10]（不是 USHORT[10]），写错会堆损坏
        public uint R1, R2, R3, R4, R5, R6, R7, R8, R9, R10;
        public ushort UsageMin, UsageMax, StringMin, StringMax, DesignatorMin, DesignatorMax, DataIndexMin, DataIndexMax;
    }

    [DllImport("user32.dll")]
    static extern uint GetRawInputDeviceList([Out] RAWINPUTDEVICELIST[] pRawInputDeviceList, ref uint puiNumDevices, uint cbSize);
    [DllImport("user32.dll", EntryPoint = "GetRawInputDeviceInfoW", CharSet = CharSet.Unicode)]
    static extern uint GetRawInputDeviceInfoStr(IntPtr hDevice, uint uiCommand, StringBuilder pData, ref uint pcbSize);
    [DllImport("user32.dll")]
    static extern uint GetRawInputDeviceInfo(IntPtr hDevice, uint uiCommand, IntPtr pData, ref uint pcbSize);
    [DllImport("hid.dll")]
    static extern bool HidP_GetCaps(IntPtr pp, ref HIDP_CAPS caps);
    [DllImport("hid.dll")]
    static extern bool HidP_GetValueCaps(int reportType, [Out] HIDP_VALUE_CAPS[] caps, ref ushort len, IntPtr pp);
    [DllImport("hid.dll")]
    static extern bool HidP_GetButtonCaps(int reportType, [Out] HIDP_BUTTON_CAPS[] caps, ref ushort len, IntPtr pp);

    const uint RIDI_DEVICENAME = 0x20000007;
    const uint RIDI_DEVICEINFO = 0x2000000b;
    const uint RIDI_PREPARSEDDATA = 0x20000005;
    const uint RIM_TYPEHID = 2;

    public static string[] Dump(string filter)
    {
        var outp = new List<string>();
        uint n = 0;
        uint sz = (uint)Marshal.SizeOf(typeof(RAWINPUTDEVICELIST));
        GetRawInputDeviceList(null, ref n, sz);
        if (n == 0) return new[] { "no raw input devices" };
        var arr = new RAWINPUTDEVICELIST[n];
        uint got = GetRawInputDeviceList(arr, ref n, sz);
        outp.Add("raw input devices: " + got);

        foreach (var d in arr)
        {
            if (d.dwType != RIM_TYPEHID) continue;

            uint s = 0;
            GetRawInputDeviceInfoStr(d.hDevice, RIDI_DEVICENAME, null, ref s);
            string path = "<none>";
            if (s > 0)
            {
                var sb = new StringBuilder((int)s + 2);
                uint s2 = s;
                GetRawInputDeviceInfoStr(d.hDevice, RIDI_DEVICENAME, sb, ref s2);
                path = sb.ToString();
            }
            if (!string.IsNullOrEmpty(filter) && path.IndexOf(filter, StringComparison.OrdinalIgnoreCase) < 0) continue;

            ushort up = 0, us = 0, vid = 0, pid = 0;
            uint isz = 0;
            GetRawInputDeviceInfo(d.hDevice, RIDI_DEVICEINFO, IntPtr.Zero, ref isz);
            if (isz > 0)
            {
                IntPtr ib = Marshal.AllocHGlobal((int)isz);
                try
                {
                    Marshal.WriteInt32(ib, (int)isz);
                    uint g2 = isz;
                    if (GetRawInputDeviceInfo(d.hDevice, RIDI_DEVICEINFO, ib, ref g2) != unchecked((uint)-1))
                    {
                        vid = (ushort)Marshal.ReadInt16(ib, 8);
                        pid = (ushort)Marshal.ReadInt16(ib, 12);
                        up = (ushort)Marshal.ReadInt16(ib, 20);
                        us = (ushort)Marshal.ReadInt16(ib, 22);
                    }
                }
                finally { Marshal.FreeHGlobal(ib); }
            }

            outp.Add("");
            outp.Add("=== " + path);
            outp.Add(string.Format("    VID=0x{0:X4} PID=0x{1:X4} topUsagePage=0x{2:X2} topUsage=0x{3:X2}", vid, pid, up, us));

            uint ppSz = 0;
            GetRawInputDeviceInfo(d.hDevice, RIDI_PREPARSEDDATA, IntPtr.Zero, ref ppSz);
            if (ppSz == 0) { outp.Add("    (no preparsed data)"); continue; }
            IntPtr pp = Marshal.AllocHGlobal((int)ppSz);
            try
            {
                uint g3 = ppSz;
                if (GetRawInputDeviceInfo(d.hDevice, RIDI_PREPARSEDDATA, pp, ref g3) == unchecked((uint)-1)) { outp.Add("    (pp fail)"); continue; }
                var caps = new HIDP_CAPS(); caps.Reserved = new ushort[17];
                if (!HidP_GetCaps(pp, ref caps)) { outp.Add("    (caps fail)"); continue; }
                outp.Add(string.Format("    len: in={0} out={1} feat={2} | linkNodes={3} inVal={4} outVal={5} featVal={6} inBtn={7} featBtn={8}",
                    caps.InputReportByteLength, caps.OutputReportByteLength, caps.FeatureReportByteLength,
                    caps.NumberLinkCollectionNodes, caps.NumberInputValueCaps, caps.NumberOutputValueCaps,
                    caps.NumberFeatureValueCaps, caps.NumberInputButtonCaps, caps.NumberFeatureButtonCaps));

                string[] names = { "IN", "OUT", "FEAT" };
                for (int rt = 0; rt <= 2; rt++)
                {
                    ushort cnt = rt == 0 ? caps.NumberInputValueCaps : (rt == 1 ? caps.NumberOutputValueCaps : caps.NumberFeatureValueCaps);
                    if (cnt == 0) continue;
                    var vc = new HIDP_VALUE_CAPS[cnt];
                    ushort c2 = cnt;
                    if (!HidP_GetValueCaps(rt, vc, ref c2, pp)) continue;
                    for (int i = 0; i < c2; i++)
                    {
                        var c = vc[i];
                        string flag = (c.UsagePage == 0x0E) ? "   <<<< HAPTICS!" : "";
                        outp.Add(string.Format("    {0} rid={1} up=0x{2:X2} u=0x{3:X2} lc={4}(up=0x{5:X2},u=0x{6:X2}) bits={7} cnt={8} log=[{9},{10}] abs={11}{12}",
                            names[rt], c.ReportID, c.UsagePage, c.UsageMin, c.LinkCollection, c.LinkUsagePage, c.LinkUsage,
                            c.BitSize, c.ReportCount, c.LogicalMin, c.LogicalMax, c.IsAbsolute, flag));
                    }
                }
                ushort bc = caps.NumberInputButtonCaps;
                if (bc > 0)
                {
                    var bcs = new HIDP_BUTTON_CAPS[bc];
                    ushort b2 = bc;
                    if (HidP_GetButtonCaps(0, bcs, ref b2, pp))
                    {
                        for (int i = 0; i < b2; i++)
                        {
                            var b = bcs[i];
                            outp.Add(string.Format("    BTN rid={0} up=0x{1:X2} u=0x{2:X2}-0x{3:X2} cnt={4} lc={5}({6})",
                                b.ReportID, b.UsagePage, b.UsageMin, b.UsageMax,
                                (int)(b.UsageMax - b.UsageMin + 1), b.LinkCollection, b.LinkUsage));
                        }
                    }
                }
            }
            finally { Marshal.FreeHGlobal(pp); }
        }
        return outp.ToArray();
    }
}
