# sniff-col04.ps1 —— 旁路嗅探器：被动读 Col04 输入报表，记录"设备收到的最后一条命令"变化
# 原理: Col04 的 IN 报表会镜像设备最近收到的命令包（任意集合的流量都会出现）
# 安全性: 纯读取，不向设备写任何东西
param(
    [int]$Seconds = 120,
    [int]$PollMs = 40
)
$ErrorActionPreference = 'Continue'
$here = $PSScriptRoot
$log = Join-Path $here 'col04-sniff-log.txt'
Add-Type -Path (Join-Path $here 'ColProbe.cs') -ErrorAction Stop

$p4 = [ColProbe]::FindPath('&col04')
$h = [ColProbe]::OpenPath($p4, $true, $false)   # 只读
if ($h -eq [IntPtr]::Zero) { "Col04 只读打开失败"; exit 1 }

function Hex16($b) { ($b[0..15] | ForEach-Object { $_.ToString('X2') }) -join ' ' }
function HexAll($b) { ($b | ForEach-Object { $_.ToString('X2') }) -join ' ' }

Set-Content -Path $log -Value ("=== col04 sniff start " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + " (read-only) ===") -Encoding utf8
"开嗅探: $Seconds 秒, 每 ${PollMs}ms 一次 (只读, 不写设备)"

$prev = $null
$count = 0
$distinct = @{}
$sw = [System.Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
    $r = [ColProbe]::GetInputReport65($h, 14)
    if ($r) {
        $key = ($r[0..15] | ForEach-Object { $_.ToString('X2') }) -join ''
        if ($key -ne $prev) {
            $count++
            $ts = (Get-Date -Format 'HH:mm:ss.fff')
            $line = "[$ts] #$count  " + (Hex16 $r)
            Write-Output $line
            Add-Content -Path $log -Value $line -Encoding utf8
            Add-Content -Path $log -Value ("            完整: " + (HexAll $r)) -Encoding utf8
            $prev = $key
            $distinct[$key] = ($distinct[$key] + 1)
        }
    }
    Start-Sleep -Milliseconds $PollMs
}
[ColProbe]::Close($h)

""
"=== 本次共捕获 $count 次变化，$($distinct.Count) 种不同包头 ==="
$i = 0
foreach ($k in $distinct.Keys) {
    $i++
    $bytes = for ($j = 0; $j -lt 16; $j++) { $k.Substring($j * 2, 2) }
    "  [$i] x$($distinct[$k])  " + ($bytes -join ' ')
}
Add-Content -Path $log -Value ("=== end: $count changes, $($distinct.Count) distinct ===") -Encoding utf8
"日志: $log"
