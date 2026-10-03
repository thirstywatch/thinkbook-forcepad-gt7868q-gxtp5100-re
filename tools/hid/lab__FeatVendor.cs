// FeatVendor.cs —— ★ 用 HID **feature report** 跑厂商帧
//   依据（fwupd 原厂源码 plugins/goodix-tp/fu-goodixtp-hid-device.c）：
//     fu_goodixtp_hid_device_set_report() → hidraw SET_FEATURE
//     fu_goodixtp_hid_device_get_report() → hidraw GET_FEATURE
//   ⇒ 厂商协议是 feature report，不是 output/input report（本项目历史一直用错了）。
//   帧（不含 report id）: [0]=0x20 [1]=more [2]=seq [3]=5 [4]=方向(1读/0写) [5..6]=addr16BE [7..8]=len16BE
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

public static class FeatVendor
{
    [DllImport("hid.dll", SetLastError = true)] static extern bool HidD_SetFeature(IntPtr h, byte[] b, uint len);
    [DllImport("hid.dll", SetLastError = true)] static extern bool HidD_GetFeature(IntPtr h, byte[] b, uint len);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool CloseHandle(IntPtr h);

    static string Hex(byte[] d, int n)
    {
        if (d == null) return "(null)";
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < d.Length && i < n; i++) { sb.Append(d[i].ToString("X2")); sb.Append(' '); }
        return sb.ToString().Trim();
    }

    static byte[] Parse(string s, int max)
    {
        byte[] r = new byte[max];
        if (string.IsNullOrEmpty(s)) return r;
        string[] t = s.Split(new char[] { ' ', ',', '-' }, StringSplitOptions.RemoveEmptyEntries);
        for (int i = 0; i < t.Length && i < max; i++) r[i] = Convert.ToByte(t[i], 16);
        return r;
    }

    /// <summary>构造 v1 读帧（不含 report id）：20 00 00 05 01 addr16BE len16BE</summary>
    public static byte[] ReadFrame(int addr, int len)
    {
        byte[] f = new byte[9];
        f[0] = 0x20; f[1] = 0x00; f[2] = 0x00; f[3] = 0x05;
        f[4] = 0x01;
        f[5] = (byte)(addr >> 8); f[6] = (byte)addr;
        f[7] = (byte)(len >> 8); f[8] = (byte)len;
        return f;
    }

    /// <summary>在一个集合上试 feature 通道；cols 用逗号分隔</summary>
    public static int Run(string cols, string framehex)
    {
        byte[] frame = Parse(framehex, 64);
        Console.WriteLine("帧(不含 report id): " + Hex(frame, 12));
        foreach (string col in cols.Split(','))
        {
            string c = col.Trim();
            string path = ColProbe.FindPath(c);
            if (string.IsNullOrEmpty(path)) { Console.WriteLine("  " + c + ": 未找到"); continue; }
            Console.WriteLine("=== " + c + " ===");
            IntPtr h = ColProbe.OpenPath(path, true, true);
            string mode = "RW";
            if (h == IntPtr.Zero) { h = ColProbe.OpenPath(path, false, true); mode = "W "; }
            if (h == IntPtr.Zero) { h = ColProbe.OpenPath(path, true, false); mode = "R "; }
            if (h == IntPtr.Zero) { Console.WriteLine("  打开失败 err=" + Marshal.GetLastWin32Error()); continue; }
            Console.WriteLine("  [" + mode + "] caps: " + ColProbe.CapsOf(h));

            byte[] b65 = new byte[65];
            b65[0] = 0x0E;
            Array.Copy(frame, 0, b65, 1, Math.Min(frame.Length, 64));

            bool ok = false; int e = 0;
            if (mode.StartsWith("R")) { Console.WriteLine("  (只读句柄，跳过 SetFeature)"); }
            else
            {
                ok = HidD_SetFeature(h, b65, 65); e = Marshal.GetLastWin32Error();
                Console.WriteLine("  SetFeature(rid=0x0E,len=65) -> " + ok + " err=" + e);
                if (!ok)
                {
                    byte[] b10 = new byte[10];
                    Array.Copy(b65, b10, 10);
                    ok = HidD_SetFeature(h, b10, 10); e = Marshal.GetLastWin32Error();
                    Console.WriteLine("  SetFeature(rid=0x0E,len=10) -> " + ok + " err=" + e);
                }
            }
            if (ok || mode.StartsWith("R"))
            {
                Thread.Sleep(250);
                byte[] r = new byte[65];
                r[0] = 0x0E;
                bool g = HidD_GetFeature(h, r, 65);
                int e3 = Marshal.GetLastWin32Error();
                Console.WriteLine("  ★GetFeature(rid=0x0E,len=65) -> " + g + " err=" + e3);
                if (g)
                {
                    int rl = r[4];
                    Console.WriteLine("     原始: " + Hex(r, 40));
                    Console.WriteLine("     [3]=" + r[3] + " [4]=" + rl + "  数据(偏移5): " + Hex(Slice(r, 5, Math.Min(rl, 32)), Math.Min(rl, 32)));
                }
            }
            CloseHandle(h);
        }
        return 0;
    }

    static byte[] Slice(byte[] s, int off, int n)
    {
        if (n <= 0 || off >= s.Length) return new byte[0];
        if (off + n > s.Length) n = s.Length - off;
        byte[] d = new byte[n];
        Array.Copy(s, off, d, 0, n);
        return d;
    }
}
