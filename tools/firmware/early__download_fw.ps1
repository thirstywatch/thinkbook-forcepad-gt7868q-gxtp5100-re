$ProgressPreference = 'SilentlyContinue'
$env:PYTHONIOENCODING = 'utf-8'
$dest = '<WORKSPACE>'
if (-not (Test-Path $dest)) { New-Item -ItemType Directory -Path $dest | Out-Null }

# 从已保存的搜索页 HTML 中提取唯一 update GUID
$html = Get-Content '<WORKSPACE>' -Raw -Encoding utf8
$guids = @()
$matches = [regex]::Matches($html, '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')
foreach ($m in $matches) { if ($guids -notcontains $m.Value) { $guids += $m.Value } }
"UNIQUE_GUIDS: $($guids.Count)" | Out-File -Append -FilePath "$dest/_log.txt" -Encoding utf8

foreach ($g in $guids) {
    try {
        $dlg = "https://www.catalog.update.microsoft.com/DownloadDialog.aspx?updateIDs=$g&uid=$g"
        $r = Invoke-WebRequest -Uri $dlg -UseBasicParsing -TimeoutSec 40
        $dh = $r.Content
        $cabs = [regex]::Matches($dh, 'https://download\.windowsupdate\.com/[^"''>\s]+')
        "GUID $g -> cab links: $($cabs.Count)" | Out-File -Append -FilePath "$dest/_log.txt" -Encoding utf8
        foreach ($c in $cabs) {
            $cf = $c.Value
            $fn = [System.IO.Path]::GetFileName($cf.Split('?')[0])
            try {
                Invoke-WebRequest -Uri $cf -OutFile "$dest/$fn" -TimeoutSec 120
                "  downloaded $fn" | Out-File -Append -FilePath "$dest/_log.txt" -Encoding utf8
            } catch {
                "  ERR download $cf : $($_.Exception.Message)" | Out-File -Append -FilePath "$dest/_log.txt" -Encoding utf8
            }
        }
    } catch {
        "GUID $g ERR dialog: $($_.Exception.Message)" | Out-File -Append -FilePath "$dest/_log.txt" -Encoding utf8
    }
}
"DONE" | Out-File -Append -FilePath "$dest/_log.txt" -Encoding utf8
