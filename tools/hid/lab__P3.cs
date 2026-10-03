// P3.cs -- READ-DIRECTION ONLY frame sender for calibration.
//   Sends ONLY frames whose byte[5] == 0x01 (the read direction flag observed in the
//   working 0e 20 read frame). It never sets byte[5]=0x00 and never builds flash-load frames.
using System;
using System.Runtime.InteropServices;
using System.Text;

public static class P3
{
    [DllImport("hid.dll", SetLastError = true)] static extern bool HidD_SetOutputReport(IntPtr h, byte[] b, uint len);
    [DllImport("hid.dll", SetLastError = true)] static extern bool HidD_GetInputReport(IntPtr h, byte[] b, uint len);
    public static int LastErr;

    // pkt: full frame WITHOUT the leading report id handling; caller passes logical bytes.
    public static byte[] Raw(IntPtr h, byte[] pkt, out string log)
    {
        byte[] b = new byte[65];
        Array.Copy(pkt, b, Math.Min(pkt.Length, 65));
        bool ok = HidD_SetOutputReport(h, b, 65);
        LastErr = Marshal.GetLastWin32Error();
        if (!ok) { log = "send-fail err=" + LastErr; return null; }
        var r = new byte[65];
        r[0] = 0x0E;
        bool ok2 = HidD_GetInputReport(h, r, 65);
        LastErr = Marshal.GetLastWin32Error();
        if (!ok2) { log = "recv-fail err=" + LastErr; return null; }
        int len = r[4]; if (len > 60) len = 60;
        log = string.Format("cont={0} seq={1} len={2}", r[2], r[3], len);
        var outb = new byte[len];
        Array.Copy(r, 5, outb, 0, len);
        return outb;
    }
}
