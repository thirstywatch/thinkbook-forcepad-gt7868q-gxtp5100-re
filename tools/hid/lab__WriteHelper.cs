// WriteHelper.cs —— HID 写入辅助类（集中在此文件，避免运行时 Add-Type -TypeDefinition 触发启发式误报）
using System;
using System.Runtime.InteropServices;

public static class FeatWrite
{
    [DllImport("hid.dll", SetLastError = true)] public static extern bool HidD_SetFeature(IntPtr h, byte[] b, uint len);

    /// <summary>经 Col02 rid=11 发厂商写命令（16 位地址帧）</summary>
    public static string Write(IntPtr h, int addr, byte[] data)
    {
        var p = new byte[66];
        p[0] = 0x0E; p[1] = 0x20; p[4] = (byte)(data.Length + 7); p[5] = 0x00;
        p[6] = (byte)(addr >> 8); p[7] = (byte)addr;
        p[8] = (byte)(data.Length >> 8); p[9] = (byte)data.Length;
        Array.Copy(data, 0, p, 10, data.Length);
        var b = new byte[67]; b[0] = 11; Array.Copy(p, 0, b, 1, 66);
        bool ok = HidD_SetFeature(h, b, 67);
        return "rid=11 write16(0x" + addr.ToString("X4") + "," + data.Length + "B) -> " + ok + " err=" + Marshal.GetLastWin32Error();
    }

    /// <summary>经 Col02 rid=11 发厂商写命令（32 位地址帧，Dell 工具风格）</summary>
    public static string Write32(IntPtr h, int addr, byte[] data)
    {
        var p = new byte[66];
        p[0] = 0x0E; p[1] = 0x20; p[4] = (byte)(data.Length + 7); p[5] = 0x00;
        p[6] = (byte)(addr >> 24); p[7] = (byte)(addr >> 16); p[8] = (byte)(addr >> 8); p[9] = (byte)addr;
        p[10] = (byte)(data.Length >> 8); p[11] = (byte)data.Length;
        Array.Copy(data, 0, p, 12, data.Length);
        var b = new byte[67]; b[0] = 11; Array.Copy(p, 0, b, 1, 66);
        bool ok = HidD_SetFeature(h, b, 67);
        return "rid=11 write32(0x" + addr.ToString("X8") + "," + data.Length + "B) -> " + ok + " err=" + Marshal.GetLastWin32Error();
    }
}

/// <summary>按 Goodix 官方 GTX8 源码构造/发送厂商包（关键修正: hidbuf[4] = data_sz + 5）</summary>
public static class GTX8
{
    [DllImport("hid.dll", SetLastError = true)] static extern bool HidD_SetFeature(IntPtr h, byte[] b, uint len);
    [DllImport("hid.dll", SetLastError = true)] static extern bool HidD_SetOutputReport(IntPtr h, byte[] b, uint len);

    public const byte REPORT_ID = 0x0E;
    public const byte I2C_DIRECT_RW = 0x20;
    public const byte I2C_READ_FLAG = 0x01;
    public const byte I2C_WRITE_FLAG = 0x00;

    /// <summary>官方 GTX8 写包: [0]=0E [1]=20 [2]=0(末块) [3]=seq [4]=len+5 [5]=0(写) [6..7]=addr16BE [8..9]=len16BE [10..]=data</summary>
    public static byte[] BuildWrite(int addr, byte[] data)
    {
        var p = new byte[65];
        p[0] = REPORT_ID; p[1] = I2C_DIRECT_RW;
        p[2] = 0x00;               // 单块 → 最后一块
        p[3] = 0x00;               // seq = 0
        p[4] = (byte)(data.Length + 5);   // ★★ 官方是 +5（16 位地址），不是 +7 ★★
        p[5] = I2C_WRITE_FLAG;
        p[6] = (byte)(addr >> 8); p[7] = (byte)addr;
        p[8] = (byte)(data.Length >> 8); p[9] = (byte)data.Length;
        Array.Copy(data, 0, p, 10, data.Length);
        return p;
    }

    /// <summary>官方 GTX8 读包</summary>
    public static byte[] BuildRead(int addr, int size)
    {
        var p = new byte[65];
        p[0] = REPORT_ID; p[1] = I2C_DIRECT_RW;
        p[4] = 0x05; p[5] = I2C_READ_FLAG;
        p[6] = (byte)(addr >> 8); p[7] = (byte)addr;
        p[8] = (byte)(size >> 8); p[9] = (byte)size;
        return p;
    }

    static string SendViaCol04(byte[] pkt)
    {
        var h = ColProbe.OpenRW(ColProbe.FindPath("&col04"));
        if (h == IntPtr.Zero) return "col04-open-fail";
        try
        {
            bool ok = HidD_SetOutputReport(h, pkt, 65);
            return "Col04 OUT -> " + ok + " err=" + Marshal.GetLastWin32Error();
        }
        finally { ColProbe.Close(h); }
    }

    static string SendViaRid11(IntPtr h, byte[] pkt)
    {
        if (h == IntPtr.Zero) return "no-col02-handle";
        var b = new byte[66];
        b[0] = 11;
        Array.Copy(pkt, 0, b, 1, 65);
        bool ok = HidD_SetFeature(h, b, 66);
        return "Col02 rid=11 -> " + ok + " err=" + Marshal.GetLastWin32Error();
    }

    /// <summary>写内存（同时尝试两条通道）</summary>
    public static string Write16(IntPtr col02, int addr, byte[] data)
    {
        var pkt = BuildWrite(addr, data);
        string a = SendViaCol04(pkt);
        string b = SendViaRid11(col02, pkt);
        return "write16(0x" + addr.ToString("X4") + "," + data.Length + "B) len+5=" + pkt[4] + " || " + a + " || " + b;
    }

    /// <summary>发送短命令（6 字节: 0E <op> 00 00 01 01），官方 send_cmd 语义</summary>
    public static string SendCmd(IntPtr col02, byte[] cmd)
    {
        var pkt = new byte[65];
        Array.Copy(cmd, 0, pkt, 0, Math.Min(cmd.Length, 65));
        pkt[0] = REPORT_ID;
        string a = SendViaCol04(pkt);
        string b = SendViaRid11(col02, pkt);
        var sb = new System.Text.StringBuilder();
        for (int i = 0; i < Math.Min(cmd.Length, 6); i++) sb.Append(cmd[i].ToString("X2")).Append(' ');
        return "cmd[" + sb.ToString().Trim() + "] || " + a + " || " + b;
    }
}

/// <summary>厂商命令探测：发命令 + 读响应状态（Col04 OUT/IN，ReportID 0x0E，65 字节）</summary>
public static class CmdProbe
{
    [DllImport("hid.dll", SetLastError = true)] static extern bool HidD_SetOutputReport(IntPtr h, byte[] b, uint len);
    [DllImport("hid.dll", SetLastError = true)] static extern bool HidD_GetInputReport(IntPtr h, byte[] b, uint len);

    /// <summary>发送 65 字节命令包，等待后读回响应</summary>
    public static string SendAndRead(byte[] pkt65, int waitMs)
    {
        var h = ColProbe.OpenRW(ColProbe.FindPath("&col04"));
        if (h == IntPtr.Zero) return "col04-open-fail";
        try
        {
            var b = new byte[65];
            Array.Copy(pkt65, b, Math.Min(pkt65.Length, 65));
            b[0] = 0x0E;
            bool w = HidD_SetOutputReport(h, b, 65);
            int we = Marshal.GetLastWin32Error();
            System.Threading.Thread.Sleep(waitMs);
            var r = new byte[65]; r[0] = 0x0E;
            bool ok = HidD_GetInputReport(h, r, 65);
            int re = Marshal.GetLastWin32Error();
            if (!ok) return string.Format("send={0}/err{1}  recvFAIL/err{2}", w, we, re);
            var sb = new System.Text.StringBuilder();
            for (int i = 0; i < 12; i++) sb.Append(r[i].ToString("X2")).Append(' ');
            return string.Format("send={0} resp[{1}] st={2} len={3}", w, sb.ToString().Trim(), r[3], r[4]);
        }
        finally { ColProbe.Close(h); }
    }

    /// <summary>发送 65 字节命令包，用 4096 字节缓冲读回（应对"响应大于 65 字节"的 err=122 情况）</summary>
    public static string SendAndReadBig(byte[] pkt65, int waitMs)
    {
        var h = ColProbe.OpenRW(ColProbe.FindPath("&col04"));
        if (h == IntPtr.Zero) return "col04-open-fail";
        try
        {
            var b = new byte[65];
            Array.Copy(pkt65, b, Math.Min(pkt65.Length, 65));
            b[0] = 0x0E;
            bool w = HidD_SetOutputReport(h, b, 65);
            int we = Marshal.GetLastWin32Error();
            System.Threading.Thread.Sleep(waitMs);
            var big = new byte[4096]; big[0] = 0x0E;
            bool ok = HidD_GetInputReport(h, big, 4096);
            int re = Marshal.GetLastWin32Error();
            if (!ok) return string.Format("send={0}/err{1}  recvFAIL/err{2}", w, we, re);
            var sb = new System.Text.StringBuilder();
            for (int i = 0; i < 24; i++) sb.Append(big[i].ToString("X2")).Append(' ');
            return string.Format("send={0} big24[{1}]", w, sb.ToString().Trim());
        }
        finally { ColProbe.Close(h); }
    }

    /// <summary>短命令探测: 0E &lt;op&gt; 00 00 01 01</summary>
    public static string ProbeOp(byte op, int waitMs)
    {
        var p = new byte[65];
        p[0] = 0x0E; p[1] = op; p[2] = 0x00; p[3] = 0x00; p[4] = 0x01; p[5] = 0x01;
        return "op=0x" + op.ToString("X2") + "  " + SendAndRead(p, waitMs);
    }

    /// <summary>读内存命令（已知合法，作为对照）</summary>
    public static string ProbeReadMem(int addr, int size, int waitMs)
    {
        var p = new byte[65];
        p[0] = 0x0E; p[1] = 0x20; p[2] = 0x00; p[3] = 0x00; p[4] = 0x05; p[5] = 0x01;
        p[6] = (byte)(addr >> 8); p[7] = (byte)addr;
        p[8] = (byte)(size >> 8); p[9] = (byte)size;
        return "readMem(0x" + addr.ToString("X4") + "," + size + ")  " + SendAndRead(p, waitMs);
    }
}

/// <summary>Col03 的 Input Mode 写入（等价于 Fn+F8 的恢复动作）</summary>
public static class InputMode
{
    [DllImport("hid.dll", SetLastError = true)] static extern bool HidD_SetFeature(IntPtr h, byte[] b, uint len);

    public static string Set(IntPtr h, int mode)
    {
        var b = new byte[3]; b[0] = 3; b[1] = (byte)mode; b[2] = 0;
        bool ok = HidD_SetFeature(h, b, 3);
        return "Col03 rid=3 InputMode=" + mode + " -> " + ok + " err=" + Marshal.GetLastWin32Error();
    }
}
