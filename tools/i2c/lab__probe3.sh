#!/bin/bash
# probe3.sh -- AW86927 主机总线可达性 · 只读探测（2026-10-13）
# =====================================================================
# 目标：回答"本机 AW86927（0x5A/0x5B）到底在不在【主机 I2C 总线】上"
#
# 与 probe2.sh 的四个关键差别（probe2 的三个真 bug，见 §1–§3）：
#   1) 【找到就停】—— 删掉"全表扫描"。[probe2] 定义了 FOUND=1 却从未使用，
#      即使已确认找到，仍会对 0x00–0x7F 全地址发事务 —— 而那正是
#      "i2cdetect 崩内核" 的经典触发条件。全表对判据零贡献，纯加风险。
#   2) 【加阳性对照】—— [probe2] 全程没有阳性对照，直接违反纪律第 12 条
#      （"没做阳性对照就下'读不到'的结论"）。本脚本用 0x2C 做通道活性对照：
#      对照不通 ⇒ 探针无效 ⇒ 立即中止，不改判"没找到"。
#   3) 【区分"无 ACK"与"有 ACK 但读失败"】—— 这两者在 [probe2] 里被一视同仁
#      存进同一个变量。而后者意味着【器件在】！这是本条判据最有价值的信号。
#
# 另：
#   4) 探测原语换成【零长度写】`i2ctransfer ... w0@0xNN`
#      = START + addr+W + STOP，不带寄存器地址、不读不写任何数据。
#      比 i2cdetect(-r)（SMBus Read Byte，会向器件要数据）和 i2cget 都干净。
#      AW86927 是纯 I²C 器件，`-r` 的 SMBus 语义对它并不合适。
#
# ★ 全程只读：只用 i2ctransfer 的 w0（零长度写）与 i2cget。绝不 i2cset、绝不写寄存器。
# ★ trap 保证异常退出也恢复 i2c_hid 绑定。
#
# 前置：
#   · 准备一个 USB 鼠标 —— 解绑期间触控板会失效
#   · 触控板是本机唯一指点设备：确认退路可用再跑
#
# 用法：
#   sudo bash probe3.sh 2>&1 | tee probe3.log
# =====================================================================

set -u
LOG_TAG="[probe3]"
say() { echo "$LOG_TAG $*"; }
hr()  { echo "---------------------------------------------------------------"; }

if [ "$(id -u)" != "0" ]; then
  echo "[!] 需要 root： sudo bash probe3.sh 2>&1 | tee probe3.log"
  exit 1
fi

# =============================== 全局状态 ===============================
BUS=""
UNBOUND=""
RC_CTRL=""
RC_5A=""
RC_5B=""
ACK_5A=0
ACK_5B=0

# ---------------------------------------------------------------- trap
restore_bind() {
  echo
  hr
  say "[R] 恢复 i2c_hid 绑定（trap：正常退出/异常退出都执行）"
  hr
  if [ -n "$UNBOUND" ]; then
    for d in /sys/bus/i2c/drivers/*/; do
      [ -e "$d" ] || continue
      case "$(basename "$d")" in
        i2c_hid*)
          if [ -e "$d/bind" ]; then
            echo "$UNBOUND" > "$d/bind" 2>/dev/null \
              && say "    rebind ok: $(basename "$d") <- $UNBOUND" \
              || say "    rebind 失败(可忽略): $(basename "$d")"
          fi
          ;;
      esac
    done
  else
    say "    （本脚本未解绑过任何客户端，无需恢复）"
  fi
  sleep 1
  if [ -n "$BUS" ]; then
    ls -l "/sys/bus/i2c/devices/i2c-$BUS-002c" 2>/dev/null \
      || say "    (i2c-$BUS-002c 仍无绑定 —— 跑 dmesg | tail -20 看 hid 是否重新枚举)"
  fi
}
trap restore_bind EXIT INT TERM

echo "==============================================================="
echo " AW86927 主机总线可达性 · 只读探测 (probe3)"
echo " 时间: $(date)"
echo "==============================================================="

# ---------------------------------------------------------------- 1
echo
say "[1] 工具检查"
for t in i2cdetect i2cget i2ctransfer; do
  printf "    %-14s : %s\n" "$t" "$(command -v "$t" || echo '缺失')"
done
if ! command -v i2ctransfer >/dev/null 2>&1; then
  say "    i2ctransfer 缺失 ⇒ 尝试安装 i2c-tools"
  ( apt-get install -y i2c-tools 2>&1 | tail -3 ) || true
fi
modprobe i2c-dev 2>/dev/null || true

# ---------------------------------------------------------------- 2
echo
hr
say "[2] 定位目标总线（判据：该适配器上存在 0x2C 客户端 = 触控板）"
hr
# 说明：probe2 的"判据 A（ACPI 路径匹配 *PC00.I2C0*）"极易静默失败 ——
#   readlink -f firmware_node 得到的是 PNP0C50:00 这类【ACPI 设备名】，
#   而 I2C0 在平台上的路径拼写（\_SB.PC00 vs \_SB.PCI0）并不统一。
#   ⇒ 本脚本不去"猜路径"，改以【0x2C 客户端存在】为唯一硬判据，
#     并把 ACPI 路径与适配器名作为【辅助信息】打印出来供人工核对。
for a in /sys/bus/i2c/devices/i2c-*; do
  [ -e "$a" ] || continue
  n="${a##*-}"
  nm="$(cat "$a/name" 2>/dev/null)"
  adev="$(basename "$(readlink -f "$a/firmware_node" 2>/dev/null)" 2>/dev/null)"
  apath="$(cat "/sys/bus/acpi/devices/$adev/path" 2>/dev/null)"
  printf "    i2c-%-4s %-28s %s\n" "$n" "$nm" "$apath"
  if [ -e "/sys/bus/i2c/devices/i2c-$n-002c" ]; then
    BUS="$n"
    say "    ★ 命中：i2c-$n 上存在 0x2C 客户端（触控板）"
  fi
done

if [ -z "$BUS" ]; then
  echo
  say "[!] 未找到带 0x2C 客户端的适配器 —— 无法继续。"
  say "    可能原因：触控板未枚举 / 已解绑 / 地址不是 0x2C。"
  say "    已做只读枚举，未发任何扫描命令。"
  exit 0
fi
say "    ⇒ 目标总线 = i2c-$BUS"

# ---------------------------------------------------------------- 3
echo
hr
say "[3] 基线：解绑【前】的 0x2C 状态"
hr
ls -l "/sys/bus/i2c/devices/i2c-$BUS-002c" 2>/dev/null || say "    (无该节点)"
CLIENT="i2c-$BUS-002c"

# ---------------------------------------------------------------- 4
echo
hr
say "[4] ★ 解绑 i2c_hid（关键步骤，probe2 的修正点）"
hr
for d in /sys/bus/i2c/drivers/*/; do
  [ -e "$d" ] || continue
  case "$(basename "$d")" in
    i2c_hid*)
      if [ -L "$d/$CLIENT" ] || [ -e "$d/$CLIENT" ]; then
        say "    unbind: $(basename "$d") <- $CLIENT"
        if echo "$CLIENT" > "$d/unbind" 2>/dev/null; then
          UNBOUND="$CLIENT"
          say "      ok"
        else
          say "      失败（继续，但阳性对照可能不通）"
        fi
      fi
      ;;
  esac
done
[ -n "$UNBOUND" ] || say "    （未发生解绑：i2c_hid 可能本就未绑定该客户端）"
sleep 2
say "    解绑后状态："
ls -l "/sys/bus/i2c/devices/$CLIENT" 2>/dev/null || say "      $CLIENT 已无绑定"

# ---------------------------------------------------------------- 5
echo
hr
say "[5] ★★★ 阳性对照（纪律 12：没有阳性对照的'读不到'是无效结论）"
hr
say "    原理：解绑后 0x2C 无人占用，对它做【零长度写】应当拿到 ACK。"
say "    判据：★ 对照不通 ⇒ 探针/总线无效 ⇒ 本脚本不再继续，也【不得】下'没找到'的结论。"
echo
CTRL_CMD="i2ctransfer -y $BUS w0@0x2c"
say "    \$ $CTRL_CMD"
RC_CTRL="$(i2ctransfer -y "$BUS" w0@0x2c 2>&1)"
RC_CTRL_RC=$?
printf "      退出码=%s  输出=%s\n" "$RC_CTRL_RC" "${RC_CTRL:-<空>}"
echo
if [ "$RC_CTRL_RC" != "0" ]; then
  say "    🔴 阳性对照【不通】⇒ 探针无效 ⇒ 立即中止。"
  say "       常见原因：总线仍被占用 / 器件未上电 / 事务格式不被接受。"
  say "       ⇒ 本次不得记录为'0x5A 没扫到'。"
  exit 0
fi
say "    ✅ 阳性对照通过 ⇒ 通道活着，下面的 NACK 才有意义。"

# ---------------------------------------------------------------- 6
echo
hr
say "[6] ★ 两点探测：0x5A / 0x5B（零长度写 = 纯地址探测，不发数据、不读数据）"
hr
probe_addr() {
  local a="$1"
  local out rc
  out="$(i2ctransfer -y "$BUS" "w0@$a" 2>&1)"; rc=$?
  printf "    %s : 退出码=%s  输出=%s\n" "$a" "$rc" "${out:-<空>}"
  return $rc
}
probe_addr 0x5a; ACK_5A=$?
probe_addr 0x5b; ACK_5B=$?
echo
if [ "$ACK_5A" = "0" ] || [ "$ACK_5B" = "0" ]; then
  say "    ★★★★★ 有 ACK —— 该地址【在主机 I2C 总线上】！"
  say "            但仍须读身份寄存器确认它是不是 AW86927（见 [7]）。"
else
  say "    ❌ 两个地址都无 ACK。"
  say "    ⚠️ 注意：'无 ACK' 有三种可能，不能直接判死："
  say "       (a) 真的不在主机这条总线"
  say "       (b) 在，但处于 power-down（数据手册：RSTN 低 = power-down）"
  say "       (c) AD 脚决定的地址不是 0x5A/0x5B"
fi

# ---------------------------------------------------------------- 7
echo
hr
say "[7] 身份读取（仅在 [6] 有 ACK 时执行）"
hr
if [ "$ACK_5A" != "0" ] && [ "$ACK_5B" != "0" ]; then
  say "    跳过：无 ACK，读寄存器没有意义（此处【不放】全表扫描 —— 那是 probe2 的致命步骤）。"
else
  say "    ★★ 关键：必须区分【无 ACK】与【有 ACK 但读失败】——"
  say "       后者意味着【器件在】，只是这个寄存器的读法/地址不对。这是本条判据最有价值的信号。"
  echo
  for a in 0x5a 0x5b; do
    for reg in 0x00 0x01 0x0a 0x0b 0x0c 0x0d 0x57 0x58 0x5a 0x5b 0x5c 0x5d; do
      out="$(i2cget -y "$BUS" "$a" "$reg" 2>&1)"; rc=$?
      printf "    %s reg %s : rc=%s  %s\n" "$a" "$reg" "$rc" "${out:-<空>}"
    done
    echo
  done
  say "    判读提示（寄存器地址来源待核，可能不准确 ⇒ 所以打一串而不是只赌 0x57/0x58）："
  say "      · 某个 reg 稳定返回同一非 0xFF 值 ⇒ 器件【在且可读】"
  say "      · 全部 rc≠0 但错误文本是 'Read failed' ⇒ 器件【在但读法不对】⇒ 仍算命中！"
  say "      · 全部 'Chip address not acknowledged' ⇒ 与 [6] 的 NACK 一致"
fi

# ---------------------------------------------------------------- 8
echo
hr
say "[8] 上下文（排错用）"
hr
echo "    DMI : $(cat /sys/class/dmi/id/product_name 2>/dev/null) / $(cat /sys/class/dmi/id/product_version 2>/dev/null)"
echo "    内核: $(uname -r)"
echo "    i2c 适配器 ACPI 归属:"
for a in /sys/bus/i2c/devices/i2c-*; do
  [ -e "$a" ] || continue
  adev="$(basename "$(readlink -f "$a/firmware_node" 2>/dev/null)" 2>/dev/null)"
  printf "      i2c-%-4s %-28s %s\n" "${a##*-}" "$(cat "$a/name" 2>/dev/null)" "$(cat "/sys/bus/acpi/devices/$adev/path" 2>/dev/null)"
done
echo "    dmesg（最近 i2c/hid 相关）:"
dmesg 2>/dev/null | grep -iE "i2c|hid" | tail -15

# ---------------------------------------------------------------- 9
echo
echo "==============================================================="
echo " 完成。请把 probe3.log 全文发回。"
echo " 判据（按顺序读）："
echo "   ① 阳性对照 0x2C 不通            => 本次无效，不得下结论"
echo "   ② 0x5A/0x5B 有 ACK + 身份对得上 => ★ 主机可达 AW86927（Path-1 成立）"
echo "   ③ 0x5A/0x5B 有 ACK 但读不通     => ★ 器件在！只是读法待定"
echo "   ④ 0x5A/0x5B 无 ACK（对照通过）  => 不在主机这条总线（或 power-down / 地址不同）"
echo "==============================================================="
