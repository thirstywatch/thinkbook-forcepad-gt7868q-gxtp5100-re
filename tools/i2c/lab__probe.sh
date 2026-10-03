#!/bin/bash
# probe.sh -- 在 Linux live USB 上只读扫描 I2C，找 AW86927 触觉驱动芯片
# ---------------------------------------------------------------------
# AW86927 身份标识：I2C 从地址 0x5A（或 0x5B），寄存器 0x57/0x58 == 0x92 0x70
#
# ★ 全程只读。绝不写任何 I2C 寄存器。
#
# 用法：
#   sudo bash probe.sh 2>&1 | tee probe.log

echo "==============================================================="
echo " AW86927 I2C 只读探测"
echo " 时间: $(date)"
echo "==============================================================="
echo

if [ "$(id -u)" != "0" ]; then
  echo "[!] 需要 root。请用: sudo bash probe.sh"
  exit 1
fi

# ---------- 1. 工具 ----------
echo "[1] 检查 i2c-tools"
if ! command -v i2cdetect >/dev/null 2>&1; then
  echo "    未安装，尝试安装 (离线镜像通常可用)..."
  (apt-get install -y i2c-tools 2>&1 | tail -3) || true
fi
for t in i2cdetect i2cget; do
  printf "    %-12s: %s\n" "$t" "$(command -v $t || echo '缺失')"
done

# ---------- 2. 内核 I2C 驱动 ----------
echo
echo "[2] 已加载的 I2C 相关内核模块"
lsmod | grep -E 'i2c' | head -20

# ---------- 3. 适配器 ----------
echo
echo "[3] I2C 适配器列表 (/sys/class/i2c-dev)"
if [ -d /sys/class/i2c-dev ]; then
  for d in /sys/class/i2c-dev/i2c-*; do
    [ -e "$d" ] || continue
    n=$(basename "$d")
    name=$(cat "$d/name" 2>/dev/null)
    printf "    %-8s : %s\n" "$n" "$name"
  done
else
  echo "    [!] /sys/class/i2c-dev 不存在"
fi

# ---------- 4. I2C 设备树（客户端） ----------
echo
echo "[4] 已枚举的 I2C 客户端设备"
if [ -d /sys/bus/i2c/devices ]; then
  for d in /sys/bus/i2c/devices/*; do
    [ -e "$d" ] || continue
    n=$(basename "$d")
    dn=$(cat "$d/name" 2>/dev/null)
    printf "    %-16s : %s\n" "$n" "$dn"
  done
fi

# ---------- 5. 找出触控板在哪条总线 ----------
echo
echo "[5] 定位触控板 (i2c-hid / Goodix)"
TP_BUS=""
TP_DEV=""
if [ -d /sys/bus/i2c/drivers ]; then
  for drv in i2c_hid_acpi i2c_hid_of i2c_hid; do
    d=/sys/bus/i2c/drivers/$drv
    [ -d "$d" ] || continue
    for dev in "$d"/*; do
      [ -e "$dev" ] || continue
      b=$(basename "$dev")
      case "$b" in
        bind|unbind|uevent|module|new_id) continue ;;
      esac
      printf "    driver=%-14s device=%-16s name=%s\n" "$drv" "$b" "$(cat "$dev/name" 2>/dev/null)"
      bus=$(echo "$b" | cut -d- -f1)
      addr=$(echo "$b" | cut -d- -f2)
      if [ -z "$TP_BUS" ]; then TP_BUS="$bus"; TP_DEV="$drv/$b"; fi
    done
  done
fi
if [ -n "$TP_BUS" ]; then
  echo "    => 触控板总线: i2c-$TP_BUS   设备: $TP_DEV"
else
  echo "    (!) 未找到 i2c-hid 设备，稍后改为全总线扫描"
fi

# ---------- 6. 扫描全部适配器（只读） ----------
echo
echo "==============================================================="
echo "[6] 只读扫描全部 I2C 适配器"
echo "==============================================================="
for d in /sys/class/i2c-dev/i2c-*; do
  [ -e "$d" ] || continue
  n=$(basename "$d" | sed 's/i2c-//')
  name=$(cat "$d/name" 2>/dev/null)
  echo
  echo "---------------- i2c-$n  ($name) ----------------"
  # -y 免确认；-r 只读探测；-q 快速；-a 全地址
  i2cdetect -y -r -a "$n" 2>&1 | head -24
done

# ---------- 7. 定向检查 AW86927 ----------
echo
echo "==============================================================="
echo "[7] 定向检查 AW86927: 0x5A / 0x5B 的 CHIPID (0x57/0x58)"
echo "    期望: 0x57=0x92  0x58=0x70"
echo "==============================================================="
for d in /sys/class/i2c-dev/i2c-*; do
  [ -e "$d" ] || continue
  n=$(basename "$d" | sed 's/i2c-//')
  name=$(cat "$d/name" 2>/dev/null)
  for a in 0x5a 0x5b; do
    det=$(i2cdetect -y -r "$n" 2>/dev/null | awk -v a="${a#0x}" '
      { for (i=2;i<=NF;i++) if ($i==a || $i==toupper(a)) found=1 }
      END { print found?"ACK":"--" }')
    if [ "$det" = "ACK" ]; then
      hi=$(i2cget -y "$n" "$a" 0x57 2>&1)
      lo=$(i2cget -y "$n" "$a" 0x58 2>&1)
      echo "    ★ i2c-$n ($name) 地址 $a 有应答!  0x57=$hi  0x58=$lo"
      if [ "$hi" = "0x92" ] && [ "$lo" = "0x70" ]; then
        echo "    ★★★ 确认是 AW86927 !!!"
      fi
    else
      echo "    i2c-$n: $a 无应答"
    fi
  done
done

# ---------- 8. 附加：读 EC 侧信息（可选） ----------
echo
echo "[8] 附加信息"
echo "    DMI 机型: $(cat /sys/class/dmi/id/product_name 2>/dev/null)"
echo "    内核: $(uname -r)"
echo "    触控板 HID:"
ls /sys/bus/hid/devices/ 2>/dev/null | head -20

echo
echo "==============================================================="
echo " 完成。把上面的输出（或 probe.log）发回。"
echo "==============================================================="
