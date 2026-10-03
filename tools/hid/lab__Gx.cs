// Gx.cs —— Goodix 厂商命令通道（已实测可用）
//   命令帧 (16 位地址 / GTX8 家族): 0E 20 00 00 05 01 <addr16BE> <size16BE>   [读]
//                                   0E 20 00 00 <len+7> 00 <addr16BE> <len16BE> <data...>  [写]
//   经 Col04 自己的 OUT 报表 (rid=14, 65B) 发送；响应从 Col04 的 IN 报表读回
//   响应: 0E 20 <cont> <seq> <len> <data...>   cont=1 表示还有后续块
using System;
using System.Runtime.InteropServices;
using System.Text;

public static class Gx
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

    /// <summary>
    /// 32 位地址帧读取（BRLB 家族帧；地址可为 0x08000000 等 MCU 空间）
    /// ⚠️ **2026-09-28 实测判否**（见 docs-触控板/追加十）：本机设备**不支持** 32 位地址读 ——
    ///   对照 Read32(0x00004000,16) 返回 8 轮 cont=1 全零（同地址 16 位读返回真实数据）；
    ///   Read32(0x08000000,16) 直接 err=122。
    ///   且本方法**只做一轮 Recv**，会丢掉 cont=1 的续块。请勿再以本方法读 MCU 空间。
    /// </summary>
    public static byte[] Read32(uint addr, int size, out string log)
    {
        var pkt = new byte[12];
        pkt[0] = 0x0E; pkt[1] = 0x20; pkt[4] = 0x07; pkt[5] = 0x01;
        pkt[6] = (byte)(addr >> 24); pkt[7] = (byte)(addr >> 16); pkt[8] = (byte)(addr >> 8); pkt[9] = (byte)addr;
        pkt[10] = (byte)(size >> 8); pkt[11] = (byte)size;
        if (!Send(pkt)) { log = "send-fail err=" + LastErr; return null; }
        System.Threading.Thread.Sleep(120);
        byte[] r = Recv();
        if (r == null) { log = "recv-fail err=" + LastErr; return null; }
        int len = r[4]; if (len > 60) len = 60;
        log = string.Format("cont={0} seq={1} len={2}", r[2], r[3], len);
        var outb = new byte[len];
        Array.Copy(r, 5, outb, 0, len);
        return outb;
    }

    /// <summary>32 位地址帧写入（Dell 工具风格: addr32@[6..9], len16@[10..11]）</summary>
    public static bool Write32(uint addr, byte[] data, out string log)
    {
        var pkt = new byte[12 + data.Length];
        pkt[0] = 0x0E; pkt[1] = 0x20; pkt[2] = 0x00; pkt[3] = 0x00;
        pkt[4] = (byte)(data.Length + 7); pkt[5] = 0x00;
        pkt[6] = (byte)(addr >> 24); pkt[7] = (byte)(addr >> 16); pkt[8] = (byte)(addr >> 8); pkt[9] = (byte)addr;
        pkt[10] = (byte)(data.Length >> 8); pkt[11] = (byte)data.Length;
        Array.Copy(data, 0, pkt, 12, data.Length);
        bool ok = Send(pkt);
        log = "write32(0x" + addr.ToString("X8") + ", " + data.Length + "B) -> " + ok + " err=" + LastErr;
        if (ok) { System.Threading.Thread.Sleep(80); byte[] r = Recv(); if (r != null) log += string.Format(" | resp {0:X2} {1:X2} {2:X2} {3:X2} {4:X2}", r[0], r[1], r[2], r[3], r[4]); }
        return ok;
    }

    /// <summary>读内存；自动续读后续块（cont=1）</summary>
    public static byte[] Read(int addr, int size, out string log)
    {
        var pkt = new byte[10];
        pkt[0] = 0x0E; pkt[1] = 0x20; pkt[4] = 0x05; pkt[5] = 0x01;
        pkt[6] = (byte)(addr >> 8); pkt[7] = (byte)addr;
        pkt[8] = (byte)(size >> 8); pkt[9] = (byte)size;
        if (!Send(pkt)) { log = "send-fail err=" + LastErr; return null; }

        var acc = new System.Collections.Generic.List<byte>();
        var sb = new StringBuilder();
        for (int round = 0; round < 12; round++)
        {
            System.Threading.Thread.Sleep(60);
            byte[] r = Recv();
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

    /// <summary>写内存（危险操作由调用方把关）</summary>
    public static bool Write(int addr, byte[] data, out string log)
    {
        var pkt = new byte[12 + data.Length];
        pkt[0] = 0x0E; pkt[1] = 0x20; pkt[2] = 0x00; pkt[3] = 0x00;
        pkt[4] = (byte)(data.Length + 5);   // ★ 修正 2026-09-29：16 位地址帧官方是 +5（原先误写 +7 ⇒ 整帧被设备丢弃）
        pkt[5] = 0x00;
        pkt[6] = (byte)(addr >> 8); pkt[7] = (byte)addr;
        pkt[8] = (byte)(data.Length >> 8); pkt[9] = (byte)data.Length;
        Array.Copy(data, 0, pkt, 10, data.Length);
        bool ok = Send(pkt);
        log = "write(0x" + addr.ToString("X4") + ", " + data.Length + "B) len+5=" + pkt[4] + " -> " + ok + " err=" + LastErr;
        if (ok) { System.Threading.Thread.Sleep(80); byte[] r = Recv(); if (r != null) log += string.Format(" | resp {0:X2} {1:X2} {2:X2} {3:X2} {4:X2}", r[0], r[1], r[2], r[3], r[4]); }
        return ok;
    }

    public static string Hex(byte[] d, int max)
    {
        if (d == null) return "(null)";
        var sb = new StringBuilder();
        for (int i = 0; i < d.Length && i < max; i++) { sb.Append(d[i].ToString("X2")); sb.Append(i % 32 == 31 ? "\n" : " "); }
        return sb.ToString().TrimEnd();
    }

    public static string Ascii(byte[] d)
    {
        if (d == null) return "";
        var sb = new StringBuilder();
        foreach (byte b in d) sb.Append(b >= 0x20 && b < 0x7F ? (char)b : '.');
        return sb.ToString();
    }
}
