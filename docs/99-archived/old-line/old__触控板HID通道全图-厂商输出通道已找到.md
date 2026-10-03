# ★ 触控板 HID 通道全图：**主机→触控板存在 64 字节厂商输出通道**

> ## 🔴 2026-09-27 更正（务必先读）
>
> **本文标题里的「推翻此前结论」是错的，作废。**
>
> 既有的触控板项目（`<LAB>\touchpad-lab`）**早已完整发现 Col04**，
> 并且**已在真机上实测判定这条扩展路径为死路**：
> - `COL04-BOUNDARY.md` 已解出读帧语义、写帧格式、命令空间边界（类 3 个 + `0xA0`×16 + `0xA1`×22，边界外 = 无害 no-op）
> - H1（"GT7868Q 会不会把 `A1` 转发给 TF100A"）**已实测判否** —— 发 `A1` 帧后**未收到 `0xA2` 应答**，
>   且 `err=122` 是**未处理类的默认应答**（连扫 28 个类全是 122）
> - 09-14 真机那一发的原始日志：`poc/probe-logs/col04-A1-realmachine-20260914.txt`
>
> **所以本文的"突破"是我自己的回归，不是新发现。**
> 本文中**仍然有效**的部分：四个集合的 caps 数值、字段级结构、权限矩阵、以及 §七 的 ctypes 踩坑记录。
> **已作废**的部分：H1 相关的一切推断（§五、§六）。
>
> 权威状态见 `touchpad-lab/PREFLIGHT-STATE.md`；本次更正的完整说明见
> `touchpad-lab/DELTA-2026-09-27-BIOS-N1更正与GoodixTpDxe.md`。

> 日期：2026-09-27　机型：ThinkBook 14 G6+ IMH（21LD）　设备：`gxtp5100`（Goodix GT7868Q）

---

## 一、结论速览

| 项 | 值 |
|---|---|
| 触控板有几个 HID 集合 | **4 个**（Col01–Col04） |
| Col01 | page 0x01 / usage 0x02（**Mouse**），In=9，Out=0 |
| Col02 | page 0x0D / usage 0x05（**Touch Pad**），In=40，Out=0，**Feat=737** |
| Col03 | page 0x0D / usage 0x0E（Digitizer / Device Configuration），Feat=3 |
| **Col04** | **page 0xFF00 / usage 0x01（VENDOR-DEFINED）**，**In=65，Out=65** |
| **★★ Col04 的用户态权限** | **只读 ✔ / 读写 ✔ 都能打开** —— 通道空闲，没有任何驱动占用 |
| Col04 的 Report ID | **0x0E（14）** —— 与 Col03 的 usage 0x0E 对应 |
| **结论** | **主机可以通过 Col04 向触控板发 64 字节厂商报文**，并且**用户态 HID API 就能做到** |

---

## 二、四个集合的实测数据

采集方式：`SetupAPI` 枚举 HID 设备接口 → `CreateFile` → `HidD_GetPreparsedData` + `HidP_GetCaps`。
（注意：`SetupDiGetClassDevsW` 的返回值**必须声明 `restype=c_void_p`**，否则 HDEVINFO 被截断成 32 位 → 枚举出 0 个设备。）

| collection | UsagePage | Usage | In | **Out** | Feat | LinkColl | 只读 | 读写 |
|---|---|---|---|---|---|---|---|---|
| `gxtp5100&col01` | 0x0001 | 0x0002 | 9 | 0 | 0 | 2 | ✘ err=5 | ✘ err=5 |
| `gxtp5100&col02` | 0x000D | 0x0005 | 40 | 0 | **737** | 7 | ✘ err=32 | ✘ err=32 |
| `gxtp5100&col03` | 0x000D | 0x000E | 0 | 0 | 3 | 3 | **✔** | **✔** |
| **`gxtp5100&col04`** | **0xFF00** | **0x0001** | **65** | **65** | **0** | 1 | **✔** | **✔** |

- `err=5`（ACCESS_DENIED）/ `err=32`（SHARING_VIOLATION）→ Col01/Col02 被系统触控板与鼠标驱动独占，用户态打不开。
- **Col03/Col04 无人占用** → 用户态可直接使用。

设备字符串（Col04）：`Product = "HIDI2C Device"`，`Manufacturer = "Microsoft"`，`Serial = "9999"`。

---

## 三、Col04 厂商通道的字段级结构

来自 `HidP_GetValueCaps` / `HidP_GetButtonCaps` 枚举（**这是权威结构数据，比解析原始描述符可靠**）：

```
Col04  UsagePage=0xFF00  Usage=0x0001   In=65  Out=65  Feat=0  LinkColl=1

  Input 值字段（2 个）：
     RID=14(0x0E)  page=0xFF00  usage=0x0000..0x003E   BitSize=8
     RID=14(0x0E)  page=0xFF00  usage=0x0001           BitSize=8

  Output 值字段（2 个）：
     RID=14(0x0E)  page=0xFF00  usage=0x0000..0x003E   BitSize=8
     RID=14(0x0E)  page=0xFF00  usage=0x0001           BitSize=8
```

**解读：**
- **Report ID = 0x0E**，报文总长 **65 字节 = 1（RID）+ 64（载荷）**。
- 载荷被声明为**按 usage 0x00–0x3E 逐个寻址的 8 位字节数组**（即一个 63/64 字节的裸缓冲）。
- **Input 与 Output 完全对称** —— 一条发、一条收，就是一个**双向信箱**。
- Col03（usage page 0x0D / usage 0x0E）里的 usage **0x0E 正是这个 report ID**，两个集合是配套的（Col03 是"配置/控制"面，Col04 是"数据"面）。

### 3.1 与 BIOS 驱动协议对得上

`GoodixTpDxe` 里的报文构造（上一轮反汇编）：

```
[0]     = 0x01          协议/版本
[1]     = 0xA1          命令码
[2..4]  = 24 位参数
[0x35]  = 0xAA          终止字节（第 53 字节）
校验    = byte[0..4] 累加和
```

**`0x35 = 53 < 64` —— 这个 54 字节报文正好装得进 Col04 的 64 字节厂商输出报文里。**
（`0x35` 这个位置本身也说明原设计就是往一个 ≥54 字节的缓冲里填。）

---

## 四、Col03 的行为（配套控制面）

| 项 | 值 |
|---|---|
| UsagePage/Usage | 0x0D / 0x0E |
| Feature 长度 | 3 字节（1 RID + 2 数据） |
| Feature 值字段 | RID=**3**，page=0x000D，usage=**0x0052**，BitSize=8，Count=2 |
| Feature 按钮字段 | RID=**5**，Count=1 |
| 实测读取 | `HidD_GetFeature` 对 RID 3/5 **一律返回 `err=122`**（ERROR_INSUFFICIENT_BUFFER，且换 3/4/8/16/64 字节缓冲都一样），RID 0 返回 `err=87`，其余 RID 返回 `err=1` |

**判读**：RID 3/5 在描述符里存在（所以不是 err=1 的"无此 report"），但**触控板不响应 GET_FEATURE**（I2C-HID 层的 GET_REPORT 没实现或需要先具备条件）。Col03 这条路暂时读不出东西。

---

## 五、这条发现推翻什么、意味着什么

### 5.1 推翻
此前结论是「**主机不能触发震动**：无 HID Manual Trigger OUTPUT 报表、`Col02 out=0`」。
**Col02 的 `Out=0` 是对的**（digitizer 集合本来就不该有输出），但**我漏看了 Col04** —— 那个 **vendor 0xFF00 集合有 65 字节的 OUTPUT report，且用户态可读写**。

**所以"没有入口"是错的。入口一直都在，只是不在 Col02。**

### 5.2 意义
- **主机确实有一条 64 字节的双向厂商通道**，而且**不需要装驱动、不需要内核态、不需要绕过签名** —— 标准 HID API 就够。
- 触觉执行器是否接受主机命令、以及用哪个命令码，**现在是可实验的了**（以前不可实验）。
- 与 BIOS 侧已知的寄存器模型拼起来：
  | 来源 | 已知 |
  |---|---|
  | `GoodixTpDxe` 反汇编 | 命令包格式 `01 A1 <24位参数> … [0x35]=0xAA` + 累加校验 |
  | `GoodixTpDxe` 字符串 | 寄存器 `0x100`(写 17B 命令) / `0x200`(写变长) / `0x300`(读 5B 状态) / `0x2194`(读 4B) / `0xB68A`(传输层) |
  | 本次实测 | Col04 出：RID **0x0E**，**64 字节**裸缓冲；Col04 入：同结构 |

### 5.3 仍然未知
- 64 字节缓冲里的**具体命令编码**（哪个字节是命令、哪几个是地址/数据）。
- 触觉是否有对应的命令码（`Haptic`/`vibrate` 在全固件 30.88 MB 里 0 命中，所以**没有现成名字可查**，只能靠枚举实验）。

---

## 六、下一步（**需要你点头再动**）

下面这一步是**写操作**（虽然只是发一条 HID 输出报文，且该通道无人占用、原厂就是这么用的），但考虑到：
- 触控板是本机唯一指针设备
- 之前它被打挂过两次

所以我**先停下等你确认**。

**建议的实验设计**（从最保险的开始）：

| 步骤 | 内容 | 风险 |
|---|---|---|
| 1 | 先只做 **`ReadFile` 带 1.5 s 超时**读 Col04 的 input report，看板子是否自发上报 | 极低（只读 + 超时） |
| 2 | 发一条**只读语义**的厂商命令（如"读 IC 版本"，即 BIOS 驱动里的 `Get IC version`），然后读 input report | 低（原厂日常就发这类查询） |
| 3 | 若 2 成功 → 通道验证完毕，再系统性枚举命令码找触觉相关 | 中（逐条试探） |

**注意**：第 1 步用 `ReadFile`（超时），**绝不用 `HidD_GetInputReport`** —— 微软官方文档明确：连续用 `HidD_GetInputReport` 会丢报文、**且部分设备会变得无响应**（这正是这块板子之前被打挂的官方机理）。

---

## 七、产物

目录：`fw-touchpad/hid-probe/`

| 文件 | 内容 |
|---|---|
| `hid_dump.py` | 枚举 HID 接口 + 抓 caps（**含 `restype=c_void_p` 的修正说明**） |
| `hid_caps.py` | 字段级 caps 枚举（value/button × input/output/feature） |
| `hid_probe2.py` | 各集合权限检查 + feature 只读扫描 |
| `hid_devices.json` | 4 个集合的路径与 caps |
| `desc_gxtp5100&co.bin` | 两次 `0x000B0193` 返回的 **preparsed data**（Col03 508 B / Col04 580 B） |

### 复用要点
```
HID 类 GUID = {4D1E55B2-F16F-11CF-88CB-001111000030}
目标接口     \\?\hid#gxtp5100&col04#5&52a7aed&0&0003#{4d1e55b2-...}
厂商集合     UsagePage 0xFF00, Usage 0x0001, Report ID 0x0E, In/Out 各 65 字节
权限         Col04 只读/读写均可；Col01/Col02 被系统独占（err 5 / 32）
坑           SetupDiGetClassDevsW 的 restype 必须是 c_void_p，否则 HDEVINFO 被截成 32 位 → 0 个设备
坑           SetupDiEnumDeviceInterfaces 也必须声明 argtypes，否则 OverflowError
坑           IOCTL 0x000B0192(报告描述符) 在本机返回 err 1/6/87 → 改用 HidP_GetCaps + ValueCaps/ButtonCaps 拿结构
坑           HidD_GetFeature 返回 err=122 时不要只怀疑"缓冲太小"：本例把缓冲从 3 试到 64 字节全是 122，
             而该 report ID 在描述符里确实存在（否则应该是 err=1）→ 判读为"板子不响应 GET_FEATURE"，别再调缓冲长度
坑           自己写探测脚本时，用「集合名前缀」做 dict key 会撞车（col03/col04 前缀都是 gxtp5100&co），
             要用正则 (col\d\d) 提取
坑           Python 格式化：`"%s=%s%s" % (a, b)` 会 TypeError，条件表达式要拆开写
```
