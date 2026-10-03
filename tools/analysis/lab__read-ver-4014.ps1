# read-ver-4014.ps1 -- STRICTLY READ ONLY (Gx::Read only, 0x0e 0x20 direct-RW read frames).
#   Replicates official GT7868QDevice::SetBasicProperties():
#       Read(CFG_START_ADDR=0x96F8, &cfg_ver, 1)
#       Read(VER_ADDR=0x4014, fw_info, 32)
#       ChecksumU8_ys(fw_info,32) must be 0  (sum(fw_info[0..29]) == BE16(fw_info[30..31]))
#       m_pid      = fw_info[14..17]   ("7869" -> reported as 7868Q)
#       m_sensorID = fw_info[27]
#       major      = fw_info[23]
#       minor      = fw_info[24]<<16 | fw_info[25]<<8 | cfg_ver
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$LOG  = Join-Path $root 'read-ver-4014-log.txt'
function W($s) { Write-Host $s; Add-Content -LiteralPath $LOG -Value $s -Encoding utf8 }
function Hexs($d) { if ($null -eq $d) { return '<null>' }; return (($d | ForEach-Object { $_.ToString('X2') }) -join ' ') }
function Asc($d) { if ($null -eq $d) { return '' }; $sb=New-Object System.Text.StringBuilder; foreach($b in $d){ if($b -ge 32 -and $b -lt 127){[void]$sb.Append([char]$b)}else{[void]$sb.Append('.')} }; return $sb.ToString() }

W ("=== official SetBasicProperties replication (READ ONLY) :: " + (Get-Date -Format 's') + " ===")
Add-Type -Path @((Join-Path $root 'ColProbe.cs'), (Join-Path $root 'Gx.cs')) -ErrorAction Stop
$r = [Gx]::Open()
W ("Gx.Open = " + $r)
if ($r -ne 'ok') { exit 1 }

# 1) cfg version byte at CFG_START_ADDR
foreach ($t in @(@(0x96F8,1,'CFG_START_ADDR cfg_ver'), @(0x4014,32,'VER_ADDR fw_info[32]'), @(0x4160,8,'CMD_ADDR'), @(0x5095,2,'BL_STATE_ADDR'), @(0x5096,2,'FLASH_RESULT_ADDR'))) {
    $a=$t[0]; $n=$t[1]; $lbl=$t[2]
    $log=''
    $d=[Gx]::Read($a,$n,[ref]$log)
    W ("0x{0:X5} len={1,2} {2,-24} :: {3}  [{4}]  log={5}" -f $a,$n,$lbl,(Hexs $d),(Asc $d),$log)
    Start-Sleep -Milliseconds 260
}

# 2) decode fw_info per official rules
$fi = [Gx]::Read(0x4014,32,[ref]$lg)
if ($fi -ne $null -and $fi.Length -ge 32) {
    $sum = 0
    for ($i=0; $i -lt 30; $i++) { $sum += $fi[$i] }
    $sum = $sum -band 0xFFFF
    $infw = ($fi[30] -shl 8) -bor $fi[31]
    W ""
    W "--- decode (official ChecksumU8_ys: sum(b[0..29]) must equal BE16(b[30..31])) ---"
    W ("sum computed = 0x{0:X4} ; in-fw = 0x{1:X4} ; diff = 0x{2:X4}  => {3}" -f $sum,$infw,($sum-$infw),$(if($sum -eq $infw){'CHECKSUM OK'}else{'MISMATCH'}))
    $pid = -join ($fi[14..17] | ForEach-Object { if($_ -ge 32 -and $_ -lt 127){[char]$_}else{'.'} })
    W ("PID  fw_info[14..17] = {0}  [{1}]   (official: if '7869' then report '7868Q')" -f $pid, (Hexs $fi[14..17]))
    W ("sensorID fw_info[27] = {0} (0x{0:X2})   <== this selects tpcfgsid<N>.cfg" -f $fi[27])
    W ("versionMajor fw_info[23] = {0}" -f $fi[23])
    W ("versionMinor fw_info[24..25] = {0:X2} {1:X2}" -f $fi[24],$fi[25])
    W ("full: " + (Hexs $fi))
    W ("ascii: " + (Asc $fi))
} else { W "fw_info read FAILED" }

W "=== DONE (read only) ==="
