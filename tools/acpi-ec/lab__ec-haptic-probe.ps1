# ec-haptic-probe.ps1 -- EC RAM 按压差分：判定"EC 是否参与震动"
#
# ★ 为什么做这个（详见 touchpad-lab\2026-10-02-EC这条线-从蓝莓截图到可执行下一步.md）：
#   barryblueice（09/13）：「thinkbook 大概率是ec」/「surface 振动是由 ec 控制的」
#   而§19.25.4 的淘汰法只列了「模组内三个候选」，EC 在主板上 ⇒ 被挡在门外。
#   ⇒ 本脚本用最便宜的办法定案：**按压时 EC RAM 有没有变化**。
#
# ★ 原理：
#   EC RAM 只有 256 B。任何"只在按压时变、且变化幅度超过噪声底"的偏移，
#   都是 EC 参与该物理动作的直接证据。
#
# ★ 安全约束：
#   - 只用 RD_EC 握手读 EC RAM，**不写 EC RAM、不改任何寄存器**
#   - 不运行任何刷写程序，不碰 NJME*.exe
#   - 需要管理员权限（PawnIO 是签名驱动）
#
# ★ 用法（必须管理员）：
#     powershell -ExecutionPolicy Bypass -File ec-haptic-probe.ps1
#   脚本会逐相位提示你要做什么，采完后自动给出判据 A/B/C 判定。

param(
    [int]$Rounds      = 6,    # 每个相位读几轮
    [int]$GapMs       = 120,  # 同相位内的轮间间隔
    [int]$SettleMs    = 900   # 切换相位前的稳定等待
)

$outFile = Join-Path $PSScriptRoot ("ec-haptic-{0}.txt" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))

# ★★ 先把文件建出来，再做任何其他事。
#   否则一旦中途出错，连"跑到哪了"都看不到（2026-10-02 实测：失败时零输出）
try {
    "EC 差分探针 启动于 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" |
        Set-Content -LiteralPath $outFile -Encoding UTF8
} catch {
    Write-Host "!! 无法写入 $outFile -- 检查目录权限" -ForegroundColor Red
    exit 9
}

$ErrorActionPreference = 'Stop'
$log = New-Object System.Collections.Generic.List[string]
function L([string]$s) {
    Write-Host $s
    $log.Add($s)
    # 边跑边落盘：崩了/被 Ctrl-C /窗口被关，已采到的数据都还在
    try { $log -join "`r`n" | Out-File -LiteralPath $outFile -Append -Encoding UTF8 } catch { }
}

# ★ trap 里不调用 L()（它依赖 $log，且此时 ErrorActionPreference 可能是 Stop）
#   用最朴素的写法落盘，保证一定写得到。
trap {
    try { $log -join "`r`n" | Out-File -LiteralPath $outFile -Append -Encoding UTF8 } catch { }
    try { "`r`n!!! 异常终止: $($_.Exception.Message)" | Out-File -LiteralPath $outFile -Append -Encoding UTF8 } catch { }
    try { "!!! 行号: $($_.InvocationInfo.ScriptLineNumber)" | Out-File -LiteralPath $outFile -Append -Encoding UTF8 } catch { }
    Write-Host ""
    Write-Host "!! 异常终止，进度已保存到: $outFile" -ForegroundColor Red
    exit 1
}

# ---------------- 权限 ----------------
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$adm = (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
L ("运行: {0}  用户: {1}  管理员: {2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $id.Name, $adm)
if (-not $adm) {
    L ""
    L "!! 需要管理员权限。PawnIO 是签名驱动，读 EC 端口 0x62/0x66 必须要管理员。"
    L ""
    L "   ★ 最省事的做法：双击同目录下的  run-ec-probe.bat"
    L "     它会自动弹 UAC，点『是』即可。"
    L ""
    L "   ★ 或者在管理员 PowerShell 里跑："
    L "     cd '$PSScriptRoot'"
    L "     powershell -ExecutionPolicy Bypass -File .\ec-haptic-probe.ps1"
    Write-Host ""
    Write-Host "诊断已保存: $outFile" -ForegroundColor Yellow
    exit 1
}

# ---------------- 找模块 ----------------
function Find-Module {
    $c = @()
    if ($env:PAWNIO_MODULE) { $c += $env:PAWNIO_MODULE }
    $c += (Join-Path $PSScriptRoot 'LpcACPIEC.bin')
    $c += (Join-Path $PSScriptRoot 'pawnio\mod011\LpcACPIEC.bin')
    # ★ 上溯一级：本项目里模块可能放在 touchpad-lab\ 根目录（实测 2026-10-02）
    $c += (Join-Path (Split-Path -Parent $PSScriptRoot) 'LpcACPIEC.bin')
    $c += (Get-ChildItem -Path (Split-Path -Parent $PSScriptRoot) -Recurse -Filter 'LpcACPIEC.bin' `
                     -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
    $c += (Get-ChildItem -Path $PSScriptRoot -Recurse -Filter 'LpcACPIEC.bin' `
                     -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
    $c += 'C:\Program Files\PawnIO\modules\LpcACPIEC.bin'
    foreach ($x in $c) { if ($x -and (Test-Path -LiteralPath $x)) { return $x } }
    return $null
}
$modPath = Find-Module
if (-not $modPath) {
    L "!! 找不到 LpcACPIEC.bin"
    L "   已尝试: 脚本同目录 / pawnio\mod011\ / 上一级 / C://Program Files\PawnIO\modules\"
    L "   解法: 把 LpcACPIEC.bin 放到脚本同目录，或设环境变量 PAWNIO_MODULE 指向它"
    exit 2
}
if (-not (Test-Path 'C:\Program Files\PawnIO\PawnIOLib.dll')) {
    L "!! 找不到 PawnIOLib.dll（应位于 C:\Program Files\PawnIO\）"
    L "   若未装 PawnIO: 先跑 C:\Program Files\PawnIO\PawnIOUtil.exe install-driver"
    exit 2
}

# ---------------- P/Invoke（照搬 ec_probe_pawnio.ps1，已实测可用）----------------
Add-Type -Namespace PW -Name Io2 -MemberDefinition @'
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
$hr = [PW.Io2]::pawnio_open([ref]$h)
if ($hr -ne 0) {
    L ("!! pawnio_open 失败 0x{0:X8}" -f $hr)
    L "   0x80070005 = 需要管理员；0x8007000E = PawnIO 驱动未加载（跑 PawnIOUtil.exe install-driver）"
    exit 3
}
$blob = [IO.File]::ReadAllBytes($modPath)
$hr = [PW.Io2]::pawnio_load($h, $blob, [UIntPtr]::new([uint64]$blob.Length))
if ($hr -ne 0) {
    L ("!! pawnio_load 失败 0x{0:X8}" -f $hr)
    L "   模块路径: $modPath"
    L "   可能是不支持本机 EC 布局，或模块版本不对"
    [void][PW.Io2]::pawnio_close($h)
    exit 4
}

function PioRead([int]$port) {
    $in = [uint64[]]@([uint64]$port); $out = [uint64[]]@(0); $rs = [UIntPtr]::Zero
    $r = [PW.Io2]::pawnio_execute($h, 'ioctl_pio_read', $in, [UIntPtr]::new(1),
                                  $out, [UIntPtr]::new(1), [ref]$rs)
    if ($r -ne 0) { throw ("pio_read 0x{0:X} HR=0x{1:X8}" -f $port, $r) }
    return [int]($out[0] -band 0xFF)
}
function PioWrite([int]$port, [int]$val) {
    $in = [uint64[]]@([uint64]$port, [uint64]$val); $out = [uint64[]]@(0); $rs = [UIntPtr]::Zero
    $r = [PW.Io2]::pawnio_execute($h, 'ioctl_pio_write', $in, [UIntPtr]::new(2),
                                  $out, [UIntPtr]::new(0), [ref]$rs)
    if ($r -ne 0) { throw ("pio_write 0x{0:X} HR=0x{1:X8}" -f $port, $r) }
}

$EC_DATA = 0x62; $EC_CMD = 0x66; $OBF = 0x01; $IBF = 0x02; $RD_EC = 0x80
function WaitFlag([int]$mask, [bool]$set, [int]$tries = 200) {
    for ($i = 0; $i -lt $tries; $i++) {
        if (((((PioRead $EC_CMD) -band $mask)) -ne 0) -eq $set) { return $true }
    }
    return $false
}
function EcReadByte([int]$offset) {
    for ($i = 0; $i -lt 16; $i++) {
        if (((PioRead $EC_CMD) -band $OBF) -eq 0) { break }
        [void](PioRead $EC_DATA)
    }
    if (-not (WaitFlag $IBF $false)) { return -1 }
    PioWrite $EC_CMD $RD_EC
    if (-not (WaitFlag $IBF $false)) { return -1 }
    PioWrite $EC_DATA $offset
    if (-not (WaitFlag $OBF $true)) { return -1 }
    return (PioRead $EC_DATA)
}
function Read-ECRam {
    $ram = New-Object int[] 256
    for ($o = 0; $o -lt 256; $o++) { $ram[$o] = EcReadByte $o }
    return ,$ram
}

# ---------------- 采集 ----------------
L ("=" * 76)
L " EC RAM 按压差分探针   $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
L ("=" * 76)
L "只读 EC RAM（RD_EC），不写任何寄存器。"
L "每相位 $Rounds 轮，轮间 ${GapMs}ms。"
L ""

$phases = @(
    @{ n = 'P1_IDLE';  a = '★ 不要碰触控板，保持完全静止' },
    @{ n = 'P2_TOUCH'; a = '★ 用一根手指【轻轻放在】触控板上（不要按下去）' },
    @{ n = 'P3_LIGHT'; a = '★ 轻点（力度小于触发点击的阈值）' },
    @{ n = 'P4_HARD';  a = '★ 重压（力度超过点击阈值，会触发震动）' },
    @{ n = 'P5_HOLD';  a = '★ 保持重压不放（按住 3 秒）' },
    @{ n = 'P6_IDLE2'; a = '★ 松开，回到完全静止' }
)

$data = @{}
foreach ($p in $phases) {
    L ("-" * 76)
    L ("【{0}】{1}" -f $p.n, $p.a)
    $snaps = @()
    for ($i = 0; $i -lt $Rounds; $i++) {
        if ($i -eq 0) {
            Write-Host ""
            Write-Host ("  >>> {0}" -f $p.a) -ForegroundColor Yellow
            Write-Host ("      {0} 秒后开始采集第 1 轮..." -f ([int]($SettleMs/1000))) -ForegroundColor Yellow
            Start-Sleep -Milliseconds $SettleMs
        }
        $snaps += ,(Read-ECRam)
        Write-Host ("      轮 {0}/{1}" -f ($i+1), $Rounds) -NoNewline
        Write-Host ("`r" + (' ' * 30) + "`r") -NoNewline
        Start-Sleep -Milliseconds $GapMs
    }
    $data[$p.n] = $snaps
    Write-Host ("  -> {0} 完成" -f $p.n)
}

[void][PW.Io2]::pawnio_close($h)

# ---------------- 分析 ----------------
L ""
L ("=" * 76)
L " 分析"
L ("=" * 76)

function Consensus($snaps) {
    # 逐偏移多数表决。
    # ★ 性能：朴素写法是 O(偏移 × 轮数²)，在 PowerShell 里会慢到分钟级。
    #   这里改成"每个轮的值各计一次票"的单遍写法，O(偏移 × 轮数)。
    $c = New-Object int[] 256
    $n = $snaps.Count
    for ($k = 0; $k -lt 256; $k++) {
        $tally = @{}
        for ($i = 0; $i -lt $n; $i++) {
            $v = $snaps[$i][$k]
            if ($tally.ContainsKey($v)) { $tally[$v]++ } else { $tally[$v] = 1 }
        }
        $best = $snaps[0][$k]; $bc = 0
        foreach ($kv in $tally.GetEnumerator()) {
            if ($kv.Value -gt $bc) { $bc = $kv.Value; $best = $kv.Key }
        }
        $c[$k] = $best
    }
    return ,$c
}

$cons = @{}
foreach ($k in $data.Keys) { $cons[$k] = Consensus $data[$k] }

# 噪声底 = 静止相位内各偏移的轮间极差
$noise = New-Object int[] 256
for ($k = 0; $k -lt 256; $k++) {
    $mn = 999; $mx = -999
    for ($i = 0; $i -lt $data['P1_IDLE'].Count; $i++) {
        $v = $data['P1_IDLE'][$i][$k]
        if ($v -lt 0) { continue }
        if ($v -lt $mn) { $mn = $v }; if ($v -gt $mx) { $mx = $v }
    }
    $noise[$k] = if ($mn -gt $mx) { 0 } else { $mx - $mn }
}
$noiseMax = ($noise | Measure-Object -Maximum).Maximum
L (" 噪声底（静止相位内的轮间极差最大值）= {0}" -f $noiseMax)
L ""

$base = $cons['P1_IDLE']
$report = @{}
foreach ($ph in @('P2_TOUCH','P3_LIGHT','P4_HARD','P5_HOLD','P6_IDLE2')) {
    $c = $cons[$ph]
    $d = @()
    for ($k = 0; $k -lt 256; $k++) {
        if ($base[$k] -lt 0 -or $c[$k] -lt 0) { continue }
        $delta = [Math]::Abs($c[$k] - $base[$k])
        if ($delta -gt $noiseMax) {
            # 同时要求该偏移在本相位所有轮次里都稳定（否则是噪声）
            $vals = $data[$ph] | ForEach-Object { $_[$k] }
            $same = ($vals | Group-Object | Sort-Object Count -Descending | Select-Object -First 1).Count
            $d += [pscustomobject]@{
                Off = $k; Idle = $base[$k]; Val = $c[$k]; Delta = $delta; Stable = ($same -eq $vals.Count)
            }
        }
    }
    $report[$ph] = $d
    L ("【{0}】变化 > 噪声底的偏移：{1} 个（其中全轮次稳定：{2} 个）" -f $ph, $d.Count, ($d | Where-Object { $_.Stable }).Count)
    foreach ($x in ($d | Sort-Object Delta -Descending | Select-Object -First 12)) {
        L ("    off 0x{0:X2}  idle=0x{1:X2} now=0x{2:X2}  delta={3,-4} {4}" -f `
           $x.Off, $x.Idle, $x.Val, $x.Delta, $(if ($x.Stable) { '[稳定]' } else { '[不稳定]' }))
    }
    L ""
}

# ---------------- 判定 ----------------
L ("=" * 76)
L (" 判定")
L ("=" * 76)
$stableAll = @{}
foreach ($ph in $report.Keys) {
    $stableAll[$ph] = @($report[$ph] | Where-Object { $_.Stable } | ForEach-Object { $_.Off })
}
$union = @()
foreach ($ph in $stableAll.Keys) { $union += $stableAll[$ph] }
$union = $union | Sort-Object -Unique

if ($union.Count -eq 0) {
    L " ⚠ 没有任何偏移在按压时【全轮次稳定】地变化。"
    L ""
    L " ⇒ EC RAM 未见与按压/震动相关的稳定活动。"
    L " ⇒ 不能据此断定 EC 不参与。可能是："
    L "      (a) EC 不经 RAM 走，而是直接驱动硬件（无 RAM 痕迹）"
    L "      (b) 采样太稀/动作太弱 -> 建议 Rounds=15 GapMs=40，P5 改成'按住 5 秒'"
    L "      (c) 读失败偏移太多 -> 看上面各相位的 delta 是否有值"
} else {
    L (" ★ 找到 {0} 个【全轮次稳定】的变化偏移：{1}" -f `
       $union.Count, (($union | ForEach-Object { '0x{0:X2}' -f $_ }) -join ' '))
    L ""
    L " 逐偏移判据判定："
    L (" {0,-6} {1,-8} {2,-8} {3,-8} {4,-8} {5}" -f 'off','TOUCH','LIGHT','HARD','HOLD','判定')
    foreach ($o in $union) {
        $marks = @{}
        foreach ($ph in @('P2_TOUCH','P3_LIGHT','P4_HARD','P5_HOLD')) {
            $marks[$ph] = if ($stableAll[$ph] -contains $o) { 'YES' } else { '-' }
        }
        # 分级
        $lvl = 'C弱(仅接触/轻触)'
        if ($marks['P4_HARD'] -eq 'YES' -and $marks['P5_HOLD'] -eq 'YES') { $lvl = 'A强(重压+保持都变)' }
        elseif ($marks['P4_HARD'] -eq 'YES') { $lvl = 'B中(仅重压变)' }
        L (" 0x{0:X2}  {1,-8} {2,-8} {3,-8} {4,-8} {5}" -f `
           $o, $marks['P2_TOUCH'], $marks['P3_LIGHT'], $marks['P4_HARD'], $marks['P5_HOLD'], $lvl)
    }
    L ""
    L " 判据含义："
    L "   A强 = 重压和保持都变 => EC 直接参与震动链路，EC 线立起来"
    L "   B中 = 只有重压变=> 可能是压力阈值判断或震动状态位"
    L "   C弱 = 只有接触/轻触变 => 更可能是接触抖动，不足以定案"
    L ""
    L " ★ 下一步：把上面 A/B 级的偏移列表发我，我据此去 NJME*.exe 的 EC 固件里"
    L "   反查这些偏移的读写点（固件里必然有对这些地址的访问）。"
}

L ""
L ("结果已保存: $outFile")
$log -join "`r`n" | Out-File -LiteralPath $outFile -Append -Encoding UTF8
$latest = Join-Path $PSScriptRoot 'ec-haptic-latest.txt'
Copy-Item $outFile $latest -Force
Write-Host ("（同时保存了一份: $latest）") -ForegroundColor Green