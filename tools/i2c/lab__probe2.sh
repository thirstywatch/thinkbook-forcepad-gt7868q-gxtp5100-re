#!/bin/bash
# probe2.sh -- 解绑优先版 I2C 只读探测（2026-10-03）
# =====================================================================
# 目标：回答"本机 AW86927（0x5A/0x5B）到底在不在【主机 I2C 总线】上"
#
# ★ 与旧 probe.sh 的三个关键差别（旧版有致命顺序问题，见 §5.1）：
#   1) 【先解绑 i2c_hid 再扫描】—— 旧版在 i2c_hid 绑着 0x2C 时全地址扫描，
#      与项目记录的"i2cdetect 崩内核"自洽。这是本条判据两周没做出来的直接原因。
#   2) 【只扫目标总线】—— 按 ACPI 路径 \_SB_.PC00.I2C0 + 客户端 i2c-N-002c 双判据定位，
#      不再"扫全部适配器"。
#   3) 【先两点、后全表】—— 先只探 0x5A..0x5B 拿到二元判据，再决定要不要全表。
#
# ★ 全程只读：只用 i2cdetect(-r) 与 i2cget。绝不 i2cset。
# ★ 收尾恢复 i2c_hid 绑定，不留状态。
#
# 用法：
#   sudo bash probe2.sh 2>&1 | tee probe2.log
# =====================================================================

set -u
LOG_TAG="[probe2]"
say() { echo "$LOG_TAG $*"; }
hr()  { echo "---------------------------------------------------------------"; }

if [ "$(id -u)" != "0" ]; then
  echo "[!] 需要 root： sudo bash probe2.sh 2>&1 | tee probe2.log"
  exit 1
fi

echo "==============================================================="
echo " AW86927 I2C 只读探测 (probe2, 解绑优先)"
echo " 时间: $(date)"
echo "==============================================================="

# ---------------------------------------------------------------- 1
echo
say "[1] 工具检查"
if ! command -v i2cdetect >/dev/null 2>&1; then
  say "    i2c-tools 缺失，尝试安装..."
  ( apt-get install -y i2c-tools 2>&1 | tail -3 ) || true
fi
for t in i2cdetect i2cget i2cset; do
  printf "    %-10s : %s\n" "$t" "$(command -v "$t" || echo '缺失')"
done
modprobe i2c-dev 2>/dev/null || true

# ---------------------------------------------------------------- 2
echo
say "[2] 目标总线定位（双判据）"

BUS=""
# 判据 A：ACPI 路径 == \_SB_.PC00.I2C0
for a in /sys/bus/i2c/devices/i2c-*; do
  [ -e "$a" ] || continue
  n="${a##*-}"
  adev="$(basename "$(readlink -f "$a/firmware_node" 2>/dev/null)" 2>/dev/null)"
  [ -n "$adev" ] || continue
  apath="$(cat "/sys/bus/acpi/devices/$adev/path" 2>/dev/null)"
  case "$apath" in
    *PC00.I2C0*)
      BUS="$n"
      say "    判据A命中: i2c-$n  ACPI=$apath  name=$(cat "$a/name" 2>/dev/null)"
      ;;
  esac
done

# 判据 B：该适配器上存在客户端 0x2C（触控板）
if [ -z "$BUS" ]; then
  for a in /sys/bus/i2c/devices/i2c-*; do
    [ -e "$a" ] || continue
    n="${a##*-}"
    if [ -e "/sys/bus/i2c/devices/i2c-$n-002c" ]; then
      BUS="$n"
      say "    判据B命中: i2c-$n 上存在 0x2C 客户端（触控板）"
    fi
  done
fi

# 判据 C：兜底——找名字像 Intel/designware 的适配器
if [ -z "$BUS" ]; then
  say "    [!] A/B 均未命中，列出全部适配器："
  for a in /sys/bus/i2c/devices/i2c-*; do
    [ -e "$a" ] || continue
    printf "        i2c-%s : %s\n" "${a##*-}" "$(cat "$a/name" 2>/dev/null)"
  done
  echo
  say "    请从上面挑出触控板所在的那条，然后： BUS=<编号> ; 手动跳到 [4]"
fi

if [ -z "$BUS" ]; then
  say "    [!] 无法自动定位目标总线。已做只读枚举，未做任何扫描。"
  echo
  say "[附] 全部 I2C 客户端（未绑定时会出现裸设备）"
  for d in /sys/bus/i2c/devices/*; do
    [ -e "$d" ] || continue
    printf "    %-20s : %s\n" "$(basename "$d")" "$(cat "$d/name" 2>/dev/null)"
  done
  exit 0
fi

echo
say "    ★ 目标总线 = i2c-$BUS"
say "    i2c_hid 客户端状态："
ls -l "/sys/bus/i2c/devices/i2c-$BUS-002c" 2>/dev/null || say "      (无 i2c-$BUS-002c 节点)"

# ---------------------------------------------------------------- 3
echo
hr
say "[3] ★ 先解绑 i2c_hid（关键步骤）"
hr
# 说明：i2c_hid 在 0x2C 上时，控制器/总线处于被占用状态；此时扫描既可能失败，
#       也可能与设备的进行中事务冲突。必须先解绑再扫。
for d in /sys/bus/i2c/drivers/*/; do
  [ -e "$d" ] || continue
  drv="$(basename "$d")"
  case "$drv" in
    i2c_hid* | hid* )
      if [ -e "$d/i2c-$BUS-002c" ]; then
        say "    unbind: $drv  <- i2c-$BUS-002c"
        echo "i2c-$BUS-002c" > "$d/unbind" 2>/dev/null && say "      ok" || say "      失败(可忽略)"
      fi
      ;;
  esac
done
# 再顺手解绑它上面的 HID 客户端（不致命，但更干净）
if [ -d /sys/bus/hid/drivers ]; then
  for d in /sys/bus/hid/drivers/*/; do
    [ -e "$d" ] || continue
    for dev in "$d"*; do
      [ -e "$dev" ] || continue
      case "$(basename "$dev")" in
        *GXTP5100* | *MSFT0001*)
          say "    unbind HID: $(basename "$d") <- $(basename "$dev")"
          echo "$(basename "$dev")" > "$d/unbind" 2>/dev/null || true
          ;;
      esac
    done
  done
fi
sleep 1
say "    解绑后状态："
ls -l "/sys/bus/i2c/devices/i2c-$BUS-002c" 2>/dev/null || say "      i2c-$BUS-002c 已无绑定（或本就不存在）"

# ---------------------------------------------------------------- 4
echo
hr
say "[4] ★ 第一枪：只探 0x5A..0x5B（最小扰动）"
hr
i2cdetect -y -r "$BUS" 0x5a 0x5b 2>&1

# ---------------------------------------------------------------- 5
echo
hr
say "[5] 定点读 AW86927 身份：寄存器 0x57 / 0x58  （期望 0x92 / 0x70）"
say "    依据：aw86927.c  regmap{reg_bits=8,val_bits=8,max_register=0x80} ⇒ i2cget 单字节地址即可"
hr
for a in 0x5a 0x5b; do
  hi="$(i2cget -y "$BUS" "$a" 0x57 2>&1)"
  lo="$(i2cget -y "$BUS" "$a" 0x58 2>&1)"
  ch="$(i2cget -y "$BUS" "$a" 0x0d 2>&1)"   # 顺手读一个非 0x00 的寄存器做"确实在应答"对照
  printf "    %s : 0x57=%s  0x58=%s  (0x0d=%s)\n" "$a" "$hi" "$lo" "$ch"
  if [ "$hi" = "0x92" ] && [ "$lo" = "0x70" ]; then
    echo
    echo "    ★★★★★ 确认是 AW86927 —— 它在【主机 I2C 总线】上！"
    echo "          ⇒ 「隔着 GT7868Q」这个问题不存在，Linux 侧可以直接驱动它。"
    FOUND=1
  fi
done

# ---------------------------------------------------------------- 6
echo
hr
say "[6] 全表（只读 -r，不含保留段 -a）—— 找 第二个从设备"
hr
i2cdetect -y -r "$BUS" 2>&1

# ---------------------------------------------------------------- 7
echo
hr
say "[7] 收尾：恢复 i2c_hid 绑定"
hr
for d in /sys/bus/i2c/drivers/*/; do
  [ -e "$d" ] || continue
  case "$(basename "$d")" in
    i2c_hid*)
      if [ -e "$d/bind" ]; then
        echo "i2c-$BUS-002c" > "$d/bind" 2>/dev/null && say "    rebind ok: $(basename "$d")" || true
      fi
      ;;
  esac
done
sleep 1
ls -l "/sys/bus/i2c/devices/i2c-$BUS-002c" 2>/dev/null || say "    (i2c-$BUS-002c 仍无绑定)"
say "    触控板是否恢复：运行  dmesg | tail -20  看有没有 hid 重新枚举"

# ---------------------------------------------------------------- 8
echo
hr
say "[8] 附加上下文（排错用）"
hr
echo "    DMI: $(cat /sys/class/dmi/id/product_name 2>/dev/null) / $(cat /sys/class/dmi/id/product_version 2>/dev/null)"
echo "    内核: $(uname -r)"
echo "    ACPI 路径核对:"
for a in /sys/bus/i2c/devices/i2c-*; do
  [ -e "$a" ] || continue
  adev="$(basename "$(readlink -f "$a/firmware_node" 2>/dev/null)" 2>/dev/null)"
  printf "      i2c-%-4s %-28s %s\n" "${a##*-}" "$(cat "$a/name" 2>/dev/null)" "$(cat "/sys/bus/acpi/devices/$adev/path" 2>/dev/null)"
done
echo "    dmesg 里的 i2c/hid 报错（最近）:"
dmesg 2>/dev/null | grep -iE "i2c|hid" | tail -15

echo
echo "==============================================================="
echo " 完成。请把 probe2.log 全文发回。"
echo " 判据："
echo "   扫到 0x5A/0x5B 且 0x57=0x92 0x58=0x70  => 赢了（路径1成立）"
echo "   全表只有 0x2C                            => 触觉 IC 在私有总线上"
echo "==============================================================="
