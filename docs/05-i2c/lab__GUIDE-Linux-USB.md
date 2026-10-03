# Linux Live USB 探测 AW86927 · 傻瓜操作手册

> 目标：确认 **AW86927（丝印 `CA4F`）的 I²C 从地址 `0x5A` 是否在主机可见的 I²C 总线上**
> 风险：**零**。全程 live USB，**不装系统、不碰硬盘、不动 Windows**
> 你要做的：插 U 盘 → 开机选 U 盘 → 粘贴一段命令 → 看结果

---

## 为什么必须走这一步

Windows 上我们**已经确认**：
- ❌ ACPI 里没有触觉通路（762 KB 全反编译，触觉关键词 0 命中）
- ❌ 不在 PCH SMBus 上（`0x5A`/`0x5B` 无应答，而有阳性对照 `0x44`）
- ❌ RWE / PawnIO 都没有"原生 I²C"通道去碰 `7E78` 那条 Intel Serial IO I²C

⇒ **Linux 是唯一能直接"看"那条 I²C 总线的办法**（内核自带 I²C 驱动，不需要签名、不需要装任何东西）。

---

# 第一步：做 U 盘（约 15 分钟，主要在下载）

## 1.1 下载 Ubuntu

浏览器打开：

**https://releases.ubuntu.com/24.04/**

下载列表里找 **`ubuntu-24.04.x-desktop-amd64.iso`**（约 5–6 GB）

> 中文站镜像更快：**https://mirrors.tuna.tsinghua.edu.cn/ubuntu-releases/24.04/**
> 文件名类似 `ubuntu-24.04.3-desktop-amd64.iso`

## 1.2 下载 Rufus（写 U 盘的工具）

**https://rufus.ie/zh/**

下载 **`rufus-4.x.exe`**（绿色，不用装）

## 1.3 写入 U 盘

1. **插上你的 U 盘**（≥8GB，**里面数据会被清空**，先备份）
2. 双击 `rufus.exe`
3. **设备**：选你的 U 盘 ⚠️ **别选错盘！**
4. **引导类型选择** → 点右边的 **"选择"** → 选刚下的 `ubuntu-24.04.x-desktop-amd64.iso`
5. 分区类型 `GPT`、目标系统 `UEFI`（默认即可）
6. 点 **"开始"** → 如果问"ISOHybrid 模式"选 **"以 ISO 映像模式写入"**
7. ⚠️ **如果弹"是否需要下载 ldlinux 等文件"** → 点 **"是"**
8. 等进度条跑完（约 5–10 分钟）

---

# 第二步：重启进 Linux（约 3 分钟）

1. **先保存好你在 Windows 里的东西**（虽然不动硬盘，但保险）
2. **重启电脑**，在开机出现 **Lenovo 标志时，连续按 `F12`**
3. 出现启动菜单，选 **`UEFI: <你的U盘名字>`** 那一项
4. 出现 Ubuntu 界面后，选 **`Try Ubuntu`**（试用，**不要**点 Install）
5. 等桌面出来（约 1–2 分钟）

> **如果 F12 没反应**：开机按 `F2` 或 `Fn+F2` 进 BIOS，把 `Secure Boot` 临时关掉，或把 USB 调到启动顺序第一位。

---

# 第三步：跑探测（约 2 分钟）

桌面上应该有个黑底的 **`Terminal`** 图标（或按 `Ctrl+Alt+T`）。

**把下面这整段复制，粘贴到终端里，回车：**

```bash
sudo apt-get update -qq; sudo apt-get install -y i2c-tools
for a in 0x5a 0x5b; do
  echo "=== 探地址 $a (只读) ==="
  for b in $(ls /sys/class/i2c-dev/ | sed 's/i2c-//'); do
    n=$(cat /sys/class/i2c-dev/i2c-$b/name)
    if i2cdetect -y -r $b 2>/dev/null | awk '{for(i=2;i<=NF;i++) if($i=="5a"||$i=="5b") f=1} END{exit !f}'; then
      echo "  ★ i2c-$b ($n): $a 有应答!"
      echo "     0x57 = $(i2cget -y $b $a 0x57 2>&1)   (期望 0x92)"
      echo "     0x58 = $(i2cget -y $b $a 0x58 2>&1)   (期望 0x70)"
    else
      echo "  i2c-$b ($n): 无"
    fi
  done
done
echo
echo "=== 所有 I2C 适配器 ==="
for d in /sys/class/i2c-dev/i2c-*; do n=$(basename $d|sed s/i2c-//); echo "i2c-$n: $(cat $d/name)"; done
echo
echo "=== 触控板在哪条总线 ==="
for drv in i2c_hid_acpi i2c_hid_of i2c_hid; do
  d=/sys/bus/i2c/drivers/$drv; [ -d $d ] || continue
  for dev in $d/*; do b=$(basename $dev); case $b in bind|unbind|uevent|module|new_id) continue;; esac
    echo "  $drv -> $b  ($(cat $dev/name 2>/dev/null))"; done
done
```

**粘贴小技巧**：终端里粘贴是 **`Ctrl+Shift+V`**，不是 `Ctrl+V`。

---

# 第四步：看结果

屏幕上会直接打印。**把整个终端窗口截图发我就行。**

三种可能：

| 结果 | 含义 |
|---|---|
| `★ i2c-0: 0x5a 有应答!  0x57 = 0x92  0x58 = 0x70` | ★★★ **确认！AW86927 在主机可见的 I²C 上** ⇒ 纯软件路成立 |
| 某条总线 `0x5a 有应答`，但 `0x57/0x58` 不是 `92/70` | 那个地址是别的设备 |
| 全部 `无` | 芯片在主机够不到的地方 ⇒ 只剩拆机 |

---

# 第五步：回 Windows

**直接重启**，把 U 盘拔了，正常进 Windows 就行。
**什么都没改**：没装系统、没动硬盘、没改 BIOS 设置之外的任何东西。

---

# 常见问题

**Q: 面板上触控板在 Linux 里能用吗？**
A: 大概率能用（Linux 有 Goodix 支持）。不能用也没关系，我们只用键盘和终端。

**Q: 会不小心装到硬盘上吗？**
A: 只要选 **`Try Ubuntu`**（不是 `Install Ubuntu`），就只在内存里跑，**不碰硬盘**。

**Q: 网络连不上怎么办？**
A: `apt-get install i2c-tools` 需要网络。如果连不上：
- 用手机 USB 共享网络给电脑
- 或者告诉我，我给你一个**不用装任何东西**的纯 bash 版本（直接读写 `/dev/i2c-*`，但需要一点点额外步骤）

**Q: 扫描会不会把触控板搞坏？**
A: `i2cdetect` 是标准只读探测，全世界的维修/调试都用它。**但注意**：如果某条总线上正跑着驱动，`i2cdetect` 可能被拒绝（resource busy）——那种情况告诉我，我给你**先解绑驱动再扫**的命令。

---

# 我这边准备的东西

`<LAB>\touchpad-lab\linux\probe.sh`

这是**完整版脚本**（比上面粘贴的详细得多，会 dump 所有适配器、所有已枚举设备）。
如果你愿意把它拷进 U 盘，也可以在 Linux 里直接 `sudo bash probe.sh`。

---

# 清单（照着勾）

- [ ] 1. 备份 U 盘里的东西
- [ ] 2. 下载 Ubuntu ISO（5–6 GB）
- [ ] 3. 下载 Rufus
- [ ] 4. Rufus 写入 U 盘
- [ ] 5. 重启，开机按 `F12`，选 U 盘
- [ ] 6. 选 **`Try Ubuntu`**
- [ ] 7. 打开终端（`Ctrl+Alt+T`），粘贴那段命令
- [ ] 8. 截图发我
- [ ] 9. 重启回 Windows，拔 U 盘
