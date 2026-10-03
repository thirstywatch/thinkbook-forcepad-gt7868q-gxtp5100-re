# 关键人物与其研究 —— 调研结果

- 时间：2026-09-27 · 起因：前几轮认定这四个人的工作与两个项目高度重合，本轮逐个查实
- 结论先给：**他们四个正好构成"ThinkBook 2024 在 Linux 侧"的完整社区**，而且**已经存在一个以你这台机器（21LD）为中心的活跃帖子**

---

## 一、ty2 = **Terry Wong**

**这是四个人里最关键的** —— 他一个人写了你两个项目各自那一个"唯一相关仓库"。

### 仓库（他的全部硬件相关仓库就这两个）

| 仓库 | Star / Fork | 更新 | 内容 |
|---|---|---|---|
| **`ty2/goodix-gt7868q-linux-driver`** | **92 ★ / 24 fork** | 2025-08-02 | GT7868Q 的 report descriptor fixup（`rdesc[605]/[607]`），已进内核 **6.12+** |
| **`ty2/ideapad-laptop-tb2024g6plus`** | **50 ★ / 11 fork** | 2025-05-20 | 专为 ThinkBook 2024 G6+："solves problem with **laptop turning off after closing the lid**" |

他的其它仓库全是 Go/TypeScript/K8s 相关（oathkeeper、OPA、vCloud…）——**说明这两个硬件仓库是他为自己这台机器顺手做的**。

### 他是 LKML 上那个 sign-off
`[PATCH v2] HID: multitouch: Add report_fixup for Goodix GT7868Q touchpad`
→ `Signed-off-by: Terry Wong` + 指向 `ty2/goodix-gt7868q-linux-driver`

### ★ Issue #20 就是你的问题，开了 2 个月无人回答
> **标题**：*Does the ThinkBook 14 G6+ IMH support the Click force option?*
> **opened Jul 8, 2026 by navnforfun**
> 原文：*"Hey bro, I'm using a **ThinkBook 14 G6+ IMH** too. I've been trying to find the **Click Force** option ever since I got this model, but **after two years I still haven't found anything**. Have you ever looked into this? Did you find any solution? P.S. By Click Force sensitivity, I mean how hard you need to press to trigger a click on the touchpad. It can be set to Low, Medium, or High."*

**同一个机型、同一个问题、开了两个月、零回复。**
→ 这条最好用：**你可以直接把这个 issue 顶起来**（"我也是同机型，我在 Windows 侧已经确认 `Col02 OutputReportByteLength = 0`，所以 Low/Medium/High 走的是设备内部阈值"），既提供了别人没有的信息，也把问题抛给 ty2 和 24 个 fork 的作者。

### 他在中文论坛也下场
Arch Linux 中文论坛帖 13210 里，2024-06-09 有人写「**感谢 @ty2 触控板已解决**」并给出 AUR 包 `goodix-gt7868q-dkms`；ty2 自己在帖中回：「我把触控板的 fixup 放到 github 了，大家试试能用不」

### 状态
他的 GitHub 简介写着 **"On vacation"** —— 所以 issue 无人回可能只是他不在。

---

## 二、Rong Zhang（`i@rong.moe`，AOSC 社区）

| 项 | 内容 |
|---|---|
| **可确证的贡献** | 主笔 `platform/x86: ideapad-laptop: use usleep_range() for EC polling`（2025-05-25），`Closes: bugzilla 218771`。**这是把"2024 起 ThinkBook 高频轮询 EC → 硬关机"这条定性的补丁** |
| 补丁里的原话 | *"Some models (e.g., ThinkBook since 2024) have a low tolerance for being polled too frequently. Doing so may break the state machine in the EC, resulting in a **hard shutdown**."* |
| 同批的 verified 人 | Felix Yan、Eric Long、Mingcong Bai（AOSC）、Minh Le、Sicheng Zhu、Jianfei Zhang |
| **与压力板触觉的关联** | ⚠️ **未能独立复核**。`touchpad-lab` 的 `VIBRATION-CONCLUSION.md` 记载「Linux 上游 RFC（2026-06-16）由 Rong Zhang 发起，Dmitry Torokhov、Peter Hutterer 参与」。我实际检索到的上游 haptic 补丁系列作者是 **Jonathan Denose / Angela Czubak（Google · ChromiumOS）**，不是他。**这条暂按"项目文档记载、待核"处理** |
| 仍成立的判断 | 他确实是"ThinkBook 2024 EC"这条线的**技术权威**，且活跃于 AOSC（Arch 系社区）—— 与同机型社区同一批人 |

> 诚实说明：我不改这个结论，但把置信度降下来。**问他的第一句话应该是问 EC，不是问 haptic。**

---

## 三、Felix Yan（`felixonmars`）

| 项 | 内容 |
|---|---|
| 身份 | Arch Linux 开发者（Arch 中文社区知名） |
| **为什么关键** | **他手上有你这台机器** —— LKML 上他的 tested-by 原文：*"Tested to work as expected on my **ThinkBook 14 G6+ IMH (Intel model)**"* |
| 他的证词 | *"Sleep via power button and **close the lid**（which is bound to sleep as well）; Wake via shaking the mouse and **open lid**. **Both caused unexpected shutdown before** and fixed now."* |
| 对本项目的意义 | 他在**同一台机器上做过 EC 层面的真机验证** —— 关于"合盖时 EC 侧发生了什么"，他是当过事的人 |

---

## 四、ferstar

| 项 | 内容 |
|---|---|
| `ferstar/ideapad-laptop-tb` | DKMS 版 EC 修复；声明兼容 **ThinkBook 2024 16+ IMH / 14 G6+ AHP / 16 G6+ AHP** |
| `ferstar/lenovo-wmi-hotkey-utilities` | 联想 WMI 灯控，**已进上游（Linux 6.15+）**；列出 6 个 ThinkBook 机型 |
| 中文说明 | `github.com/ferstar/blog/issues/85`《修复联想笔记本 Linux 下合盖睡死与功能键异常关机问题》—— 完整安装步骤 |
| **一个有用的小工具** | 文中给出一条测试命令 **`lidctrl close`**（测试合盖响应） |
| 价值 | **中文沟通零障碍**，且他做的是"联想 WMI/EC 这两个接口在 ThinkBook 上的落地" |

---

## 五、★ 意外收获：以你这台机器为中心的社区节点

### 5.1 Arch Linux 中文论坛 · 帖 13210（**同机型 21LD**）

标题：《Thinkbook 14 2024 的兼容性问题：触控板不识别 & Wayland **合盖关机** & 声卡不工作》
发帖人 `xfzfflm`（2024-02-15），**neofetch 显示 `Host: 21LD ThinkBook 14 G6+ IMH`，`Kernel: 6.7.4-arch1-1`** —— 你的型号。

**帖中的硬信息**：

| 项 | 内容 |
|---|---|
| 触控板识别失败的原报错 | `hid-multitouch: probe of 0018:27C6:01E9.0007 failed with error -22`<br>`hid-multitouch ...: item 0 1 0 11 parsing failed` |
| 设备路径 | `GXTP5100:00`，`MODALIAS=acpi:GXTP5100:PNP0C50:` |
| 修好的包 | **AUR `goodix-gt7868q-dkms`** |
| 现成的 quirks 内容 | ```[Goodix GT7868Q]<br>MatchVendor=0x27C6<br>MatchProduct=0x01E9<br>AttrEventCode=-ABS_MT_PRESSURE;-ABS_PRESSURE;<br>AttrPalmPressureThreshold=600<br>AttrThumbPressureThreshold=1000``` |
| 合盖关机 | 该帖明确把它作为机型兼容问题列出（KDE on Wayland 合盖会关机；XOrg 无此问题） |
| 声卡 | 装 `sof-firmware` 解决 |

**这个帖子的价值**：它是**同机型用户的聚集地**，且 ty2 本人下场。**比 GitHub issue 活跃得多。**

### 5.2 libinput 1.31.0（2026-02）加了 Goodix 触控板 quirk

发布说明的 git shortlog：`Richie Roy Jayme (1): quirks: add quirk support for Goodix touchpad`
同时：**libinput 1.30.1 起处理 `INPUT_PROP_PRESSUREPAD`（内核 6.18）**，**内核 6.19 起该属性会自动设置**，不再需要逐机型 quirk。

### 5.3 ★★ 上游 haptic 触控板补丁系列（这是本轮最有用的技术收获）

`[PATCH v3 00/11] HID: Implement haptic touchpad support`（2025-08-18，v1 是 2025-07）
作者 **Jonathan Denose**（Google），11 个补丁的原始作者 **Angela Czubak**（Google · ChromiumOS），Dmitry Torokhov 参与评审。LWN 有专文：`lwn.net/Articles/1034290`

它给出**主机触发触觉的准入条件**（权威、可当判据用）：

```
CONFIG_HID_MULTITOUCH_HAPTIC 打开
  ∧ ABS_MT_PRESSURE 已定义且以牛顿/克为单位上报
  ∧ 设备按 HUTRR63 支持 haptic effects（= 有 Manual Trigger）
  ⇒ 内核才初始化 haptic 设备，并打上 INPUT_PROP_HAPTIC_TOUCHPAD
```

并且明写：**切换到 host-controlled 模式需要用户态上传 `WAVEFORM_PRESS`/`WAVEFORM_RELEASE`** —— 也就是**必须有 Manual Trigger 通道**。
新增的数据结构：`struct ff_haptic_effect { hid_usage, vendor_id, vendor_waveform_page, intensity, repeat_count, retrigger_period }`。

**⇒ 与项目结论一致，但这次是"上游代码级条件"，不是推断。**

### 5.4 一条可以直接执行的判据（★ 新增，之前没有）

内核 `input-event-codes.h` 与文档给出：

```
INPUT_PROP_PRESSUREPAD = 0x07   /* pressure triggers clicks */
内核文档：若触觉反馈可由用户态控制，设备必须
         "support simple haptic auto and manual triggering"
         "provide the EV_FF FF_HAPTIC force feedback effect"
```

**⇒ 在 Linux 上一条命令就能定死"这台触控板能不能被主机触发"：**

| 命令 | 看什么 |
|---|---|
| `evtest /dev/input/eventX` | 顶部 **`Event code: ... (EV_FF)`** 是否出现 |
| `cat /proc/bus/input/devices` | 该设备的 `B: EV=` 位图里是否有 **`15`（EV_FF）** 位 |
| `libinput list-devices` | 是否被标为 pressure pad / 有无 force feedback 能力 |
| `libinput quirks list /dev/input/eventX` | 是否带 `AttrInputProp=+INPUT_PROP_PRESSUREPAD` |

**预期是没有 EV_FF**（与 `Col02 out=0` 一致），但**这次是"命令输出"而不是"论证"**。而且一旦真跑 Linux，这一步零成本。

---

## 六、这轮调研对两个项目的净影响

### 触控板项目
| 变化 | 内容 |
|---|---|
| ➕ 新增一条**可执行**判据 | Linux 下查 `EV_FF` / `FF_HAPTIC`（见 5.4） |
| ➕ 上游准入条件被代码级确认 | v3 补丁系列 + 内核文档（见 5.3） |
| ➕ 新增一个**活跃的**同机型社区 | Arch CN 帖 13210 + AUR `goodix-gt7868q-dkms` |
| ➕ 新增一个**高价值回复目标** | ty2 的 issue #20（同机型同问题，2 个月零回复） |
| ➖ **结论不变** | 主机触发仍不通；`Col02 out=0` |

### 角度项目
| 变化 | 内容 |
|---|---|
| ⭕ **无新线索** | 这四个人的工作全部集中在**触控板 / EC 电源与合盖**，**没有一个人碰角度传感器** |
| ✅ 侧面确认了一件事 | **"合盖"在这批机器上是被反复处理的头等问题**（合盖关机、合盖睡死、合盖唤醒）—— 但处理方式全是"电源状态机"，不是"角度" |
| ⚠️ 一条降级 | Rong Zhang 的"压力板触觉 RFC"**未能独立复核** |

---

## 七、联系人优先级与"第一封信"要点

| 优先 | 对象 | 渠道 | 第一句问什么 |
|---|---|---|---|
| **1** | **ty2 (Terry Wong)** | GitHub issue #20 顶帖（他休假中，但 24 个 fork 的作者也在） | 「同机型 21LD。我在 Windows 侧确认了 `Col02 OutputReportByteLength = 0`、Haptics page 下只有 `Intensity`（rid=9）—— 即 **Click Force 的 Low/Med/High 走的是设备内部阈值**。你查过 TF100A 那边吗？」 |
| **2** | **Arch CN 帖 13210 的回帖者** | 中文回帖 | 「同机型 21LD。你们合盖关机的问题现在用哪个方案？我在 Windows 侧把 EC 的 ACPI 表全反编译了，`_Q15` 是 lid 事件的唯一入口，可以对照」 |
| **3** | **felixonmars（Felix Yan）** | 邮件 / GitHub | 只问 EC：「你的 14 G6+ IMH 上，合盖时 EC 除了 `LIDF` 那一位，还有别的字节在动吗？」 |
| **4** | **Rong Zhang** | `i@rong.moe` | 只问 EC，**不要问 haptic** |
| **5** | **ferstar** | GitHub issue（中文） | WMI/EC 细节；顺带问 `lidctrl` 是什么工具 |

> 原则：**用你自己的账号发**；需要起草就说。

---

## 八、诚实标注

| 项 | 状态 |
|---|---|
| ty2 两个仓库、Issue #20、AUR 包、Arch CN 帖 13210 | ✅ 直接读到原文 |
| 上游 haptic 补丁 v3 内容与准入条件 | ✅ LWN + LKML 原文 |
| `INPUT_PROP_PRESSUREPAD` / `FF_HAPTIC` 判据 | ✅ 内核 `input-event-codes.h` + 内核文档 |
| libinput 1.31.0 加 Goodix quirk | ✅ 发布说明 shortlog |
| **Rong Zhang 发起"压力板触觉 RFC"（2026-06-16）** | ⚠️ **未独立复核**。我能查到的上游 haptic 补丁作者是 Denose / Czubak。**降级为"项目文档记载、待核"** |
| Issue #20 是否已有新回复 | ✅ 已确认**仍无人回复**（只有原始提问） |
| ty2 的 24 个 fork 里有没有人加了触觉相关代码 | ⭕ 未查（值得一查：24 个 fork 是现成的人力池） |
