// HapticCap.cs —— 触控板「触觉能力」探测内核（纯用户态、只读、零注入）
//
// 判据来源（全部为一手规范）：
//   · Linux 6.18 drivers/hid/hid-haptic.c —— 能力驱动，无 vendor ID 白名单：
//       需要 0x0E/0x20 AutoTrigger + 0x0E/0x21 ManualTrigger(OUTPUT) + 0x0E/0x10/0x11
//       + ABS_MT_PRESSURE 单位 = 克/牛顿
//   · 微软 Input Device Haptics Implementation Guide / Precision Touchpad Tuning：
//       host-initiated 必需 Manual Trigger(0x0E/0x21, OUTPUT) + Waveform/Duration List(FEATURE)
//       device-initiated 允许 Haptic Intensity(0x0E/0x23, FEATURE) + ButtonPressThreshold(0x0D/0xB0)
//   · ★ 分水岭：同一个 0x0E/0x23，落在 OUTPUT（Manual Trigger 报表内）⇒ 有扳机；
//                 落在独立 FEATURE ⇒ 只有音量旋钮。
//
// 安全：只做 SetupAPI 枚举 + CreateFile(access=0) + HidD_GetPreparsedData + HidP_Get*Caps。
//       不发送任何报文、不写任何 feature、不改任何设备状态。
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public static class HapticCap
{
    // ================= P/Invoke =================
    [StructLayout(LayoutKind.Sequential)]
    public struct GUID { public uint D1; public ushort D2, D3; [MarshalAs(UnmanagedType.ByValArray, SizeConst = 8)] public byte[] D4; }
    [StructLayout(LayoutKind.Sequential)]
    public struct SP_DID { public uint cbSize; public GUID g; public uint Flags; public IntPtr R; }
    [StructLayout(LayoutKind.Sequential)]
    public struct HIDP_CAPS
    {
        public ushort Usage, UsagePage;
        public ushort InLen, OutLen, FeatLen;
        public ushort R0, R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13, R14, R15, R16;
        public ushort LinkColl;
        public ushort InBtn, InVal, InDI;
        public ushort OutBtn, OutVal, OutDI;
        public ushort FeatBtn, FeatVal, FeatDI;
    }
    [StructLayout(LayoutKind.Sequential)]
    public struct VCAPS
    {
        public ushort UsagePage; public byte ReportID, IsAlias;
        public ushort BitField, LinkCollection, LinkUsage, LinkUsagePage;
        public byte IsRange, IsStringRange, IsDesignatorRange, IsAbsolute, HasNull, Reserved;
        public ushort BitSize, ReportCount;
        public ushort R2a, R2b, R2c, R2d, R2e;
        public uint UnitsExp, Units;
        public int LogicalMin, LogicalMax, PhysicalMin, PhysicalMax;
        public ushort UsageMin, UsageMax, StringMin, StringMax, DesignatorMin, DesignatorMax, DataIndexMin, DataIndexMax;
    }

    [DllImport("setupapi", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr SetupDiGetClassDevsW(ref GUID g, string e, IntPtr h, uint f);
    [DllImport("setupapi", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool SetupDiEnumDeviceInterfaces(IntPtr h, IntPtr di, ref GUID g, uint i, ref SP_DID d);
    [DllImport("setupapi", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool SetupDiGetDeviceInterfaceDetailW(IntPtr h, ref SP_DID d, IntPtr buf, uint sz, ref uint need, IntPtr di);
    [DllImport("setupapi", SetLastError = true)]
    static extern bool SetupDiDestroyDeviceInfoList(IntPtr h);
    [DllImport("hid", SetLastError = true)]
    static extern void HidD_GetHidGuid(ref GUID g);
    [DllImport("hid", SetLastError = true)]
    static extern bool HidD_GetPreparsedData(IntPtr h, out IntPtr pp);
    [DllImport("hid", SetLastError = true)]
    static extern bool HidD_FreePreparsedData(IntPtr pp);
    [DllImport("hid", SetLastError = true)]
    static extern int HidP_GetCaps(IntPtr pp, ref HIDP_CAPS c);
    [DllImport("hid", SetLastError = true)]
    static extern int HidP_GetValueCaps(int type, [Out] VCAPS[] arr, ref ushort n, IntPtr pp);
    [DllImport("kernel32", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr CreateFileW(string p, uint acc, uint share, IntPtr sa, uint disp, uint fl, IntPtr t);
    [DllImport("kernel32", SetLastError = true)]
    static extern bool CloseHandle(IntPtr h);

    const uint DIGCF_PRESENT = 0x2, DIGCF_DEVICEINTERFACE = 0x10;
    static readonly IntPtr INVALID = new IntPtr(-1);
    // ★ HidP_* 返回的是 NTSTATUS，成功值是 0x00110000 而不是 0 —— 判成 `!= 0` 会把所有结果跳过
    const int HIDP_STATUS_SUCCESS = 0x00110000;
    public static bool HidpOk(int rc) { return rc == HIDP_STATUS_SUCCESS; }

    // ================= 结果模型 =================
    public class Field
    {
        public string ReportType;     // Input / Output / Feature
        public byte Rid;
        public ushort Page, UsageMin, UsageMax;
        public bool IsRange;
        public ushort BitSize, ReportCount;
        public int LMin, LMax;
        public uint Units, UnitsExp;
        public string Usage { get { return IsRange ? ("0x" + Page.ToString("X4") + "/" + UsageMin.ToString("X4") + ".." + UsageMax.ToString("X4")) : ("0x" + Page.ToString("X4") + "/" + UsageMin.ToString("X4")); } }
    }

    public class Collection
    {
        public string Path;
        public string Tag;
        public ushort UsagePage, Usage;
        public ushort InLen, OutLen, FeatLen;
        public int LinkColl;
        public int HidpStatus;
        public List<Field> Fields = new List<Field>();
        public string OpenNote = "";

        // —— 判据位 ——
        public bool HasAutoTrigger, HasManualTriggerOut, HasWaveformList, HasDurationList;
        public bool HasIntensity, IntensityInOutput, IntensityInFeature;
        public bool HasButtonPressThreshold;
        public Field PressureField;
        public int PressureRid;
        public bool HasHapticsPage;

        public string Level
        {
            get
            {
                bool coreComplete = HasAutoTrigger && HasManualTriggerOut && HasWaveformList && HasDurationList;
                if (coreComplete) return "A_HAS_TRIGGER";
                if (HasManualTriggerOut || HasIntensity) return "B_PARTIAL";
                if (HasHapticsPage) return "B_PARTIAL";
                return "C_NONE";
            }
        }
        public string LevelText
        {
            get
            {
                switch (Level)
                {
                    case "A_HAS_TRIGGER": return "A · 有扳机（主机可主动触发震动）";
                    case "B_PARTIAL": return "B · 只有旋钮（可调参数，不能主动触发）";
                    default: return "C · 无触觉接口";
                }
            }
        }
    }

    static IntPtr OpenAny(string path, out string note)
    {
        // ★ access=0 + share=3 可绕过 PTP 驱动对 Col02 的独占（实测 err=32 → ok）
        uint[] shares = { 3, 1, 0 };
        foreach (uint sh in shares)
        {
            IntPtr h = CreateFileW(path, 0, sh, IntPtr.Zero, 3, 0, IntPtr.Zero);
            if (h != INVALID && h != IntPtr.Zero) { note = "access=0/share=" + sh; return h; }
        }
        note = "打开失败 err=" + Marshal.GetLastWin32Error();
        return IntPtr.Zero;
    }

    public static List<string> EnumPaths(string filter)
    {
        var list = new List<string>();
        GUID g = new GUID { D4 = new byte[8] };
        HidD_GetHidGuid(ref g);
        IntPtr hdev = SetupDiGetClassDevsW(ref g, null, IntPtr.Zero, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);
        if (hdev == INVALID || hdev == IntPtr.Zero) return list;
        uint i = 0;
        while (true)
        {
            var did = new SP_DID(); did.cbSize = (uint)Marshal.SizeOf(typeof(SP_DID));
            did.g.D4 = new byte[8];
            if (!SetupDiEnumDeviceInterfaces(hdev, IntPtr.Zero, ref g, i++, ref did)) break;
            uint need = 0;
            SetupDiGetDeviceInterfaceDetailW(hdev, ref did, IntPtr.Zero, 0, ref need, IntPtr.Zero);
            if (need == 0) continue;
            IntPtr buf = Marshal.AllocHGlobal((int)need + 8);
            try
            {
                Marshal.WriteInt32(buf, IntPtr.Size == 8 ? 8 : 6);
                if (SetupDiGetDeviceInterfaceDetailW(hdev, ref did, buf, need, ref need, IntPtr.Zero))
                {
                    string p = Marshal.PtrToStringUni(new IntPtr(buf.ToInt64() + 4));
                    if (!string.IsNullOrEmpty(p) && (string.IsNullOrEmpty(filter) || p.ToLower().Contains(filter.ToLower())))
                        list.Add(p);
                }
            }
            finally { Marshal.FreeHGlobal(buf); }
        }
        SetupDiDestroyDeviceInfoList(hdev);
        return list;
    }

    public static List<Collection> Probe(string filter)
    {
        var outp = new List<Collection>();
        foreach (string path in EnumPaths(filter))
        {
            var c = new Collection { Path = path };
            int hash = path.IndexOf('#');
            c.Tag = (hash >= 0 && path.Length > hash + 1) ? path.Substring(hash + 1).Split('#')[0] : path;

            IntPtr h = OpenAny(path, out c.OpenNote);
            if (h == IntPtr.Zero) { outp.Add(c); continue; }
            try
            {
                IntPtr pp;
                if (!HidD_GetPreparsedData(h, out pp) || pp == IntPtr.Zero)
                { c.OpenNote += " / preparsed 失败 err=" + Marshal.GetLastWin32Error(); outp.Add(c); continue; }
                try
                {
                    var caps = new HIDP_CAPS();
                    c.HidpStatus = HidP_GetCaps(pp, ref caps);
                    c.UsagePage = caps.UsagePage; c.Usage = caps.Usage;
                    c.InLen = caps.InLen; c.OutLen = caps.OutLen; c.FeatLen = caps.FeatLen;
                    c.LinkColl = caps.LinkColl;

                    string[] names = { "Input", "Output", "Feature" };
                    for (int t = 0; t <= 2; t++)
                    {
                        ushort n = 256;
                        var arr = new VCAPS[256];
                        int rc = HidP_GetValueCaps(t, arr, ref n, pp);
                        if (rc != HIDP_STATUS_SUCCESS || n == 0) continue;
                        for (int k = 0; k < n && k < 256; k++)
                        {
                            var v = arr[k];
                            var f = new Field
                            {
                                ReportType = names[t],
                                Rid = v.ReportID,
                                Page = v.UsagePage,
                                UsageMin = v.UsageMin,
                                UsageMax = v.UsageMax,
                                IsRange = v.IsRange != 0,
                                BitSize = v.BitSize,
                                ReportCount = v.ReportCount,
                                LMin = v.LogicalMin,
                                LMax = v.LogicalMax,
                                Units = v.Units,
                                UnitsExp = v.UnitsExp
                            };
                            c.Fields.Add(f);
                        }
                    }
                    Classify(c);
                }
                finally { HidD_FreePreparsedData(pp); }
            }
            finally { CloseHandle(h); }
            outp.Add(c);
        }
        return outp;
    }

    static void Classify(Collection c)
    {
        foreach (var f in c.Fields)
        {
            bool isHap = (f.Page == 0x000E);
            if (isHap) c.HasHapticsPage = true;

            if (isHap && f.UsageMin == 0x20) c.HasAutoTrigger = true;                       // Auto Trigger
            if (isHap && f.UsageMin == 0x21 && f.ReportType == "Output") c.HasManualTriggerOut = true; // ★ 扳机
            if (isHap && f.UsageMin == 0x10) c.HasWaveformList = true;
            if (isHap && f.UsageMin == 0x11) c.HasDurationList = true;
            if (isHap && f.UsageMin == 0x23)
            {
                c.HasIntensity = true;
                if (f.ReportType == "Output") c.IntensityInOutput = true;
                if (f.ReportType == "Feature") c.HasIntensity = true; c.IntensityInFeature |= (f.ReportType == "Feature");
            }
            if (f.Page == 0x000D && f.UsageMin == 0xB0) c.HasButtonPressThreshold = true;    // Button Press Threshold
            if (f.Page == 0x000D && f.UsageMin == 0x0030 && f.ReportType == "Input" && c.PressureField == null)
            { c.PressureField = f; c.PressureRid = f.Rid; }                                 // Tip Pressure
        }
    }

    // ---- 单位解码：HID 的 Units 是 nibble 编码，质量在 bits 8..11 ----
    public static string UnitText(Field f)
    {
        if (f == null) return "(无压力字段)";
        uint mass = (f.Units >> 8) & 0xF;
        string sysName = ((f.Units >> 0) & 0xF) == 1 ? "SI Linear" : ((f.Units >> 0) & 0xF) == 2 ? "SI Rotation" : ((f.Units >> 0) & 0xF) == 3 ? "English Linear" : "无";
        string massName = mass == 1 ? "克(gram)" : mass == 2 ? "slug" : mass == 3 ? "克? (3)" : mass == 4 ? "千克?" : mass == 0 ? "无" : ("未知(" + mass + ")");
        string exp = ((f.UnitsExp & 0xF) == 0xF) ? ("-" + (((f.UnitsExp >> 4) & 0xF))) : ("" + ((f.UnitsExp >> 4) & 0xF));
        return "Units=0x" + f.Units.ToString("X4") + " (" + sysName + ", 质量=" + massName + ") UnitsExp=0x" + f.UnitsExp.ToString("X2") + " (10^" + exp + ")";
    }

    // ---- 报告 ----
    public static string Report(string filter)
    {
        var cols = Probe(filter);
        var sb = new StringBuilder();
        sb.AppendLine("================================================================================");
        sb.AppendLine(" 触控板触觉能力探测（纯用户态只读 · 零注入）");
        sb.AppendLine(" 判据：Linux 6.18 hid-haptic.c（能力驱动，无 ID 白名单）+ 微软 Haptics 规范");
        sb.AppendLine("================================================================================");
        sb.AppendLine("枚举到 " + cols.Count + " 个匹配接口");
        int a = 0, b = 0, cc = 0;
        foreach (var c in cols)
        {
            sb.AppendLine();
            sb.AppendLine("------------------------------------------------------------");
            sb.AppendLine("接口  : " + c.Tag);
            sb.AppendLine("句柄  : " + c.OpenNote + (c.HidpStatus != HIDP_STATUS_SUCCESS ? ("   HidP_GetCaps rc=0x" + c.HidpStatus.ToString("X8")) : ""));
            if (c.Fields.Count == 0 && c.HidpStatus != HIDP_STATUS_SUCCESS) { sb.AppendLine("判定  : (读不到 caps)"); continue; }
            sb.AppendLine(string.Format("Caps  : UsagePage=0x{0:X4} Usage=0x{1:X4}  In={2} Out={3} Feat={4}  LinkColl={5}",
                c.UsagePage, c.Usage, c.InLen, c.OutLen, c.FeatLen, c.LinkColl));
            sb.AppendLine();
            sb.AppendLine("★ 判定: " + c.LevelText);
            sb.AppendLine();
            sb.AppendLine("判据逐条 ——（来自 Linux hid-haptic.c，四条核心齐全才算 A）");
            sb.AppendLine("  [1] 0x0E/0x20 Auto Trigger          : " + YN(c.HasAutoTrigger));
            sb.AppendLine("  [2] 0x0E/0x21 Manual Trigger(OUTPUT): " + YN(c.HasManualTriggerOut) + "   ← ★ 决定性");
            sb.AppendLine("  [3] 0x0E/0x10 Waveform List         : " + YN(c.HasWaveformList));
            sb.AppendLine("  [4] 0x0E/0x11 Duration List         : " + YN(c.HasDurationList));
            sb.AppendLine("  [5] TipPressure(0x0D/0x30) 的单位    : " + UnitText(c.PressureField));
            sb.AppendLine("      ⇒ 上游要求 克/牛顿；" + (c.PressureField != null && ((c.PressureField.Units >> 8) & 0xF) != 0 ? "★ 有质量单位" : "✗ 无物理单位 ⇒ 不满足"));
            sb.AppendLine();
            sb.AppendLine("旋钮位置（★ 分水岭）");
            sb.AppendLine("  Haptics usage page 0x0E 出现        : " + YN(c.HasHapticsPage));
            sb.AppendLine("  0x0E/0x23 Intensity                 : " + YN(c.HasIntensity));
            sb.AppendLine("      · 在 OUTPUT 报表里 ⇒ 有扳机形态  : " + YN(c.IntensityInOutput));
            sb.AppendLine("      · 在 FEATURE 报表里 ⇒ 只有旋钮    : " + YN(c.IntensityInFeature));
            sb.AppendLine("  0x0D/0xB0 Button Press Threshold    : " + YN(c.HasButtonPressThreshold));
            sb.AppendLine();
            sb.AppendLine("触觉相关字段明细");
            bool any = false;
            foreach (var f in c.Fields)
            {
                bool rel = (f.Page == 0x000E) || (f.Page == 0x000D && (f.UsageMin == 0xB0 || f.UsageMin == 0x0030));
                if (!rel) continue;
                any = true;
                sb.AppendLine(string.Format("  {0,-7} RID={1,-3} {2,-18} bit={3,-3} cnt={4,-3} {5}..{6}",
                    f.ReportType, f.Rid, f.Usage, f.BitSize, f.ReportCount, f.LMin, f.LMax));
            }
            if (!any) sb.AppendLine("  (无)");
            if (c.Level == "A_HAS_TRIGGER") a++;
            else if (c.Level == "B_PARTIAL") b++;
            else cc++;
        }
        sb.AppendLine();
        sb.AppendLine("================================================================================");
        sb.AppendLine(string.Format("汇总：A(有扳机)={0}   B(只有旋钮)={1}   C(无)={2}", a, b, cc));
        sb.AppendLine("================================================================================");
        return sb.ToString();
    }
    static string YN(bool x) { return x ? "✅ 有" : "❌ 无"; }
}
