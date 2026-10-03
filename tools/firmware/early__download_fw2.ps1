$ProgressPreference = 'SilentlyContinue'
$env:PYTHONIOENCODING = 'utf-8'
$dest = '<WORKSPACE>'
if (-not (Test-Path $dest)) { New-Item -ItemType Directory -Path $dest | Out-Null }

# 目标 firmware GUID（Goodix - Firmware 三个条目，均 originalSize=135386 = 0.0.2.8）
# 以及另外两个 firmware: 0.0.0.9 (125145) / 0.0.0.2 (117579) 的 GUID 需要从搜索页映射
# 先打印搜索页中各 GUID 及其 originalSize，用于映射
$html = Get-Content '<WORKSPACE>' -Raw -Encoding utf8
# 匹配 <span ... id="<GUID>_originalSize">NUM</span>
$re = [regex]::new('<span[^>]*id="([0-9a-fA-F-]{36})_originalSize"[^>]*>(\d+)</span>')
$m = $re.Matches($html)
$map = @{}
foreach ($x in $m) { $map[$x.Groups[1].Value] = $x.Groups[2].Value }
"MAP count: $($map.Count)" | Out-File -FilePath "$dest/_map.txt" -Encoding utf8
foreach ($k in $map.Keys) { "  $($map[$k]) -> $k" | Out-File -Append -FilePath "$dest/_map.txt" -Encoding utf8 }

function Get-CabLinks($guid, $session) {
    $url = "https://www.catalog.update.microsoft.com/DownloadDialog.aspx?updateIDs=$guid&updateIDs=$guid&uid=$guid"
    # GET 拿 viewstate
    $r1 = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 40 -WebSession $session
    $h1 = $r1.Content
    $vs = ([regex]::new('<input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="([^"]*)"')).Match($h1).Groups[1].Value
    $ev = ([regex]::new('<input type="hidden" name="__EVENTVALIDATION" id="__EVENTVALIDATION" value="([^"]*)"')).Match($h1).Groups[1].Value
    $vsg = ([regex]::new('<input type="hidden" name="__VIEWSTATEGENERATOR" id="__VIEWSTATEGENERATOR" value="([^"]*)"')).Match($h1).Groups[1].Value
    $body = "__VIEWSTATE=$([uri]::EscapeDataString($vs))&__VIEWSTATEGENERATOR=$([uri]::EscapeDataString($vsg))&__EVENTVALIDATION=$([uri]::EscapeDataString($ev))&updateIDs=$guid&updateIDs=$guid&uid=$guid"
    $r2 = Invoke-WebRequest -Uri $url -Method Post -ContentType 'application/x-www-form-urlencoded' -Body $body -TimeoutSec 40 -WebSession $session
    $h2 = $r2.Content
    $links = [regex]::Matches($h2, 'https?://download\.windowsupdate\.com/[^"''>\s]+')
    $out = @()
    foreach ($l in $links) { if ($out -notcontains $l.Value) { $out += $l.Value } }
    return $out
}

# 建立会话
$r0 = Invoke-WebRequest -Uri 'https://www.catalog.update.microsoft.com/Search.aspx?q=Goodix+Firmware' -UseBasicParsing -TimeoutSec 40 -SessionVariable s

foreach ($guid in $map.Keys) {
    try {
        $links = Get-CabLinks $guid $s
        "GUID $guid (size $($map[$guid])) -> cabs: $($links.Count)" | Out-File -Append -FilePath "$dest/_log2.txt" -Encoding utf8
        foreach ($cf in $links) {
            $fn = [System.IO.Path]::GetFileName($cf.Split('?')[0])
            try {
                Invoke-WebRequest -Uri $cf -OutFile "$dest/$fn" -TimeoutSec 180
                "  OK $fn" | Out-File -Append -FilePath "$dest/_log2.txt" -Encoding utf8
            } catch {
                "  ERR $cf : $($_.Exception.Message)" | Out-File -Append -FilePath "$dest/_log2.txt" -Encoding utf8
            }
        }
    } catch {
        "GUID $guid ERR: $($_.Exception.Message)" | Out-File -Append -FilePath "$dest/_log2.txt" -Encoding utf8
    }
}
"DONE" | Out-File -Append -FilePath "$dest/_log2.txt" -Encoding utf8
