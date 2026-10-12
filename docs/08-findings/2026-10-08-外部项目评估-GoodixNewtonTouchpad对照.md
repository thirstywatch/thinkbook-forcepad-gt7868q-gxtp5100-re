# 2026-10-08 · 外部项目评估：`edimetia3d/GoodixNewtonTouchpad` 对本项目的对照价值

> 触发：喆贴来两个 Windows Hello 红外摄像头项目（`andresbeltranc/ir_camera_sample_win32`、`lemand005/IRCameraView`），
> 让我判断"对触控板逆向有没有帮助"，并让搜 GitHub 上其他类似项目。
> **本轮结论：截图里那两个项目与本项目无关；但检索过程中找到一个【直接命中】的项目，它对"强度旋钮"这条悬案给出了新约束。**
>
> 本轮**未触碰设备**（只读 GitHub API / 源码 / 本地仓库文档）。

---

## 0. 一句话

| # | 结论 | 强度 |
|---|---|---|
| 1 | 截图两个项目：**与本项目零相关**（红外摄像头视频流 ≠ HID vendor 通道）；其中 `lemand005/IRCameraView` **仓库与账号均已不存在**（API 404） | ★★★★★ |
| 2 | **`edimetia3d/GoodixNewtonTouchpad`** 是**同厂同代同通道**（Goodix + HID Output Report）的**成功案例**：用 `RID 14 / 类 0x02 / 等级 0..2` 三档设触觉强度，**写入持久** | ★★★★（第三方单例，未跨机验证） |
| 3 | ★★ **它的 Report ID 是 `14`，不是本机那套 `0E 20`** —— 这**强化**本项目的既有定案：本机 Col04 的 `0x0E/0x20/0x21/0x23` 通路缺失是**描述符层**问题 | ★★★★ |
| 4 | ★★★ **它的"强度"是 3 档离散 enum（0/1/2），不是 0..255 连续值** —— 这给本项目 `cfg+0x115` 的 5 档自相矛盾（0≈20≈120、60 反常、240 偏强）提供了一个**新的、更简洁的解释**：**固件可能把连续输入量化到少数几档** | ★★★ 假说（可证伪，见 §4） |
| 5 | 它自述 **"No verified hardware command for reading the current haptic level is known"** ⇒ **读不回不是本项目的方法问题，是同代 IC 的共性** | ★★★★ |

---

## 1. 截图里的两个项目：结论 = 无关

| 项目 | 内容 | 与本项目关系 |
|---|---|---|
| `andresbeltranc/ir_camera_sample_win32` | C++/WinRT **非 UWP** 桌面程序，用 **Media Foundation** 打开 Windows Hello 红外摄像头，喂给 OpenCV 显示。2023-05，~400 行，VS2022 + OpenCV | ❌ **零相关**。它是摄像头**视频流**路径；本项目是 **HID vendor 私有集合 + I²C 直通读写**。唯一可借的是"WinRT API 在非 UWP 桌面程序里怎么用"这条**通用**经验，但本项目走的是 `WriteFile` + HID，不经过 WinRT |
| `lemand005/IRCameraView` | **不存在** | ❌ 无法评估。`api.github.com/repos/lemand005/IRCameraView` → 404；`/users/lemand005` → 404 ⇒ 账号已注销/改名/转私有 |

> **注**：本项目的 `SimpleHapticsController`（WinRT HID 路径）与第一个项目的"WinRT 用法"同源，但那条路本项目已定案**在本机不可行**（Col02 `Out=0`，缺 `0x0E/0x21`）。所以它连"旁证"都算不上。

---

## 2. ★★★ 命中的项目：`edimetia3d/GoodixNewtonTouchpad`

**性质**：C# 命令行工具（.NET Framework 4.7.2+，`build.bat` 一键编译），2026-09-09 推送，**作者实测机 = 荣耀 MagicBook Pro 16 2026**。
**功能**：设置 Goodix Newton 触控板的 **force-click 触觉反馈等级**。

### 2.1 协议（README 逐字 + `Hid.cs:180-185` 源码核对）

| 等级 | 参数 | HID Output Report（9 B） |
|---|---|---|
| Low 低 | `low` / `0` / `低` | `0E 02 00 00 00 00 00 00 00` |
| Medium 中 | `medium` / `1` / `中` | `0E 02 01 00 00 00 00 00 00` |
| High 高 | `high` / `2` / `高` | `0E 02 02 00 00 00 00 00 00` |

```csharp
// Hid.cs:180  —— 注释原文："Verified protocol: report ID 0E, operation 02, level 0/1/2"
public static byte[] Report(int level)
{
    if (level < 0 || level > 2) throw new ArgumentOutOfRangeException("level");
    return new byte[] { 0x0e, 0x02, (byte)level, 0, 0, 0, 0, 0, 0 };
}
```

### 2.2 匹配条件（`Hid.cs:162-170`，逐字）

| 属性 | 要求值 |
|---|---|
| VID / PID | **`27C6 / 0F9A`** |
| UsagePage / Usage | **`FF00 / 0001`** |
| Input / Output 报告长度 | **`9 / 9`** 字节 |
| Feature 报告长度 | **`0`** |

⇒ **`27C6/0F9A` = Goodix `0x0F9A`，不是本机 `0x01E9`**（不同 PID = 不同硬件代次）。
⇒ 但它用的 `UsagePage FF00 / Usage 0001` 与本机 **Col04 完全同一组**（本机 Col04 = `UP=FF00 / Usage 0x0001`）。

### 2.3 传输方式与持久性（README 逐字）

| 项 | 原文 |
|---|---|
| 传输 | "The utility sends a HID Output Report with **`WriteFile`**; it does **not** call `HidD_SetFeature`." |
| 持久性 | "After a successful write, the process exits and **the touchpad retains the setting in hardware**. On the tested device, another write was only needed after **complete power loss**." |
| 读回 | "**No verified hardware command for reading the current haptic level is known.**" ⇒ `status` 报 `hardwareState = unverified-no-readback` |
| 实测范围 | "It has **not yet been tested on a second physical computer**." |

---

## 3. ★★ 与本项目既有定案的交叉核对（逐条）

### 3.1 【强化】它用的 Report ID 是 `14`，本机缺 `0x0E` 通路

| # | 事实 | 出处 |
|---|---|---|
| 1 | **本机 Col04 = `UP FF00 / Usage 0001`，唯一 Output = `RID 14`，65 bit** | `docs/07-hid/lab__GXTP5100-HID-usage-report.md:92`（caps 实测） |
| 2 | 本机**全设备不存在任何 `page = 0x0E` 的 output 字段**；`0x0E/0x21 Manual Trigger` **缺失** | 同上 :132、:349 |
| 3 | ⇒ 既判定：主机无法主动触发震动，是**描述符层缺口**，与驱动/API/权限无关 | 同上 §5.5 |
| 4 | **外部项目用的 RID = `14`**（= 本机 Col04 的 RID！），而不是 `0x0E` 系列 | 本项目 `Hid.cs` |

**⇒ 关键推论**：那个项目**没有**走标准 `SimpleHapticsController`（`0x0E/0x01/0x21`）通路，而是**直接往厂商私有集合（`FF00/0001`、RID 14）写 Output Report**。
**这正好与本项目"厂家把触觉闸门放在私有通道、标准通路被故意留空"的判定方向一致**，而且给出了一个**已验证的报文形状**：`0E 02 [level] …`。

> ⚠️ **但本机不能照抄**：本机的 Col04 RID 14 已明确用于 **I²C 直通读写**（`0E 20 …`），
> 首字节 `0E` 是 Report ID、第二字节 `20` 是"操作类"。外部项目的第二字节 `02` 在本机语义未知。
> **⚠️ 尤其不要盲发**：本项目历史上有"发 `0x0E` 类把板子打挂两次"的记录（见 `lab__COL04-BOUNDARY.md` §11.5）。

### 3.2 【新解释】"强度 = 3 档离散 enum"给了 `+0x115` 一个新假说

本项目现状（`2026-10-05-cfg下发通道打通…md` §七）：
`+0x115` 五档实测 `0 ≈ 20 ≈ 120`、`60` 变绵软、`240` 明显更强 ⇒ **自相矛盾** ⇒ 已降级为"存疑/疑似感知噪声"。

**外部项目提供的对照**：同厂同代 IC 的触觉等级是 **只有 3 档的离散 enum**（`0/1/2`），不是 0..255 连续值。

**⇒ 新假说（此前不在本项目假设集里）**：

> **固件可能把连续输入量化/钳位到少数几个"档位"**，
> 因此 `0`/`20` 落在同一档（都≈默认档）、`60` 恰好跨到另一档的边界、`240` 落在最高档。
> **这比"感知噪声"更简洁地解释了"0≈20，而 60 反而与两者都不同"** —— 量化映射本就不保证单调外的相邻性。

**★ 可证伪的判定实验（零成本，纯重测）**：
把 `+0x115` 按 **{0, 40, 80, 128, 192, 255}** 扫一遍（介于已知的 0/20/60/120/240 之间补点），
若反馈呈现**"只有 2–4 个可区分等级"**的台阶（而非连续渐变）⇒ **量化假说成立**，`+0x115` 可重新定为"强度档位"。
若仍无规律 ⇒ 维持"存疑"。

> ⚠️ **仍须遵守纪律第 109 条**：主观感受不能单独支撑字段定名，须"可复现 + 能证伪的极端档 + 单调"。
> 且**必须先做盲测 A/B**（同一档写两次、中间夹另一档），否则台阶可能只是对比效应。

### 3.3 【共性】"读不回"是同代 IC 的普遍现象

外部项目（另一颗 IC、另一台机器）自述**没有任何可读回当前触觉等级的已验证命令** ⇒
本项目"`0x96F8` 只有前 32 B 可读、`+0x115` 不在窗口内故只能靠感官验收"**不是本项目的方法缺陷**，而是**同代 Goodix 触觉接口的共性设计**（微软规范对 device-initiated 旋钮也只要求 `SET_FEATURE`，不要求 `GET_FEATURE` —— LKML RFC 独立观察一致）。

---

## 4. 检索到的其余相关项目（分级）

| 项目 | 内容 | 价值 | 本项目是否已有 |
|---|---|---|---|
| **`fwupd/fwupd` → `plugins/goodix-tp`** | ★ **官方级** Goodix 触控 IC 固件更新插件；GUID `HIDRAW\VEN_27C6&DEV_xxxx`；协议 ID `com.goodix.goodixtp`；维护者挂 Goodix 官方 `@xulinkun` | ★★★★ **可信度最高**的第三方实现，是"下发通道/刷写流程"的官方对照 | ❌ **未见引用，建议补** |
| `ty2/goodix-gt7868q-linux-driver` ⭐92 | `hid-multitouch` 的 **report_fixup**（`rdesc[607]: 0x15 → 0x25`），针对 PID `0x01E9` | ★★★★ 已是本项目 §19.30.1 的**核心证据** | ✅ 已有（`vendor-refs/links.md` §5 第 1 行） |
| `wszqkzqk/goodix-gt7868q-linux-driver` | 同 IC fork（测试机 ThinkBook 16+ 2024 IMH），带 `local-overrides.quirks`：压阈 > 掌压阈致光标不动；设备报 2000 但驱动截到 1000 | ★★★ 压力/阈值语义的旁证 | ⚠️ 与 ty2 同源，本项目只记了 ty2 |
| `wang-xuemin/gt9xx_driver_linux` | 汇顶 gt9xx 安卓→Linux 移植，含 **`goodix_tool.c`**（CFG 读写工具源码） | ★★★ 同厂原生 **cfg 读写的第三份实现**，可与本项目 cfg 格式交叉验算 | ⚠️ 本项目记的是 `github.com/goodix` 三个仓库，未含此移植版 |
| **USB-IF `HUTRR63`** | Haptic Usage Page 原始规范：Waveform List / Ordinal 0 保留 / **Vendor Waveform 区间 `0x2100+`**、"Duration 之外行为未定义" | ★★★★ **对本项目直接有用**：解释为什么改 `TAG 0x50–0x7A` 的厂商波形"不产生可预期效果"—— **厂商波形本就是设备自定义，主机不必也无法用通用方式预测** | ⚠️ 已引用 HUT 1.5 与 HUTRR111，**HUTRR63 这份未见单独引用** |
| 微软《Input Device Haptics Implementation Guide》 | Waveform 表明确 **`Click` 波形对触控板 Forbidden**（会与按压反馈混淆） | ★★★ | ✅ 已引用 |

---

## 5. 本轮建议（按优先级）

| # | 动作 | 成本 | 预期 |
|---|---|---|---|
| **1** | **重测 `+0x115` 的量化假说**：扫 `{0,40,80,128,192,255}`（补点）+ **盲测 A/B**，看是否有"台阶" | 零（cfg 通道已通，可 `restore`） | 要么把 `+0x115` 从"存疑"救回"强度档位"，要么彻底删掉这条 |
| **2** | 把 `fwupd/fwupd` 的 `goodix-tp` 插件源码取回**只读对照**（它含官方侧的下发/校验流程），核对本项目 §二 的官方序列 | 低（纯离线） | 交叉验证 `0x4160` 命令序列与 `7E 00 07/02` 语义；可能补上"官方怎么读回"这条路 |
| **3** | 在 `vendor-refs/links.md` §4 补登三项：`fwupd/goodix-tp`、`wszqkzqk` fork、`wang-xuemin/gt9xx_driver_linux`；§3 补 **HUTRR63** | 低 | 资料完整性 |
| **4** | 若量化假说成立 ⇒ 把 `cfg+0x115` 定名为"**触觉强度档位（离散）**"，并撤销"0..255 连续域"的说法 | 低 | 修正 `2026-10-05` 文档 §十三 的"现证可调，0–255 域"这句 |

> **❌ 不建议**：照抄外部项目的 `0E 02 XX` 报文发到本机 Col04。
> 原因：本机 Col04 的 `0x0E 类`已表征为 `20`=I²C 直通（读写）；`02` 在本机语义未知；且本项目有"`0x0E` 类打挂板子"的实测记录。
> **要试也必须先有"失败模式可表征"的前提**（读回窗口 / 健康三连）。

---

## 6. 未定项（不夸大）

| 项 | 状态 |
|---|---|
| `0x0F9A`（外部项目）与本机 `0x01E9` 是否同一个 HID 私有协议版本 | 【未定】需拿到 `0x0F9A` 的描述符比 usage/报告布局 |
| 外部项目的 `0x02` 在本机 Col04 上的语义 | 【未定】未试，且不建议盲试（见 §5） |
| `+0x115` 量化假说是否成立 | 【未定】§5 第 1 项实验可判 |
| 本机是否有"3 档"之外的强度表达 | 【未定】`cfg +0x113` / `+0x117` 也疑似落在触觉簇（`:256`），需一并重测 |

---

## 附：本轮证据来源

- 截图项目：`https://github.com/andresbeltranc/ir_camera_sample_win32`（已读 README）；`https://github.com/lemand005/IRCameraView`（404）
- 命中项目：`https://github.com/edimetia3d/GoodixNewtonTouchpad`（已读 `README.md` / `Hid.cs` / `Program.cs`，C# 源码逐行核对）
- 本项目既有定案：`docs/07-hid/lab__GXTP5100-HID-usage-report.md`、`docs/08-findings/2026-10-05-cfg下发通道打通-首个主机写入改变行为的实证.md`、`docs/07-hid/lab__COL04-BOUNDARY.md`
- 本轮**未执行任何设备操作**；未写入任何第三方源码（只记出处）。
