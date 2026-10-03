# col04-ext-probe.ps1 —— Col04 命令空间 · 安全探测编排器
#
# ★★★ 只能在【台面样机】上运行。真机禁止。★★★
#
# 用法：
#   .\col04-ext-probe.ps1 -Phase 0 -DryRun                 # 只看会做什么，不发任何帧
#   .\col04-ext-probe.ps1 -Phase 0 -IAmOnSampleUnit        # ★ L0：字节序定案实验（纯读为主）
#   .\col04-ext-probe.ps1 -Phase 1 -IAmOnSampleUnit        # L1：单发通道可用性判定
#   .\col04-ext-probe.ps1 -Phase 2 -IAmOnSampleUnit -ByteOrder H1   # L2：22 个已知 A1 值（只读）
#   .\col04-ext-probe.ps1 -Phase 3 -IAmOnSampleUnit -ByteOrder H1   # L3：16 个已知 A0 值（写）
#   .\col04-ext-probe.ps1 -Phase 4 -IAmOnSampleUnit -ByteOrder H1   # L4：A0-0x0B / A0-0x0D 定向
#
# ★ 边界来源：COL04-BOUNDARY.md（静态解出：0xA0 恰好 16 个值、0xA1 恰好 22 个值，边界外 = no-op）
#   ⇒ 因此本脚本**不再盲扫**，只发已知合法值。
#
# 字节序说明（COL04-BOUNDARY.md §4）：
#   固件比较值形如 0xNN00（低字节必须为 0）。而 VibLink.Send 把 sub 按 u16 小端放到 pkt[2]=lo / pkt[3]=hi。
#   ⇒ -ByteOrder H1 : 传 sub = op<<8  ⇒ pkt[2]=0x00, pkt[3]=op   （假设内部块是原样拷贝）
#   ⇒ -ByteOrder H2 : 传 sub = op     ⇒ pkt[2]=op,   pkt[3]=0x00 （假设链路层做了字节交换）
#   ★ 先用 Phase 0 定案，再据此选 H1/H2。
#
# 设计原则（对应 COL04-EXT-PROBE-PLAN.md §5）：
#   1. 强制显式声明"在样机上"，否则拒绝运行
#   2. 每一步固定四件事：前置体检 → 单发 → 读回 → 后置体检
#   3. 任何异常（体检失败 / err=122 / 读阻塞）立即中止
#   4. 单发、间隔 >=200ms、不并发
#   5. 每个 HID 动作都起【独立子进程】（沿用 VibLink 的"发/读分离"，一次阻塞不毒死整轮）
#   6. 全程结构化日志，含"是否震动"人工栏
param(
    [Parameter(Mandatory=$true)][ValidateSet("0","1","2","3","4")][string]$Phase,
    [switch]$DryRun,
    [switch]$IAmOnSampleUnit,
    [ValidateSet("H1","H2")][string]$ByteOrder = "H1",
    [int]$DwellMs = 400,
    [int]$StepDelayMs = 250,
    [int]$ListenTimeoutMs = 3000
)

try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$ErrorActionPreference = "Continue"

# ─────────────── 安全闸门 ───────────────
if (-not $DryRun -and -not $IAmOnSampleUnit) {
    Write-Host ""
    Write-Host "  x 拒绝执行" -ForegroundColor Red
    Write-Host "    本脚本会向 Col04 厂商通道发送【未经验证】的命令。" -ForegroundColor Red
    Write-Host "    在真机上运行可能导致触控板失效（本项目已发生过两次）。" -ForegroundColor Red
    Write-Host ""
    Write-Host "    确实在【台面样机】上 -> 加参数: -IAmOnSampleUnit" -ForegroundColor Yellow
    Write-Host "    只想先看会做什么    -> 加参数: -DryRun" -ForegroundColor Yellow
    Write-Host ""
    exit 9
}

$root   = Split-Path -Parent $MyInvocation.MyCommand.Path
$linker = Join-Path $root "vib-link.ps1"
if (-not (Test-Path $linker)) { Write-Host "x 找不到 vib-link.ps1（应在 poc/ 目录）" -ForegroundColor Red; exit 8 }

# ── 选择子进程解释器：★ 优先 pwsh7
#    原因：本项目所有 .ps1 / .cs 均为「无 BOM + 含中文」。PowerShell 5.1 在中文系统上
#    默认按 ANSI(GBK) 解码无 BOM 文件 ⇒ 中文注释/字符串乱码，甚至触发语法错误。
#    PowerShell 7 默认 UTF-8，可正确处理。故此处优先 pwsh，仅在缺失时回退 5.1。
$psExe = $null
$c1 = Get-Command pwsh -ErrorAction SilentlyContinue
if ($c1) { $psExe = $c1.Source }
if (-not $psExe) {
    $c2 = Get-Command powershell.exe -ErrorAction SilentlyContinue
    if ($c2) { $psExe = $c2.Source }
}
if (-not $psExe) { $psExe = "powershell.exe" }


$logDir = Join-Path $root "probe-logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir ("probe-L{0}-{1}.log" -f $Phase, (Get-Date -Format "yyyyMMdd-HHmmss"))

function Log([string]$m) {
    Write-Host $m
    Add-Content -Path $logFile -Value $m -Encoding UTF8
}

# ─────────────── 独立子进程调用 vib-link.ps1 ───────────────
function Call-VibLink {
    param([string[]]$A)
    $out = & $psExe -NoProfile -ExecutionPolicy Bypass -File $linker @A 2>&1
    return ($out | Out-String).Trim()
}

# ─────────────── 已知合法值（来自 COL04-BOUNDARY.md §2） ───────────────
# 0xA1：22 个 —— 全部把结果写进响应缓冲 0x200041B4 ⇒ 查询/只读
$A1_KNOWN = @(
    0x02,0x04,0x07,0x08,0x0A,0x0B,0x0F,0x13,0x15,0x16,0x18,
    0x1D,0x23,0x28,0x29,0x2B,0x2C,0x2E,0x32,0x34,0x35,0x36
)
# 0xA0：16 个 —— 参数取 ctx+4 的载荷 ⇒ 命令/写
$A0_KNOWN = @(
    0x01,0x05,0x0B,0x0D,0x0E,0x11,0x12,0x14,
    0x17,0x1F,0x20,0x24,0x26,0x32,0x33,0x35
)

# 关键地址（COL04-BOUNDARY.md §1）
$ADDR_CMDBLK = 0x4134   # 内部命令块 p（= 0x20004134，主机以 16 位偏移寻址）
$ADDR_CLSFLD = 0x4238   # 类字节字段（= 0x20004238 = p+0x104）
$ADDR_RSPBUF = 0x41B4   # 响应缓冲（= 0x200041B4 = p+0x8C）

# ─────────────── 从 vib-link ONE mem 的输出里抠出 16 进制字节 ───────────────
# 输出形如：  ONE mem ... : ok=True  0E 20 03 00 ...
# 注意：嵌套 PowerShell 的 stdout 对【中文】会乱码，但十六进制是 ASCII，不受影响。
function Read-MemBytes {
    param([int]$Addr, [int]$Size)
    $raw = Call-VibLink @("ONE", "mem", ("{0:X4}" -f $Addr), "$Size")
    $hex = $null
    $m = [regex]::Match($raw, 'ok=True\s+((?:[0-9A-Fa-f]{2}\s+)+)')
    if ($m.Success) { $hex = $m.Groups[1].Value }
    $bytes = @()
    if ($hex) {
        foreach ($t in ($hex -split '\s+')) {
            if ($t) { $bytes += [Convert]::ToInt32($t, 16) }
        }
    }
    return ,@($bytes)
}

function Show-MemLine {
    param([int]$Addr, [int[]]$Bytes, [string]$tag)
    if ($Bytes.Count -eq 0) { Log ("    {0} 0x{1:X4} : (无数据 / 读失败)" -f $tag, $Addr); return }
    # 打印 8 个数据字节（跳过回复头 [0]=rid [1]=class [2..3]=len [4]=len）
    $data = @()
    for ($k = 5; $k -lt $Bytes.Count; $k++) { $data += $Bytes[$k] }
    $n = [Math]::Min(16, $data.Count)
    $s = ""
    for ($k = 0; $k -lt $n; $k++) { $s += ("{0:X2} " -f $data[$k]) }
    Log ("    {0} 0x{1:X4}[+0..+{2}] : {3}" -f $tag, $Addr, ($n - 1), $s.Trim())
}

# ─────────────── Phase 0：字节序定案实验 ───────────────
# ★★★ Phase 0 已删除（2026-09-14 23:1x 真机实测证伪）★★★
#   原 Phase 0 计划是"发一条识别帧 -> 读回 RAM 0x4134 看字节落点"来定字节序。
#   真机实测证明：类 0x20 的读窗口【够不到 TF100A 的 0x20000000 空间】
#     - 读 0x40D0（TF100A 触觉 ctx）得到 24 个 0x00（应为 0x40000000/0x77/0x3E7/0x0800D6F5）
#     - 读 0x4134（TF100A 命令块）得到 32 个 0xFF
#   详见 COL04-BOUNDARY.md §10。因此该实验【无法】用来定字节序，已整段移除。
#
#   替代判定法（现由 Phase 1 承担）：
#     发一条 A1 帧 -> LISTEN -> 看回复的【类字节是不是 0xA2】。
#     0xA2 是固件的"回复类"（依据：应答打包器 0x080052A8 与读回函数 0x0800865C/0x08008868
#     都把输出首字节写成 0xA2）。收到 0xA2 = TF100A 的处理器真的跑了 = 通道可达。
#     收不到任何东西 = 连"GT7868Q 会不会转发"这一层都没成立，直接转拆机路线。

# ─────────────── 探测项清单 ───────────────
$items = @()
function New-Item2([int]$cls, [int]$op, [string]$pay, [string]$note) {
    # 按 ByteOrder 换算成传给 VibLink 的 sub 数值
    $subVal = if ($ByteOrder -eq "H1") { $op * 256 } else { $op }
    return ,@{ cls=$cls; sub=$subVal; op=$op; pay=$pay; note=$note }
}
switch ($Phase) {
  "1" {
    $items += New-Item2 0xA1 0x0B "00" "L1 单发判定：A1-0x0B 读回波形缓冲（只读，最安全的一发）"
  }
  "2" {
    foreach ($op in $A1_KNOWN) {
      $items += New-Item2 0xA1 $op "00" ("L2 A1-0x{0:X2}（已知合法值·只读查询 {1}/22）" -f $op, ($A1_KNOWN.IndexOf($op)+1))
    }
  }
  "3" {
    foreach ($op in $A0_KNOWN) {
      $items += New-Item2 0xA0 $op "00" ("L3 A0-0x{0:X2}（已知合法值·★ 写操作 {1}/16）" -f $op, ($A0_KNOWN.IndexOf($op)+1))
    }
  }
  "4" {
    $items += New-Item2 0xA0 0x0B "00" "L4 A0-0x0B 写波形缓冲（★ 写）"
    $items += New-Item2 0xA0 0x0D "00" "L4 A0-0x0D 清缓冲/arm（★ 写）"
  }
}

# ─────────────── 开跑 ───────────────
Log ("=" * 74)
Log ("Col04 探测 · Phase {0} · {1}" -f $Phase, (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
Log ("日志文件 : {0}" -f $logFile)
Log ("解释器   : {0}" -f $psExe)
Log ("字节序   : {0}（H1=op 放 pkt[3] / H2=op 放 pkt[2]）" -f $ByteOrder)
Log ("参数     : dwell={0}ms  step={1}ms  listenTimeout={2}ms  DryRun={3}" -f $DwellMs, $StepDelayMs, $ListenTimeoutMs, $DryRun)
Log ("")
Log ("!! 提醒：本脚本只应在【台面样机】上跑。真机禁止。")
Log ("")

$stopReason = $null

if ($Phase -eq "0") {
    Log ("=" * 74)
    Log ("Phase 0 · 已作废（2026-09-14 23:1x 真机实测证伪）")
    Log ("=" * 74)
    Log ("")
    Log ("  原方法：发一条识别帧 -> 读回 RAM 0x4134 看字节落点，以此定字节序。")
    Log ("  为什么作废：真机实测证明类 0x20 的读窗口【够不到 TF100A 的 0x20000000 空间】——")
    Log ("    读 0x40D0（TF100A 触觉 ctx）得到 24 个 0x00（应为 40000000 / 77 / 3E7 / 0800D6F5）")
    Log ("    读 0x4134（TF100A 命令块）得到 32 个 0xFF")
    Log ("  详见 COL04-BOUNDARY.md §10。")
    Log ("")
    Log ("  请改用 Phase 1（发一条 A1 帧 -> LISTEN -> 看回复类字节是否 0xA2）。")
    Log ("")
    exit 7
} else {
    Log ("共 {0} 项。" -f $items.Count)
    Log ("")
    $i = 0
    foreach ($it in $items) {
        $i++
        $clsHex = "{0:X2}" -f $it.cls
        $subHex = "{0:X4}" -f $it.sub
        Log ("-" * 74)
        Log ("[{0}/{1}] {2}" -f $i, $items.Count, $it.note)

        if ($DryRun) {
            Log ("    [DRY-RUN] 会执行 4 件事：")
            Log ("      1) .\vib-link.ps1 HEALTH")
            Log ("      2) .\vib-link.ps1 SEND {0} {1} '{2}' {3} 1" -f $clsHex, $subHex, $it.pay, $DwellMs)
            Log ("      3) .\vib-link.ps1 LISTEN {0}" -f $ListenTimeoutMs)
            Log ("      4) .\vib-link.ps1 HEALTH")
            if ($i -lt $items.Count) { Log ("    （然后等 {0}ms 进入下一项）" -f $StepDelayMs) }
            continue
        }

        # ① 前置体检
        Log ("    1) 前置体检 …")
        $r1 = Call-VibLink @("HEALTH")
        foreach ($l in ($r1 -split "`n")) { if ($l.Trim()) { Log ("       | " + $l.TrimEnd()) } }
        if (-not ($r1 -match "exit=0")) { $stopReason = "前置体检失败"; Log ("    x 前置体检未通过 ⇒ 立即中止"); break }

        # ② 单发
        Log ("    2) 单发 SEND {0} {1} '{2}' {3} 1 …" -f $clsHex, $subHex, $it.pay, $DwellMs)
        $r2 = Call-VibLink @("SEND", $clsHex, $subHex, $it.pay, "$DwellMs", "1")
        foreach ($l in ($r2 -split "`n")) { if ($l.Trim()) { Log ("       | " + $l.TrimEnd()) } }

        # ③ 读回
        Log ("    3) 读回 LISTEN {0} …" -f $ListenTimeoutMs)
        $r3 = Call-VibLink @("LISTEN", "$ListenTimeoutMs")
        foreach ($l in ($r3 -split "`n")) { if ($l.Trim()) { Log ("       | " + $l.TrimEnd()) } }

        # ④ 后置体检
        Log ("    4) 后置体检 …")
        $r4 = Call-VibLink @("HEALTH")
        foreach ($l in ($r4 -split "`n")) { if ($l.Trim()) { Log ("       | " + $l.TrimEnd()) } }
        $ok4 = ($r4 -match "exit=0")

        # ⑤ 响应缓冲（★ 只有 0xA1 族会写这里；读到非空 = 通道真的到了扩展空间）
        if ($it.cls -eq 0xA1 -and -not $DryRun) {
            Log ("    4.5) 读响应缓冲 0x{0:X4}（A1 族的结果落点）…" -f $ADDR_RSPBUF)
            $rb = Read-MemBytes $ADDR_RSPBUF 48
            Show-MemLine $ADDR_RSPBUF $rb "rspbuf"
        }

        # ⑥ 人工栏
        Log ("    5) ### 人工观察栏：刚才触控板有没有震动？( 无 / 有：请描述 ) ###")

        if (-not $ok4) { $stopReason = "后置体检失败"; Log ("    x 后置体检未通过 ⇒ 立即中止，请给样机重新上电"); break }

        Start-Sleep -Milliseconds $StepDelayMs
    }
}

Log ("")
Log ("=" * 74)
if ($stopReason) {
    Log ("!! 提前中止：{0}" -f $stopReason)
    Log ("   处置：停止一切探测 -> 样机断电重新上电 -> 检查样机是否恢复正常")
} else {
    Log ("Phase {0} 执行完毕。" -f $Phase)
}
Log ("日志已保存：{0}" -f $logFile)
Log ("")
Log ("判读提示（详见 COL04-BOUNDARY.md §2.4/§10 与 COL04-EXT-PROBE-PLAN.md §7）：")
Log ("  · Phase 1：回复的【类字节 = 0xA2】 -> ★ 通道可达（TF100A 处理器真的跑了），继续 Phase 2")
Log ("  · Phase 1：收不到任何回复    -> GT7868Q 不转发（或路径不通），本方案终止，转拆机路线")
Log ("  · 任一动作【触发震动】     -> *** 命中 ***，立即记下完整帧并停手")
Log ("")
exit 0
