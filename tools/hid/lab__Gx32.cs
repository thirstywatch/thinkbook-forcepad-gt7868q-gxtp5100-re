// Gx32.cs —— Goodix 厂商通道的 **32 位地址 / 多轮续读** 读取器
//   帧: 0E 20 00 00 07 01 <addr32BE> <size16BE>        (pkt[4]=7, pkt[5]=1)
//   响应: 0E 20 <cont> <seq> <len> <data...>   cont=1 表示还有后续块
// 与既有 Gx.cs 的区别：① 32 位地址；② **按 cont 续读多轮**（Gx.Read32 只做一轮 Recv）
// 只读，不写任何数据。
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

public static class Gx32
{
    [DllImport("hid.dll", SetLastError = true)] static extern bool HidD_SetOutputReport(IntPtr h, byte[] b, uint len);
    [DllImport("hid.dll", SetLastError = true)] static extern bool HidD_GetInputReport(IntPtr h, byte[] b, uint len);

    static IntPtr _h = IntPtr.Zero;
    public static int LastErr;

    public static string Open()
    {
        _h = ColProbe.OpenRW("Col04");
        return _h == IntPtr.Zero ? "open-failed" : "ok";
    }

    static bool Send(byte[] pkt)
    {
        if (_h == IntPtr.Zero && Open() != "ok") return false;
        var b = new byte[65];
        Array.Copy(pkt, b, Math.Min(pkt.Length, 65));
        b[0] = 0x0E;
        bool ok = HidD_SetOutputReport(_h, b, 65);
        LastErr = Marshal.GetLastWin32Error();
        return ok;
    }

    static byte[] Recv()
    {
        var r = new byte[65];
        r[0] = 0x0E;
        bool ok = HidD_GetInputReport(_h, r, 65);
        LastErr = Marshal.GetLastWin32Error();
        return ok ? r : null;
    }

    /// <summary>32 位地址读，按 cont 续读到收敛（最多 8 轮）</summary>
    public static byte[] Read32(uint addr, int size, out string log)
    {
        var pkt = new byte[12];
        pkt[0] = 0x0E; pkt[1] = 0x20; pkt[4] = 0x07; pkt[5] = 0x01;
        pkt[6] = (byte)(addr >> 24); pkt[7] = (byte)(addr >> 16);
        pkt[8] = (byte)(addr >> 8);  pkt[9] = (byte)addr;
        pkt[10] = (byte)(size >> 8); pkt[11] = (byte)size;

        if (!Send(pkt)) { log = "send-fail err=" + LastErr; return null; }

        var acc = new List<byte>();
        var sb = new StringBuilder();
        for (int round = 0; round < 8; round++)
        {
            Thread.Sleep(70);
            byte[] r = Recv();
            if (r == null) { sb.Append("recv-fail err=" + LastErr + " "); break; }
            int len = r[4]; if (len > 60) len = 60;
            sb.Append(string.Format("[c{0} st{1} len{2}] ", r[2], r[3], len));
            for (int i = 0; i < len && (5 + i) < 65; i++) acc.Add(r[5 + i]);
            if (r[2] == 0) break;
        }
        log = sb.ToString().Trim();
        if (acc.Count == 0) return null;
        var o = acc.ToArray();
        if (size > 0 && o.Length > size) { var t = new byte[size]; Array.Copy(o, t, size); o = t; }
        return o;
    }
}
