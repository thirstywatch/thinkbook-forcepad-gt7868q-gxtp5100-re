# dump-all-caps.ps1 —— 打印触控板全部 HID 接口的【所有】value caps（不筛选）
# 配套 AllCaps.cs。纯只读（CreateFileW access=0 / share=3），不向设备写任何东西。

$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

Add-Type -Path (Join-Path $here 'AllCaps.cs') -ErrorAction Stop

$paths = [AllCaps]::Paths()
Write-Host ("枚举到 {0} 个 HID 接口" -f $paths.Count)
Write-Host ""

foreach ($p in $paths) {
    if ($p -notmatch 'gxtp5100') { continue }
    Write-Host ("=" * 78)
    Write-Host ("接口 : {0}" -f ($p -replace '.*hid#', '' -replace '#.*', ''))
    Write-Host ("路径 : {0}" -f $p)
    $brief = $null
    $txt = [AllCaps]::Dump($p, [ref]$brief)
    if ($txt) { Write-Host $txt } else { Write-Host ("  <失败: {0}>" -f $brief) }
}
Write-Host ("=" * 78)
Write-Host "完成（未向设备写入任何数据）"
