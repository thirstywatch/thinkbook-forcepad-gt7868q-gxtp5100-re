// DumpPad.cs — 触控板原始报表字段测绘工具（方案 A 第一步）
// 目的：把 Col02（PTP）40 字节输入报表的字段布局用实测钉死，不做任何猜测
// 编译：csc /target:exe /out:DumpPad.exe DumpPad.cs
// 用法：DumpPad.exe [秒数]        默认 20 秒
// 说明：只读 Raw Input（RIDEV_INPUTSINK，全局接收），不打开设备、不发任何命令 —— 零风险
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

static class DumpPad
{
    const int WM_INPUT = 0x00FF;
    const uint RIDEV_INPUTSINK = 0x00000100;
    const uint RID_INPUT = 0x10000003;

    [StructLayout(LayoutKind.Sequential)]
    struct RAWINPUTDEVICE { public ushort usUsagePage; public ushort usUsage; public uint dwFlags; public IntPtr hwndTarget; }
    [StructLayout(LayoutKind.Sequential)]
    struct RAWINPUTHEADER { public uint dwType; public uint dwSize; public IntPtr hDevice; public IntPtr wParam; }
    [StructLayout(LayoutKind.Sequential)]
    struct MSG { public IntPtr hwnd; public uint message; public IntPtr wParam; public IntPtr lParam; public uint time; public int ptX; public int ptY; }

    delegate IntPtr WndProcDelegate(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct WNDCLASSEX
    {
        public uint cbSize; public uint style; public IntPtr lpfnWndProc; public int cbClsExtra; public int cbWndExtra;
        public IntPtr hInstance; public IntPtr hIcon; public IntPtr hCursor; public IntPtr hbrBackground;
        [MarshalAs(UnmanagedType.LPWStr)] public string lpszMenuName;
        [MarshalAs(UnmanagedType.LPWStr)] public string lpszClassName;
        public IntPtr hIconSm;
    }

    [DllImport("user32.dll", SetLastError = true)] static extern bool RegisterRawInputDevices(RAWINPUTDEVICE[] d, uint n, uint cb);
    [DllImport("user32.dll")] static extern uint GetRawInputData(IntPtr h, uint cmd, IntPtr data, ref uint size, uint hdr);
    [DllImport("user32.dll")] static extern bool PeekMessage(out MSG m, IntPtr h, uint min, uint max, uint rm);
    [DllImport("user32.dll")] static extern bool TranslateMessage(ref MSG m);
    [DllImport("user32.dll")] static extern IntPtr DispatchMessage(ref MSG m);
    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode)] static extern ushort RegisterClassEx(ref WNDCLASSEX c);
    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern IntPtr CreateWindowEx(uint ex, string cls, string name, uint style, int x, int y, int w, int h,
        IntPtr parent, IntPtr menu, IntPtr inst, IntPtr param);
    [DllImport("user32.dll")] static extern IntPtr DefWindowProc(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] static extern IntPtr GetModuleHandle(string name);

    static WndProcDelegate _proc;
    static IntPtr _hwnd = IntPtr.Zero;

    // 字段测绘：每个字节偏移的最小/最大值 + 出现次数
    static int[] _min = new int[256];
    static int[] _max = new int[256];
    static int[] _cnt = new int[256];
    static int _reports = 0;
    static bool _verbose = true;

    static IntPtr WndProc(IntPtr h, uint msg, IntPtr w, IntPtr l)
    {
        if (msg == WM_INPUT) { try { OnRaw(l); } catch (Exception e) { Console.WriteLine("EX " + e.Message); } return IntPtr.Zero; }
        return DefWindowProc(h, msg, w, l);
    }

    static string DevPath(IntPtr hdev)
    {
        // GetRawInputDeviceInfo(RIDI_DEVICENAME)
        uint sz = 0;
        GetRawInputDeviceInfo(hdev, 0x20000007, IntPtr.Zero, ref sz);
        if (sz == 0) return "";
        var sb = new StringBuilder((int)sz + 2);
        uint sz2 = sz;
        GetRawInputDeviceInfoStr(hdev, 0x20000007, sb, ref sz2);
        return sb.ToString();
    }
    [DllImport("user32.dll")] static extern uint GetRawInputDeviceInfo(IntPtr h, uint cmd, IntPtr data, ref uint size);
    [DllImport("user32.dll", EntryPoint = "GetRawInputDeviceInfoW", CharSet = CharSet.Unicode)]
    static extern uint GetRawInputDeviceInfoStr(IntPtr h, uint cmd, StringBuilder data, ref uint size);

    static readonly Dictionary<IntPtr, string> _paths = new Dictionary<IntPtr, string>();

    static void OnRaw(IntPtr lParam)
    {
        uint size = 0;
        uint hdr = (uint)Marshal.SizeOf(typeof(RAWINPUTHEADER));
        GetRawInputData(lParam, RID_INPUT, IntPtr.Zero, ref size, hdr);
        if (size == 0) return;
        IntPtr buf = Marshal.AllocHGlobal((int)size);
        try
        {
            uint got = size;
            if (GetRawInputData(lParam, RID_INPUT, buf, ref got, hdr) != size) return;
            var h = (RAWINPUTHEADER)Marshal.PtrToStructure(buf, typeof(RAWINPUTHEADER));
            if (h.dwType != 2) return;              // 只看 HID
            int off = Marshal.SizeOf(typeof(RAWINPUTHEADER));
            uint hidLen = (uint)Marshal.ReadInt32(buf, off);
            byte[] d = new byte[hidLen];
            Marshal.Copy(buf + off + 8, d, 0, (int)hidLen);

            string path;
            if (!_paths.TryGetValue(h.hDevice, out path)) { path = DevPath(h.hDevice); _paths[h.hDevice] = path; }
            if (path.IndexOf("col02", StringComparison.OrdinalIgnoreCase) < 0) return;   // 只要 PTP 集合

            _reports++;
            for (int i = 0; i < d.Length && i < 256; i++)
            {
                if (_cnt[i] == 0) { _min[i] = d[i]; _max[i] = d[i]; }
                if (d[i] < _min[i]) _min[i] = d[i];
                if (d[i] > _max[i]) _max[i] = d[i];
                _cnt[i]++;
            }

            if (_verbose && _reports <= 400)
            {
                var sb = new StringBuilder();
                foreach (byte b in d) sb.Append(b.ToString("X2")).Append(' ');
                Console.WriteLine("#{0,-4} len={1}  {2}", _reports, hidLen, sb.ToString().Trim());
                Console.WriteLine("       guess: b1=0x{0:X2}(btn{1}/id{2})  u16@2={3} u16@4={4} u16@6={5} u16@8={6} u16@10={7}",
                    d.Length > 1 ? d[1] : 0, d.Length > 1 ? (d[1] & 0x0F) : 0, d.Length > 1 ? (d[1] >> 4) : 0,
                    U16(d, 2), U16(d, 4), U16(d, 6), U16(d, 8), U16(d, 10));
            }
        }
        finally { Marshal.FreeHGlobal(buf); }
    }

    static int U16(byte[] d, int o) { return (o + 1 < d.Length) ? (d[o] | (d[o + 1] << 8)) : -1; }

    static int Main(string[] args)
    {
        int seconds = 20;
        if (args.Length > 0) int.TryParse(args[0], out seconds);
        if (args.Length > 1 && args[1] == "-q") _verbose = false;

        _proc = new WndProcDelegate(WndProc);
        var wc = new WNDCLASSEX();
        wc.cbSize = (uint)Marshal.SizeOf(typeof(WNDCLASSEX));
        wc.lpfnWndProc = Marshal.GetFunctionPointerForDelegate(_proc);
        wc.hInstance = GetModuleHandle(null);
        wc.lpszClassName = "DumpPadWnd";
        RegisterClassEx(ref wc);
        _hwnd = CreateWindowEx(0x80, "DumpPadWnd", "dump", 0x80000000, -32000, -32000, 1, 1,
            IntPtr.Zero, IntPtr.Zero, wc.hInstance, IntPtr.Zero);
        if (_hwnd == IntPtr.Zero) { Console.WriteLine("CreateWindowEx 失败"); return 1; }

        var dev = new RAWINPUTDEVICE { usUsagePage = 0x0D, usUsage = 0x05, dwFlags = RIDEV_INPUTSINK, hwndTarget = _hwnd };
        var arr = new[] { dev };
        bool ok = RegisterRawInputDevices(arr, 1, (uint)Marshal.SizeOf(typeof(RAWINPUTDEVICE)));
        Console.WriteLine("RegisterRawInputDevices(0x0D/0x05) = " + ok);
        if (!ok) { Console.WriteLine("注册失败，退出"); return 2; }

        Console.WriteLine("=== 开始采集 {0} 秒 ===", seconds);
        Console.WriteLine("请依次做：①单指轻放 ②单指上下滑动 ③左边缘内滑 ④右边缘内滑 ⑤双指滑动 ⑥用力按下");
        Console.WriteLine("(每做完一个动作停 1 秒)");
        Console.WriteLine();

        var sw = System.Diagnostics.Stopwatch.StartNew();
        MSG m;
        while (sw.Elapsed.TotalSeconds < seconds)
        {
            while (PeekMessage(out m, IntPtr.Zero, 0, 0, 1)) { TranslateMessage(ref m); DispatchMessage(ref m); }
            System.Threading.Thread.Sleep(1);
        }

        Console.WriteLine();
        Console.WriteLine("=== 采集结束：共 {0} 条报表 ===", _reports);
        Console.WriteLine("=== 各字节偏移的取值范围（只列变化过的）===");
        for (int i = 0; i < 64; i++)
        {
            if (_cnt[i] == 0) continue;
            if (_min[i] != _max[i])
                Console.WriteLine("  byte[{0,2}]  min=0x{1:X2} ({1,3})  max=0x{2:X2} ({2,3})  出现 {3}", i, _min[i], _max[i], _cnt[i]);
        }
        Console.WriteLine();
        Console.WriteLine("=== 恒定字节（未变化，按偏移列出）===");
        var sb = new StringBuilder();
        for (int i = 0; i < 64; i++)
        {
            if (_cnt[i] == 0) continue;
            if (_min[i] == _max[i]) sb.Append(string.Format("[{0}]=0x{1:X2} ", i, _min[i]));
        }
        Console.WriteLine("  " + sb.ToString().Trim());
        return 0;
    }
}
