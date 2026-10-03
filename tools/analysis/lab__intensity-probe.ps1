# intensity-probe.ps1 —— 写 Col02 feature rid=9（Haptic Intensity）→ 读两个已证稳定的窗口 → 差分
#
# 目的（修正后的目标）：不是"能不能靠写强度触发震动"（那个 2026-09-13 已测，阴性），
#   而是回答：**64 KB 窗口里到底有没有"触觉控制面"？**
#     若某个地址随 intensity 变化 ⇒ 有，且我们得到一个可复用的"探针"
#     若完全不随 intensity 变  ⇒ 这个窗口不是触觉控制面，别再往里找
#
# 设计（含内置噪声基线）：
#   step1 = 10（基线，项目已知良好值）
#   step2 = 0
#   step3 = 100
#   step4 = 10（回写）
#   差分：1vs2 / 1vs3 / 2vs3  ⇒ 强度相关变化
#         1vs4                ⇒ ★ 噪声基线（同一个值、不同时刻；若它也大量变化，则实验无效）
#
# 安全：只写 rid=9（描述符正式声明、实测可写可回写）；只读两个已证秒级稳定的窗口；
#       总帧数 ≈ 4×7 读 + 4 写；活性门；任何失败立即回写 10 并退出。
param([ValidateSet('Run','Diff')][string]$Phase = 'Run')

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$LOG  = Join-Path $root 'intensity-probe-log.txt'
function W($s) { $s | Tee-Object -FilePath $LOG -Append | Write-Host }

$WINDOWS = @(@(0x4000, 256), @(0x5B80, 128))
$STEPS   = @(
    @{ n = 1; v = 10 },
    @{ n = 2; v = 0 },
    @{ n = 3; v = 100 },
    @{ n = 4; v = 10 }
)

function SaveMap($map, $path) {
    $lines = New-Object System.Collections.Generic.List[string]
    foreach ($w in $WINDOWS) {
        $lines.Add(("0x{0:X4} {1}" -f $w[0], (($map[$w[0]] | ForEach-Object { $_.ToString('X2') }) -join ' ')))
    }
    [IO.File]::WriteAllLines($path, $lines.ToArray())
}
function LoadMap($path) {
    $m = @{}
    foreach ($ln in [IO.File]::ReadAllLines($path)) {
        $sp = $ln.IndexOf(' '); if ($sp -lt 3) { continue }
        $b = New-Object System.Collections.Generic.List[byte]
        foreach ($t in $ln.Substring($sp + 1).Split(' ')) { if ($t.Length -eq 2) { $b.Add([Convert]::ToByte($t, 16)) } }
        $m[[Convert]::ToInt32($ln.Substring(2, $sp - 2), 16)] = $b.ToArray()
    }
    return $m
}

if ($Phase -eq 'Run') {
    Add-Type -Path @((Join-Path $root 'ColProbe.cs'), (Join-Path $root 'Gx.cs')) -ErrorAction Stop
    W ("=== intensity probe :: {0} ===" -f (Get-Date -Format s))

    $r = [Gx]::Open()
    W "Col04 open: $r"
    if ($r -ne 'ok') { W "ABORT: Col04 打不开"; exit 1 }
    $p02 = [ColProbe]::FindPath('&col02')
    if (-not $p02) { W "ABORT: 找不到 Col02"; exit 1 }
    $h = [ColProbe]::OpenPath($p02, $false, $true)
    if ($h -eq [IntPtr]::Zero) { W "ABORT: Col02 只写句柄打不开"; exit 1 }
    W "Col02 write-only handle: OK"

    foreach ($s in $STEPS) {
        W ""
        W ("--- step {0}: intensity = {1} ---" -f $s.n, $s.v)
        W ("  " + [ColProbe]::SetFeat($h, 9, [byte[]]@([byte]$s.v)))
        Start-Sleep -Milliseconds 400

        $lg = ''
        $probe = [Gx]::Read(0x5B8E, 16, [ref]$lg)
        if ($null -eq $probe) {
            W ("  LIVENESS FAILED at 0x5B8E :: {0} -- ABORT（回写 10）" -f $lg)
            [void][ColProbe]::SetFeat($h, 9, [byte[]]@([byte]10)); exit 2
        }

        $map = @{}
        foreach ($w in $WINDOWS) {
            $base = $w[0]; $size = $w[1]
            $acc = New-Object System.Collections.Generic.List[byte]
            $a = $base
            while ($a -lt ($base + $size)) {
                $n = [Math]::Min(60, $base + $size - $a)
                $l2 = ''
                $d = [Gx]::Read($a, $n, [ref]$l2)
                if ($null -eq $d -or $d.Length -eq 0) {
                    W ("  FAIL at 0x{0:X4} :: {1} -- ABORT（回写 10）" -f $a, $l2)
                    [void][ColProbe]::SetFeat($h, 9, [byte[]]@([byte]10)); exit 3
                }
                $acc.AddRange($d); $a += $d.Length
                Start-Sleep -Milliseconds 10
            }
            $map[$base] = $acc.ToArray()
            W ("  window 0x{0:X4} = {1} bytes" -f $base, $acc.Count)
        }
        SaveMap $map (Join-Path $root ("intensity-step{0}.txt" -f $s.n))
    }
    [ColProbe]::Close($h)
    W ""
    W "全部完成，已回写 intensity=10。"
    exit 0
}

# ---- 纯离线差分 ----
W ""
W "=== 差分（窗口里若某地址随 intensity 变 ⇒ 那是触觉控制面）==="
$maps = @{}
foreach ($n in 1, 2, 3, 4) {
    $p = Join-Path $root ("intensity-step{0}.txt" -f $n)
    if (Test-Path $p) { $maps[$n] = LoadMap $p } else { W ("缺 intensity-step{0}.txt" -f $n) }
}
$pairs = @(@(1, 2, '10 vs 0'), @(1, 3, '10 vs 100'), @(2, 3, '0 vs 100'), @(1, 4, '★10 vs 10（噪声基线）'))
foreach ($pr in $pairs) {
    W ""
    W ("--- {0} ---" -f $pr[2])
    # NB: PS 变量名大小写不敏感 —— 不要把这两个 map 命名成 $A/$B，否则下面 $arrA/$arrB 会冲掉它们
    #     （这一个坑 diff-probe.ps1 第 98 行已经写过警告）
    $mapP = $maps[$pr[0]]; $mapQ = $maps[$pr[1]]
    if ($null -eq $mapP -or $null -eq $mapQ) { W "  缺数据，跳过"; continue }
    foreach ($w in $WINDOWS) {
        $base = $w[0]
        $arrP = $mapP[$base]; $arrQ = $mapQ[$base]
        if ($null -eq $arrP -or $null -eq $arrQ) { W ("  窗口 0x{0:X4}: 缺数据" -f $base); continue }
        $cells = 0; $shown = 0
        $lim = [Math]::Min($arrP.Length, $arrQ.Length) - 1
        for ($i = 0; $i -lt $lim; $i += 2) {
            $va = $arrP[$i] + $arrP[$i + 1] * 256; $vb = $arrQ[$i] + $arrQ[$i + 1] * 256
            if ($va -ne $vb) {
                $cells++
                if ($shown -lt 12) { W ("    0x{0:X4}  {1,6} -> {2,6}" -f ($base + $i), $va, $vb); $shown++ }
            }
        }
        $tot = [Math]::Floor([Math]::Min($arrP.Length, $arrQ.Length) / 2)
        W ("  窗口 0x{0:X4}: 变化 {1}/{2} 个 16 位单元" -f $base, $cells, $tot)
    }
}
W ""
W "done"
