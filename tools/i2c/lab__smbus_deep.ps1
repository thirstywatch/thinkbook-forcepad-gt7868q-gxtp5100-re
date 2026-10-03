# smbus_deep.ps1 -- PawnIO SmbusI801 深度只读扫描
# ---------------------------------------------------------------
# 目的：
#   1) 用 BYTE_DATA 协议(不是 Quick)扫全部地址 0x03..0x77
#   2) 对每个应答设备 dump 寄存器 0x00..0x0F，帮助识别身份
#   3) 特别 dump 0x44(已知应答)看它是什么
#   4) 再确认 0x5A/0x5B 的 AW86927 身份证(0x57/0x58 == 0x92 0x70)
#
# ★ 全程只读，只用 READ 方向。
# 用法(管理员 PowerShell)：
#     & "<LAB>\touchpad-lab\smbus_deep.ps1"

$ErrorActionPreference = 'Continue'
$outFile = Join-Path $PSScriptRoot 'smbus_deep_result.txt'
$log = New-Object System.Collections.Generic.List[string]
function L([string]$s) { Write-Host $s; $log.Add($s) }

L "=========================================================="
L " PawnIO SmbusI801 深度只读扫描"
L " $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
L "=========================================================="

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$adm = (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $adm) {
    L "[!] 不是管理员。请在管理员 PowerShell 里运行。"
    $log -join "`r`n" | Set-Content -LiteralPath $outFile -Encoding UTF8
    exit 1
}

$mod = Join-Path $PSScriptRoot 'SmbusI801.bin'
if (-not (Test-Path -LiteralPath $mod)) { L "[!] 找不到 $mod"; exit 2 }
$blob = [IO.File]::ReadAllBytes($mod)
L "[1] 模块 $mod ($($blob.Length) bytes)"

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
if ($hr -ne 0) { L ("[!] pawnio_open 0x{0:X8}" -f $hr); $log -join "`r`n" | Set-Content $outFile -Encoding UTF8; exit 3 }
$hr = [PW.Io]::pawnio_load($h, $blob, [UIntPtr]::new([uint64]$blob.Length))
if ($hr -ne 0) { L ("[!] pawnio_load 0x{0:X8}" -f $hr); [void][PW.Io]::pawnio_close($h); exit 4 }
L "[2] pawnio_load OK"

function Exec([string]$name, [uint64[]]$in, [int]$outN) {
    $out = New-Object 'uint64[]' ([Math]::Max($outN,1))
    $rs = [UIntPtr]::Zero
    $r = [PW.Io]::pawnio_execute($h, $name, $in, [UIntPtr]::new([uint64]$in.Length),
                                  $out, [UIntPtr]::new([uint64]$outN), [ref]$rs)
    return @{ hr = $r; out = $out }
}
$READ = 1; $BYTE_DATA = 2; $BYTE = 1; $QUICK = 0
function SmbRead([int]$addr, [int]$cmd, [int]$proto) {
    $in = [uint64[]]@([uint64]$addr, [uint64]$READ, [uint64]$cmd, [uint64]$proto)
    $r = Exec 'ioctl_smbus_xfer' $in 1
    if ($r.hr -ne 0) { return @{ ok = $false; hr = $r.hr; v = -1 } }
    return @{ ok = $true; hr = 0; v = [int]($r.out[0] -band 0xFF) }
}

# ---------- 1. 三种协议交叉扫描 ----------
L ""
L "[3] 三种协议交叉扫描 0x03..0x77(找出所有真实存在的设备)"
$devices = @{}
foreach ($a in 0x03..0x77) {
    $hit = $null
    $q = Exec 'ioctl_smbus_xfer' ([uint64[]]@([uint64]$a, [uint64]$READ, 0, [uint64]$QUICK)) 1
    if ($q.hr -eq 0) { $hit = 'Quick' }
    if (-not $hit) {
        $b = SmbRead $a 0x00 $BYTE
        if ($b.ok) { $hit = 'Byte' }
    }
    if (-not $hit) {
        $bd = SmbRead $a 0x00 $BYTE_DATA
        if ($bd.ok) { $hit = "ByteData=0x$('{0:X2}' -f $bd.v)" }
    }
    if ($hit) {
        $devices[$a] = $hit
        L ("    [ACK] 0x{0:X2}   ({1})" -f $a, $hit)
    }
}
if ($devices.Count -eq 0) { L "    (三种协议都没有应答)" }
else { L ("    共 " + $devices.Count + " 个地址应答: " + (($devices.Keys | Sort-Object | ForEach-Object { '0x{0:X2}' -f $_ }) -join ' ')) }

# ---------- 2. dump 各设备的 0x00..0x0F ----------
L ""
L "[4] dump 每个应答设备的寄存器 0x00..0x0F"
foreach ($a in ($devices.Keys | Sort-Object)) {
    L ("    --- 0x{0:X2} ---" -f $a)
    $line = @(); $raw = @()
    foreach ($cmd in 0x00..0x0F) {
        $r = SmbRead $a $cmd $BYTE_DATA
        if ($r.ok) { $line += ('{0:X2}' -f $r.v); $raw += $r.v }
        else { $line += '--'; $raw += -1 }
    }
    L ("      reg 00-0F: " + ($line -join ' '))
    $asc = -join ($raw | ForEach-Object { if ($_ -ge 32 -and $_ -lt 127) { [char]$_ } else { '.' } })
    L ("      ascii    : " + $asc)
}

# ---------- 3. 0x44 专项 ----------
L ""
L "[5] 0x44 专项 dump(寄存器 0x00..0x7F)"
if ($devices.ContainsKey(0x44)) {
    for ($base = 0; $base -lt 0x80; $base += 16) {
        $line = @(); $asc = ''
        foreach ($i in 0..15) {
            $r = SmbRead 0x44 ($base + $i) $BYTE_DATA
            if ($r.ok) { $line += ('{0:X2}' -f $r.v); $asc += $(if ($r.v -ge 32 -and $r.v -lt 127) { [char]$r.v } else { '.' }) }
            else { $line += '--'; $asc += '.' }
        }
        L ("      {0:X2}: {1}  {2}" -f $base, ($line -join ' '), $asc)
    }
    L ""
    L "      提示：0x44 + SBS 寄存器含义 —— 0x09=电池电压(mV) 0x0A=电流 0x08=温度(0.1K) 0x0D=相对电量(%)"
    $v09 = SmbRead 0x44 0x09 3   # WORD_DATA
    if ($v09.ok) { L ("      读 0x09(WORD)=0x{0:X4}  => 若为电池，约 {1} mV" -f $v09.v, $v09.v) } else { L ("      0x09(WORD) 读取失败 hr=0x{0:X8}" -f $v09.hr) }
} else {
    L "    0x44 本次未应答"
}

# ---------- 4. AW86927 复核 ----------
L ""
L "[6] AW86927 复核：读 0x5A/0x5B 的 CHIPID(0x57/0x58)，期望 0x9270"
foreach ($a in 0x5A, 0x5B) {
    $hi = SmbRead $a 0x57 $BYTE_DATA
    $lo = SmbRead $a 0x58 $BYTE_DATA
    if ($hi.ok -and $lo.ok) {
        $chip = ($hi.v -shl 8) -bor $lo.v
        L ("    0x{0:X2}: CHIPID=0x{1:X4}  {2}" -f $a, $chip, $(if ($chip -eq 0x9270) { '★★★ 命中' } else { '不匹配' }))
    } else {
        L ("    0x{0:X2}: 无应答 (hr=0x{1:X8})" -f $a, $hi.hr)
    }
}

L ""
L "=========================================================="
L " 完成。把 smbus_deep_result.txt 发我。"
L "=========================================================="
[void][PW.Io]::pawnio_close($h)
$log -join "`r`n" | Set-Content -LiteralPath $outFile -Encoding UTF8
Write-Host ""
Write-Host "结果已保存: $outFile" -ForegroundColor Green
