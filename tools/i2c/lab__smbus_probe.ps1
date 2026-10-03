# smbus_probe.ps1 -- 用 PawnIO 的 SmbusI801 模块(签名)扫描 PCH SMBus
# ---------------------------------------------------------------------
# 目的：在主机可见的 SMBus 上找 AW86927(触觉驱动 IC)
#   AW86927 身份标识：读寄存器 0x57(高)/0x58(低) == 0x92 0x70
#
# ★ 全程只读。只用 I2C_SMBUS_BYTE_DATA 的 READ 方向，绝不写。
#
# 用法(管理员 PowerShell)：
#     powershell -ExecutionPolicy Bypass -File smbus_probe.ps1

$ErrorActionPreference = 'Continue'
$outFile = Join-Path $PSScriptRoot 'smbus_probe_result.txt'
$log = New-Object System.Collections.Generic.List[string]
function L([string]$s) { Write-Host $s; $log.Add($s) }

L "=========================================================="
L " PawnIO SmbusI801 只读扫描  (找 AW86927)"
L " $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
L "=========================================================="

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$adm = (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $adm) {
    L "[*] 当前不是管理员，正在请求提权(会弹 UAC，请点『是』)..."
    $log -join "`r`n" | Set-Content -LiteralPath $outFile -Encoding UTF8
    try {
        Start-Process -FilePath 'powershell.exe' -Verb RunAs -Wait -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass',
            '-File', ('"{0}"' -f $PSCommandPath)
        )
        L "[*] 提权进程已结束。见下方结果(或窗口里的报告)。"
    } catch {
        L "[!] 提权被拒绝或失败: $($_.Exception.Message)"
    }
    $log -join "`r`n" | Set-Content -LiteralPath $outFile -Encoding UTF8
    exit 0
}
L "[0] admin=OK"

# ---- 找模块 ----
$mod = Join-Path $PSScriptRoot 'SmbusI801.bin'
if (-not (Test-Path -LiteralPath $mod)) {
    L "[!] 找不到 $mod"
    $log -join "`r`n" | Set-Content -LiteralPath $outFile -Encoding UTF8
    exit 2
}
$blob = [IO.File]::ReadAllBytes($mod)
L "[1] 模块: $mod  ($($blob.Length) bytes)"

# ---- P/Invoke ----
Add-Type -Namespace PW -Name Io -MemberDefinition @'
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
$hr = [PW.Io]::pawnio_open([ref]$h)
if ($hr -ne 0) { L ("[!] pawnio_open 失败 0x{0:X8}" -f $hr); $log -join "`r`n" | Set-Content $outFile -Encoding UTF8; exit 3 }
$hr = [PW.Io]::pawnio_load($h, $blob, [UIntPtr]::new([uint64]$blob.Length))
if ($hr -ne 0) { L ("[!] pawnio_load 失败 0x{0:X8}(模块不匹配本机？)" -f $hr); [void][PW.Io]::pawnio_close($h); $log -join "`r`n" | Set-Content $outFile -Encoding UTF8; exit 4 }
L "[2] pawnio_load OK"

function Exec([string]$name, [uint64[]]$in, [int]$outN) {
    $out = New-Object 'uint64[]' ([Math]::Max($outN,1))
    $rs = [UIntPtr]::Zero
    $r = [PW.Io]::pawnio_execute($h, $name, $in, [UIntPtr]::new([uint64]$in.Length),
                                  $out, [UIntPtr]::new([uint64]$outN), [ref]$rs)
    return @{ hr = $r; out = $out }
}

# ---- 控制器身份 ----
L ""
L "[3] 控制器身份 ioctl_identity"
$r = Exec 'ioctl_identity' ([uint64[]]@()) 3
if ($r.hr -eq 0) {
    $t = $r.out[0]
    $chars = @()
    foreach ($sh in 0,8,16,24,32) { $c = ($t -shr $sh) -band 0xFF; if ($c) { $chars += [char]$c } }
    L ("    type      = " + (-join $chars))
    L ("    IO base   = 0x{0:X}" -f $r.out[1])
    L ("    PCI IDs   = 0x{0:X16}" -f $r.out[2])
} else {
    L ("    [-] 失败 HRESULT=0x{0:X8}" -f $r.hr)
    L "    => 说明这个模块不认本机的 SMBus 控制器"
}

# ---- SMBus 传输封装 ----
# in [0]=addr [1]=rw(1=读) [2]=cmd [3]=protocol(2=BYTE_DATA)
# out[0]=数据
$I2C_SMBUS_READ  = 1
$I2C_SMBUS_WRITE = 0
$I2C_SMBUS_BYTE_DATA = 2

function SmbReadByteData([int]$addr, [int]$cmd) {
    $in = [uint64[]]@([uint64]$addr, [uint64]$I2C_SMBUS_READ, [uint64]$cmd, [uint64]$I2C_SMBUS_BYTE_DATA)
    $r = Exec 'ioctl_smbus_xfer' $in 1
    if ($r.hr -ne 0) { return @{ ok = $false; hr = $r.hr; val = -1 } }
    return @{ ok = $true; hr = 0; val = [int]($r.out[0] -band 0xFF) }
}
function SmbQuick([int]$addr) {
    $in = [uint64[]]@([uint64]$addr, [uint64]$I2C_SMBUS_READ, 0, 0)
    $r = Exec 'ioctl_smbus_xfer' $in 1
    return @{ ok = ($r.hr -eq 0); hr = $r.hr }
}

# ---- 扫描 ----
L ""
L "[4] 扫描 SMBus 地址 0x03..0x77(Quick 探测有无 ACK)"
$present = @()
for ($a = 0x03; $a -le 0x77; $a++) {
    $q = SmbQuick $a
    if ($q.ok) {
        $present += $a
        $b = SmbReadByteData $a 0x00
        $v = if ($b.ok) { '0x{0:X2}' -f $b.val } else { ('读失败 0x{0:X8}' -f $b.hr) }
        L ("    [ACK] 0x{0:X2}   reg00={1}" -f $a, $v)
    }
}
if ($present.Count -eq 0) { L "    (没有任何地址应答)" } else { L ("    应答地址: " + (($present | ForEach-Object { '0x{0:X2}' -f $_ }) -join ' ')) }

# ---- 针对 AW86927 的定向检查 ----
L ""
L "[5] 定向检查 AW86927(读 CHIPID 0x57/0x58，期望 0x92 0x70)"
$AW86927_CHIPID = 0x9270
$found = $false
foreach ($a in 0x5A, 0x5B) {
    $hi = SmbReadByteData $a 0x57
    $lo = SmbReadByteData $a 0x58
    if ($hi.ok -and $lo.ok) {
        $chip = ($hi.val -shl 8) -bor $lo.val
        $mark = if ($chip -eq $AW86927_CHIPID) { '  ★★★ 命中！这就是 AW86927' } else { '' }
        L ("    0x{0:X2}: CHIPID = 0x{1:X4}  (0x57=0x{2:X2} 0x58=0x{3:X2}){4}" -f $a, $chip, $hi.val, $lo.val, $mark)
        if ($chip -eq $AW86927_CHIPID) { $found = $true }
    } else {
        L ("    0x{0:X2}: 无应答 (0x57 hr=0x{1:X8}, 0x58 hr=0x{2:X8})" -f $a, $hi.hr, $lo.hr)
    }
}

L ""
L "=========================================================="
if ($found) {
    L " 结果：★ AW86927 就在主机可见的 SMBus 上!"
    L "       => 纯软件路成立，可以直接写它让它震动。"
} elseif ($present.Count -gt 0) {
    L " 结果：SMBus 上有设备(见 [4])，但 0x5A/0x5B 不是 AW86927。"
    L "       => 它不在这条 SMBus 上。"
} else {
    L " 结果：整条 SMBus 无任何设备应答。"
    L "       => 要么控制器没启用，要么本来就没挂设备(需另找阳性对照)。"
}
L " 把这份结果发给我。"
L "=========================================================="

[void][PW.Io]::pawnio_close($h)
$log -join "`r`n" | Set-Content -LiteralPath $outFile -Encoding UTF8
Write-Host ""
Write-Host "结果已保存: $outFile" -ForegroundColor Green
