# ec_probe_pawnio.ps1 -- 用 PawnIO(已签名驱动)只读访问 ACPI EC RAM
# ----------------------------------------------------------------------
# 为什么用这个：RWE 的 SMBus 在你机器上不可用(连电池 0x0B 都读不到)，
# 而 PawnIO 是签名驱动，不进"易受攻击驱动"黑名单，能直接碰 EC 端口 0x62/0x66。
#
# ★ 全程只读。绝不写 EC。
#   唯一的"写"操作是 ACPI 规范的 RD_EC 握手本身(向命令口写命令字节、
#   向数据口写寄存器偏移)——这是读操作的必要步骤，不改变 EC 内容。
#
# 用法(必须先以管理员身份运行 PowerShell)：
#     powershell -ExecutionPolicy Bypass -File ec_probe_pawnio.ps1
#
# 需要：C:\Program Files\PawnIO\PawnIOLib.dll  +  LpcACPIEC.bin 模块

$ErrorActionPreference = 'Continue'
$outFile = Join-Path $PSScriptRoot 'ec_probe_result.txt'
$log = New-Object System.Collections.Generic.List[string]
function L([string]$s) { Write-Host $s; $log.Add($s) }

L "=================================================="
L " PawnIO EC 只读探测"
L " $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
L "=================================================="

# ---------- 权限 ----------
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$adm = (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
L ""
L "[0] user=$($id.Name)  admin=$adm"
if (-not $adm) {
    L "    [*] 不是管理员，正在请求提权(弹 UAC 请点『是』)..."
    $log -join "`r`n" | Set-Content -LiteralPath $outFile -Encoding UTF8
    try {
        Start-Process -FilePath 'powershell.exe' -Verb RunAs -Wait -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass',
            '-File', ('"{0}"' -f $PSCommandPath)
        )
    } catch {
        L "    [!] 提权失败: $($_.Exception.Message)"
    }
    $log -join "`r`n" | Set-Content -LiteralPath $outFile -Encoding UTF8
    exit 0
}

# ---------- 找模块 ----------
function Find-Module {
    $cands = @()
    if ($env:PAWNIO_MODULE) { $cands += $env:PAWNIO_MODULE }
    $cands += (Join-Path $PSScriptRoot 'LpcACPIEC.bin')
    $cands += (Get-ChildItem -Path $PSScriptRoot -Recurse -Filter 'LpcACPIEC.bin' -ErrorAction SilentlyContinue |
                 Select-Object -ExpandProperty FullName)
    $cands += 'C:\Program Files\PawnIO\modules\LpcACPIEC.bin'
    foreach ($c in $cands) { if ($c -and (Test-Path -LiteralPath $c)) { return $c } }
    return $null
}
$modPath = Find-Module
L ""
L "[1] 模块: " + $(if ($modPath) { $modPath } else { '未找到 LpcACPIEC.bin' })
if (-not $modPath) {
    L "    [!] 把 LpcACPIEC.bin 放到脚本同目录，或设环境变量 PAWNIO_MODULE 指向它。"
    $log -join "`r`n" | Set-Content -LiteralPath $outFile -Encoding UTF8
    exit 2
}

# ---------- P/Invoke ----------
Add-Type -Namespace PW -Name Io -MemberDefinition @'
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
$hr = [PW.Io]::pawnio_open([ref]$h)
if ($hr -ne 0) {
    L ("    [-] pawnio_open 失败 HRESULT=0x{0:X8}" -f $hr)
    L "        (0x80070005 = 需要管理员)"
    $log -join "`r`n" | Set-Content -LiteralPath $outFile -Encoding UTF8
    exit 3
}
L "    [+] pawnio_open OK"

$blob = [IO.File]::ReadAllBytes($modPath)
$hr = [PW.Io]::pawnio_load($h, $blob, [UIntPtr]::new([uint64]$blob.Length))
if ($hr -ne 0) {
    L ("    [-] pawnio_load 失败 HRESULT=0x{0:X8}" -f $hr)
    [void][PW.Io]::pawnio_close($h)
    $log -join "`r`n" | Set-Content -LiteralPath $outFile -Encoding UTF8
    exit 4
}
L "    [+] pawnio_load OK ($($blob.Length) bytes)"

function PioRead([int]$port) {
    $in  = [uint64[]]@([uint64]$port)
    $out = [uint64[]]@(0)
    $rs = [UIntPtr]::Zero
    $r = [PW.Io]::pawnio_execute($h, 'ioctl_pio_read', $in, [UIntPtr]::new(1),
                                  $out, [UIntPtr]::new(1), [ref]$rs)
    if ($r -ne 0) { throw ("ioctl_pio_read(0x{0:X}) HR=0x{1:X8}" -f $port, $r) }
    return [int]($out[0] -band 0xFF)
}
function PioWrite([int]$port, [int]$val) {
    $in  = [uint64[]]@([uint64]$port, [uint64]$val)
    $out = [uint64[]]@(0)
    $rs = [UIntPtr]::Zero
    $r = [PW.Io]::pawnio_execute($h, 'ioctl_pio_write', $in, [UIntPtr]::new(2),
                                  $out, [UIntPtr]::new(0), [ref]$rs)
    if ($r -ne 0) { throw ("ioctl_pio_write(0x{0:X}) HR=0x{1:X8}" -f $port, $r) }
}

# ---------- EC RD_EC 握手 ----------
$EC_DATA = 0x62
$EC_CMD  = 0x66
$OBF = 0x01
$IBF = 0x02
$RD_EC = 0x80

function WaitFlag([int]$mask, [bool]$set, [int]$tries = 200) {
    for ($i = 0; $i -lt $tries; $i++) {
        $st = PioRead $EC_CMD
        if (((($st -band $mask) -ne 0)) -eq $set) { return $true }
    }
    return $false
}

function EcReadByte([int]$offset) {
    # 清掉上一笔遗留的输出字节
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

# ---------- 读 EC RAM ----------
L ""
L "[2] 读 EC RAM(RD_EC，偏移 0x00..0xFF)"
$ram = @{}
$fail = 0
for ($o = 0; $o -le 0xFF; $o++) {
    $v = EcReadByte $o
    $ram[$o] = $v
    if ($v -lt 0) { $fail++ }
}
L ("    读完 256 字节，失败 $fail 个")

$nonff = ($ram.GetEnumerator() | Where-Object { $_.Value -ge 0 -and $_.Value -ne 0xFF }).Count
L ("    非 0xFF 的偏移数: $nonff / 256")

L ""
L "[3] EC RAM 全表"
for ($base = 0; $base -lt 0x100; $base += 16) {
    $hexs = @(); $asc = ''
    for ($i = 0; $i -lt 16; $i++) {
        $v = $ram[$base + $i]
        if ($v -lt 0) { $hexs += '--'; $asc += '.' }
        else { $hexs += ('{0:X2}' -f $v); $asc += $(if ($v -ge 32 -and $v -lt 127) { [char]$v } else { '.' }) }
    }
    L ("    {0:X2}: {1}  {2}" -f $base, ($hexs -join ' '), $asc)
}

L ""
L "[4] 我们关心的偏移(来自 DSDT OperationRegion 反编译)"
L "    LA3M  = SystemMemory 0xFE0B0F00, size 0xFF"
L "    MLR0  @ +0xBD    MLR1 @ +0xBE    MLR2 @ +0xBF    MLR3 @ +0xC0"
L "    注意：EC RAM 偏移与 SystemMemory 窗口偏移不一定相同，需交叉验证。"
foreach ($o in 0xBD, 0xBE, 0xBF, 0xC0, 0xD0, 0xD1, 0xDE) {
    $v = $ram[$o]
    L ("    EC[0x{0:X2}] = {1}" -f $o, $(if ($v -lt 0) { '读取失败' } else { '0x{0:X2}' -f $v }))
}

[void][PW.Io]::pawnio_close($h)
L ""
L "[5] 完成。把这个文件的内容发给我。"
$log -join "`r`n" | Set-Content -LiteralPath $outFile -Encoding UTF8
Write-Host ""
Write-Host "结果已保存: $outFile" -ForegroundColor Green
