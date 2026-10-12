# 2026-10-08 · 外部项目对照（二）：`nwkyz/goodhaptic` 对本项目的独立交叉验证

> 触发：喆让再搜一遍 GitHub 触控板相关项目（"你再去看看github有没有触控板相关的项目了"）。
> 结果命中 **`nwkyz/goodhaptic`**（★，C，GPL-3.0，2026-07-07 建）——**同厂 GXTP5100、同代 HID feature 表**，
> 是本项目迄今找到的**唯一一个把 host 侧触觉控制真正做出来并在真机上跑通**的开源实现（Linux 侧）。
>
> **本轮全程只读**：只读 GitHub API / 源码 / 本地 HID 描述符 caps，**未发任何 report、未写设备**。
>
> ★ **第 22 轮追加（喆「测呗」）**：已在本机真机实测 `0x09` 写入 —— **通道打通（无禁用、无管理员）**，
> 4 次 `SetFeature` 全部被接受；**手感裁决待喆跑交互版**。详见 **§2d**。

---

## 0. 一句话

| # | 结论 | 强度 |
|---|---|---|
| 1 | `nwkyz/goodhaptic` 用 **HID Feature Report `0x09`（Haptics 0x0E / Intensity 0x23，0–100）** 控制振动力度；**本机同一条 usage 确实存在**（COL02 RID 0x09）| ★★★★★ |
| 2 | **★ 本机 RID 0x09 是【只写型】（Write-only）feature**：`HidD_GetFeature` 在 2..79 全部长度上均失败（err=122/1）| ★★★★★ 实测 |
| 3 | **goodhaptic 独立复现了同一现象**并写进 README 限制项："`HIDIOCGFEATURE` 对 report `0x08`、`0x09` 不生效，硬件不支持回读" | ★★★★★ |
| 4 | **★ goodhaptic 明确不主张"落盘"**：它的"开机恢复"是 **daemon 每次开机重写**，不是写 flash ⇒ **独立印证本项目 B12**（cfg 写入只在会话期有效）| ★★★★★ |
| 5 | **★★ goodhaptic 独立把 Report `0x0D`（Vendor 0xFF00/0xC4）标为"固件命令写入入口"、`0x0E` 标为"Vendor 双向通道"** ⇒ **第三方独立确认**本项目 Col04 的 `FF00/0001` 家族定位 | ★★★★ |
| 6 | **★ goodhaptic 的 Report 表与本机 caps 逐项高度重合**（10 项里 **9 项**本机都有，含 `0x05`/`0x07` 这两条**只以 button cap 声明**的），仅 `0x08`(0xB0) 确缺 ⇒ vendor 通道设计是**家族级**，不是单机型特例 | ★★★★★ |
| 6b | **★ 自我更正**：首版把 `0x05`/`0x07` 判为"本机缺"是**错的**（只抓了 value caps）⇒ **"caps 里没有"≠"设备没有"** | ★★★★★ |
| 7 | **★ `0x08` 点击阈值三档带真实克数（110/150/190 g）** ⇒ 给本项目 `+0x115` 阈值/档位之争提供了**外部量纲参照** | ★★★ |
| 8 | **模型差异**：goodhaptic 目标 `27C6:01E7`（USB `27c6:659a`，ThinkBook 16 G8+ IPD）；本机 `27C6:01E9`（GT7868Q）⇒ **同族不同代次**，report 表几乎全同 | ★★★★ |
| **9** | **★★★★★ 第 22 轮实测定案**：**`0x09` 就是本机的"震动开关"** —— 写 `0` → 震动消失（喆实测）；写 `100` → 恢复。**无需管理员、无需禁 Col03**。⇒ 登记表 **B14** | ★★★★★ |

---

## 1. 项目身份与内容

| 项 | 内容 |
|---|---|
| 仓库 | `nwkyz/goodhaptic` |
| 形态 | C（GTK4 + libadwaita GUI + systemd daemon `goodhapticd`），GPL-3.0 |
| 目标设备 | **Goodix GXTP5100**（USB `27c6:659a`，**HID `27C6:01E7`**），测试机 **Lenovo ThinkBook 16 G8+ IPD** |
| 接口 | `/dev/hidrawN`，**HID feature report 写入**（`ioctl(HIDIOCSFEATURE)`） |
| 关键文件 | `src/haptic.c`（力度/阈值写入）、`src/daemon.c`、`test/plan.md`（vendor 报文分析）、`test/probe_0*.py` |
| 自述 Windows 对照 | "通过 Procmon 确认 Windows 设置「触控板 → 震动力度」**本质上是写 HID feature report**" |

> ★ 这条"Windows 设置页 = 写 HID feature report"是**本项目的直接旁证**：
> 本项目曾用 `cfg` 通道/主观感受推 `+0x115`，而 goodhaptic 用 **Procmon 抓到了 OS 的真实行为** ——
> **Windows 的"震动力度"滑块就是 SetFeature RID 9**。⇒ 官方 UI 只暴露"强度旋钮"，**不暴露"触发"**。

---

## 2. ★★★ 本机实测：RID 0x09 确实在，且是【只写型】

### 2.1 caps 层（`lab__r22_feature_caps.py`，只读 access=0）

```
集合 COL02   UP=0x000D U=0x0005   In/Out/Feat = 40/0/737   声明 caps: feat=7 out=0
    RID=0x02  UP=0x000D  U=0x0059  logi[0..15]   4bit ×1   ← goodhaptic 0x02 (0x59 Pad Type)
    RID=0x02  UP=0x000D  U=0x0055  logi[0..15]   4bit ×1   ← goodhaptic 0x02 (0x55 Contact Max)
    RID=0x09  UP=0x000E  U=0x0023  logi[100..1]  8bit ×1   ← ★★ goodhaptic 0x09 (0x0E/0x23 Intensity)
    RID=0x06  UP=0xFF00  U=0x00C5  8bit ×256               ← goodhaptic 0x06 (0xC5 init blob)
    RID=0x0D  UP=0xFF00  U=0x00C4  8bit ×4                 ← goodhaptic 0x0D (0xC4 fw cmd)
    RID=0x0C  UP=0xFF00  U=0x00C6  8bit ×736               ← goodhaptic 0x0C (0xC6 vendor cfg)
    RID=0x0B  UP=0xFF00  U=0x00C7  8bit ×66                ← goodhaptic 0x0B (0xC7 vendor status)

集合 COL03   RID=0x03  UP=0x000D  U=0x0052  logi[0..10]  8bit ×2   ← goodhaptic 0x03 (0x52 Input Mode)

集合 COL04   [OUTPUT] RID=0x0E  UP=0xFF00  U=0x0000 / 0x0001   8bit ×1 ×2   ← 本项目 I²C 直通通道
```

### 2.2 与 goodhaptic 报告表逐项对照

| goodhaptic Report | goodhaptic 说明 | 本机 | 位置 | 判定 |
|---|---|---|---|---|
| `0x02` 2B Get | 设备能力（0x55 Contact Max + 0x59 Pad Type） | ✅ **可读**，实测 `02 15` | COL02 RID 0x02 | 完全一致 |
| `0x03` 2B Set | Input Mode（0x0D/0x52）0=鼠标 3=PTP | ✅ | COL03 RID 0x03（`logi[0..10]`） | 一致 |
| `0x05` 2B Set | 选择性上报 Surface/Button Switch | ✅ **存在**（以 **button cap** 形式，见 §2.2b） | COL03 RID 0x05 `UP 0x0D / linkU 0x22` | **一致** |
| `0x06` 256B | Vendor init blob（0xFF00/0xC5） | ✅（实测可读，头 `FC 28 FE 84…`） | COL02 RID 0x06 | 完全一致 |
| `0x07` 2B Set | Latency Mode（0x0D/0x60） | ✅ **存在**（以 **button cap** 形式，见 §2.2b） | COL02 RID 0x07 `UP 0x0D / linkU 0x05` | **一致**（usage 与 goodhaptic 的 0x60 不同，见 §2.2b 注） |
| `0x08` 2B Set | 点击力度阈值（0x0D/0xB0）1–3 档 | ❌ 本机 caps（value+button 两轮）**均无 0xB0** | — | **★ 本机确缺**（见 §4） |
| **`0x09` 2B Set** | **震动强度（0x0E/0x23）0–100** | **✅ 存在，只写** | **COL02 RID 0x09** | **★★★ 完全一致** |
| `0x0B` 66B | Vendor 状态（0xFF00/0xC7） | ✅ | COL02 RID 0x0B | 完全一致 |
| `0x0C` 736B | Vendor 配置（0xFF00/0xC6） | ✅ | COL02 RID 0x0C | 完全一致 |
| `0x0D` 4B | **固件命令（0xFF00/0xC4）** | ✅ | COL02 RID 0x0D | 完全一致 |
| `0x0E` 64B | Vendor 双向通道 In/Out | ✅（本项目已定性为 I²C 直通） | COL04 RID 0x0E（In/Out 65B） | 一致 |
| `0x04` Input | PTP 触摸数据 | （未查，非本轮目标） | — | — |
| `0x0F` | 未声明但 GET 全零 | （未查） | — | — |

⇒ **10 项可比中，本机命中 9 项（含最关键的 `0x09` 与全部 vendor `0xC4/C5/C6/C7`）**，
仅 `0x08`（0x0D/0xB0 点击阈值）未命中。**这是家族级协议，不是单机型特例。**

### 2.2b ★★ 补齐：`0x05` / `0x07` 在本机是【button cap】形式，不是 value cap

**首版（只抓 value caps）误判 `0x05`/`0x07` 为"本机缺"** —— 这是**本轮的一处自我更正**。
补抓 `HidP_GetButtonCaps`（`lab__r23_button_caps.py`）后可见：

```
集合 COL02
    [FEATURE] button caps = 1
        RID=0x07 UP=0x000D linkUP=0x000D linkU=0x0005 usage=0x0000 count=1
集合 COL03
    [FEATURE] button caps = 2
        RID=0x05 UP=0x000D linkUP=0x000D linkU=0x0022 usage=0x0000 count=1
```

⇒ **`0x07` 与 `0x05` 都在，只是以"button/switch"（开关型）声明**，
所以只抓 value caps 会漏掉。**这是"选择性上报开关"（Surface/Button Switch）的典型声明方式**，
与 goodhaptic 的 `0x05 = 选择性上报（Surface/Button Switch）`**语义完全吻合**。

| 项 | goodhaptic | 本机 | 吻合度 |
|---|---|---|---|
| `0x05` | 选择性上报 Surface/Button Switch（`0x0D/0x22` 类） | **COL03 RID 0x05，`UP 0x0D / linkU 0x22`** | ★★★ **完全吻合**（连 link usage `0x22` 都对上） |
| `0x07` | Latency Mode（goodhaptic 标 `0x0D/0x60`） | **COL02 RID 0x07，`UP 0x0D / linkU 0x05`** | ★★ **report ID 与 page 吻合**；link usage 本机报 `0x05`（集合根 usage），未直接见 `0x60`（见下注） |

> **注（不夸大）**：本机 `0x07` 的 button cap 里 `linkU=0x05`（= COL02 顶集合的 `Digitizers/0x05`），
> **没有**直接出现 goodhaptic 说的 `0x60`。这可能是（a）`0x60` 在更深的 Link Collection 里而 caps 未展开，
> 或（b）本机固件对 `0x07` 的用途与 goodhaptic 不同。**【未定】—— 不据此断言"本机 0x07 = Latency Mode"。**

⇒ **纪律第 107 条精神再得一次验证**：**"caps 里没有"≠"设备没有"** ——
换一种 caps 类型（value → button）就能翻案。**凡"缺失"结论必须声明抓取范围。**

### 2.3 ★ 只写型实证（`HidD_GetFeature` 失败）

```
句柄 = OK（Col02, access=0）
  RID=2   L=3    ✅ 02 15 EE
  RID=6   L=257  ✅ 06 FC 28 FE 84 40 CB 9A 87 0D BE 57 3C B6 70 09 88 07 97 2D
  RID=9   L=3    ❌ err=122   （ERROR_INSUFFICIENT_BUFFER）
  RID=11  L=67   ❌ err=122
  RID=12  L=737  ✅ 06 FC 28 FE 84 40 CB 9A …   ← 与 RID 6 头部相同
  RID=13  L=5    ❌ err=122
后续长度枚举：RID 9 / 11 / 13 在 L=2..79 上【全部失败】
```

**注**：先前的 `0E 20 00 00` 是**复用缓冲区残留**（上一次 Col04 读取的遗留），
按长度枚举后确认 RID 9 **在任何合理长度下都读不到** ⇒ **只写，不可回读**。

这与 goodhaptic README 的"限制"节**逐字吻合**：

> **无法读取当前力度/灵敏度**：`HIDIOCGFEATURE` 对 report `0x08`、`0x09` 不生效，硬件不支持回读

⇒ **两台不同机器、两个不同 HID ID（01E7 vs 01E9）、两套不同 OS（Linux hidraw vs Windows HidD），
观测到同一个"只写不可读"特性** —— 这已经是**跨平台、跨机型的高强度独立复现**。

---

## 2c. ★★★ 他到底怎么做的（`src/haptic.c` / `src/daemon.c` / `test/probe_08.py` 逐字核对）

> 本节回答喆的问题"那他是怎么做的呢"。以下全部为**源码逐字**核对结果。

### 2c.1 核心写入 = 3 行（`src/haptic.c: haptic_set`）

```c
int haptic_set(const char *device, int value)
{
    if (value < 0)  value = 0;
    if (value > 100) value = 100;       // 钳位 0..100

    int fd = open(device, O_RDWR);      // 打开 /dev/hidrawN，读写
    if (fd < 0) { perror("open hidraw"); return -1; }

    unsigned char buf[2];
    buf[0] = 0x09;                      // ★ report ID = 0x09
    buf[1] = value;                     // ★ 强度 0..100（1 个数据字节）

    int ret = ioctl(fd, HIDIOCSFEATURE(sizeof(buf)), buf);   // ★ 内核代发 Feature Report
    close(fd);
    return ret;
}
```

**⇒ 就这么简单。没有握手、没有 cfg、没有 I²C 直通、没有结果码。**
`HIDIOCSFEATURE(n)` = `_IOC(_IOC_WRITE|_IOC_READ, "H", 0x06, n)`，
**n = 报告总长度（含 RID 字节）**。

| 它 | 本项目对应 |
|---|---|
| `open(O_RDWR)` + `HIDIOCSFEATURE` | `CreateFileW` + `HidD_SetFeature` |
| `buf[0]=0x09, buf[1]=value` | 同一 RID / 同一语义 |
| 无结果码 | 无结果码（HID 层无回执） |

### 2c.2 它**不解决**的三个问题（这是最有价值的部分）

| 问题 | goodhaptic 的处理 | 出处 |
|---|---|---|
| **读不回** | `haptic_get()` **照调** `HIDIOCGFEATURE`，失败返回 `-1`；README 如实写"硬件不支持回读" | `haptic.c: haptic_get` |
| **写入易失** | **不解决，用 daemon 补偿**：`apply_config()` 在 daemon **启动时把保存的 4 个值重写一遍**；配置存 `/etc/goodhaptic.conf` | `daemon.c: apply_config` + `main()` |
| **主机主动触发** | **不做** —— 全代码库无"现在震一下"的命令 | 全 `src/` |

```c
/* daemon.c —— 开机补偿（不是写 flash！） */
static void apply_config(const GoodhapticConfig *cfg)
{
    if (!cfg->persist || !cfg->device[0]) return;
    haptic_set(cfg->device, cfg->strength);              // 重写强度
    haptic_set_threshold(cfg->device, cfg->threshold);   // 重写阈值
    haptic_set_input_mode(cfg->device, cfg->inputmode);
    haptic_set_selective_reporting(cfg->device, cfg->selective_surface,
                                   cfg->selective_button);
}
/* main(): */ config_load(&cfg); ... apply_config(&cfg);   // ★ 每次启动执行一次
```

> ★★★ **这就是它对"写入易失"的全部应对**：**不去攻 flash，而是每次开机重写。**
> 本项目想攻的"落盘"，它**直接放弃**。⇒ **B12（写入只在会话期有效）再添一条旁证**。

### 2c.3 ★★ 那张 report 表不是猜的 —— 它写了完整的描述符解析器

`haptic_get_resolution()` 是一段**逐 item 的 HID 描述符 TLV 解析器**：
读 `/sys/class/hidraw/hidrawN/device/report_descriptor`，
识别 `bSize/bType/bTag`，跟踪 `Usage Page(0x05)` / `Logical Maximum(0x26)` / `Report ID(0x85)`，
在 **Report 0x04 + Usage Page 0x01** 下取 `Usage 0x30 → max_x`、`0x31 → max_y`。

⇒ **它和我们 `lab__r14_xlogicalmax.py` 干的是同一件事**（只是它解原始描述符，我们读 caps）。
**两条独立的路都得到 `LogicalMax = 点数 − 1`。**

### 2c.4 ★★ 量纲（110/150/190 g）来自描述符，不是手感估的

`test/probe_08.py` 头部**逐字**给出 `0x08` 的描述符原样：

```
Report 0x08 decoded from HID descriptor:
  Usage Page:    Digitizers (0x0D)
  Usage:         0x00B0
  Physical Min:  110 g  (force)
  Physical Max:  190 g  (force)
  Logical Min:   1
  Logical Max:   3
  Report Size:   2 bits (Data) + 6 bits (Const padding)
  Type:          Feature (Data, Var, Abs)
```

⇒ **三档 110/150/190 g 是从 `Physical Min/Max` 读出来的**，不是"我感觉重/轻"。
**这正好符合本项目纪律第 109 条**（主观感受不能单独定名；要有描述符/规范级依据）。

### 2c.5 ★★★ 一个可直接迁移的方法论：**"唯一可用长度"验证**

`probe_08.py` 的读回逻辑**试 2 / 1 / 3 三种长度全失败**才下"不支持读回"的结论：

```python
for nbytes in (2, 1, 3):
    buf[0] = REPORT_ID
    try: fcntl.ioctl(fd, HIDIOCGFEATURE(nbytes), buf); return val
    except OSError: continue
print(f"GET_FEATURE not supported ... (hardware does not allow readback)")
```

⇒ **与本项目本轮做法完全同型**：我们对 RID 9 **枚举 L=2..79 全失败**才判"只写"。
**这正是规避"err=122 只是长度不对"这类假阴性的正确姿势。**

各报告的**精确长度**（含 RID）他逐个标定过：
| RID | 长度 | 布局 | 备注 |
|---|---|---|---|
| `0x03` Input Mode | 2 B | `[0x03, mode]` | ★ 描述符声明 2 字节数据，**固件只认第 1 字节**；3 字节被静默忽略 —— 与 Elan `0x300b` 内核修复 `73e7d63e` 同型 |
| `0x05` 选择性上报 | 3 B | `[0x05, (btn<<1)\|surf, 0]` | bit0=Surface Switch(0x57)、bit1=Button Switch(0x58)，后 14 bit Const |
| `0x07` Latency | 3 B | `[0x07, mode, 0]` | 1 bit 数据 + 15 bit Const |
| `0x09` 强度 | 2 B | `[0x09, 0..100]` | 只写 |
| `0x08` 阈值 | 2 B | `[0x08, 1..3]` | 只写（2 bit 数据 + 6 bit Const） |

> ★ **`0x03` 那条尤其值得记**：**"描述符声明的数据长度 ≠ 固件实际接受的长度"**。
> 本项目 RID 9 读回时"任何长度都 err=122"、以及 `lab__r18` 里 T2 段的可读性随相位变化，
> **都是同一族"长度/相位敏感"行为** —— 印证本项目需要"多长度枚举"才有资格下结论。

### 2c.6 它怎么找设备

`haptic_scan()` 遍历 `/sys/class/hidraw`，从 `device/uevent` 读 `HID_NAME=`。
**注意：它不做 VID/PID 白名单** —— 靠用户/daemon 配置里存 `device` 路径。
⇒ 与本项目"必须精确匹配 `GXTP5100`+`ColNN`"不同：**它赌"用户配对了就会对"，我们赌"路径选错会打挂板子"。**

---

## 3. ★★★ goodhaptic 的 vendor 报文分析（`test/plan.md`）逐条对照

goodhaptic 在 `test/plan.md` 里对 vendor 区做了**独立标注**，与本项目高度一致：

| goodhaptic 原文 | 本项目对应 | 判定 |
|---|---|---|
| "`0x0D` 不是查询接口，是**固件命令写入入口**（可能用于固件更新/配置下发）" | 本项目 Col04 `0E 20` = I²C 直通；`0x4160`/`0x96F8` = 官方 cfg_update 通道 | ★★ **方向一致**（都说 vendor C4/0x0D 是"下发入口"） |
| "`0x0E` \| Input/Output \| Vendor **双向通道**（64 bytes）" | 本项目 Col04 RID 0x0E（In/Out 65B）**就是** I²C 直通双向通道 | ★★★ **完全一致** |
| "潜在用途: 固件通信、校准、工厂模式" | 本项目的 `0x80/0x82/0x83/0x7D` 握手序列 = 配置下发 | ★★ 一致 |
| "Report `0x0D` 的 GET_FEATURE 不支持（EINVAL），SET_FEATURE 成功但为固件命令写入入口，**不可读**" | 本项目实测 RID 0x0D 对应 COL02 的 RID 13-ish 不可读；且 cfg 窗口只有 32 B 可读 | ★★★ **独立复现"不可读"** |
| "Report `0x06` 为 Win8 初始化 blob（Vendor 0xFF00/0xC5），Linux 内核 `hid-multitouch` probe 阶段自动读取以激活设备" | 本项目 caps 实测 RID 0x06 = `0xFF00/0xC5`，256B | ★★★ **完全一致** |
| "`0x0B`（0xC7）/`0x0C`（0xC6）同属 Vendor 0xFF00，内核 `case 0xff000000: return -1` 不作特殊处理" | 本项目 caps 实测 RID 0x0B=0xC7(66B)、RID 0x0C=0xC6(736B) | ★★★ **完全一致** |

> ★★★ **这是本项目第一次拿到"第三方独立实现"对同一 vendor 家族的逐条标注** ——
> 尤其 **`0x0D` = 固件命令写入入口** 这一条，与本项目"官方 cfg_update 通道（`0x80`→`0x96F8`→`0x83`→`0x7D`）"
> 是**从两条完全不同的路**（Linux hidraw feature vs Windows Col04 I²C 直通）指向**同一个结论**。

---

## 4. ★ `0x08` 点击阈值三档带真实克数 ⇒ 对 `+0x115` 之争的外部量纲

goodhaptic README 给出：

| 档位 | 力度阈值 | 体验 |
|---|---|---|
| 轻 | ~110 g | 轻触即可触发点击 |
| 中 | ~150 g | 中等力度 |
| 重 | ~190 g | 需要较重的按压 |

⇒ **三点重要信息**：

1. **官方阈值是 3 档离散**，不是连续域 —— 与本项目 `2026-10-08` 文档 §3.2 的"量化假说"（引用 `edimetia3d/GoodixNewtonTouchpad` 的 3 档 enum）**方向一致**；
2. **档间间距 ~40 g**，是**近似等差**的 —— 若本机 `+0x115` 也是同族阈值旋钮，其"0≈20≈120、60 反常、240 偏强"的**自相矛盾**就更可能是**感知噪声**（等差 3 档不该出现"相邻两档无差"）；
3. **goodhaptic 使用的是 `0x08`（0x0D/0xB0）**，而**本机 caps 里没有 0xB0** ⇒
   **本机可能把"阈值旋钮"实现在了别的通道**（例如 `cfg+0x115`），或者本机**根本不做这个旋钮**。
   ⇒ 这条**削弱**了"`+0x115` = 阈值档位"的类比（若厂商在本机也用 0xB0，cap 里应能见到）。

> ⚠️ **纪律第 109 条仍适用**：主观感受不能单独支撑字段定名。本节只提供**外部量纲参照**，不据此定名。

---

## 5. ★★★ "开机恢复" = daemon 重写 ⇒ 独立印证 B12（写入不落盘）

goodhaptic README 逐字：

> **开机恢复**：`系统`中开启`开机恢复设置`后，goodhapticd 会在**每次开机时自动将保存的力度和点击灵敏度写入硬件**，
> **防止重启后恢复默认值**。

⇒ **这是决定性的第三方旁证**：

- 如果写入是**落盘持久**的，就**不需要**"每次开机重写"；
- 正因为**写入是易失的（volatile）**，goodhaptic 才必须用 daemon 在每次开机时补写；
- 这与本项目 **B12**（`7E 00 02` 只代表 RAM 暂存区被改写；`0x7D` 后丢弃；IC 从 flash 重载）**机制完全一致**，
  只是 goodhaptic 在**另一条通道**（HID feature）上遇到同一个"易失"性质。

⇒ **本项目的 B12 从"本机单机结论"升级为"同代 Goodix 触觉接口的共性"**（两台机器、两种通道、两种 OS 同证）。

---

## 6. ★ 未命中项的最终处理（含一处自我更正）

| 项 | goodhaptic 用途 | 本机状态（value + button 两轮 caps 后） | 处理 |
|---|---|---|---|
| `0x05` 选择性上报 | Surface/Button 独立上报开关 | ✅ **存在**（COL03 RID 0x05 button cap，`0x0D/0x22`） | ~~本机缺~~ → **更正：存在** |
| `0x07` Latency Mode（0x60） | 正常/省电模式，内核自动管理 | ✅ **存在**（COL02 RID 0x07 button cap，`0x0D/0x05`） | ~~本机缺~~ → **更正：存在**（语义【未定】） |
| `0x08` 点击阈值（0xB0） | 三档 110/150/190 g | ❌ **确缺**（value caps 无，button caps 亦无） | **★ 本机确不做此旋钮**（见 §4） |
| `0x0F` 未声明但全零 | 用途不明 | 未查 | 【未定】无价值 |

> ★★ **本轮自我更正（重要）**：首版把 `0x05`/`0x07` 列为"本机缺"是**错的** ——
> 我只抓了 **value caps**，而这两条是 **button/switch** 形式的 **feature cap**。
> **教训（与纪律 107 同源）**：**"caps 里没有" ≠ "设备没有"**；下"缺失"结论**必须声明抓取范围**。
> 已补 `lab__r23_button_caps.py` 并把两轮 caps 都纳入对照。

---

## 7. 对项目主线（主机能否触发震动）的影响：**无正面突破，但强化了否定结论**

goodhaptic **也没有**解决"主机主动触发"：

- 它的"振动"功能全部是 **SetFeature `0x09`（力度偏好）** + **SetFeature `0x08`（阈值偏好）**；
- **没有任何**"现在震一下"的命令；
- README 的"振动"节只有：档位/无级调节、开关（关 = 把强度设 0）；
- ⇒ **goodhaptic 做的是"改旋钮"，不是"拉扳机"**，与本项目 §5.3 的判定完全一致。

**⇒ 三方（本项目 / Newton / goodhaptic）在三个不同机器上得出同一个结论：**
> **这块 IC 家族只暴露"强度/阈值"两个 device-initiated 偏好旋钮，不暴露 host-initiated 触发指令。**
> 主机能改的只是"设备自主触发时用多大劲/多难触发"，**不能在任意时刻命令它震**。

**唯一的"触发"路径仍是：**
1. 改 `0x09` 强度（非 0）+ 人手按压 → 设备自主触发；
2. 走 vendor 私有通道（本机 Col04 / goodhaptic 的 `0x0D`）—— **可能**有私有触发命令，但**无公开语义、不可通用**。

---

## 8. 由本轮新增的、值得做的动作（按价值排序）

| # | 动作 | 成本 | 预期 |
|---|---|---|---|
| **1** | ~~补抓本机 Col02 的 button caps~~ | — | **✅ 本轮已完成**（`lab__r23_button_caps.py`，见 §2.2b） |
| **2** | 把 goodhaptic 加入 `vendor-refs/links.md`（它是本项目**第一个可参照的 host 侧触觉实现**） | 低 | 资料完整性 |
| **3** | ★ **用 `0x09` 做一次"A/B 交叉验证"**：SetFeature 9=0 → 按压无震；9=100 → 按压强震；**中间夹 50** | **低（需 Col03 短暂禁用）** | **客观、可复现、能证伪** —— 这是本项目**第一次**有一条"主机写入 + 可观测行为"的**干净闭环**（若成立，把 `2026-10-05` 那条被降级的实证**从"存疑"救回"成立"**） |
| **4** | 若第 3 项成立 ⇒ 与 `cfg+0x115` 做对照：host 设 `0x09=0` 时，读 `cfg+0x115` 是否变化？⇒ 判定"两条通道是否指向同一物理存储" | 中 | 回答本项目最大的开放问题（通道归并） |

> **★ 第 3 项为什么值得做**：它是**唯一**一条
> "主机 → 设备写入（已确认真被接受）→ 人手触发 → 客观可感"的**完整闭环**，
> 且**有极端档（0 = 无震）可证伪**（满足纪律第 109 条：须有能证伪的极端档）。
> **风险可控**：只写 `0x09`（官方 Windows UI 就是这条），**不碰 `0x0E` 类、不碰 `0x0D`**。

---

## 9. 未定项（不夸大）

| 项 | 状态 |
|---|---|
| 本机 `27C6:01E9` 与 goodhaptic `27C6:01E7` 的 feature 表差异是否是"代次差异"还是"机型差异" | 【未定】需第二台机器的完整 caps（**本轮已证：两边 10 项里 9 项相同，仅 `0x08/0xB0` 不同**） |
| 本机 `0x05`/`0x07` 是否真的可用（声明在 ≠ 固件响应） | 【未定】声明已在（button cap），**响应未测** |
| 本机 `0x07` 是否等同 goodhaptic 的 Latency Mode（0x60） | 【未定】caps 里只见到 `linkU=0x05`，未见 `0x60` |
| 本机 `0x08`（0x0D/0xB0）确缺 ⇒ 本机把"阈值"放哪了 | 【未定】可能是 `cfg+0x115`；**但 §4 第 3 点说明这条类比被削弱** |
| 本机 `0x09` 的 `logi[100..1]` 反转声明是否影响写入语义 | 【未定】（goodhaptic 同 usage 是可用的 0–100） |
| 本机是否存在 host-initiated 触发私有命令 | 【未定】需逆向 `0x0D`（COL04 或 COL02 RID 13）；**红线不试** |

---

## 附：本轮证据来源

- `https://github.com/nwkyz/goodhaptic`（已读 `readme_zh.md` 全文 + `src/haptic.c` + `test/plan.md`）
- 本机实测：`tools/hid/lab__r22_feature_caps.py`（已修 3 处 bug，见下）
- 本项目既有定案：`docs/07-hid/lab__GXTP5100-HID-usage-report.md` §5、`docs/08-findings/2026-10-08-cfg写入只在会话期有效-7E0002不是落盘信号.md`（B12）
- 本轮**未执行任何设备写操作**（只有 `access=0` 的只读 caps 查询与 `HidD_GetFeature` 读尝试）

### 附注：`lab__r22_feature_caps.py` 本轮修的三处 bug

1. `HIDP_NOTRANGE` 只写了 3 个字段 ⇒ `sizeof(HIDP_VALUE_CAPS)` 偏小 ⇒ 数组步长错位、全表读空。**改为与 `lab__r14` 一致的完整 8×USHORT 布局**。
2. 路径过滤用 `'27c6' in p` ⇒ **0 命中**（设备接口路径里出现的是硬件 ID 串 **`gxtp5100`**，VID 只在 hardware id 里）。**改为 `gxtp5100 or 27c6`**。
3. `HIDP_STATUS_SUCCESS` 常量与比较方式统一为 `(st & 0xFFFFFFFF) == 0x00110000`。

---

## 2d. ★★★ 本机实测（第 22 轮）：`0x09` 写入通道**已打通**（无禁用、无管理员）

> 本节是喆「测呗」之后在**本机真机**上跑出的结果。**全程只写 `0x09`，未碰 `0x0E`/`0x0D`/cfg。**

### 2d.1 ★★★ 前置发现：**不需要禁用 Col03！**

逐 access 探测 `CreateFileW`：

```
COL01  QUERY=OK  READ=FAIL(5)   WRITE=OK   RW=FAIL(5)
COL02  QUERY=OK  READ=FAIL(32)  WRITE=OK   RW=FAIL(32)   ← ★ WRITE-only 可开！
COL03  QUERY/READ/WRITE/RW 全 OK
COL04  QUERY/READ/WRITE/RW 全 OK
```

- Col02 的 **READ 被 Col03 占用**（err=32 共享冲突），但 **WRITE 可单独打开**
- `HidD_SetFeature` **只需写权限** ⇒ **无需 `pnputil /disable-device`**
- ⇒ ★ **推翻历史操作前提**："必须先禁 Col03 才能写 Col02" **不成立**

### 2d.2 ★★★ 实测：4 次 `SetFeature(0x09, v)` **全部被接受**

| 步 | 写入 `0x09` | `HidD_SetFeature` 返回 |
|---|---|---|
| 1 | 100 | ✅ 被接受 |
| 2 | 50 | ✅ 被接受 |
| 3 | **0** | ✅ 被接受 |
| 4 | 100 | ✅ 被接受 |
| 收尾 | 100 | ✅ 被接受 |

- **无管理员权限、未禁用任何设备**
- 前置 / 后置健康检查**均通过**（COL02/COL04 在；`RID 0x09` 声明 `logi[100..1] 8bit×1` 不变）

⇒ **本机 Windows 上，写 `0x09` 这条路【通】的** —— 与 goodhaptic 的 Linux 路径**行为一致**。

> ⚠️ **重要限定**：`SetFeature` 返回 `TRUE` **只证明"报文被驱动/设备接受"**，
> **不证明"强度真的变了"** —— 这正是纪律 **第 108 条**（"通道有效" ≠ "参数有效"）在起作用。
> 判"旋钮是否有效"必须靠**人机闭环**（下方 2d.3）。

### 2d.3 ★★★★★ 人机闭环**已达成** —— `0x09` 就是震动开关

**过程**（第 22 轮）：
1. 写 `0x09 = 0` 后，喆反馈 **「没震动反馈了」** ← **决定性证据**
2. 核查系统层：四集合权限/caps **全部正常**（COL02 `R`=e32 是 Col03 占用，设计如此；`W`=OK）
   ⇒ **排除硬件损坏**，判定为**软件设置被改写**
3. 观察到：Windows 设置里 **「触觉点击」开关仍显示"开"** ⇒ **UI 与硬件脱钩**
   （因为 `0x09` 是**易失**的，外部改写不会同步到 UI 状态）
4. 写回 `0x09 = 100` → 恢复

**⇒ 结论（定案）**：

| 项 | 内容 |
|---|---|
| **地址** | **`HID COL02 · RID 0x09`**（`Haptics 0x0E / Intensity 0x23`，8bit，**0–100**） |
| **语义** | **震动强度 / 开关**（`0` = 完全静音 · `100` = 最强） |
| **写法** | `HidD_SetFeature(handle, [0x09, value], 2)`，句柄用 **`GENERIC_WRITE`** 打开 Col02 |
| **前置条件** | **无需管理员、无需禁用 Col03**（本轮实测推翻历史前提） |
| **读回** | ❌ 不可读（err=122，与 goodhaptic 一致） |
| **持久性** | ❌ 易失（不落盘，同 B12） |
| **与 Windows UI 的关系** | 设置里「触觉点击」开关**就是写这条**（关=0 / 开=100） |

**⚠️ 但仍不能"主机主动触发"** —— `0x09` 只是**设备自主触发时用多大劲**的旋钮；
「主机任意时刻命令它震」依旧不可能（缺 `0x0E/0x21 Manual Trigger` OUTPUT 报，见 §7）。

### 2d.4 ⚠️ 操作事故与教训（本轮）

- `lab__r24_haptic_ab.py` 的**自动推进版**（`printf '\n\n\n\n' | ...`）写入 `0x09=0` 后未及时写回，
  喆发现"没震动反馈了"；Windows UI 仍显示"开" ⇒ **UI/硬件脱钩**让人误判为"坏了"。
- **教训**：
  1. **写"开关型"字段的脚本，收尾必须无条件写回满值**（`finally` 块）
  2. **不得用"自动回车"掩盖人机闭环的缺失** —— 要么逐步等真人确认，要么明确标注"本轮未取手感"
  3. **动作类实验前须先写清"恢复路径"**（本例：写回 100 / UI 关开 / 重启设备）
- **恢复工具**：`tools/hid/lab__r25_haptic_restore.py`（`--cycle` 模拟 UI 关开 / 指定值 / `--report` 只读）

**风险**：不落盘（HID 层本来就易失，与 B12 一致）；最坏情况 = 设置被重置，重启设备即恢复默认。

### 2d.5 新增纪律：第 114 条

> **实测一个"开关型"字段时，必须包含【0 = 关】这一档。**
> 只测"大 vs 中"（如 10 vs 100）得到的"无差别"阴性，**不能断言通道无效** ——
> 开关型字段的可见效应在**极端档**（0 vs 满值），不在中间段。
> （这解释了第十二轮 `追加十五`"写 10/0/100 无效"为何与本次矛盾：旧测的操作条件不满足。）
