// VibLink.cs —— "发/读分离" 探针 v2（2026-09-14）
//   设计要点（针对上一轮两次卡死）：
//     ★ 每一次 HID 调用都跑在独立后台线程里 + Join(超时) ⇒ 任何一次阻塞都只损失那一条，绝不吞掉整轮
//     ★ 发命令(SEND)与读回复(LISTEN)强制分成两个进程：SEND 只发不读，进程立刻退出
//   帧格式（VibProbe 已验证）：[0]=0x0E [1]=类 [2..3]=子命令(u16 LE) [4]=长度 [5]=方向 [6..]=payload
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

public static class VibLink
{
    [DllImport("hid.dll", SetLastError = true)] static extern bool HidD_SetOutputReport(IntPtr h, byte[] b, uint len);
    [DllImport("hid.dll", SetLastError = true)] static extern bool HidD_GetInputReport(IntPtr h, byte[] b, uint len);
    [DllImport("hid.dll", SetLastError = true)] static extern bool HidD_GetFeature(IntPtr h, byte[] b, uint len);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool ReadFile(IntPtr h, byte[] buf, uint n, out uint got, IntPtr ol);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool CloseHandle(IntPtr h);

    delegate string Job();

    static string Hex(byte[] d, int n)
    {
        if (d == null) return "(null)";
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < d.Length && i < n; i++) { sb.Append(d[i].ToString("X2")); sb.Append(' '); }
        return sb.ToString().Trim();
    }

    static byte[] ParseHex(string s, int max)
    {
        byte[] r = new byte[max];
        if (string.IsNullOrEmpty(s)) return r;
        string[] t = s.Split(new char[] { ' ', ',', '-' }, StringSplitOptions.RemoveEmptyEntries);
        for (int i = 0; i < t.Length && i < max; i++) r[i] = Convert.ToByte(t[i], 16);
        return r;
    }

    static IntPtr OpenCol(string col, bool rd, bool wr, out string path)
    {
        path = ColProbe.FindPath(col);
        if (string.IsNullOrEmpty(path)) { Console.WriteLine("!! 未找到集合 " + col); return IntPtr.Zero; }
        if (path.IndexOf("gxtp5100", StringComparison.OrdinalIgnoreCase) < 0)
        { Console.WriteLine("!! 路径不是 GXTP5100，拒绝: " + path); return IntPtr.Zero; }
        IntPtr h = ColProbe.OpenPath(path, rd, wr);
        if (h == IntPtr.Zero) Console.WriteLine("!! 打开失败 " + col + " err=" + Marshal.GetLastWin32Error());
        return h;
    }

    /// <summary>★ 所有 HID 调用的统一护栏：独立线程 + 超时</summary>
    static void G(string tag, int ms, Job j)
    {
        string res = "(未完成)";
        Thread t = new Thread(delegate ()
        {
            try { res = j(); }
            catch (Exception ex) { res = "EX " + ex.GetType().Name + ": " + ex.Message; }
        });
        t.IsBackground = true;
        t.Start();
        bool fin = t.Join(ms);
        Console.WriteLine("  " + tag.PadRight(40) + " : " + (fin ? res : "★阻塞(>" + ms + "ms) — 该路径无回复"));
    }

    static string InRep(IntPtr h, int rid, int len)
    {
        byte[] b = new byte[len];
        b[0] = (byte)rid;
        bool ok = HidD_GetInputReport(h, b, (uint)len);
        int err = Marshal.GetLastWin32Error();
        if (!ok) return "ok=False err=" + err;
        return "ok=True  " + Hex(b, Math.Min(len, 40));
    }

    static string Feat(IntPtr h, int rid, int len)
    {
        byte[] b = new byte[len];
        b[0] = (byte)rid;
        bool ok = HidD_GetFeature(h, b, (uint)len);
        int err = Marshal.GetLastWin32Error();
        if (!ok) return "ok=False err=" + err;
        return "ok=True  " + Hex(b, Math.Min(len, 32));
    }

    static string Spont(IntPtr h, int ms)
    {
        byte[] buf = new byte[4096];
        uint got = 0;
        bool ok = ReadFile(h, buf, 4096, out got, IntPtr.Zero);
        int err = Marshal.GetLastWin32Error();
        if (!ok) return "ok=False err=" + err;
        byte[] r = new byte[got];
        Array.Copy(buf, r, (int)got);
        return "ok=True got=" + got + "  " + Hex(r, 64);
    }

    /// <summary>体检：类 0x20 读 0x1000 ×16（项目里唯一"已知安全"的命令）</summary>
    static bool Health(IntPtr h, string tag)
    {
        byte[] pkt = new byte[65];
        pkt[0] = 0x0E;
        pkt[1] = 0x20; pkt[4] = 0x05; pkt[5] = 0x01;
        pkt[6] = 0x10; pkt[7] = 0x00; pkt[8] = 0x00; pkt[9] = 0x10;
        int err;
        bool sent = HidD_SetOutputReport(h, pkt, 65);
        err = Marshal.GetLastWin32Error();
        if (!sent) { Console.WriteLine("  [" + tag + "] 发送失败 err=" + err); return false; }
        Thread.Sleep(120);
        byte[] r = new byte[65]; r[0] = 0x0E;
        bool ok = HidD_GetInputReport(h, r, 65);
        err = Marshal.GetLastWin32Error();
        if (!ok) { Console.WriteLine("  [" + tag + "] 读回失败 err=" + err); return false; }
        Console.WriteLine("  [" + tag + "] " + Hex(r, 24));
        return r[4] > 0;
    }

    // ────────────────────────────── SEND：只发不读，立刻退出 ──────────────────────────────
    public static int Send(int cls, int sub, string payhex, int dwellMs, int dir)
    {
        string path;
        IntPtr h = OpenCol("col04", true, true, out path);
        if (h == IntPtr.Zero) return 1;
        Console.WriteLine("path: " + path);
        Console.WriteLine("== 体检(发送前) ==");
        Health(h, "before");

        byte[] pkt = new byte[65];
        pkt[0] = 0x0E;
        pkt[1] = (byte)cls;
        pkt[2] = (byte)(sub & 0xFF);
        pkt[3] = (byte)((sub >> 8) & 0xFF);
        pkt[4] = 0x05; pkt[5] = (byte)dir;
        byte[] pay = ParseHex(payhex, 59);
        Array.Copy(pay, 0, pkt, 6, 59);
        // 长度字节 = payload 实际长度 + 1（方向字节），与已验证的读帧同规则
        int plen = 0;
        if (!string.IsNullOrEmpty(payhex))
            plen = payhex.Split(new char[] { ' ', ',', '-' }, StringSplitOptions.RemoveEmptyEntries).Length;
        pkt[4] = (byte)(plen + 1);

        Console.WriteLine("== 单发: " + Hex(pkt, 6 + plen) + "  ([4]=" + pkt[4] + " [5] 方向=" + pkt[5] + ") ==");
        bool ok = HidD_SetOutputReport(h, pkt, 65);
        int e = Marshal.GetLastWin32Error();
        Console.WriteLine("send = " + ok + " err=" + e);
        if (ok) Thread.Sleep(dwellMs);   // 留时间给 IC 处理并排队回复
        CloseHandle(h);
        Console.WriteLine("(进程立即退出，把读留给下一个进程)");
        return ok ? 0 : 2;
    }

    // ────────────────────────────── LISTEN：只读不发（新进程） ──────────────────────────────
    public static int Listen(int ms)
    {
        string path;
        IntPtr h = OpenCol("col04", true, true, out path);
        if (h == IntPtr.Zero) return 1;
        Console.WriteLine("path: " + path);

        Console.WriteLine("== ① 自发输入报文 ReadFile（独立读线程，超时 " + ms + "ms） ==");
        G("ReadFile(Col04, 4096B)", ms, delegate () { return Spont(h, ms); });

        Console.WriteLine("== ② GET_INPUT(report id 0x0E) 各种长度 ==");
        G("GetInputReport(0x0E, 65)", ms, delegate () { return InRep(h, 0x0E, 65); });
        G("GetInputReport(0x0E, 66)", ms, delegate () { return InRep(h, 0x0E, 66); });
        G("GetInputReport(0x0E, 129)", ms, delegate () { return InRep(h, 0x0E, 129); });
        G("GetInputReport(0x0E, 257)", ms, delegate () { return InRep(h, 0x0E, 257); });
        G("GetInputReport(0x0E, 4096)", ms, delegate () { return InRep(h, 0x0E, 4096); });

        Console.WriteLine("== ③ 试探其它 report id（回复类 0xA2 等） ==");
        G("GetInputReport(0xA2, 65)", ms, delegate () { return InRep(h, 0xA2, 65); });
        G("GetInputReport(0x00, 65)", ms, delegate () { return InRep(h, 0x00, 65); });
        G("GetInputReport(0x0B, 65)", ms, delegate () { return InRep(h, 0x0B, 65); });

        Console.WriteLine("== ④ Col04 feature report ==");
        G("GetFeature(0x0E, 65)", ms, delegate () { return Feat(h, 0x0E, 65); });
        G("GetFeature(0x0E, 737)", ms, delegate () { return Feat(h, 0x0E, 737); });
        G("GetFeature(0x0B, 65)", ms, delegate () { return Feat(h, 0x0B, 65); });
        G("GetFeature(0x11, 65)", ms, delegate () { return Feat(h, 0x11, 65); });

        Console.WriteLine("== ⑤ 换个集合：Col02(PTP) 厂商 feature ==");
        IntPtr h2 = ColProbe.OpenRO("col02");
        if (h2 == IntPtr.Zero) Console.WriteLine("  Col02 打开失败 err=" + Marshal.GetLastWin32Error());
        else
        {
            G("Col02 GetFeature(11, 67)", ms, delegate () { return Feat(h2, 11, 67); });
            G("Col02 GetFeature(6, 257)", ms, delegate () { return Feat(h2, 6, 257); });
            G("Col02 GetFeature(12, 737)", ms, delegate () { return Feat(h2, 12, 737); });
            G("Col02 GetFeature(2, 2)", ms, delegate () { return Feat(h2, 2, 2); });
            G("Col02 GetFeature(13, 5)", ms, delegate () { return Feat(h2, 13, 5); });
        }

        Console.WriteLine("== ⑥ 体检（本进程读通道是否可用） ==");
        G("类0x20 读 0x1000×16", ms, delegate ()
        {
            byte[] pkt = new byte[65];
            pkt[0] = 0x0E;
            pkt[1] = 0x20; pkt[4] = 0x05; pkt[5] = 0x01;
            pkt[6] = 0x10; pkt[7] = 0x00; pkt[8] = 0x00; pkt[9] = 0x10;
            if (!HidD_SetOutputReport(h, pkt, 65)) return "send 失败 err=" + Marshal.GetLastWin32Error();
            Thread.Sleep(150);
            return InRep(h, 0x0E, 65);
        });
        return 0;
    }

    /// <summary>★ 点按对照：轮询 4 个窄窗口（各 60B），找"只在震动时变化"的字节。
    /// 剂量：每 cycle 4 次读，极低；带单次读超时护栏。</summary>
    public static int ClickWatch(int intervalMs, int cycles)
    {
        string path;
        IntPtr h = OpenCol("col04", true, true, out path);
        if (h == IntPtr.Zero) return 1;
        int[] wins = new int[] { 0x4080, 0x4CC0, 0x56C0, 0x17E0 };
        byte[][] prev = new byte[wins.Length][];
        Console.WriteLine("轮询窗口: " + string.Join(" ", Array.ConvertAll(wins, w => "0x" + w.ToString("X4"))) + "  每窗 60B");
        for (int c = 0; c < cycles; c++)
        {
            string stamp = DateTime.Now.ToString("HH:mm:ss.fff");
            StringBuilder line = new StringBuilder("[" + stamp + "]");
            for (int w = 0; w < wins.Length; w++)
            {
                int err; bool blocked;
                byte[] d = MemReadEx(h, wins[w], 60, out err, out blocked);
                if (blocked) { Console.WriteLine(line + "  ★0x" + wins[w].ToString("X4") + " 读被阻塞(>2.5s) ⇒ 停止"); CloseHandle(h); return 3; }
                if (d == null) { line.Append("  W" + w + ":err" + err); continue; }
                int nd = 0; var det = new StringBuilder();
                if (prev[w] != null)
                    for (int i = 0; i < d.Length && i < prev[w].Length; i++)
                        if (d[i] != prev[w][i]) { nd++; if (nd <= 6) det.Append(string.Format(" +{0:X2}:{1:X2}>{2:X2}", i, prev[w][i], d[i])); }
                line.Append("  W" + w + ":" + (prev[w] == null ? "初值" : nd + (nd > 0 ? det.ToString() : "")));
                prev[w] = d;
            }
            Console.WriteLine(line.ToString());
            Thread.Sleep(intervalMs);
        }
        CloseHandle(h);
        return 0;
    }

    /// <summary>逐次完整 dump 一个 60B 窗口（看 (tag,value) 结构用）</summary>
    public static int WatchDump(int addr, int intervalMs, int cycles)
    {
        string path;
        IntPtr h = OpenCol("col04", true, true, out path);
        if (h == IntPtr.Zero) return 1;
        Console.WriteLine("dump 0x" + addr.ToString("X4") + " 60B  间隔 " + intervalMs + "ms ×" + cycles);
        for (int c = 0; c < cycles; c++)
        {
            int err; bool blocked;
            byte[] d = MemReadEx(h, addr, 60, out err, out blocked);
            if (blocked) { Console.WriteLine("[" + DateTime.Now.ToString("HH:mm:ss.fff") + "] ★读被阻塞(>2.5s) ⇒ 停止"); CloseHandle(h); return 3; }
            Console.WriteLine("[" + DateTime.Now.ToString("HH:mm:ss.fff") + "] " + (d == null ? "err=" + err : Hex(d, d.Length)));
            Thread.Sleep(intervalMs);
        }
        CloseHandle(h);
        return 0;
    }

    /// <summary>★ v2 读：帧 = 0E 20 00 00 07 01 &lt;addr32BE&gt; &lt;len16BE&gt;（12 字节）
    /// 来源：Dell 刷写器 TlcConnection::readV2 @0x411960 的逐字节反汇编。
    ///
    /// ★★★ 2026-09-14 23:2x 真机实测改正（原实现有 bug）：
    ///   这个 32 位"地址"其实不是地址，而是 **((字节偏移 &lt;&lt; 16) | 读取字节数)** ——
    ///   高 16 位 = 偏移，**低 16 位 = 要读多少字节**。实测三点定案：
    ///     低 16 位 = 0      -> err=122 拒收（长度为 0）
    ///     低 16 位 = 1      -> 回复 [4]=0x01，回 1 字节
    ///     低 16 位 = 0x10   -> 回复 [4]=0x10，回 16 字节
    ///     低 16 位 = 0x40D0 -> 回复 [4]=0x3C（封顶 60），回 60 字节
    ///   且 v2(offset=0x40D0,len=24) 与 v1(addr=0x40D0,size=24) 结果逐字节一致。
    ///   原先直接把 addr 当 32 位地址填进去 —— 只有「addr 恰好等于 (offset&lt;&lt;16)|len」时才碰巧对。
    ///   帧尾那个 len16 字段实测被设备忽略，保留只是照抄 Dell 的字节布局。</summary>
    public static int Mem2Read(int addr, int len)
    {
        if (len < 1) { Console.WriteLine("!! 长度必须 >= 1（低 16 位为 0 会被设备拒收 err=122）"); return 3; }
        if (len > 60) { Console.WriteLine("!! 长度 >60 会被传输层封顶到 60，已按 60 处理"); len = 60; }
        int addr32 = ((addr & 0xFFFF) << 16) | (len & 0xFFFF);   // ★ 正确编码：偏移<<16 | 字节数
        string path;
        IntPtr h = OpenCol("col04", true, true, out path);
        if (h == IntPtr.Zero) return 1;
        Console.WriteLine("== 体检 v1(类0x20 读 0x1000×16) ==");
        Health(h, "before");

        byte[] pkt = new byte[65];
        pkt[0] = 0x0E; pkt[1] = 0x20;
        pkt[4] = 0x07; pkt[5] = 0x01;                       // v2 选择子 + 读方向
        pkt[6] = (byte)(addr32 >> 24); pkt[7] = (byte)(addr32 >> 16);
        pkt[8] = (byte)(addr32 >> 8); pkt[9] = (byte)addr32; // ★ (偏移<<16|字节数) 大端
        pkt[10] = (byte)(len >> 8); pkt[11] = (byte)len;     // 帧尾长度（设备实测忽略，照抄 Dell）
        Console.WriteLine("== v2 读: " + Hex(pkt, 12) + "  offset=0x" + addr.ToString("X4") + " len=" + len + " ==");
        if (!HidD_SetOutputReport(h, pkt, 65)) { Console.WriteLine("send 失败 err=" + Marshal.GetLastWin32Error()); CloseHandle(h); return 2; }
        Thread.Sleep(200);
        byte[] r = new byte[65]; r[0] = 0x0E;
        if (!HidD_GetInputReport(h, r, 65))
        {
            Console.WriteLine("  读回失败 err=" + Marshal.GetLastWin32Error());
        }
        else
        {
            int rl = (r[3] << 8) | r[4];                     // 长度：偏移 3-4 大端（与 Dell 工具一致）
            Console.WriteLine("  回复: " + Hex(r, 40));
            Console.WriteLine("  解析: class=0x" + r[1].ToString("X2") + " len=" + rl + " 数据: " + Hex(Slice(r, 5, rl), Math.Min(rl, 32)));
        }
        Console.WriteLine("== 体检 2 ==");
        Health(h, "after");
        CloseHandle(h);
        return 0;
    }

    static byte[] Slice(byte[] src, int off, int n)
    {
        if (n <= 0) return new byte[0];
        if (off + n > src.Length) n = src.Length - off;
        byte[] d = new byte[n];
        Array.Copy(src, off, d, 0, n);
        return d;
    }

    /// <summary>只做体检（新进程验证设备健康）</summary>
    public static int HealthOnly()
    {
        string path;
        IntPtr h = OpenCol("col04", true, true, out path);
        if (h == IntPtr.Zero) return 1;
        bool b = Health(h, "only");
        CloseHandle(h);
        return b ? 0 : 2;
    }

    // ────────────── ONE：一个进程只做一次 HID 调用（★避免"被前面的阻塞毒死"） ──────────────
    public static int One(string op, string a1, string a2)
    {
        string path;
        IntPtr h = OpenCol("col04", true, true, out path);
        if (h == IntPtr.Zero) return 1;
        Console.WriteLine("path: " + path);
        int t = 3000;
        switch (op.ToLower())
        {
            case "in":
                Console.WriteLine("GetInputReport(rid=0x" + a1 + ", len=" + a2 + ")");
                G("ONE in", t, delegate () { return InRep(h, Convert.ToInt32(a1, 16), Convert.ToInt32(a2)); });
                break;
            case "read":
                Console.WriteLine("ReadFile(len=" + a1 + ")");
                G("ONE read", t, delegate () { return Spont(h, t); });
                break;
            case "feat":
                Console.WriteLine("GetFeature(rid=0x" + a1 + ", len=" + a2 + ")");
                G("ONE feat", t, delegate () { return Feat(h, Convert.ToInt32(a1, 16), Convert.ToInt32(a2)); });
                break;
            case "mem":
                {
                    int addr = Convert.ToInt32(a1, 16), size = Convert.ToInt32(a2);
                    Console.WriteLine("类0x20 读 addr=0x" + addr.ToString("X4") + " size=" + size);
                    G("ONE mem", t, delegate ()
                    {
                        byte[] pkt = new byte[65];
                        pkt[0] = 0x0E; pkt[1] = 0x20; pkt[4] = 0x05; pkt[5] = 0x01;
                        pkt[6] = (byte)(addr >> 8); pkt[7] = (byte)addr;
                        pkt[8] = (byte)(size >> 8); pkt[9] = (byte)size;
                        if (!HidD_SetOutputReport(h, pkt, 65)) return "send 失败 err=" + Marshal.GetLastWin32Error();
                        Thread.Sleep(160);
                        return InRep(h, 0x0E, 65);
                    });
                    break;
                }
            default:
                Console.WriteLine("未知 op=" + op);
                return 9;
        }
        return 0;
    }

    // ────────────── MEM*：只读地看 16 位地址空间（类0x20 读 60B/次，项目历史上最安全的操作） ──────────────
    static int _readDelayMs = 60;

    /// <summary>带护栏的读：若 2.5 s 内不返回则判为"阻塞"并放弃（进程不再被卡死）</summary>
    static byte[] MemReadEx(IntPtr h, int addr, int size, out int err, out bool blocked)
    {
        byte[] res = null; int e0 = 0;
        Thread t = new Thread(delegate ()
        {
            byte[] pkt = new byte[65];
            pkt[0] = 0x0E; pkt[1] = 0x20; pkt[4] = 0x05; pkt[5] = 0x01;
            pkt[6] = (byte)(addr >> 8); pkt[7] = (byte)addr;
            pkt[8] = (byte)(size >> 8); pkt[9] = (byte)size;
            if (!HidD_SetOutputReport(h, pkt, 65)) { e0 = Marshal.GetLastWin32Error(); return; }
            Thread.Sleep(_readDelayMs);
            byte[] r = new byte[65]; r[0] = 0x0E;
            if (!HidD_GetInputReport(h, r, 65)) { e0 = Marshal.GetLastWin32Error(); return; }
            int n = r[4]; if (n > 60) n = 60; if (n < 0) n = 0;
            byte[] d = new byte[n]; Array.Copy(r, 5, d, 0, n); res = d;
        });
        t.IsBackground = true;
        t.Start();
        bool fin = t.Join(2500);
        blocked = !fin;
        err = e0;
        return fin ? res : null;
    }

    /// <summary>★ 速率阶梯：逐级升高的读频率 + 用"活数据是否还在变"当输入侧是否已挂的探针</summary>
    public static int RateLadder(int addr, int len)
    {
        string path;
        IntPtr h = OpenCol("col04", true, true, out path);
        if (h == IntPtr.Zero) return 1;
        Console.WriteLine("监测地址 0x" + addr.ToString("X4") + " 长度 " + len);
        int[][] stages = new int[][] {
            new int[]{ 1000, 15 },   // 阶段0：不要碰触控板（对照）
            new int[]{ 1000, 15 },   // 阶段1：持续滑动手指
            new int[]{  300, 20 },   // 阶段2：持续滑动
            new int[]{  100, 40 }    // 阶段3：持续滑动
        };
        string[] tags = { " ★请【不要碰】触控板", " ★请【持续缓慢滑动】手指", " ★继续滑动", " ★继续滑动" };
        byte[] prev = null;
        int still = 0, total = 0;
        for (int s = 0; s < stages.Length; s++)
        {
            int iv = stages[s][0], cnt = stages[s][1];
            Console.WriteLine("=== 阶段" + s + "  间隔 " + iv + "ms ×" + cnt + "  (≈" + (1000.0 / iv).ToString("F1") + " 次/秒)" + tags[s] + " ===");
            _readDelayMs = Math.Min(60, Math.Max(10, iv / 3));
            for (int k = 0; k < cnt; k++)
            {
                int err; bool blocked;
                byte[] d = MemReadEx(h, addr, len, out err, out blocked);
                total++;
                string stamp = DateTime.Now.ToString("HH:mm:ss.fff");
                if (blocked) { Console.WriteLine("  [" + stamp + "] ★读被阻塞(>2.5s) ⇒ 输入侧已挂，立即停止"); CloseHandle(h); return 3; }
                if (d == null) { Console.WriteLine("  [" + stamp + "] 读失败 err=" + err); still++; }
                else
                {
                    int nd = 0;
                    if (prev != null)
                        for (int i = 0; i < d.Length && i < prev.Length; i++) if (d[i] != prev[i]) nd++;
                    if (prev == null) Console.WriteLine("  [" + stamp + "] 初值 " + Hex(d, 16));
                    else
                    {
                        if (nd == 0) still++; else still = 0;
                        Console.WriteLine("  [" + stamp + "] 变化 " + nd + " 字节" + (still >= 3 ? "   ★连续 " + still + " 次无变化 ⇒ 活数据停了" : ""));
                    }
                    prev = d;
                }
                Thread.Sleep(iv);
            }
        }
        Console.WriteLine("总读次数 " + total);
        CloseHandle(h);
        return 0;
    }

    static byte[] MemRead(IntPtr h, int addr, int size, out int err)
    {
        bool blocked;
        return MemReadEx(h, addr, size, out err, out blocked);
    }

    public static int MemScan(int addr, int len)
    {
        string path;
        IntPtr h = OpenCol("col04", true, true, out path);
        if (h == IntPtr.Zero) return 1;
        Console.WriteLine("基址 0x" + addr.ToString("X4") + " 长度 " + len);
        for (int off = 0; off < len; off += 60)
        {
            int a = addr + off, n = Math.Min(60, len - off);
            int err;
            byte[] d = MemRead(h, a, n, out err);
            if (d == null) { Console.WriteLine("  0x" + a.ToString("X4") + " 读失败 err=" + err); continue; }
            Console.WriteLine("  0x" + a.ToString("X4") + " (" + d.Length + "B) " + Hex(d, d.Length));
        }
        CloseHandle(h);
        return 0;
    }

    /// <summary>反复读同一块，打印变化的字节（用于"点按触控板时哪块 RAM 在动"）</summary>
    public static int MemWatch(int addr, int len, int intervalMs, int count)
    {
        string path;
        IntPtr h = OpenCol("col04", true, true, out path);
        if (h == IntPtr.Zero) return 1;
        Console.WriteLine("监视 0x" + addr.ToString("X4") + " 长度 " + len + " 间隔 " + intervalMs + "ms ×" + count);
        byte[] prev = null;
        for (int k = 0; k < count; k++)
        {
            int err;
            byte[] d = MemRead(h, addr, len, out err);
            string stamp = DateTime.Now.ToString("HH:mm:ss.fff");
            if (d == null) { Console.WriteLine("  [" + stamp + "] 读失败 err=" + err); }
            else if (prev == null) { Console.WriteLine("  [" + stamp + "] 初始 " + Hex(d, d.Length)); }
            else
            {
                StringBuilder ch = new StringBuilder();
                int nd = 0;
                for (int i = 0; i < d.Length && i < prev.Length; i++)
                    if (d[i] != prev[i]) { ch.Append(string.Format(" +{0:X2}:{1:X2}->{2:X2}", i, prev[i], d[i])); nd++; }
                Console.WriteLine("  [" + stamp + "] " + (nd == 0 ? "无变化" : nd + " 字节变化" + ch));
            }
            prev = d;
            Thread.Sleep(intervalMs);
        }
        CloseHandle(h);
        return 0;
    }

    /// <summary>把一段地址空间 dump 成文件（每行 "0xADDR hex..."），用于前后对比</summary>
    public static int MemDump(int addr, int len, string file)
    {
        string path;
        IntPtr h = OpenCol("col04", true, true, out path);
        if (h == IntPtr.Zero) return 1;
        var sb = new StringBuilder();
        sb.AppendLine("# MEMDUMP 0x" + addr.ToString("X4") + " len=" + len + "  " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
        int bad = 0;
        for (int off = 0; off < len; off += 60)
        {
            int a = addr + off, n = Math.Min(60, len - off);
            int err;
            byte[] d = MemRead(h, a, n, out err);
            if (d == null) { sb.AppendLine(string.Format("0x{0:X4} ERR {1}", a, err)); bad++; continue; }
            sb.AppendLine("0x" + a.ToString("X4") + " " + Hex(d, d.Length));
        }
        System.IO.File.WriteAllText(file, sb.ToString(), Encoding.UTF8);
        CloseHandle(h);
        Console.WriteLine("已写 " + file + "  失败块=" + bad);
        return bad == 0 ? 0 : 2;
    }
}
