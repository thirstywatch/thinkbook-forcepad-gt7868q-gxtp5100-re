# ec_diff.ps1 -- EC RAM differential experiment (ASCII-only output, encoding-safe)
# ------------------------------------------------------------------------------
# Goal: find which EC RAM offsets change while you operate the touchpad,
#       to test the hypothesis that the EC manages haptics/touch on this board.
#
# Method: read baseline EC RAM -> you operate the touchpad 30s -> read 3 snapshots
#         -> diff -> settle 10s -> read again (noise control)
#
# READ-ONLY. The only writes are the ACPI RD_EC handshake bytes (required to read).
#
# Usage (administrator PowerShell):
#     & "<LAB>\touchpad-lab\ec_diff.ps1"

$ErrorActionPreference = 'Continue'
$outFile = Join-Path $PSScriptRoot 'ec_diff_result.txt'
$log = New-Object System.Collections.Generic.List[string]
function L([string]$s) { Write-Host $s; $log.Add($s) }

L "=========================================================="
L " EC RAM differential experiment"
L " $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
L "=========================================================="

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    L "[!] Administrator required. Run from an elevated PowerShell."
    $log -join "`r`n" | Set-Content -LiteralPath $outFile -Encoding UTF8
    exit 1
}

$mod = Join-Path $PSScriptRoot 'LpcACPIEC.bin'
if (-not (Test-Path -LiteralPath $mod)) { L "[!] module not found: $mod"; exit 2 }
$blob = [IO.File]::ReadAllBytes($mod)

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
if ($hr -ne 0) { L ("[!] pawnio_open 0x{0:X8}" -f $hr); exit 3 }
$hr = [PW.Io]::pawnio_load($h, $blob, [UIntPtr]::new([uint64]$blob.Length))
if ($hr -ne 0) { L ("[!] pawnio_load 0x{0:X8}" -f $hr); [void][PW.Io]::pawnio_close($h); exit 4 }
L "[1] PawnIO + LpcACPIEC ready"

$EC_DATA = 0x62; $EC_CMD = 0x66; $OBF = 0x01; $IBF = 0x02; $RD_EC = 0x80

function PioR([int]$p) {
    $o = New-Object 'uint64[]' 1; $rs = [UIntPtr]::Zero
    $r = [PW.Io]::pawnio_execute($h, 'ioctl_pio_read', ([uint64[]]@([uint64]$p)),
         [UIntPtr]::new(1), $o, [UIntPtr]::new(1), [ref]$rs)
    if ($r -ne 0) { throw ("pio_read 0x{0:X} hr=0x{1:X8}" -f $p, $r) }
    return [int]($o[0] -band 0xFF)
}
function PioW([int]$p, [int]$v) {
    $o = New-Object 'uint64[]' 1; $rs = [UIntPtr]::Zero
    $r = [PW.Io]::pawnio_execute($h, 'ioctl_pio_write', ([uint64[]]@([uint64]$p, [uint64]$v)),
         [UIntPtr]::new(2), $o, [UIntPtr]::new(0), [ref]$rs)
    if ($r -ne 0) { throw ("pio_write hr=0x{0:X8}" -f $r) }
}
function WaitF([int]$m, [bool]$set, [int]$t = 200) {
    for ($i = 0; $i -lt $t; $i++) {
        if ((((PioR $EC_CMD) -band $m) -ne 0) -eq $set) { return $true }
    }
    return $false
}
function EcByte([int]$off) {
    for ($i = 0; $i -lt 16; $i++) {
        if (((PioR $EC_CMD) -band $OBF) -eq 0) { break }
        [void](PioR $EC_DATA)
    }
    if (-not (WaitF $IBF $false)) { return -1 }
    PioW $EC_CMD $RD_EC
    if (-not (WaitF $IBF $false)) { return -1 }
    PioW $EC_DATA $off
    if (-not (WaitF $OBF $true)) { return -1 }
    return (PioR $EC_DATA)
}

function ReadEcRam([int]$retries = 3) {
    $ram = New-Object 'int[]' 256
    for ($o = 0; $o -le 0xFF; $o++) {
        $votes = @{}
        for ($k = 0; $k -lt $retries; $k++) {
            $v = EcByte $o
            if ($v -ge 0) { if ($votes.ContainsKey($v)) { $votes[$v]++ } else { $votes[$v] = 1 } }
        }
        if ($votes.Count -eq 0) { $ram[$o] = -1 }
        else {
            $best = ($votes.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 1)
            $ram[$o] = [int]$best.Key
        }
    }
    return $ram
}

function DumpRam($ram) {
    for ($base = 0; $base -lt 256; $base += 16) {
        $hexs = @(); $asc = ''
        for ($i = 0; $i -lt 16; $i++) {
            $v = $ram[$base + $i]
            if ($v -lt 0) { $hexs += '--'; $asc += '.' }
            else { $hexs += ('{0:X2}' -f $v); $asc += $(if ($v -ge 32 -and $v -lt 127) { [char]$v } else { '.' }) }
        }
        L ("    {0:X2}: {1}  {2}" -f $base, ($hexs -join ' '), $asc)
    }
}

# ---------- baseline ----------
L ""
L "[2] Reading baseline (3 reads per offset, majority vote)..."
$t0 = Get-Date
$base = ReadEcRam 3
$valid = ($base | Where-Object { $_ -ge 0 }).Count
L ("    baseline done in {0:N1}s, valid offsets {1}/256" -f ((Get-Date) - $t0).TotalSeconds, $valid)
L ""
L "    baseline EC RAM:"
DumpRam $base

# ---------- interaction window ----------
L ""
L "=========================================================="
L "  *** ACTION REQUIRED: operate the touchpad now (30s) ***"
L "   - slide one finger across the touchpad"
L "   - click / press the touchpad several times"
L "   - note whether you feel any vibration"
L "  The program waits 30 seconds."
L "=========================================================="
for ($s = 30; $s -gt 0; $s--) {
    Write-Host ("`r  {0,2}s remaining... " -f $s) -NoNewline
    Start-Sleep -Seconds 1
}
Write-Host "`r  reading interaction snapshots...      "

$snaps = @()
for ($k = 1; $k -le 3; $k++) {
    $snaps += ,(ReadEcRam 1)
    Write-Host ("  snapshot {0}/3 done" -f $k)
}

# ---------- diff ----------
L ""
L "[3] DIFF: baseline vs 3 interaction snapshots"
$changed = @{}
foreach ($o in 0..255) {
    $vals = @()
    foreach ($s in $snaps) { $vals += $s[$o] }
    $distinct = ($vals | Where-Object { $_ -ge 0 } | Sort-Object -Unique)
    $b = $base[$o]
    $diff = $false
    foreach ($v in $distinct) { if ($v -ne $b) { $diff = $true } }
    if ($distinct.Count -gt 1) { $diff = $true }
    if ($diff) { $changed[$o] = @{ base = $b; snaps = $vals } }
}

if ($changed.Count -eq 0) {
    L "    *** NO offset changed. ***"
    L "    => 30s of touchpad operation produced no visible EC RAM change."
} else {
    L ("    *** {0} offsets changed: ***" -f $changed.Count)
    L ""
    L "    off    base   snapshot1 snapshot2 snapshot3   note"
    foreach ($o in ($changed.Keys | Sort-Object)) {
        $c = $changed[$o]
        $note = ''
        if ($o -ge 0xB8 -and $o -le 0xC2) { $note = '<- near MLR0-3 (0xBD-0xC0)' }
        elseif ($o -ge 0xD0 -and $o -le 0xDF) { $note = '<- near PL1V/MOFD (0xD0-0xDE)' }
        L ("    0x{0:X2}   {1,-6} {2}   {3}" -f $o,
            $(if ($c.base -lt 0) { '--' } else { '0x{0:X2}' -f $c.base }),
            (($c.snaps | ForEach-Object { if ($_ -lt 0) { '--' } else { '0x{0:X2}' -f $_ } }) -join '     '),
            $note)
    }
}

# ---------- settle re-read ----------
L ""
L "[4] Settle re-read (do NOT touch the touchpad, wait 10s)..."
Start-Sleep -Seconds 10
$after = ReadEcRam 1
$noise = 0
$noiseList = @()
foreach ($o in 0..255) {
    if ($after[$o] -ne $base[$o]) { $noise++; $noiseList += $o }
}
L ("    offsets different from baseline after settle: {0}" -f $noise)
if ($noise -gt 0) {
    L "    (these are likely natural drift: temperature, timers)"
    foreach ($o in $noiseList) {
        L ("      0x{0:X2}: baseline=0x{1:X2} -> settle=0x{2:X2}" -f $o, $base[$o], $after[$o])
    }
}

L ""
L "[5] Key offsets (from DSDT: LA3M window 0xFE0B0F00)"
foreach ($o in 0xBD, 0xBE, 0xBF, 0xC0, 0xD0, 0xD1, 0xDE) {
    L ("    EC[0x{0:X2}]  base={1}  snapshots={2}" -f $o,
        $(if ($base[$o] -lt 0) { '--' } else { '0x{0:X2}' -f $base[$o] }),
        (($snaps | ForEach-Object { if ($_[$o] -lt 0) { '--' } else { '0x{0:X2}' -f $_[$o] } }) -join ' '))
}

[void][PW.Io]::pawnio_close($h)
L ""
L "=========================================================="
L " DONE. Send ec_diff_result.txt back."
L "=========================================================="
$log -join "`r`n" | Set-Content -LiteralPath $outFile -Encoding UTF8
Write-Host ""
Write-Host "saved: $outFile" -ForegroundColor Green
