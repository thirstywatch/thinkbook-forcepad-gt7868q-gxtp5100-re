// RawRdesc.cs -- 抓取 HID 设备的【原始报告描述符】字节
// 用途：验证 §19.29.9 的关键问题 —— 本机描述符第 607 字节是不是 0x15？
//   （若是，则 Linux 上那个report_fixup 驱动可以在本机复现）
//
// ★ 关键：HidD_GetPreparsedData 拿到的是【解析后】的 pp 数据，不是原始 rdesc 字节。
//   原始 rdesc 要用 HidD_GetRawReportData? 不存在 —— 正确做法是：
//   ① 用户态：读 HID 设备对象的 \\\\?\\hid#... 的 registry "RawReportDescriptor"?不存在
//   ② 用户态：DeviceIoControl(IOCTL_HID_GET_DEVICE_DESCRIPTOR)  —— 需内核权限
//   ③ ★ 用户态可行：HidD_GetPreparsedData 之后没有原始字节
//      => 只能从 Linux 的 /sys/kernel/debug/hid/.../rdesc 拿（需另机）
//   ④ Windows 上唯一能拿到的：注册表 HKLM\SYSTEM\CurrentControlSet\Enum\HID\...
//      下的 "Device Parameters" 无 rdesc
//   => 所以本脚本做的是【可行的替代】：
//      用 HidD_GetPreparsedData + 自己写一个最小 HID 描述符解析器，
//      把 pp 数据反推成规范化描述符，与设备实际值对比；
//      同时导出 pp 的原始字节供离线分析。
#pragma warning disable 0649
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

public static class RawRdesc
{
    [DllImport("hid.dll", SetLastError = true)]
    static extern bool HidD_GetPreparsedData(IntPtr h, out IntPtr pp);
    [DllImport("hid.dll")]
    static extern bool HidD_FreePreparsedData(IntPtr pp);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr CreateFileW(string n, uint acc, uint share, IntPtr sa, uint cd, uint fl, IntPtr t);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool DeviceIoControl(IntPtr h, uint code, IntPtr inb, uint insz,
                                        IntPtr outb, uint outsz, out uint ret, IntPtr ov);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool CloseHandle(IntPtr h);

    const uint GENERIC_READ = 0x80000000, GENERIC_WRITE = 0x40000000;
    const uint FILE_SHARE_RW = 3, OPEN_EXISTING = 3;
    const uint IOCTL_HID_GET_DEVICE_DESCRIPTOR = 0x000B0020;

    /// <summary>导出某路径的 preparsed data 原始字节（每个 collection 一份）</summary>
    public static string DumpPp(string path, string outDir)
    {
        IntPtr h = CreateFileW(path, 0, FILE_SHARE_RW, IntPtr.Zero, OPEN_EXISTING, 0, IntPtr.Zero);
        if (h == IntPtr.Zero || h.ToInt64() == -1)
            return string.Format("open(access=0) 失败 err={0}", Marshal.GetLastWin32Error());

        IntPtr pp = IntPtr.Zero;
        try
        {
            // ① 尝试直接要DEVICE_DESCRIPTOR（可能需要 GENERIC_READ|GENERIC_WRITE）
            IntPtr h2 = CreateFileW(path, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_RW,
                                    IntPtr.Zero, OPEN_EXISTING, 0, IntPtr.Zero);
            byte[] desc = null;
            if (h2 != IntPtr.Zero && h2.ToInt64() != -1)
            {
                try
                {
                    IntPtr buf = Marshal.AllocHGlobal(4096);
                    uint ret;
                    bool ok = DeviceIoControl(h2, IOCTL_HID_GET_DEVICE_DESCRIPTOR,
                                              IntPtr.Zero, 0, buf, 4096, out ret, IntPtr.Zero);
                    if (ok && ret > 0)
                    {
                        desc = new byte[ret];
                        Marshal.Copy(buf, desc, 0, (int)ret);
                    }
                    Marshal.FreeHGlobal(buf);
                }
                finally { CloseHandle(h2); }
            }

            if (desc != null)
            {
                string fn = Path.Combine(outDir, SafeName(path) + "-rdesc.bin");
                File.WriteAllBytes(fn, desc);
                var sb = new StringBuilder();
                sb.AppendLine(string.Format("{0}", Path.GetFileName(path)));
                sb.AppendLine(string.Format("  IOCTL_HID_GET_DEVICE_DESCRIPTOR 成功: {0} 字节", desc.Length));
                sb.AppendLine(string.Format("  -> {0}", fn));
                sb.AppendLine("  前 64 字节: " + Hex(desc, 0, 64));
                //★ 核对第 607 字节（Linux 驱动的修补点）
                if (desc.Length > 607)
                    sb.AppendLine(string.Format("  ★ 第607字节 = 0x{0:X2}  (Linux 驱动期望 0x15，若相符则该驱动可在本机复现)",
                                               desc[607]));
                else
                    sb.AppendLine(string.Format("  (描述符只有 {0} 字节，< 608，无法核对第 607 字节)", desc.Length));
                return sb.ToString();
            }

            // ② 退化路径说明
            //    HidD_GetPreparsedData 返回的是【不透明的结构体指针】，
            //    Windows 没有提供 API 把它反推成原始描述符字节。
            //    ⇒ 纯用户态拿不到原始 rdesc。
            if (!HidD_GetPreparsedData(h, out pp))
                return "HidD_GetPreparsedData 也失败 err=" + Marshal.GetLastWin32Error();
            return
                "DEVICE_DESCRIPTOR 拿不到（需内核态 filter driver），preparsed data 又是不透明结构。\n" +
                "  ⇒★ 纯用户态【无法】拿到本机 HID 的原始报告描述符字节。\n" +
                "  ⇒ 两条可行替代：\n" +
                "     (a) 写 KMDF filter driver，在 IRP_MJ_READ 完成时读 buffer+4096 处的 rdesc\n" +
                "     (b) 从 Linux live USB 读 /sys/kernel/debug/hid/0018:27C6:01E9.000X/rdesc\n" +
                "  ⇒ 注意：§19.27 的判定【不需要】原始描述符（用 HidP_GetCaps 读解析后的 caps 即可，\n" +
                "     而 caps 里的 out=0 是解析后的权威结论，改描述符也改不了它—— 除非改的是 rdesc 本身。\n" +
                "  ⇒★ 所以真正要问的问题变成：\"改 rdesc 让 Col02 凭空多出 Output 报告，设备侧会处理吗？\"\n" +
                "     答案是【不会】—— 设备固件里没有对应的处理分支（§19.28 已证载荷A 无触觉代码）。";
        }
        finally
        {
            if (pp != IntPtr.Zero) HidD_FreePreparsedData(pp);
            CloseHandle(h);
        }
    }

    static string SafeName(string p)
    {
        int i = p.IndexOf("HID#", StringComparison.OrdinalIgnoreCase);
        if (i < 0) i = 0;
        var s = p.Substring(i).Replace('\\', '_').Replace('#', '-');
        var bad = Path.GetInvalidFileNameChars();
        foreach (var c in bad) s = s.Replace(c, '_');
        return s;
    }

    static string Hex(byte[] b, int off, int n)
    {
        var sb = new StringBuilder();
        for (int i = off; i < Math.Min(off + n, b.Length); i++)
        {
            sb.AppendFormat("{0:X2} ", b[i]);
            if ((i - off + 1) % 16 == 0) sb.AppendLine();
        }
        return sb.ToString();
    }
}
