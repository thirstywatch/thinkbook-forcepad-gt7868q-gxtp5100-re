$ProgressPreference = 'SilentlyContinue'
$env:PYTHONIOENCODING = 'utf-8'
$dest = '<WORKSPACE>'
if (-not (Test-Path $dest)) { New-Item -ItemType Directory -Path $dest | Out-Null }

# 仅固件条目（Firmware 分类）的 GUID
$guids = @(
  'e45c248f-3bc6-4426-948a-741a0cec0480',  # 0.0.2.8 / 135386
  '845fad87-2868-43fc-a5f3-0dd932714fab',  # 0.0.2.8 / 135386
  '0477a61f-d855-4109-af15-2075f4a4bd98',  # 0.0.2.8 / 135386
  'ab9e8550-e8e1-466b-8873-a2d1b496b407',  # 0.0.0.9 / 125145
  '9023a17b-ea9b-4948-b834-c4455ce93e09',  # 0.0.0.2 / 117579
  'bb167078-ef6a-4272-9ff2-f18e012fa9af',  # 0.0.0.2 / 117579
  'fe998415-3a41-4098-959e-ab91346d5491',  # 0.0.0.2 / 117579
  '1bb7f286-9669-4ce1-ab70-bfa9d31c6706',  # 0.0.0.2 / 117579
  'f78d1e39-b66f-476b-ac66-10537085e4ea',  # 0.0.0.2 / 117579
  'f1be69ee-5349-48b0-ac6c-b6dc735c635d',  # 0.0.0.2 / 117579
  '1eaaa74e-ed3e-4da2-915d-b6b900541c92',  # 0.0.0.2 / 117579
  '8fa80b6a-834e-4699-8737-6f3965b6d0c8'   # 0.0.0.2 / 117579
)

function Get-CabLinks($guid, $session) {
    $url = "https://www.catalog.update.microsoft.com/DownloadDialog.aspx?updateIDs=$guid&updateIDs=$guid&uid=$guid"
    $r1 = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 40 -WebSession $session
    $h1 = $r1.Content
    $vs = ([regex]::new('<input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="([^"]*)"')).Match($h1).Groups[1].Value
    $ev = ([regex]::new('<input type="hidden" name="__EVENTVALIDATION" id="__EVENTVALIDATION" value="([^"]*)"')).Match($h1).Groups[1].Value
    $vsg = ([regex]::new('<input type="hidden" name="__VIEWSTATEGENERATOR" id="__VIEWSTATEGENERATOR" value="([^"]*)"')).Match($h1).Groups[1].Value
    $body = "__VIEWSTATE=$([uri]::EscapeDataString($vs))&__VIEWSTATEGENERATOR=$([uri]::EscapeDataString($vsg))&__EVENTVALIDATION=$([uri]::EscapeDataString($ev))&updateIDs=$guid&updateIDs=$guid&uid=$guid&__EVENTTARGET=&__EVENTARGUMENT="
    $r2 = Invoke-WebRequest -Uri $url -Method Post -ContentType 'application/x-www-form-urlencoded' -Body $body -TimeoutSec 40 -WebSession $session
    $h2 = $r2.Content
    $links = [regex]::Matches($h2, 'https?://download\.windowsupdate\.com/[^"''>\s]+')
    $out = @()
    foreach ($l in $links) { if ($out -notcontains $l.Value) { $out += $l.Value } }
    return $out
}

$r0 = Invoke-WebRequest -Uri 'https://www.catalog.update.microsoft.com/Search.aspx?q=Goodix+Firmware' -UseBasicParsing -TimeoutSec 40 -SessionVariable s
$i = 0
foreach ($guid in $guids) {
    $i++
    try {
        $links = Get-CabLinks $guid $s
        "GUID $guid -> cabs: $($links.Count)" | Out-File -Append -FilePath "$dest/_log3.txt" -Encoding utf8
        foreach ($cf in $links) {
            $fn = [System.IO.Path]::GetFileName($cf.Split('?')[0])
            try {
                Invoke-WebRequest -Uri $cf -OutFile "$dest/$fn" -TimeoutSec 180
                "  OK $fn" | Out-File -Append -FilePath "$dest/_log3.txt" -Encoding utf8
            } catch {
                "  ERR $cf : $($_.Exception.Message)" | Out-File -Append -FilePath "$dest/_log3.txt" -Encoding utf8
            }
        }
    } catch {
        "GUID $guid ERR: $($_.Exception.Message)" | Out-File -Append -FilePath "$dest/_log3.txt" -Encoding utf8
    }
}
"DONE total $i" | Out-File -Append -FilePath "$dest/_log3.txt" -Encoding utf8
