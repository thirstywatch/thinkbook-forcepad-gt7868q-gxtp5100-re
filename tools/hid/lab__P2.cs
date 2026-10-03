// P2.cs -- read-only helper: issue the SAME 16-bit-address READ frame as Gx.Read,
// but on a caller-supplied handle (so we can pin the exact GXTP5100 Col04 path).
// This class only ever sends READ frames (pkt[5] = 0x01). It has NO write method.
using System;
using System.Runtime.InteropServices;
using System.Text;

public static class P2
{
    [DllImport("hid.dll", SetLastError = true)] static extern bool HidD_SetOutputReport(IntPtr h, byte[] b, uint len);
    [DllImport("hid.dll", SetLastError = true)] static extern bool HidD_GetInputReport(IntPtr h, byte[] b, uint len);

    public static int LastErr;

    static bool Send(IntPtr h, byte[] pkt)
    {
        var b = new byte[65];
        Array.Copy(pkt, b, Math.Min(pkt.Length, 65));
        bool ok = HidD_SetOutputReport(h, b, 65);
        LastErr = Marshal.GetLastWin32Error();
        return ok;
    }

    static byte[] Recv(IntPtr h)
    {
        var r = new byte[65];
        r[0] = 0x0E;
        bool ok = HidD_GetInputReport(h, r, 65);
        LastErr = Marshal.GetLastWin32Error();
        return ok ? r : null;
    }

    // 16-bit address READ frame: 0E 20 00 00 05 01 <addr16BE> <size16BE>
    public static byte[] Read(IntPtr h, int addr, int size, out string log)
    {
        var pkt = new byte[10];
        pkt[0] = 0x0E; pkt[1] = 0x20; pkt[4] = 0x05; pkt[5] = 0x01;   // 0x01 = READ
        pkt[6] = (byte)(addr >> 8); pkt[7] = (byte)addr;
        pkt[8] = (byte)(size >> 8); pkt[9] = (byte)size;
        if (!Send(h, pkt)) { log = "send-fail err=" + LastErr; return null; }

        var acc = new System.Collections.Generic.List<byte>();
        var sb = new StringBuilder();
        for (int round = 0; round < 12; round++)
        {
            System.Threading.Thread.Sleep(60);
            byte[] r = Recv(h);
            if (r == null) { sb.Append("recv-fail err=" + LastErr + " "); break; }
            int len = r[4];
            sb.Append(string.Format("[c{0} st{1} len{2}] ", r[2], r[3], len));
            if (len > 60) len = 60;
            for (int i = 0; i < len && (5 + i) < 65; i++) acc.Add(r[5 + i]);
            if (r[2] == 0) break;
        }
        log = sb.ToString().Trim();
        if (acc.Count == 0) return null;
        var outb = acc.ToArray();
        if (size > 0 && outb.Length > size) { var t = new byte[size]; Array.Copy(outb, t, size); outb = t; }
        return outb;
    }
}
