#!/bin/bash
# =====================================================================
# lab__linux_full_recon.sh  --  原装触控板 · Linux Live 一次性全量侦察
# =====================================================================
# 目标：用【一次 Live USB 启动】把所有「只有 Linux 能做」的判据一次跑完，
#       产出【一个日志文件】，拿回 Windows 侧接着分析。
#
# 覆盖的判据（全部只读）：
#   P1 系统与总线画像        —— DMI / 内核 / I²C 控制器全集 / BAR / ACPI 归属
#   P2 GPIO 归属            —— RSTN / INT 由谁控制（debugfs + gpioinfo）
#   P3 ★ HID 原始报告描述符  —— HIDIOCGRDESC / sysfs，【逐字节】权威副本
#                              （Windows 只能拿解析后的；这里拿原始字节）
#   P4 EC 只读快照          —— ec_sys / acpi_call（若可用）
#   P5 ★ AW86927 主机可达性   —— 解绑 i2c_hid → 阳性对照 → 0x5A/0x5B 零长度写
#                              → 身份寄存器串 → 定向地址枚举
#   P6 ★ hidraw 原始报文抽样  —— Col02 的 MT 原生报文（限量、低频）
#   P7 收尾                 —— 恢复绑定 + 结论汇总
#
# ★ 安全边界（本脚本的硬约束）
#   · 绝不 i2cset / 绝不发任何 HID feature 或 output report
#   · 只做：零长度写（i2ctransfer w0@，纯地址探测）、i2cget 单点读、hidraw 读
#   · 唯一"写"是 sysfs 的 unbind/bind —— 那是【软件绑定状态】，不写设备
#   · trap 保证任何退出路径都恢复 i2c_hid
#
# 前置（务必先做）：
#   □ 插好一个 USB 鼠标 —— 解绑期间触控板失效，而它是本机唯一指点设备
#   □ 确认退路：真出问题时，重启（热重启）或断电重开
#
# 用法：
#   sudo bash lab__linux_full_recon.sh                 # 全跑（默认）
#   sudo bash lab__linux_full_recon.sh --safe-only     # 只跑 P1–P4，不碰总线
#   sudo bash lab__linux_full_recon.sh --no-enum       # 跑 P5 但只探 0x5A/0x5B，不做 77 地址枚举
#   sudo bash lab__linux_full_recon.sh --out /mnt/sdb1 # 直接写到你挂好的 U 盘
#   sudo bash lab__linux_full_recon.sh --i-have-usb-mouse
#        # ★ 显式声明"我已插好独立鼠标"。不加这个 flag 时脚本会【自动检测】；
#        #    检测不到就【跳过 P5】—— 因为 P5 会让触控板失效（它是本机唯一指点设备）。
#
# ⚠️ 关于 Live 环境的两条硬前置（脚本只能提示，不能代做）：
#   1. Ubuntu Live 默认【不带 i2c-tools】。先连 WiFi，再：
#        sudo apt update && sudo apt install -y i2c-tools
#   2. 插好 USB 鼠标 —— 见上面 --i-have-usb-mouse
# =====================================================================

set -u
TAG="[recon]"
say() { echo "$TAG $*"; }
hr()  { echo "-------------------------------------------------------------------"; }
h1()  { echo; echo "==============================================================="; echo " $*"; echo "==============================================================="; }

SAFE_ONLY=0
NO_ENUM=0
FORCE_UNBIND=0
OUTDIR="/tmp"
while [ $# -gt 0 ]; do
  case "$1" in
    --safe-only) SAFE_ONLY=1; shift ;;
    --no-enum)   NO_ENUM=1;   shift ;;
    --i-have-usb-mouse) FORCE_UNBIND=1; shift ;;
    --out) OUTDIR="${2:-/tmp}"; shift 2 ;;
    *) shift ;;
  esac
done

if [ "$(id -u)" != "0" ]; then
  echo "[!] 需要 root： sudo bash $0"
  exit 1
fi

TS="$(date +%Y%m%d-%H%M%S)"
# ---- 修①：--out 必须验证，否则 tee 静默失败、日志丢失 ----
if [ ! -d "$OUTDIR" ]; then
  echo "[!] --out 目录不存在：$OUTDIR  ⇒ 回退到 /tmp"
  OUTDIR="/tmp"
fi
if ! touch "${OUTDIR}/.wtest_$$" 2>/dev/null; then
  echo "[!] --out 目录不可写：$OUTDIR  ⇒ 回退到 /tmp"
  OUTDIR="/tmp"
else
  rm -f "${OUTDIR}/.wtest_$$"
fi
OUT="${OUTDIR}/touchpad_recon_${TS}.txt"
# ---- 修⑧：先保存原始 fd，收尾时脱离 tee，避免日志末尾被截断丢失 ----
exec 3>&1 4>&2
exec > >(tee "$OUT") 2>&1

# ---- 修②：工具存在性检查（i2ctransfer 缺失会让整个 P5 静默全失败）----
MISSING=""
for t in i2ctransfer i2cget; do
  command -v "$t" >/dev/null 2>&1 || MISSING="$MISSING $t"
done
HAS_TIMEOUT=1; command -v timeout >/dev/null 2>&1 || HAS_TIMEOUT=0
HAS_OD=1;      command -v od      >/dev/null 2>&1 || HAS_OD=0

# ============================== 全局状态 ==============================
BUS=""
CLIENT=""
UNBOUND=""
KEEPGOING=1

restore() {
  h1 "[R] 收尾：恢复 i2c_hid 绑定（trap：正常/异常/Ctrl+C 都会执行）"
  if [ -n "$UNBOUND" ]; then
    for d in /sys/bus/i2c/drivers/*/; do
      [ -e "$d" ] || continue
      case "$(basename "$d")" in
        i2c_hid*)
          [ -e "$d/bind" ] && { echo "$UNBOUND" > "$d/bind" 2>/dev/null \
            && say "rebind ok: $(basename "$d") <- $UNBOUND" \
            || say "rebind 失败（可忽略）: $(basename "$d")"; }
          ;;
      esac
    done
    sleep 1
  else
    say "（本脚本未解绑过任何客户端）"
  fi
  [ -n "$CLIENT" ] && { ls -l "/sys/bus/i2c/devices/$CLIENT" 2>/dev/null \
    || say "($CLIENT 仍无绑定 → 跑 dmesg | tail -20 看 hid 是否重新枚举)"; }
  # 修⑧续：脱离 tee 并把 tee 冲刷干净，保证上面每一行都落盘
  exec 1>&3 2>&4
  sync; sleep 1
  echo
  echo "日志已写入： $OUT"
  if [ -s "$OUT" ]; then
    echo "字节数： $(stat -c%s "$OUT" 2>/dev/null || echo '?')   行数： $(wc -l < "$OUT" 2>/dev/null || echo '?')"
  else
    echo "🔴 日志为空！请检查 tee/权限。"
  fi
  echo "★ 请立刻拷到 U 盘：  cp \"$OUT\" /mnt/<你的U盘>/"
}
trap restore EXIT INT TERM

echo "==============================================================="
echo " 原装触控板 · Linux Live 一次性全量侦察"
echo " 时间: $(date)    模式: $([ $SAFE_ONLY = 1 ] && echo 'safe-only' || echo 'full')"
echo "==============================================================="

# =====================================================================
h1 "P1 · 系统与总线画像"
# =====================================================================
say "DMI      : $(cat /sys/class/dmi/id/product_name 2>/dev/null) / $(cat /sys/class/dmi/id/product_version 2>/dev/null)"
say "主板     : $(cat /sys/class/dmi/id/board_name 2>/dev/null)"
say "BIOS     : $(cat /sys/class/dmi/id/bios_version 2>/dev/null)"
say "内核     : $(uname -r)"
say "发行版   : $(grep PRETTY_NAME /etc/os-release 2>/dev/null | cut -d= -f2-)"
echo
say "[1.0] 依赖检查"
say "      i2ctransfer/i2cget 缺失项:${MISSING:- 无}"
say "      timeout:$([ $HAS_TIMEOUT = 1 ] && echo 有 || echo 缺失)   od:$([ $HAS_OD = 1 ] && echo 有 || echo 缺失)"
if [ -n "$MISSING" ]; then
  say "      ⇒ 缺 i2c-tools，尝试安装"
  say "      ⚠️ Ubuntu Live 默认【不带 i2c-tools】。若下面安装失败（多半是没网），"
  say "         请先连 WiFi，再手动跑： sudo apt update && sudo apt install -y i2c-tools"
  ( apt-get install -y i2c-tools 2>&1 | tail -3 ) || true
  for t in $MISSING; do command -v "$t" >/dev/null 2>&1 && say "      $t 已就绪" || say "      $t 仍缺失 → P5 将不可用"; done
  MISSING=""
  for t in i2ctransfer i2cget; do command -v "$t" >/dev/null 2>&1 || MISSING="$MISSING $t"; done
  [ -z "$MISSING" ] && say "      ✅ i2c-tools 就绪" || say "      🔴 仍缺:$MISSING → P5 会跳过"
fi
echo
say "[1.1] I²C 控制器（内核侧）"
if command -v lspci >/dev/null 2>&1; then
  lspci -nnk 2>/dev/null | grep -iA2 -E "i2c|serial bus|smbus" | head -40
fi
echo
say "[1.2] i2c 适配器 + 客户端 + ACPI 归属"
for a in /sys/bus/i2c/devices/i2c-*; do
  [ -e "$a" ] || continue
  n="${a##*-}"
  adev="$(basename "$(readlink -f "$a/firmware_node" 2>/dev/null)" 2>/dev/null)"
  apath="$(cat "/sys/bus/acpi/devices/$adev/path" 2>/dev/null)"
  printf "    i2c-%-4s name=%-26s acpi_dev=%-16s acpi_path=%s\n" \
    "$n" "$(cat "$a/name" 2>/dev/null)" "$adev" "$apath"
  if [ -e "/sys/bus/i2c/devices/i2c-$n-002c" ]; then
    BUS="$n"; CLIENT="i2c-$n-002c"
    say "        ★ 命中：本适配器上有 0x2C 客户端（触控板）"
  fi
done
echo
say "[1.3] 全部 i2c 客户端"
for d in /sys/bus/i2c/devices/*; do
  [ -e "$d" ] || continue
  printf "    %-22s %s\n" "$(basename "$d")" "$(cat "$d/name" 2>/dev/null)"
done
echo
say "[1.4] ACPI 表清单"
ls -1 /sys/firmware/acpi/tables/ 2>/dev/null | tr '\n' ' '; echo
if [ -z "$BUS" ]; then
  say "[!] 未找到带 0x2C 客户端的适配器 —— P5 将无法进行。"
  KEEPGOING=0
else
  say "⇒ 目标总线 = i2c-$BUS   客户端 = $CLIENT"
fi

# =====================================================================
h1 "P2 · GPIO 归属（RSTN / INT 由谁控制）"
# =====================================================================
mountpoint -q /sys/kernel/debug 2>/dev/null || mount -t debugfs none /sys/kernel/debug 2>/dev/null
if [ -r /sys/kernel/debug/gpio ]; then
  say "[2.1] /sys/kernel/debug/gpio"
  sed -n '1,80p' /sys/kernel/debug/gpio
else
  say "[2.1] debugfs gpio 不可读（内核可能未开 CONFIG_GPIOLIB_IRQCHIP / debugfs）"
fi
echo
if command -v gpioinfo >/dev/null 2>&1; then
  say "[2.2] gpioinfo（含未申请的线）"
  gpioinfo 2>/dev/null | head -60
else
  say "[2.2] gpioinfo 缺失（libgpiod 未装）—— 可 apt-get install gpiod"
fi
echo
say "[2.3] 触控板设备的 ACPI 资源（_CRS）：在 /sys 侧只能看资源节点"
ls -l /sys/bus/acpi/devices/*/physical_node* 2>/dev/null | head -20

# =====================================================================
h1 "P3 · ★ HID 原始报告描述符（逐字节权威副本）"
# =====================================================================
say "说明：Windows 只能拿【解析后】的报表列表；Linux sysfs 给出【原始字节】。"
say "      这能对「0x0E/0x01 SHC 集合」「0x0D/0xB0 ButtonPressThreshold」等"
say "      给出不依赖任何解析器的权威判据。"
echo
for d in /sys/bus/hid/devices/*/; do
  [ -e "$d" ] || continue
  id="$(basename "$d")"
  echo "-------------------------------------------------------------------"
  say "HID 设备: $id"
  printf "    name=%s\n" "$(cat "$d/uevent" 2>/dev/null | grep -E '^HID_NAME=' | cut -d= -f2-)"
  printf "    id  =%s\n" "$(cat "$d/uevent" 2>/dev/null | grep -E '^HID_ID='   | cut -d= -f2-)"
  printf "    phys=%s\n" "$(cat "$d/uevent" 2>/dev/null | grep -E '^HID_PHYS=' | cut -d= -f2-)"
  if [ -r "$d/report_descriptor" ]; then
    # 修⑦：stat() 的 st_size 不可信！
    #   sysfs bin_attribute 声明 .size = HID_MAX_DESCRIPTOR_SIZE(4096) ⇒ stat 可能恒返 4096；
    #   老内核(4.15–5.2) 还可能返 0 或把 read() 截断到 1024 B。
    #   ⇒ 必须以【实际读到的字节数】为准。
    statsz="$(stat -c%s "$d/report_descriptor" 2>/dev/null)"
    if [ "$HAS_OD" = "1" ]; then
      COMPACT="$(od -An -tx1 "$d/report_descriptor" 2>/dev/null | tr -d ' \n')"
      real=$(( ${#COMPACT} / 2 ))
      say "    report_descriptor: stat=${statsz}B  实际读到=${real}B"
      if [ "$statsz" != "$real" ]; then
        say "    ⚠️ stat 与实际不一致（正常现象：sysfs bin_attr 的 size 字段）—— 以【实际读到】为准"
      fi
      say "    ---- 人类可读（od -A x -t x1z）----"
      od -A x -t x1z "$d/report_descriptor" 2>/dev/null
      # 修③：加【无空格紧凑 hex】——P3 的用途是"搜锚点"，
      #   而 od 的默认输出带空格/偏移/ASCII 尾，无法直接 grep 多字节锚点。
      say "    ---- 紧凑 hex（可直接搜锚点）----"
      say "    锚点：050e0901=SHC集合(0x0E/0x01) · 050d0905=PTP主体集合 · 09b0=ButtonPressThreshold · 0600ff=厂商页"
      echo "    $COMPACT"
      say "    ---- 锚点命中检查 ----"
      for anchor in 050e0901 050e 09b0 050d0905 0600ff; do
        case "$COMPACT" in
          *"$anchor"*) say "      ✅ 命中 $anchor" ;;
          *)           say "      ❌ 未命中 $anchor" ;;
        esac
      done
    else
      cat "$d/report_descriptor" 2>/dev/null | od -An -tx1
    fi
  else
    say "    （本内核未导出 report_descriptor 节点）"
    say "    兜底方案（择一）："
    say "      · sudo apt-get install hid-tools  →  hid-recorder  （需停用 hid-input 才干净）"
    say "      · python3 + ioctl HIDIOCGRDESCSIZE / HIDIOCGRDESC 读 /dev/hidrawN"
    say "      · 本脚本不内置 ioctl 实现：作者无法在交付前实测，"
    say "        而本项目有『脚本看起来完好、其实从未跑过』的前科（99-pitfalls）⇒ 宁缺勿滥"
  fi
done
echo
say "[3.1] hidraw 节点清单"
for h in /sys/class/hidraw/hidraw*; do
  [ -e "$h" ] || continue
  printf "    %-14s -> %s\n" "$(basename "$h")" "$(readlink -f "$h/device" 2>/dev/null)"
done

# =====================================================================
h1 "P4 · EC 只读快照（若可用）"
# =====================================================================
if [ -r /sys/kernel/debug/ec/ec0/io ]; then
  say "[4.1] ec_sys 已就绪，dump 前 256 B"
  od -A x -t x1z -N 256 /sys/kernel/debug/ec/ec0/io 2>/dev/null
else
  say "[4.1] ec_sys 未加载 —— 如需要：modprobe ec_sys write_support=0，再读 /sys/kernel/debug/ec/ec0/io"
  say "      （触控板不经过 EC，本节仅作对照，可跳过）"
fi
echo
say "[4.2] dmesg 中 i2c / hid / goodix / haptic 相关"
dmesg 2>/dev/null | grep -iE "i2c|hid|goodix|haptic|GXTP|27c6" | tail -40

# =====================================================================
h1 "P5 · ★ AW86927 主机可达性（I2C 只读探测）"
# =====================================================================
# ---------- 修⑪：P5 会让触控板失效 ⇒ 先确认有【独立的】备用指点设备 ----------
# ⚠️ 不要用 `ls /dev/input/by-path | grep -i mouse` 来判断 ——
#    本机触控板的 Col01 就是 0x0001/0x0002 Mouse 应用集合（驱动 mouhid）
#    ⇒ /dev/input/by-path 里也有 *-event-mouse，照那样判会把【触控板自己】
#      当成"已插鼠标"，给出虚假安全感。必须排除触控板关键词后，
#      再去找真正外接的鼠标/指点杆。
MOUSE_OK=0
MOUSE_EVID=""
for f in /sys/class/input/event*/device/name; do
  [ -r "$f" ] || continue
  nm="$(cat "$f" 2>/dev/null)"
  case "$nm" in
    *GXTP*|*Goodix*|*goodix*|*27C6*|*27c6*|*TouchPad*|*Touchpad*|*触控板*|*触摸板*) continue ;;
  esac
  case "$nm" in
    *Mouse*|*MOUSE*|*mouse*|*鼠标*|*TrackPoint*|*Trackpoint*|*指点杆*)
      MOUSE_OK=1; MOUSE_EVID="input name = $nm"; break ;;
  esac
done
# 强判据：USB 总线上真的有鼠标（by-id 名字里带 usb 且带 mouse）
if [ "$MOUSE_OK" != "1" ]; then
  for f in /dev/input/by-id/*; do
    [ -e "$f" ] || continue
    case "$(basename "$f")" in
      *usb*[Mm]ouse*) MOUSE_OK=1; MOUSE_EVID="by-id = $(basename "$f")"; break ;;
    esac
  done
fi
if [ "$MOUSE_EVID" = "" ]; then MOUSE_EVID="（未找到任何非触控板的鼠标类设备）"; fi
say "      备用指点设备检测：$([ "$MOUSE_OK" = 1 ] && echo '✅ 找到' || echo '❌ 未找到')  $MOUSE_EVID"

if [ "$KEEPGOING" != "1" ] || [ "$SAFE_ONLY" = "1" ] || [ -n "$MISSING" ]; then
  say "跳过（safe-only / 未定位到目标总线 / 缺 i2c-tools）"
elif [ "$MOUSE_OK" != "1" ] && [ "$FORCE_UNBIND" != "1" ]; then
  say "🔴 跳过 P5：未检测到独立的备用指点设备。"
  say "   原因：P5 会 unbind i2c_hid ⇒ 触控板（本机唯一指点设备）立即失效。"
  say "   处理：① 插好 USB 鼠标后重跑；或 ② 明确加 --i-have-usb-mouse 表示你已确认。"
  say "   注意：触控板自己的 Col01 就名为 mouse，所以本脚本【不会】把它当备用设备。"
else
  [ "$FORCE_UNBIND" = "1" ] && [ "$MOUSE_OK" != "1" ] \
    && say "      ⚠️ 你用了 --i-have-usb-mouse 强制继续（自动检测未找到）。后果自负。"
  say "[5.0] 基线状态"
  ls -l "/sys/bus/i2c/devices/$CLIENT" 2>/dev/null || say "    （无 $CLIENT 节点）"
  echo
  # ---------- 修④：解绑【前】先做一次 0x2C 探测 = 对照 A ----------
  say "[5.0a] 对照 A：解绑【前】探测 0x2C（此时 i2c_hid 占着总线）"
  say "      说明：这一步不通是【预期】的（总线被占用）。但两种失败文本含义不同："
  say "        · 'Remote I/O error'(NACK)       ⇒ 设备此刻不应答（可能已 suspend）"
  say "        · 'lost arbitration' / 忙        ⇒ 总线被驱动占用（预期）"
  outA="$(i2ctransfer -y "$BUS" w0@0x2c 2>&1)"; rcA=$?
  printf "      rc=%s  out=%s\n" "$rcA" "${outA:-<空>}"
  echo
  say "[5.1] ★ 解绑 i2c_hid（关键：不解绑就扫 = 与进行中事务冲突 = 崩内核）"
  for d in /sys/bus/i2c/drivers/*/; do
    [ -e "$d" ] || continue
    case "$(basename "$d")" in
      i2c_hid*)
        if [ -e "$d/$CLIENT" ] || [ -L "$d/$CLIENT" ]; then
          say "      unbind: $(basename "$d") <- $CLIENT"
          echo "$CLIENT" > "$d/unbind" 2>/dev/null && { UNBOUND="$CLIENT"; say "      ok"; } \
                                               || say "      失败"
        fi ;;
    esac
  done
  [ -n "$UNBOUND" ] || say "      （未发生解绑：i2c_hid 可能本就未绑定）"
  sleep 2
  # 修⑤：解绑可能触发 runtime PM 把设备挂起 ⇒ 先确认电源域是 on，
  #      否则阳性对照会【假阴性】（设备真的不应答）
  if [ -w "/sys/bus/i2c/devices/$CLIENT/power/control" ]; then
    pc="$(cat "/sys/bus/i2c/devices/$CLIENT/power/control" 2>/dev/null)"
    rs="$(cat "/sys/bus/i2c/devices/$CLIENT/power/runtime_status" 2>/dev/null)"
    say "      power/control=$pc   runtime_status=$rs"
  fi
  echo
  # -------------------------------------------------- 阳性对照
  say "[5.2] ★★★ 阳性对照（纪律 12）"
  say "      解绑后 0x2C 无人占用 ⇒ 对它做零长度写应拿到 ACK。"
  say "      ★ 对照不通 = 探针无效 = 本次不得记录为『0x5A 没扫到』。"
  out="$(i2ctransfer -y "$BUS" w0@0x2c 2>&1)"; rc=$?
  printf "      \$ i2ctransfer -y %s w0@0x2c   → rc=%s  out=%s\n" "$BUS" "$rc" "${out:-<空>}"
  # 修⑤续：对照不通时，尝试把设备从挂起里唤起来再试一次
  if [ "$rc" != "0" ] && [ -w "/sys/bus/i2c/devices/$CLIENT/power/control" ]; then
    say "      ⚠️ 对照不通 —— 尝试 power/control=on 强制唤醒后重试一次"
    echo on > "/sys/bus/i2c/devices/$CLIENT/power/control" 2>/dev/null || true
    sleep 1
    out="$(i2ctransfer -y "$BUS" w0@0x2c 2>&1)"; rc=$?
    printf "      重试 → rc=%s  out=%s\n" "$rc" "${out:-<空>}"
    say "      （power/control 已被置 on，若本次会话不再需要可自行还原）"
  fi
  if [ "$rc" != "0" ]; then
    say "      🔴 阳性对照不通 ⇒ 立即中止 P5，且【不得】下任何『不在』的结论。"
    say "         已排除的解释：挂起（已试过唤醒）。仍未通 ⇒ 通道/控制器层面问题。"
  else
    say "      ✅ 阳性对照通过 ⇒ 后面的 NACK 才有意义。"
    echo
    # ------------------------------------------------ 两点探测
    say "[5.3] 两点探测：0x5A / 0x5B（零长度写 = 纯地址探测，不发数据、不读数据）"
    ACK5A=1; ACK5B=1
    for a in 0x5a 0x5b; do
      out="$(i2ctransfer -y "$BUS" "w0@$a" 2>&1)"; rc=$?
      printf "      %s : rc=%s  out=%s\n" "$a" "$rc" "${out:-<空>}"
      [ "$a" = "0x5a" ] && ACK5A=$rc
      [ "$a" = "0x5b" ] && ACK5B=$rc
    done
    echo
    if [ "$ACK5A" = "0" ] || [ "$ACK5B" = "0" ]; then
      say "      ★★★★★ 有 ACK ⇒ 该地址【在主机 I²C 总线上】！"
    else
      say "      ❌ 两个地址都无 ACK。⚠️ 三种可能，不可直接判死："
      say "         (a) 真的不在主机这条总线"
      say "         (b) 在，但 power-down（数据手册：RSTN 低 = power-down）"
      say "         (c) AD 脚决定的地址不是 0x5A/0x5B"
    fi
    echo
    # ------------------------------------------------ 身份寄存器串
    say "[5.4] 身份寄存器串（区分『无 ACK』与『有 ACK 但读失败』—— 后者意味着器件在！）"
    say "      ⚠️ 寄存器地址来源待核，故打一串而不是只赌 0x57/0x58。"
    for a in 0x5a 0x5b; do
      for reg in 0x00 0x01 0x0a 0x0b 0x0c 0x0d 0x57 0x58 0x5a 0x5b 0x5c 0x5d; do
        out="$(i2cget -y "$BUS" "$a" "$reg" 2>&1)"; rc=$?
        printf "      %s reg %s : rc=%s  %s\n" "$a" "$reg" "$rc" "${out:-<空>}"
      done
      echo
    done
    # ------------------------------------------------ 定向枚举
    say "[5.5] 定向地址枚举"
    # 修⑨：Quick Command 残留风险告知 + --no-enum 开关。
    #   某些器件把【零长度写】当功能命令（经典例：SMBus 智能电池/风扇用 Quick Command 做开关）。
    #   AW86927 是寄存器制器件，地址相位之后没有寄存器地址，本应被忽略；
    #   但这是本脚本【唯一】的残留风险点 ⇒ 给一个只做二元判据的开关。
    if [ "$NO_ENUM" = "1" ]; then
      say "      已用 --no-enum 跳过（只保留 [5.3] 两点探测与 [5.4] 身份读取）"
    else
    say "      ⚠️ 残留风险告知：零长度写(Quick Command)在极少数器件上会被当【功能命令】。"
    say "         不想承担就改用 --no-enum —— 那也足够回答『0x5A/0x5B 在不在』这一问。"
    say "      范围 0x08–0x77，【跳过】0x2C（触控板，已知）与保留段。"
    hits=""
    i=0
    for hi in 0 1 2 3 4 5 6 7; do
      for lo in 0 1 2 3 4 5 6 7 8 9 a b c d e f; do
        a="0x${hi}${lo}"
        # 跳过 0x00–0x07 与 0x78–0x7f（I2C 保留）
        [ "$hi" = "0" ] && [ "$(printf '%d' "0x${lo}")" -lt 8 ] && continue
        [ "$hi" = "7" ] && [ "$(printf '%d' "0x${lo}")" -ge 8 ] && continue
        [ "$a" = "0x2c" ] && continue
        i=$((i+1))
        if [ $((i % 16)) -eq 0 ]; then
          if ! i2ctransfer -y "$BUS" w0@0x2c >/dev/null 2>&1; then
            say "      ⚠️ 活性体检失败（0x2C 不应答）⇒ 中止枚举。已枚举 $i 个地址。"
            break 2
          fi
        fi
        if i2ctransfer -y "$BUS" "w0@$a" >/dev/null 2>&1; then
          say "      ★ ACK @ $a"
          hits="$hits $a"
        fi
      done
    done
    echo
    if [ -n "$hits" ]; then
      say "      ⇒ 应答地址：$hits"
    else
      say "      ⇒ 主机这条总线上，除 0x2C 外无其它 ACK（对照通过的前提下，此结论有效）"
    fi
    fi   # ← 修⑨：NO_ENUM gate 闭合
  fi
fi

# ---------- 修⑫：P5 一结束就回绑！否则 P6 必然采不到报文 ----------
# 机制（已核）：hidraw 是挂在 hid_device 之上的接口驱动；
#   i2c_hid 被 unbind 时，hid core 会调用 hid_hw_stop() 并注销 hidraw 设备
#   ⇒ /dev/hidraw* 节点【直接消失】（不是"可能读不到"，是节点不存在）。
#   所以必须在 P6 之前把 i2c_hid 绑回去。
if [ -n "$UNBOUND" ]; then
  echo
  say "[5.6] ★ 立即回绑 i2c_hid（P6 需要 /dev/hidraw*；不回绑则节点不存在）"
  for d in /sys/bus/i2c/drivers/*/; do
    [ -e "$d" ] || continue
    case "$(basename "$d")" in
      i2c_hid*)
        [ -e "$d/bind" ] && { echo "$UNBOUND" > "$d/bind" 2>/dev/null \
          && say "      rebind ok: $(basename "$d")" || say "      rebind 失败"; }
        ;;
    esac
  done
  sleep 3   # 等 udev + probe 把 hidraw 节点重新建出来
  say "      回绑后 /sys/class/hidraw/ ：$(ls /sys/class/hidraw/ 2>/dev/null | tr '\n' ' ')"
  say "      回绑后 i2c 客户端：$(ls -l "/sys/bus/i2c/devices/$CLIENT" 2>/dev/null | head -1)"
  UNBOUND=""   # 已回绑 ⇒ 让 trap 不再重复动作
fi

# =====================================================================
h1 "P6 · hidraw 原生报文抽样（限量、低频）"
# =====================================================================
say "说明：hidraw 拿到的是【驱动之外的同一份报文】，不影响 hid-input。"
say "      限量 20 条、超时即止 —— 遵守本项目『不做高频轮询』的红线。"
say "      ★ 本节运行在 [5.6] 回绑 i2c_hid 之后 ⇒ /dev/hidraw* 已重建。"
say "        若本次未进过 P5（--safe-only），节点本就存在。"
say "        若上面显示『无候选』，请先确认 /sys/class/hidraw/ 下确有节点。"
echo
CAND=""
for h in /sys/class/hidraw/hidraw*; do
  [ -e "$h" ] || continue
  n="$(basename "$h")"
  dev="$(readlink -f "$h/device" 2>/dev/null)"
  # 修⑥：候选判据改用【PTP 主体集合的锚点 05 0d 09 05】，
  #        原先 grep "0d" 命中一切（几乎每个描述符都含 '0d'），候选集形同虚设。
  # 修⑩：修⑥ 依赖 report_descriptor；老内核不导出该节点时候选会【静默为空】。
  #        ⇒ 加 HID_ID 含 27C6（汇顶 VID）的兜底。
  if [ -r "$dev/report_descriptor" ]; then
    CMP="$(od -An -tx1 "$dev/report_descriptor" 2>/dev/null | tr -d ' \n')"
    case "$CMP" in
      *050d0905*) CAND="$CAND /dev/$n"; say "      候选 $n：命中 PTP 主体集合 05 0d 09 05" ;;
      *050d*)     CAND="$CAND /dev/$n"; say "      候选 $n：命中 Digitizer 页 05 0d（弱判据）" ;;
    esac
  else
    if grep -qi "27C6" "$dev/uevent" 2>/dev/null; then
      CAND="$CAND /dev/$n"; say "      候选 $n：report_descriptor 不可读，但 HID_ID 含 27C6（汇顶 VID）"
    fi
  fi
done
[ -z "$CAND" ] && say "⚠️ 无候选：既没命中 PTP 锚点，HID_ID 里也没有 27C6 ⇒ P6 将跳过（可插上 USB 触控板/鼠标后重跑本节）"
say "候选 hidraw：${CAND:-<无>}"
if [ "$HAS_TIMEOUT" = "0" ]; then
  say "🔴 timeout 命令缺失 ⇒ 跳过 P6（无超时保护时 dd 会永久阻塞）"
else
  say "抽样方式：循环「单次 read」—— 每次 bs=4096 count=1，拿【一个完整报文】。"
  say "          （原先 bs=64 count=20 要求 20×64 字节，而 PTP 报文是 40 字节 ⇒ 会错位/卡住）"
  say "          每条约 3s 超时，最多 20 条，不做重试（遵守禁高频轮询红线）。"
  for dev in $CAND; do
    echo "-------------------------------------------------------------------"
    say "抽样 $dev （最多 20 条）"
    k=0; got=0
    while [ $k -lt 20 ]; do
      k=$((k+1))
      if out="$(timeout 3 dd if="$dev" bs=4096 count=1 2>/dev/null | od -An -tx1)"; then
        [ -n "$(echo "$out" | tr -d ' \n')" ] || continue
        printf "      %2d : %s\n" "$k" "$(echo "$out" | tr -s ' ')"
        got=$((got+1))
      fi
    done
    say "      实得 $got 条"
  done
  say "（若为空：抽样期间没有输入。把手指放到触控板上再跑一次 P6 即可 —— 本脚本不自动重试。）"
fi

# =====================================================================
h1 "P7 · 结论汇总（按判据读）"
# =====================================================================
echo "  P3  HID 原始描述符  → 在报告里搜 0e 01 / 0e 21 / 0e 23 / 0d b0 的原始字节"
echo "       · 有 05 0e 09 01（Usage Page 0x0E, Usage 0x01）= SHC 集合存在"
echo "       · 有 09 b0（Usage 0xB0，在 0x0D 页）= ButtonPressThreshold 存在"
echo
echo "  P5  依次读："
echo "       ① 阳性对照 0x2C 不通        => 本次无效，不得下结论"
echo "       ② 0x5A/0x5B 有 ACK 且身份对 => ★ 主机可达 AW86927（Path-1 成立）"
echo "       ③ 0x5A/0x5B 有 ACK 但读不通  => ★ 器件在！只是读法待定"
echo "       ④ 0x5A/0x5B 无 ACK（对照通过）=> 不在主机这条总线（或 power-down / 地址不同）"
echo "       ⑤ 枚举出的 ACK 地址表        => 主机总线上到底还挂了谁"
echo
echo "  P6  原生报文                 => 与 Windows 侧报文交叉验证字段布局"
echo "       （现在跑在 [5.6] 回绑之后 —— i2c_hid 解绑时 hidraw 节点会消失，"
echo "         不回绑则 P6 必然采不到）"
echo
echo "  环境自检（先看这几行，判据才有意义）："
echo "       · P1[1.0] 依赖检查：i2ctransfer / i2cget 是否就绪？缺则 P5 不可用"
echo "       · P5 前的『备用指点设备检测』：未找到且未加 --i-have-usb-mouse ⇒ P5 被跳过"
echo "       · P5[5.0a] 对照 A（解绑前）与 [5.2] 对照 B（解绑后）的失败文本不同含义："
echo "           - NACK('Remote I/O error')        => 设备不应答"
echo "           - lost arbitration / 忙            => 总线被占用"
echo
echo "  ★ 拿到日志后：先看 P5 的①。① 不通，P5 全部作废。"
echo "  ★ 若 P5 曾执行 power/control=on，重启即复原（Live 环境本就不落盘）。"
echo "==============================================================="
say "完成。日志： $OUT"
