#requires -Version 5.1
<#
  ec_probe.ps1 -- 通过 Windows 内置 ACPI 接口[只读]访问 EC RAM
  ------------------------------------------------------------------
  目的：不装任何第三方驱动，判断本机能否用管理员权限读到 EC RAM。
        (RWE/PawnIO 那类工具要带内核驱动；这个走微软自己的 ACPI 驱动。)

  ★ 本脚本只做[读]。没有任何写 EC / 写 I/O 端口的代码路径。

  用法(必须[以管理员身份]运行 PowerShell)：
      powershell -ExecutionPolicy Bypass -File ec_probe.ps1

  产出：
      ec_probe_result.txt   —— 完整结果(贴给我看)
      屏幕输出              —— 摘要
#>

$ErrorActionPreference = 'Continue'
$outFile = Join-Path $PSScriptRoot 'ec_probe_result.txt'
$lines = New-Object System.Collections.Generic.List[string]

function Log([string]$s) {
    Write-Host $s
    $lines.Add($s)
}

Log "==================================================="
Log " EC 只读探测(Windows 内置 ACPI 接口)"
Log " 时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Log "==================================================="

# ---------- 0. 权限检查 ----------
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
$isAdmin = $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Log ""
Log "[0] 身份: $($id.Name)   管理员=$isAdmin"
if (-not $isAdmin) {
    Log "    [!] 不是管理员。请右键 PowerShell -> 以管理员身份运行，再执行本脚本。"
    $lines -join "`r`n" | Set-Content -LiteralPath $outFile -Encoding UTF8
    exit 1
}

# ---------- 1. 找到 ACPI 设备 ----------
Add-Type -Namespace Win32 -Name Native -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
public static extern IntPtr CreateFileW(string lpFileName, uint dwDesiredAccess,
    uint dwShareMode, IntPtr lpSecurityAttributes, uint dwCreationDisposition,
    uint dwFlagsAndAttributes, IntPtr hTemplateFile);

[DllImport("kernel32.dll", SetLastError=true)]
public static extern bool DeviceIoControl(IntPtr hDevice, uint dwIoControlCode,
    IntPtr lpInBuffer, uint nInBufferSize,
    IntPtr lpOutBuffer, uint nOutBufferSize,
    out uint lpBytesReturned, IntPtr lpOverlapped);

[DllImport("kernel32.dll", SetLastError=true)]
public static extern bool CloseHandle(IntPtr hObject);

[DllImport("setupapi.dll", CharSet=CharSet.Unicode)]
public static extern IntPtr SetupDiGetClassDevsW(IntPtr ClassGuid, string Enumerator,
    IntPtr hwndParent, uint Flags);

[DllImport("setupapi.dll", CharSet=CharSet.Unicode)]
public static extern bool SetupDiEnumDeviceInfo(IntPtr DeviceInfoSet, uint MemberIndex,
    ref SP_DEVINFO_DATA DeviceInfoData);

[DllImport("setupapi.dll", CharSet=CharSet.Unicode)]
public static extern bool SetupDiGetDeviceRegistryPropertyW(IntPtr DeviceInfoSet,
    ref SP_DEVINFO_DATA DeviceInfoData, uint Property, out uint PropertyRegDataType,
    byte[] PropertyBuffer, uint PropertyBufferSize, out uint RequiredSize);

[DllImport("setupapi.dll")]
public static extern bool SetupDiDestroyDeviceInfoList(IntPtr DeviceInfoSet);

[StructLayout(LayoutKind.Sequential)]
public struct SP_DEVINFO_DATA {
    public uint cbSize; public Guid ClassGuid; public uint DevInst; public IntPtr Reserved;
}
'@

$DIGCF_PRESENT = 0x2
$SPDRP_HARDWAREID = 0x1
$SPDRP_DEVICEDESC = 0x0

Log ""
Log "[1] 枚举 ACPI 设备，找 PNP0C09(嵌入式控制器)"
$h = [Win32.Native]::SetupDiGetClassDevsW([IntPtr]::Zero, 'ACPI', [IntPtr]::Zero, $DIGCF_PRESENT)
if ($h -eq [IntPtr]::new(-1)) {
    Log "    [!] SetupDiGetClassDevs 失败 err=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
} else {
    $did = New-Object Win32.Native+SP_DEVINFO_DATA
    $did.cbSize = [Runtime.InteropServices.Marshal]::SizeOf($did)
    $idx = 0
    while ([Win32.Native]::SetupDiEnumDeviceInfo($h, $idx, [ref]$did)) {
        $buf = New-Object byte[] 1024
        $need = 0; $ty = 0
        if ([Win32.Native]::SetupDiGetDeviceRegistryPropertyW($h, [ref]$did, $SPDRP_HARDWAREID, [ref]$ty, $buf, 1024, [ref]$need)) {
            $hwids = [Text.Encoding]::Unicode.GetString($buf, 0, [int]$need) -split "`0" | Where-Object { $_ }
            if ($hwids -match 'PNP0C09') {
                $d2 = New-Object byte[] 512; $n2 = 0
                [void][Win32.Native]::SetupDiGetDeviceRegistryPropertyW($h, [ref]$did, $SPDRP_DEVICEDESC, [ref]$ty, $d2, 512, [ref]$n2)
                $desc = [Text.Encoding]::Unicode.GetString($d2, 0, [int]$n2) -replace "`0",''
                Log "    [+] 找到 EC: $desc"
                Log "        InstanceId(DevInst)=$($did.DevInst)  HWID=$($hwids -join ' | ')"
            }
        }
        $idx++
    }
    [void][Win32.Native]::SetupDiDestroyDeviceInfoList($h)
}

# ---------- 2. 打开 ACPI 设备并试 IOCTL ----------
Log ""
Log "[2] 尝试打开 \\.\ACPI 并发送 IOCTL"

$GENERIC_READ  = 0x80000000
$GENERIC_WRITE = 0x40000000
$OPEN_EXISTING = 3
$FILE_ATTRIBUTE_NORMAL = 0x80

$hAcpi = [Win32.Native]::CreateFileW('\\.\ACPI', $GENERIC_READ -bor $GENERIC_WRITE, 3,
            [IntPtr]::Zero, $OPEN_EXISTING, $FILE_ATTRIBUTE_NORMAL, [IntPtr]::Zero)
if ($hAcpi -eq [IntPtr]::new(-1)) {
    $e = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
    Log "    [-] 打开 \\.\ACPI 失败, GetLastError=$e"
    Log "        (2=找不到文件, 5=拒绝访问)"
    $hAcpi = $null
} else {
    Log "    [+] 已打开 \\.\ACPI"
}

# 候选 IOCTL 码(ACPI 设备的 FUNCTION 号)——只试读，不试写
#   CTL_CODE(FILE_DEVICE_ACPI=0x32, fn, METHOD_BUFFERED=0, FILE_ANY_ACCESS=0)
#   = (0x32 << 16) | (fn << 2)
$candidates = @(
    @{ name = 'READ_EC (0x08)';            code = 0x00320020 },
    @{ name = 'READ_EC_ALT (0x0C)';        code = 0x00320030 },
    @{ name = 'ENUM_ACPI_OBJECTS (0x02)';  code = 0x00320008 },
    @{ name = 'GET_DEVICE_INFORMATION';    code = 0x0032000C }
)

if ($hAcpi) {
    foreach ($c in $candidates) {
        $outBuf = [Runtime.InteropServices.Marshal]::AllocHGlobal(256)
        try {
            [Runtime.InteropServices.Marshal]::WriteInt64($outBuf, 0)
            $br = 0
            $ok = [Win32.Native]::DeviceIoControl($hAcpi, [uint32]$c.code,
                    $outBuf, 8, $outBuf, 256, [ref]$br, [IntPtr]::Zero)
            $err = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
            if ($ok) {
                Log "    [+] $($c.name)  code=0x$('{0:X8}' -f $c.code)  OK  bytesReturned=$br"
                $first = [Runtime.InteropServices.Marshal]::ReadInt32($outBuf)
                Log "        first4=0x$('{0:X8}' -f $first)"
            } else {
                Log "    [-] $($c.name)  code=0x$('{0:X8}' -f $c.code)  失败 err=$err"
            }
        } finally {
            [Runtime.InteropServices.Marshal]::FreeHGlobal($outBuf)
        }
    }
    [void][Win32.Native]::CloseHandle($hAcpi)
}

# ---------- 3. 汇总 ----------
Log ""
Log "==================================================="
Log " 如果 [2] 里 READ_EC 成功 => 我们可以纯用户态只读 EC,"
Log "    接着就能监视 EC RAM 里 MLR1(0xBD)/MLR2(0xBE) 是否随触控板变化。"
Log " 如果全部失败 => 需要第三方带签名的内核驱动(如 PawnIO)，再评估。"
Log "==================================================="

$lines -join "`r`n" | Set-Content -LiteralPath $outFile -Encoding UTF8
Write-Host ""
Write-Host "结果已保存: $outFile" -ForegroundColor Green
Write-Host "把 ec_probe_result.txt 的内容贴给我。" -ForegroundColor Yellow
