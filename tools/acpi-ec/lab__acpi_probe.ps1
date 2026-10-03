#requires -Version 5.1
<#
  acpi_probe.ps1 -- Read-only probe of what the Windows ACPI driver will let us do.
  ---------------------------------------------------------------------------
  Purpose: find out, without installing any third-party driver, whether this
  machine gives us a user-mode path to (a) enumerate ACPI namespace and
  (b) evaluate ACPI methods. If a firmware method exists that reads the
  embedded controller, that would be a zero-driver route.

  THIS SCRIPT ONLY READS. There is no write path anywhere in it.

  Run elevated:
      powershell -ExecutionPolicy Bypass -File acpi_probe.ps1

  Output:
      acpi_probe_result.txt
#>

$ErrorActionPreference = 'Continue'
$outFile = Join-Path $PSScriptRoot 'acpi_probe_result.txt'
$lines = New-Object System.Collections.Generic.List[string]
function Log([string]$s) { Write-Host $s; $lines.Add($s) }

Log "==================================================="
Log " ACPI user-mode probe (read only)"
Log " time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Log "==================================================="

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
$isAdmin = $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Log ""
Log "[0] user=$($id.Name)  admin=$isAdmin"
if (-not $isAdmin) {
    Log "    [!] Not elevated. Right-click PowerShell -> Run as administrator."
    $lines -join "`r`n" | Set-Content -LiteralPath $outFile -Encoding UTF8
    exit 1
}

Add-Type -Namespace Win32 -Name Native -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
public static extern IntPtr CreateFileW(string lpFileName, uint dwDesiredAccess,
    uint dwShareMode, IntPtr lpSecurityAttributes, uint dwCreationDisposition,
    uint dwFlagsAndAttributes, IntPtr hTemplateFile);

[DllImport("kernel32.dll", SetLastError=true)]
public static extern bool DeviceIoControl(IntPtr hDevice, uint dwIoControlCode,
    byte[] lpInBuffer, uint nInBufferSize,
    byte[] lpOutBuffer, uint nOutBufferSize,
    out uint lpBytesReturned, IntPtr lpOverlapped);

[DllImport("kernel32.dll", SetLastError=true)]
public static extern bool CloseHandle(IntPtr hObject);
'@

# CTL_CODE(FILE_DEVICE_ACPI=0x32, fn, METHOD_BUFFERED=0, FILE_READ_ACCESS|FILE_WRITE_ACCESS)
# access bits = 0x0003 -> (3 << 14) = 0xC000
function CtlCode([int]$fn) { [uint32]((0x32 -shl 16) -bor ($fn -shl 2) -bor 0xC000) }

$GENERIC_READ  = 0x80000000
$GENERIC_WRITE = 0x40000000
$OPEN_EXISTING = 3
$FILE_ATTRIBUTE_NORMAL = 0x80

Log ""
Log "[1] Open \\.\ACPI"
$h = [Win32.Native]::CreateFileW('\\.\ACPI', ($GENERIC_READ -bor $GENERIC_WRITE), 3,
        [IntPtr]::Zero, $OPEN_EXISTING, $FILE_ATTRIBUTE_NORMAL, [IntPtr]::Zero)
if ($h -eq [IntPtr]::new(-1)) {
    Log "    [-] CreateFile failed err=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())  (5 = access denied -> need elevation)"
    $h = $null
} else {
    Log "    [+] opened"
}

if ($h) {
    # ---- 1a. ENUM_CHILDREN (function 8) ----
    Log ""
    Log "[2] IOCTL_ACPI_ENUM_CHILDREN (fn=8) code=0x$('{0:X8}' -f (CtlCode 8))"
    $sigEnum = [Text.Encoding]::ASCII.GetBytes('EIeA')     # ACPI_ENUM_CHILDREN_INPUT_BUFFER Signature
    $inb = New-Object byte[] 8
    [Array]::Copy($sigEnum, 0, $inb, 0, 4)
    [BitConverter]::GetBytes([uint32]0x00000400).CopyTo($inb, 4)   # Flags = CHILDREN
    $outb = New-Object byte[] 8192
    $br = 0
    $ok = [Win32.Native]::DeviceIoControl($h, (CtlCode 8), $inb, 8, $outb, 8192, [ref]$br, [IntPtr]::Zero)
    if ($ok) {
        Log "    [+] OK  bytes=$br"
        Log "        header: " + (([BitConverter]::ToString($outb, 0, [Math]::Min(64,$br))))
    } else {
        Log "    [-] failed err=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
    }

    # ---- 1b. EVAL_METHOD (function 1) on a harmless path, just to see if the interface works ----
    Log ""
    Log "[3] IOCTL_ACPI_EVAL_METHOD (fn=1) code=0x$('{0:X8}' -f (CtlCode 1))"
    Log "    evaluating \_SB.PC00.LPCB.EC0._STA (a harmless read-only status method)"
    $path = [Text.Encoding]::ASCII.GetBytes("\_SB.PC00.LPCB.EC0._STA`0")
    $inb2 = New-Object byte[] (16 + $path.Length)
    [Text.Encoding]::ASCII.GetBytes('ACPI').CopyTo($inb2, 0)       # Signature
    [BitConverter]::GetBytes([uint32]8).CopyTo($inb2, 4)           # MethodNameLength = 8
    [BitConverter]::GetBytes([uint32]($path.Length)).CopyTo($inb2, 8)
    [BitConverter]::GetBytes([uint32]$path.Length).CopyTo($inb2, 12)  # ArgumentCount = 0 ... (layout approximated)
    [Array]::Copy($path, 0, $inb2, 16, $path.Length)
    $outb2 = New-Object byte[] 4096
    $br2 = 0
    $ok2 = [Win32.Native]::DeviceIoControl($h, (CtlCode 1), $inb2, [uint32]$inb2.Length, $outb2, 4096, [ref]$br2, [IntPtr]::Zero)
    if ($ok2) {
        Log "    [+] OK  bytes=$br2"
        Log "        " + (([BitConverter]::ToString($outb2, 0, [Math]::Min(32,$br2))))
    } else {
        Log "    [-] failed err=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
    }

    [void][Win32.Native]::CloseHandle($h)
}

Log ""
Log "==================================================="
Log " Interpretation:"
Log "  * ENUM_CHILDREN OK  -> user mode can walk the ACPI namespace."
Log "  * EVAL_METHOD  OK   -> user mode can invoke ACPI methods."
Log "  * Both fail w/ err=5 -> need full elevation; err=87 -> buffer layout."
Log "  * NOTE: on Windows there is NO IOCTL_ACPI_READ_EC (that is Linux)."
Log "          Reading EC RAM without a kernel driver is only possible if"
Log "          the firmware exposes an ACPI method that does it."
Log "==================================================="

$lines -join "`r`n" | Set-Content -LiteralPath $outFile -Encoding UTF8
Write-Host ""
Write-Host "saved: $outFile" -ForegroundColor Green
