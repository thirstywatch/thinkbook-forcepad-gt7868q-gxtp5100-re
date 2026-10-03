// VibProbe.cs —— 扩展命令类（0x80/0xA0/0xA1）**单发**探针
//   帧格式（本轮从固件反汇编得出）：
//     [0]=0x0E  [1]=类  [2..3]=子命令(u16 LE)  [4]=长度  [5]=方向(1=读/0=写)  [6..]=payload
//   历史教训：以前所有帧的 [2..3] 恒为 0 ⇒ 扩展类从未被探测过。
//
// 本工具只做四件事（严格单发、不轮询、不枚举）：
//   ① 打开 Col04（完整路径 + 校验 VID 27C6，防 Intel intc816&col02 误命中）
//   ② 体检：已知安全的类 0x20 读 0x1000 ×16
//   ③ 单发一条扩展帧，然后排空读回（最多 3 次、每次间隔 200ms）
//   ④ 再体检一次
using System;
using System.Runtime.InteropServices;
using System.Text;

public static class VibProbe
{
    [DllImport("hid.dll", SetLastError = true)] static extern bool HidD_SetOutputReport(IntPtr h, byte[] b, uint len);
    [DllImport("hid.dll", SetLastError = true)] static extern bool HidD_GetInputReport(IntPtr h, byte[] b, uint len);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool ReadFile(IntPtr h, byte[] buf, uint n, out uint got, IntPtr ol);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool CloseHandle(IntPtr h);

    static IntPtr _h = IntPtr.Zero;
    static string _path = null;

    static IntPtr Open()
    {
        string p = ColProbe.FindPath("col04");
        if (string.IsNullOrEmpty(p)) { Console.WriteLine("!! Col04 路径未找到"); return IntPtr.Zero; }
        if (p.IndexOf("gxtp5100", StringComparison.OrdinalIgnoreCase) < 0 ||
            p.IndexOf("col04", StringComparison.OrdinalIgnoreCase) < 0)
        { Console.WriteLine("!! 路径既非 GXTP5100 也非 col04，拒绝打开（防误命中）: " + p); return IntPtr.Zero; }
        Console.WriteLine("path: " + p);
        _path = p;
        IntPtr h = ColProbe.OpenPath(p, true, true);
        if (h == IntPtr.Zero) Console.WriteLine("!! OpenPath 失败 err=" + Marshal.GetLastWin32Error());
        return h;
    }

    static bool Send(IntPtr h, byte[] pkt, out int err)
    {
        byte[] b = new byte[65];
        Array.Copy(pkt, b, Math.Min(pkt.Length, 65));
        b[0] = 0x0E;
        bool ok = HidD_SetOutputReport(h, b, 65);
        err = Marshal.GetLastWin32Error();
        return ok;
    }

    static byte[] Recv(IntPtr h, out int err)
    {
        byte[] r = new byte[65];
        r[0] = 0x0E;
        bool ok = HidD_GetInputReport(h, r, 65);
        err = Marshal.GetLastWin32Error();
        return ok ? r : null;
    }

    static byte[] RecvBig(IntPtr h, out int err)
    {
        byte[] r = new byte[4096];
        r[0] = 0x0E;
        bool ok = HidD_GetInputReport(h, r, 4096);
        err = Marshal.GetLastWin32Error();
        return ok ? r : null;
    }

    /// <summary>捞"自发"输入报文（ReadFile，带超时；超时则线程留在后台，进程随即退出）</summary>
    static byte[] RecvSpontaneous(IntPtr h, int ms, out int err)
    {
        byte[] buf = new byte[4096];
        uint got = 0;
        int e = 0;
        byte[] result = null;
        System.Threading.Thread t = new System.Threading.Thread(delegate ()
        {
            bool ok = ReadFile(h, buf, 4096, out got, IntPtr.Zero);
            e = Marshal.GetLastWin32Error();
            if (ok && got > 0) { result = new byte[got]; Array.Copy(buf, result, (int)got); }
        });
        t.IsBackground = true;
        t.Start();
        bool finished = t.Join(ms);
        err = finished ? e : -1;
        return finished ? result : null;
    }

    static string Hex(byte[] d, int n)
    {
        if (d == null) return "(null)";
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < d.Length && i < n; i++) { sb.Append(d[i].ToString("X2")); sb.Append(' '); }
        return sb.ToString().Trim();
    }

    /// <summary>体检：类 0x20 读 0x1000 ×16（项目历史上唯一"已知安全"的命令）</summary>
    static bool Health(IntPtr h, string tag)
    {
        byte[] pkt = new byte[10];
        pkt[1] = 0x20; pkt[4] = 0x05; pkt[5] = 0x01;
        pkt[6] = 0x10; pkt[7] = 0x00; pkt[8] = 0x00; pkt[9] = 0x10;   // addr16BE=0x1000, size16BE=16
        int err;
        if (!Send(h, pkt, out err)) { Console.WriteLine("[" + tag + "] 发送失败 err=" + err); return false; }
        System.Threading.Thread.Sleep(120);
        byte[] r = Recv(h, out err);
        if (r == null) { Console.WriteLine("[" + tag + "] 读回失败 err=" + err + "  ⇒ IC 不应答！"); return false; }
        Console.WriteLine("[" + tag + "] " + Hex(r, 24));
        return r[4] > 0;
    }

    public static int Run(int cls, int sub, string payhex)
    {
        IntPtr h = Open();
        if (h == IntPtr.Zero) return 1;

        Console.WriteLine("== 体检 1 ==");
        bool alive1 = Health(h, "before");

        byte[] pkt = new byte[65];
        pkt[1] = (byte)cls;
        pkt[2] = (byte)(sub & 0xFF);
        pkt[3] = (byte)((sub >> 8) & 0xFF);
        pkt[4] = 0x05; pkt[5] = 0x01;                       // 长度 / 读方向（与已验证的读帧同形）
        if (!string.IsNullOrEmpty(payhex))
        {
            string[] t = payhex.Split(new char[] { ' ', ',' }, StringSplitOptions.RemoveEmptyEntries);
            for (int i = 0; i < t.Length && 6 + i < 65; i++) pkt[6 + i] = Convert.ToByte(t[i], 16);
        }

        Console.WriteLine("== 单发扩展帧: " + Hex(pkt, 12) + " ==");
        int err;
        bool sent = Send(h, pkt, out err);
        Console.WriteLine("send = " + sent + " err=" + err);
        if (sent)
        {
            System.Threading.Thread.Sleep(220);
            byte[] r = Recv(h, out err);
            if (r == null) { System.Threading.Thread.Sleep(220); r = Recv(h, out err); }
            if (r == null) Console.WriteLine("  65B 读回失败 err=" + err);
            else Console.WriteLine("  65B recv " + Hex(r, 40));
            if (r == null)
            {
                byte[] rb = RecvBig(h, out err);
                if (rb == null) Console.WriteLine("  4096B 读回也失败 err=" + err);
                else Console.WriteLine("  4096B recv " + Hex(rb, 64));
            }
            if (r == null)
            {
                // ★ 独立句柄做自发报文监听：绝不能用命令句柄（会堵死后续 GetInputReport）
                IntPtr h2 = ColProbe.OpenPath(_path, true, false);
                if (h2 == IntPtr.Zero) Console.WriteLine("  监听句柄打开失败 err=" + Marshal.GetLastWin32Error());
                else
                {
                    byte[] rs = RecvSpontaneous(h2, 700, out err);
                    if (rs == null) Console.WriteLine("  [独立句柄] ReadFile 700ms 内无数据 err=" + err);
                    else Console.WriteLine("  [独立句柄] ReadFile 收到 " + rs.Length + "B: " + Hex(rs, 64));
                    CloseHandle(h2);
                }
            }
        }

        Console.WriteLine("== 体检 2 ==");
        bool alive2 = Health(h, "after");
        CloseHandle(h);
        Console.WriteLine("结论: 前 " + (alive1 ? "活" : "死") + " / 后 " + (alive2 ? "活" : "死"));
        return alive2 ? 0 : 2;
    }

    /// <summary>只发不读（因为 0xA1 之后同进程读会永久阻塞）</summary>
    public static int SendOnly(int cls, int sub, string payhex)
    {
        IntPtr h = Open();
        if (h == IntPtr.Zero) return 1;
        Console.WriteLine("== 体检 ==");
        Health(h, "before");
        byte[] pkt = new byte[65];
        pkt[1] = (byte)cls; pkt[2] = (byte)(sub & 0xFF); pkt[3] = (byte)((sub >> 8) & 0xFF);
        pkt[4] = 0x05; pkt[5] = 0x01;
        if (!string.IsNullOrEmpty(payhex))
        {
            string[] t = payhex.Split(new char[] { ' ', ',' }, StringSplitOptions.RemoveEmptyEntries);
            for (int i = 0; i < t.Length && 6 + i < 65; i++) pkt[6 + i] = Convert.ToByte(t[i], 16);
        }
        int err;
        Console.WriteLine("== 单发(不读): " + Hex(pkt, 12) + " ==");
        Console.WriteLine("send = " + Send(h, pkt, out err) + " err=" + err);
        return 0;   // 立刻退出，把读留给下一个进程
    }

    /// <summary>只读不发：找 0xA2 形状的回复（新进程，输入通道已恢复）</summary>
    public static int Listen(int ms)
    {
        IntPtr h = Open();
        if (h == IntPtr.Zero) return 1;
        int err;
        byte[] r = Recv(h, out err);
        Console.WriteLine("  GET_INPUT(0x0E, 65B)  : " + (r == null ? "err=" + err : Hex(r, 40)));
        byte[] rb = RecvBig(h, out err);
        Console.WriteLine("  GET_INPUT(0x0E, 4096B): " + (rb == null ? "err=" + err : Hex(rb, 64)));
        IntPtr h2 = ColProbe.OpenPath(_path, true, false);
        if (h2 != IntPtr.Zero)
        {
            byte[] rs = RecvSpontaneous(h2, ms, out err);
            Console.WriteLine("  ReadFile(" + ms + "ms)      : " + (rs == null ? "无数据 err=" + err : rs.Length + "B " + Hex(rs, 64)));
            CloseHandle(h2);
        }
        else Console.WriteLine("  监听句柄打开失败 err=" + Marshal.GetLastWin32Error());
        CloseHandle(h);
        return 0;
    }
}
