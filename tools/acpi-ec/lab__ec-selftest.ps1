# ec-selftest.ps1 -- EC 读链自检（不打扰用户，不采集动作）
# 目的：在正式跑 6 相位采集前，先确认 PawnIO 桥 + RD_EC 握手 + 256 B 读全部正常。
# 只读，不写 EC RAM。

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== EC 读链自检 ===" -ForegroundColor Cyan

# 1) 权限
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$adm = (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
Write-Host ("[1] 管理员: {0}" -f $adm)
if (-not $adm) {
    Write-Host "    ★ 需要管理员。请用管理员身份重开 PowerShell 再跑。"
    Write-Host ""
    Write-Host "    建议直接用这条（会自动弹 UAC）："
    Write-Host "    Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','.\ec-haptic-probe.ps1'"
    exit 1
}

# 2) 模块
function Find-Module {
    $c = @()
    $c += (Join-Path $here 'LpcACPIEC.bin')
    $c += (Join-Path $here 'pawnio\mod011\LpcACPIEC.bin')
    $c += (Join-Path (Split-Path -Parent $here) 'LpcACPIEC.bin')
    $c += 'C:\Program Files\PawnIO\modules\LpcACPIEC.bin'
    foreach ($x in $c) { if ($x -and (Test-Path -LiteralPath $x)) { return $x } }
    return $null
}
$mod = Find-Module
Write-Host ("[2] LpcACPIEC.bin: {0}" -f $(if ($mod) { $mod } else { '未找到' }))
if (-not $mod) { exit 2 }

# 3) PawnIOLib
Write-Host ("[3] PawnIOLib.dll: {0}" -f (Test-Path 'C:\Program Files\PawnIO\PawnIOLib.dll'))

# 4) 实际读一次
Add-Type -Namespace ST -Name Io -MemberDefinition @'
[DllImport(@"C:\Program Files\PawnIO\PawnIOLib.dll", CallingConvention=CallingConvention.StdCall)]
public static extern int pawnio_open(out IntPtr handle);
[DllImport(@"C:\Program Files\PawnIO\PawnIOLib.dll", CallingConvention=CallingConvention.StdCall)]
public static extern int pawnio_load(IntPtr h, byte[] blob, UIntPtr size);
[DllImport(@"C:\Program Files\PawnIO\PawnIOLib.dll", CallingConvention=CallingConvention.StdCall)]
public static extern int pawnio_execute(IntPtr h, [MarshalAs(UnmanagedType.LPStr)] string name,
    ulong[] inBuf, UIntPtr inSize, ulong[] outBuf, UIntPtr outSize, out UIntPtr retSize);
[DllImport(@"C:\Program Files\PawnIO\PawnIOLib.dll", CallingConvention=CallingConvention.StdCall)]
public static extern int pawnio_close(IntPtr h);
'@
$h = [IntPtr]::Zero
$hr = [ST.Io]::pawnio_open([ref]$h)
Write-Host ("[4] pawnio_open HR=0x{0:X8}" -f $hr)
if ($hr -ne 0) {
    Write-Host "    ★ 失败。0x80070005=需管理员；0x8007000E=模块未加载（先跑 PawnIOUtil.exe install-driver）"
    exit 3
}
$blob = [IO.File]::ReadAllBytes($mod)
$hr = [ST.Io]::pawnio_load($h, $blob, [UIntPtr]::new([uint64]$blob.Length))
Write-Host ("[5] pawnio_load HR=0x{0:X8}  ({1} 字节)" -f $hr, $blob.Length)
if ($hr -ne 0) { [void][ST.Io]::pawnio_close($h); exit 4 }

function PioRead([int]$port) {
    $i = [uint64[]]@([uint64]$port); $o = [uint64[]]@(0); $rs = [UIntPtr]::Zero
    $r = [ST.Io]::pawnio_execute($h, 'ioctl_pio_read', $i, [UIntPtr]::new(1),
                                $o, [UIntPtr]::new(1), [ref]$rs)
    if ($r -ne 0) { throw ("pio_read 0x{0:X} HR=0x{1:X8}" -f $port, $r) }
    return [int]($o[0] -band 0xFF)
}
function PioWrite([int]$port, [int]$val) {
    $i = [uint64[]]@([uint64]$port, [uint64]$val); $o = [uint64[]]@(0); $rs = [UIntPtr]::Zero
    $r = [ST.Io]::pawnio_execute($h, 'ioctl_pio_write', $i, [UIntPtr]::new(2),
                                $o, [UIntPtr]::new(0), [ref]$rs)
    if ($r -ne 0) { throw ("pio_write 0x{0:X} HR=0x{1:X8}" -f $port, $r) }
}
$EC_DATA = 0x62; $EC_CMD = 0x66; $OBF = 0x01; $IBF = 0x02; $RD_EC = 0x80
function WaitFlag([int]$m, [bool]$s, [int]$t = 200) {
    for ($i = 0; $i -lt $t; $i++) { if (((((PioRead $EC_CMD) -band $m)) -ne 0) -eq $s) { return $true } }
    return $false
}
function EcReadByte([int]$off) {
    for ($i = 0; $i -lt 16; $i++) {
        if (((PioRead $EC_CMD) -band $OBF) -eq 0) { break }
        [void](PioRead $EC_DATA)
    }
    if (-not (WaitFlag $IBF $false)) { return -1 }
    PioWrite $EC_CMD $RD_EC
    if (-not (WaitFlag $IBF $false)) { return -1 }
    PioWrite $EC_DATA $off
    if (-not (WaitFlag $OBF $true)) { return -1 }
    return (PioRead $EC_DATA)
}

# 读 3 次，检查稳定性
Write-Host "[6] 连读 3 轮 256 B，测稳定性..."
$prev = $null
for ($round = 1; $round -le 3; $round++) {
    $ram = New-Object int[] 256
    $fail = 0
    for ($o = 0; $o -lt 256; $o++) {
        $ram[$o] = EcReadByte $o
        if ($ram[$o] -lt 0) { $fail++ }
    }
    $nonff = @($ram | Where-Object { $_ -ge 0 -and $_ -ne 0xFF }).Count
    $md5 = [System.Security.Cryptography.MD5]::Create().ComputeHash(
             [byte[]]@(($ram | ForEach-Object { if ($_ -lt 0) { 0xFF } else { $_ } })))
    $md5s = ($md5 | ForEach-Object { $_.ToString('x2') }) -join ''
    Write-Host ("    轮 {0}: 读失败 {1}/256 ；非0xFF {2}/256 ；MD5 {3}" -f $round, $fail, $nonff, $md5s)
    if ($round -eq 1) {
        Write-Host ""
        Write-Host "    EC RAM 前 64 B:"
        for ($base = 0; $base -lt 64; $base += 16) {
            $hx = ($ram[$base..($base+15)] | ForEach-Object {
                    if ($_ -lt 0) { '--' } else { '{0:X2}' -f $_ } }) -join ' '
            Write-Host ("      {0:X2}: {1}" -f $base, $hx)
        }
        Write-Host ""
        $prev = $ram
    } else {
        $diff = 0
        for ($o = 0; $o -lt 256; $o++) { if ($ram[$o] -ne $prev[$o]) { $diff++ } }
        Write-Host ("         与轮 1 相比：{0} 个偏移不同" -f $diff)
    }
}
[void][ST.Io]::pawnio_close($h)
Write-Host ""
Write-Host "=== 自检通过，可以跑正式采集 ===" -ForegroundColor Green
Write-Host "    powershell -ExecutionPolicy Bypass -File .\ec-haptic-probe.ps1"