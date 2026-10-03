# goodix-probe.ps1 — Goodix 命令通道收发矩阵（只发 READ 命令）
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
Add-Type -Path (Join-Path $here 'GoodixCmd.cs')
Add-Type -Path (Join-Path $here 'RawTouchProbe.cs')

"Col04: $([GoodixCmd]::Open('GXTP5100','Col04'))"
"Col03: $([GoodixCmd]::OpenCol03())"
[RawTouchProbe]::Start($true, $false) | Out-Null
Start-Sleep -Milliseconds 300
[RawTouchProbe]::Drain() | Out-Null

function New-Pkt {
    $p = New-Object byte[] 65
    $p[0] = 0x0E
    return $p
}

function Attempt($desc, $pkt, $transport) {
    Write-Host ""
    Write-Host "--- $desc  [$transport] ---"
    $hex = ($pkt[0..11] | ForEach-Object { $_.ToString('X2') }) -join ' '
    Write-Host "    发送: $hex"
    switch ($transport) {
        'out'      { Write-Host "    $([GoodixCmd]::SendRaw($pkt))" }
        'col03r14' { Write-Host "    $([GoodixCmd]::SetFeatureVia(3,14,$pkt,65))" }
        'col03r11' { Write-Host "    $([GoodixCmd]::SetFeatureVia(3,11,$pkt,66))" }
    }
    $resp = [GoodixCmd]::RecvWindow(1200)
    $raw = New-Object System.Collections.ArrayList
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    while ($sw.ElapsedMilliseconds -lt 1600) {
        [RawTouchProbe]::Pump(150) | Out-Null
        foreach ($l in [RawTouchProbe]::Drain()) { [void]$raw.Add($l) }
    }
    if ($resp.Count) {
        Write-Host "    ★★ Col04 输入报文响应:" -ForegroundColor Green
        $resp | Select-Object -First 6 | ForEach-Object { Write-Host "        $_" }
    }
    $nonTouch = $raw | Where-Object { $_ -match '^RPT ' } | Where-Object { $_ -notmatch 'data= 04 ' }
    if ($nonTouch) {
        Write-Host "    ★★ Col02 出现非触摸报文:" -ForegroundColor Green
        $nonTouch | Select-Object -First 6 | ForEach-Object { Write-Host "        $_" }
    }
    if (-not $resp.Count -and -not $nonTouch) { Write-Host "    无任何响应" }
}

# ---- 构造各变体 ----
# A. GTX8 帧读 0x60DC(1)
$A = New-Pkt; $A[1]=0x20; $A[4]=5; $A[5]=1; $A[6]=0x60; $A[7]=0xDC; $A[8]=0; $A[9]=1
# B. GTX8 帧读 0x452C(72)
$B = New-Pkt; $B[1]=0x20; $B[4]=5; $B[5]=1; $B[6]=0x45; $B[7]=0x2C; $B[8]=0; $B[9]=0x48
# C. BRLB 帧读 0x1001E(14)
$C = New-Pkt; $C[1]=0x20; $C[4]=7; $C[5]=1; $C[6]=0; $C[7]=1; $C[8]=0; $C[9]=0x1E; $C[10]=0; $C[11]=0x0E

Attempt "A: GTX8 读 0x60DC(1B)"  $A 'out'
Attempt "B: GTX8 读 0x452C(72B)" $B 'out'
Attempt "C: BRLB 读 0x1001E(14B)" $C 'out'
Attempt "A: GTX8 读 0x60DC(1B)"  $A 'col03r14'
Attempt "C: BRLB 读 0x1001E(14B)" $C 'col03r14'
Attempt "A: GTX8 读 0x60DC(1B)"  $A 'col03r11'
Attempt "C: BRLB 读 0x1001E(14B)" $C 'col03r11'
