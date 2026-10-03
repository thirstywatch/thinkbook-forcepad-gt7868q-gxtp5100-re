using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using System.Security.Cryptography;

public static class ReadFeatureRO
{
    [StructLayout(LayoutKind.Sequential)] struct RAW { public IntPtr hDevice; public uint dwType; }
    [DllImport("user32.dll")] static extern uint GetRawInputDeviceList([Out] RAW[] a, ref uint n, uint sz);
    [DllImport("user32.dll", EntryPoint="GetRawInputDeviceInfoW", CharSet=CharSet.Unicode)]
    static extern uint GetName(IntPtr d, uint cmd, StringBuilder b, ref uint n);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern IntPtr CreateFileW(string p, uint acc, uint share, IntPtr sa, uint disp, uint flags, IntPtr t);
    [DllImport("kernel32.dll", SetLastError=true)] static extern bool CloseHandle(IntPtr h);
    [DllImport("hid.dll", SetLastError=true)] static extern bool HidD_GetFeature(IntPtr h, byte[] b, uint n);
    const uint INVALID = 0xFFFFFFFF, OPEN_EXISTING=3, SHARE=3;

    public static string Read(string filter, string collection, int rid, int len)
    {
        uint n=0, sz=(uint)Marshal.SizeOf(typeof(RAW)); GetRawInputDeviceList(null, ref n, sz);
        var a=new RAW[n]; GetRawInputDeviceList(a, ref n, sz); string path=null;
        foreach(var d in a){ if(d.dwType!=2) continue; uint q=0; GetName(d.hDevice,0x20000007,null,ref q); if(q==0) continue;
            var s=new StringBuilder((int)q+2); uint q2=q; GetName(d.hDevice,0x20000007,s,ref q2); var p=s.ToString();
            if(p.IndexOf(filter,StringComparison.OrdinalIgnoreCase)>=0 && p.IndexOf(collection,StringComparison.OrdinalIgnoreCase)>=0){path=p;break;}}
        if(path==null) return "path-not-found";
        var h=CreateFileW(path,0,SHARE,IntPtr.Zero,OPEN_EXISTING,0,IntPtr.Zero);
        if(h==IntPtr.Zero || h.ToInt64()==-1) return "open-failed err="+Marshal.GetLastWin32Error();
        var b=new byte[len]; b[0]=(byte)rid; bool ok=HidD_GetFeature(h,b,(uint)b.Length); int e=Marshal.GetLastWin32Error();
        var hex=new StringBuilder(); int lim=Math.Min(16,b.Length); for(int i=0;i<lim;i++){if(i>0)hex.Append(' ');hex.Append(b[i].ToString("X2"));}
        string hash = "";
        if (ok) using (var sha=SHA256.Create()) {
            var d=sha.ComputeHash(b); var hs=new StringBuilder();
            foreach(var x in d) hs.Append(x.ToString("X2")); hash=hs.ToString();
        }
        CloseHandle(h); return string.Format("ok={0} err={1} len={2} hash={3} bytes={4}",ok,e,len,hash,hex);
    }
}
