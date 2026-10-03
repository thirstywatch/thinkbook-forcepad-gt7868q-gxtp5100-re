// WhoHolds.cs —— 枚举全系统句柄，找出谁打开了 GXTP5100 的设备接口
// 原理: NtQuerySystemInformation(SystemExtendedHandleInformation) 列出所有句柄；
//       先用自建文件句柄确定 "File" 对象类型索引，再只对 File 类型句柄查名字（避免挂起）
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public static class WhoHolds
{
    [DllImport("ntdll.dll")]
    static extern int NtQuerySystemInformation(int cls, IntPtr buf, int len, out int retLen);
    [DllImport("ntdll.dll")]
    static extern int NtQueryObject(IntPtr h, int cls, IntPtr buf, int len, out int retLen);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool DuplicateHandle(IntPtr srcProc, IntPtr src, IntPtr dstProc, out IntPtr dst, uint access, bool inherit, uint opts);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern IntPtr GetCurrentProcess();
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr CreateFileW(string p, uint acc, uint share, IntPtr sa, uint cd, uint fl, IntPtr t);
    [DllImport("kernel32.dll")]
    static extern bool CloseHandle(IntPtr h);

    const int SystemExtendedHandleInformation = 64;
    const int ObjectNameInformation = 1;
    const uint PROCESS_DUP_HANDLE = 0x0040;
    const uint DUPLICATE_SAME_ACCESS = 0x0002;

    [StructLayout(LayoutKind.Sequential)]
    struct HandleEntry
    {
        public IntPtr Object;
        public IntPtr UniqueProcessId;
        public IntPtr HandleValue;
        public uint GrantedAccess;
        public ushort CreatorBackTraceIndex;
        public ushort ObjectTypeIndex;
        public uint HandleAttributes;
        public uint Reserved;
    }

    public static string Run(string filter)
    {
        var sb = new StringBuilder();

        // 1) 自建一个文件句柄，确定 File 类型索引
        string tmp = System.IO.Path.GetTempFileName();
        IntPtr probe = CreateFileW(tmp, 0x80000000, 1 | 2, IntPtr.Zero, 3, 0, IntPtr.Zero);
        ushort fileTypeIdx = 0;
        IntPtr buf = IntPtr.Zero;
        int len = 1 << 20;
        int status;
        while (true)
        {
            buf = Marshal.AllocHGlobal(len);
            status = NtQuerySystemInformation(SystemExtendedHandleInformation, buf, len, out int ret);
            if (status == 0) break;
            Marshal.FreeHGlobal(buf);
            buf = IntPtr.Zero;
            len = ret + (1 << 16);
            if (len > (1 << 28)) return "NtQuerySystemInformation 失败 status=0x" + status.ToString("X8");
        }
        try
        {
            int count = Marshal.ReadInt32(buf);
            // x64: ULONG NumberOfHandles; PVOID Reserved;  -> 4 + 4(padding) + 8 = 16 字节
            IntPtr p = (IntPtr)(buf.ToInt64() + 16);
            int myPid = System.Diagnostics.Process.GetCurrentProcess().Id;
            long myHandle = probe.ToInt64();
            var entries = new List<HandleEntry>();
            int sz = Marshal.SizeOf(typeof(HandleEntry));
            for (int i = 0; i < count; i++)
            {
                var e = (HandleEntry)Marshal.PtrToStructure((IntPtr)(p.ToInt64() + i * sz), typeof(HandleEntry));
                entries.Add(e);
                if (e.UniqueProcessId.ToInt64() == myPid && e.HandleValue.ToInt64() == myHandle)
                    fileTypeIdx = e.ObjectTypeIndex;
            }
            sb.AppendLine($"总句柄数={count}  File 类型索引={fileTypeIdx}  (探测句柄={(probe == IntPtr.Zero ? "失败" : "ok")})");
            CloseHandle(probe);
            System.IO.File.Delete(tmp);

            // 2) 只查 File 类型句柄的名字
            var pidNames = new Dictionary<int, string>();
            int scanned = 0, named = 0;
            foreach (var e in entries)
            {
                if (e.ObjectTypeIndex != fileTypeIdx || fileTypeIdx == 0) continue;
                int pid = (int)e.UniqueProcessId.ToInt64();
                IntPtr hp = OpenProcess(PROCESS_DUP_HANDLE, false, pid);
                if (hp == IntPtr.Zero) continue;
                scanned++;
                IntPtr dup;
                if (DuplicateHandle(hp, e.HandleValue, GetCurrentProcess(), out dup, 0, false, DUPLICATE_SAME_ACCESS))
                {
                    IntPtr nb = Marshal.AllocHGlobal(2048);
                    try
                    {
                        if (NtQueryObject(dup, ObjectNameInformation, nb, 2048, out int rl) == 0 && rl > 0)
                        {
                            // OBJECT_NAME_INFORMATION { UNICODE_STRING Name; }  x64: Buffer 指针在偏移 8
                            IntPtr strPtr = Marshal.ReadIntPtr(nb, 8);
                            string name = strPtr == IntPtr.Zero ? null : Marshal.PtrToStringUni(strPtr);
                            if (!string.IsNullOrEmpty(name) && name.IndexOf(filter, StringComparison.OrdinalIgnoreCase) >= 0)
                            {
                                if (!pidNames.TryGetValue(pid, out string pn))
                                {
                                    try { pn = System.Diagnostics.Process.GetProcessById(pid).ProcessName; }
                                    catch { pn = "?"; }
                                    pidNames[pid] = pn;
                                }
                                sb.AppendLine($"  pid={pid} ({pn})  handle=0x{e.HandleValue.ToInt64():X}  access=0x{e.GrantedAccess:X8}  {name}");
                                named++;
                            }
                        }
                    }
                    finally { Marshal.FreeHGlobal(nb); CloseHandle(dup); }
                }
                CloseHandle(hp);
            }
            sb.AppendLine($"扫描 File 句柄 {scanned} 个，命中 '{filter}' 的 {named} 个");
        }
        finally { if (buf != IntPtr.Zero) Marshal.FreeHGlobal(buf); }
        return sb.ToString();
    }
}
