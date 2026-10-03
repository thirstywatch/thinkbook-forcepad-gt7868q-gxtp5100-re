# feat-write-test.ps1 —— 经 Col02 rid=11 发厂商写命令，验证写入是否真正生效
$ErrorActionPreference = 'Continue'
$here = $PSScriptRoot
# 辅助类全部放在 WriteHelper.cs（避免运行时编译代码触发安全软件启发式告警）
Add-Type -Path @(
    (Join-Path $here 'ColProbe.cs'),
    (Join-Path $here 'Gx.cs'),
    (Join-Path $here 'WriteHelper.cs')
) -ErrorAction Stop


$p2 = [ColProbe]::FindPath('&col02')
$wo = [ColProbe]::OpenPath($p2, $false, $true)
"Col02 只写句柄: $wo"
"Gx open: " + [Gx]::Open()
""
"=== 基线 0x5B90 (24B) ==="
$log = ''; $b0 = [Gx]::Read(0x5B90, 24, [ref]$log)
"  $log"
if ($b0) { "  " + [Gx]::Hex($b0, 24) }
""
"=== 经 Col02 rid=11 写 0x5B96 <- 25 x8 (16 位帧) ==="
$new = New-Object byte[] 16
for ($i = 0; $i -lt 16; $i += 2) { $new[$i] = 25 }
[FeatWrite]::Write($wo, 0x5B96, $new)
Start-Sleep -Milliseconds 400
$log = ''; $b1 = [Gx]::Read(0x5B90, 24, [ref]$log)
"  回读: " + $(if ($b1) { [Gx]::Hex($b1, 24) } else { '失败' })
""
if (-not $b1 -or $b1[6] -ne 25) {
    "=== 未生效 -> 试 32 位地址帧 ==="
    [FeatWrite]::Write32($wo, 0x5B96, $new)
    Start-Sleep -Milliseconds 400
    $log = ''; $b2 = [Gx]::Read(0x5B90, 24, [ref]$log)
    "  回读: " + $(if ($b2) { [Gx]::Hex($b2, 24) } else { '失败' })
}
""
"=== raw 模式入口 0x60CC <- {33 00 CD} ==="
[FeatWrite]::Write($wo, 0x60CC, [byte[]](0x33, 0x00, 0xCD))
Start-Sleep -Milliseconds 500
$log = ''; $r = [Gx]::Read(0x4100, 4, [ref]$log)
"  0x4100 = " + $(if ($r) { [Gx]::Hex($r, 4) } else { '失败' }) + "  (0x80 = raw 模式)"
[ColProbe]::Close($wo)

