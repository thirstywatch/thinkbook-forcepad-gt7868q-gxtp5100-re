# probe-haptic.ps1 —— 触控板触觉能力探测 + 分级支持建议
#
# 用法：
#   .\probe-haptic.ps1                 # 探测所有 HID 接口，只报告"触控板类"
#   .\probe-haptic.ps1 -Filter gxtp    # 只探测名字含 gxtp 的接口
#   .\probe-haptic.ps1 -All            # 连非触控板接口也打印
#
# 安全：纯用户态只读（SetupAPI 枚举 + access=0 句柄 + HidP_Get*Caps）。不发报文、不写设备。
param([string]$Filter = "", [switch]$All)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Add-Type -Path (Join-Path $here 'HapticCap.cs') -ErrorAction Stop

$cols = [HapticCap]::Probe($Filter)

# —— 只保留"触控板类"：有 Haptics page / 是 Digitizer 集合 / 有 TipPressure ——
function Is-TouchpadLike($c) {
    if ($c.HasHapticsPage) { return $true }
    if ($c.UsagePage -eq 0x000D) { return $true }
    if ($null -ne $c.PressureField) { return $true }
    if ($c.Fields | Where-Object { $_.Page -eq 0x000D }) { return $true }
    return $false
}

$tp = @($cols | Where-Object { Is-TouchpadLike $_ })
if ($All) { $tp = $cols }

Write-Host ""
Write-Host "======================================================================"
Write-Host " 触控板触觉能力探测（纯用户态只读 · 零注入）"
Write-Host " 判据来源：Linux 6.18 drivers/hid/hid-haptic.c（能力驱动，无 ID 白名单）"
Write-Host "           + 微软 Input Device Haptics Implementation Guide"
Write-Host "======================================================================"
Write-Host ("枚举 {0} 个 HID 接口，其中触控板类 {1} 个" -f $cols.Count, $tp.Count)

$sumA = 0; $sumB = 0; $sumC = 0
foreach ($c in $tp) {
    Write-Host ""
    Write-Host "----------------------------------------------------------------------"
    Write-Host ("接口   : {0}" -f $c.Tag)
    Write-Host ("句柄   : {0}" -f $c.OpenNote)
    if ($c.Fields.Count -eq 0) { Write-Host "判定   : (读不到 caps，跳过)"; continue }
    Write-Host ("Caps   : UsagePage=0x{0:X4} Usage=0x{1:X4}  In={2} Out={3} Feat={4}  LinkColl={5}" -f `
        $c.UsagePage, $c.Usage, $c.InLen, $c.OutLen, $c.FeatLen, $c.LinkColl)
    Write-Host ""
    Write-Host ("★ 判定 : {0}" -f $c.LevelText)
    Write-Host ""
    Write-Host "判据逐条（Linux hid-haptic.c：四条核心齐全才算 A）"
    Write-Host ("  [1] 0x0E/0x20 Auto Trigger           : {0}" -f $(if($c.HasAutoTrigger){'✅ 有'}else{'❌ 无'}))
    Write-Host ("  [2] 0x0E/0x21 Manual Trigger(OUTPUT) : {0}   ← ★ 决定性" -f $(if($c.HasManualTriggerOut){'✅ 有'}else{'❌ 无'}))
    Write-Host ("  [3] 0x0E/0x10 Waveform List          : {0}" -f $(if($c.HasWaveformList){'✅ 有'}else{'❌ 无'}))
    Write-Host ("  [4] 0x0E/0x11 Duration List          : {0}" -f $(if($c.HasDurationList){'✅ 有'}else{'❌ 无'}))
    $u = [HapticCap]::UnitText($c.PressureField)
    $mass = if ($c.PressureField) { ($c.PressureField.Units -shr 8) -band 0xF } else { 0 }
    Write-Host ("  [5] TipPressure 单位                 : {0}" -f $u)
    Write-Host ("      ⇒ 上游要 克/牛顿  {0}" -f $(if($mass -ne 0){'✅ 有质量单位'}else{'❌ 无物理单位 ⇒ 不满足'}))
    Write-Host ""
    Write-Host "旋钮位置（★ 分水岭：同一个 0x0E/0x23，在 OUTPUT=有扳机 / 在 FEATURE=只有旋钮）"
    Write-Host ("  0x0E page 出现                       : {0}" -f $(if($c.HasHapticsPage){'✅'}else{'❌'}))
    Write-Host ("  0x0E/0x23 Intensity 存在             : {0}" -f $(if($c.HasIntensity){'✅'}else{'❌'}))
    Write-Host ("      · 在 OUTPUT 报表 ⇒ 有扳机形态     : {0}" -f $(if($c.IntensityInOutput){'✅'}else{'❌'}))
    Write-Host ("      · 在 FEATURE 报表 ⇒ 只有旋钮       : {0}" -f $(if($c.IntensityInFeature){'✅'}else{'❌'}))
    Write-Host ("  0x0D/0xB0 Button Press Threshold     : {0}" -f $(if($c.HasButtonPressThreshold){'✅'}else{'❌'}))

    $rel = @($c.Fields | Where-Object { $_.Page -eq 0x000E -or ($_.Page -eq 0x000D -and ($_.UsageMin -eq 0xB0 -or $_.UsageMin -eq 0x0030)) })
    if ($rel.Count) {
        Write-Host ""
        Write-Host "触觉/压力相关字段明细"
        foreach ($f in $rel) {
            Write-Host ("  {0,-7} RID={1,-3} {2,-18} bit={3,-3} cnt={4,-3} {5}..{6}" -f `
                $f.ReportType, $f.Rid, $f.Usage, $f.BitSize, $f.ReportCount, $f.LMin, $f.LMax)
        }
    }
    switch ($c.Level) { 'A_HAS_TRIGGER' { $sumA++ } 'B_PARTIAL' { $sumB++ } default { $sumC++ } }
}

# ==================== 主机侧 API 可用性 ====================
Write-Host ""
Write-Host "======================================================================"
Write-Host " 主机侧 API 可用性"
Write-Host "======================================================================"
Write-Host ("PowerShell: {0}  ({1})" -f $PSVersionTable.PSVersion, $PSVersionTable.PSEdition)

$apiOk = $false
try {
    $t = [Windows.Devices.Haptics.InputHapticsManager, Windows.Devices.Haptics, ContentType = WindowsRuntime]
    Write-Host "  Type  Windows.Devices.Haptics.InputHapticsManager : ✅ 可加载"
    try {
        $m = [Windows.Devices.Haptics.InputHapticsManager, Windows.Devices.Haptics, ContentType = WindowsRuntime]::IsSupported()
        Write-Host ("  IsSupported()                                     : {0}" -f $m)
        $apiOk = [bool]$m
    } catch { Write-Host ("  IsSupported() 调用失败: {0}" -f $_.Exception.Message) }
} catch {
    Write-Host "  Type  Windows.Devices.Haptics.InputHapticsManager : ❌ 不可用"
    Write-Host ("        （{0}）" -f $_.Exception.Message)
    Write-Host "        ⇒ 需要 Windows 11 SDK 10.0.28000.1721+（2026-03）运行时；本机没有则该 API 不存在"
}

# ==================== 分级支持建议 ====================
Write-Host ""
Write-Host "======================================================================"
Write-Host " 分级支持建议（可发布形态）"
Write-Host "======================================================================"
Write-Host ("汇总：A(有扳机)={0}   B(只有旋钮)={1}   C(无触觉接口)={2}" -f $sumA, $sumB, $sumC)
Write-Host ""
if ($sumA -gt 0) {
    Write-Host "  ★ 级别 A 命中：本机存在「主机可主动触发」的触觉接口"
    Write-Host "      ⇒ 走 Windows.Devices.Haptics.InputHapticsManager"
    Write-Host "        （TrySendHapticWaveform / TrySendHapticWaveformForPlayCount / TryStopFeedback）"
    Write-Host "      ⇒ 任意时机、任意波形、可连续 —— 「滑动跟随震动」可实现"
    Write-Host ""
}
if ($sumB -gt 0) {
    Write-Host "  级别 B 命中：只有「旋钮」没有「扳机」"
    Write-Host "      ⇒ 主机只能改偏好值（强度 / 力度阈值），不能决定何时震"
    Write-Host "      ⇒ 可实现：强度调节（对用户仍有价值）"
    Write-Host "      ⇒ 不能实现：按我们的时机触发震动（这是描述符级限制，非驱动/API 层）"
    Write-Host ""
}
if ($sumA -eq 0 -and $sumB -eq 0) {
    Write-Host "  级别 C：未发现任何 0x0E（Haptics）usage"
    Write-Host "      ⇒ 该设备的触觉完全在设备固件内闭环，主机侧无接口"
    Write-Host ""
}
Write-Host "  判据速查（拿去测任何一台机器）"
Write-Host "    · 0x0E/0x23 出现在 OUTPUT 报表（与 0x0E/0x21 同报表） ⇒ 有扳机"
Write-Host "    · 0x0E/0x23 只出现在独立 FEATURE 报表               ⇒ 只有旋钮"
Write-Host "    · 完全没有 0x0E page                                ⇒ 无接口"
Write-Host ""
Write-Host "注意：HidP_GetValueCaps 读的是 hidclass 已解析的 preparsed data，"
Write-Host "      因此本探测在设备被 PTP 驱动独占时同样可用（access=0 句柄）。"
Write-Host ""
