# GdixSpbProbe 安装与验证步骤

> **当前状态：停用，不要按本文部署。**
>
> 这份文档记录的是早期 SPB 客户端草稿。后续审计确认：`hidi2c` 已持有
> `GXTP5100` 的 SPB 连接；本 INF 直接匹配 `ACPI\\GXTP5100`，并没有实现文档所说的
> root-enumerated 附加设备；驱动还硬编码了会变化的 PDO 名称
> `\\Device\\0000008a`。因此不要开启 `testsigning`、不要安装 INF、不要停止 HID 栈。
>
> 仅保留源码和已编译产物作协议/架构参考。新的证据记录见同目录
> `..\\AUDIT-2026-10-02.md`。

> **状态：已编译成功。** 产物：
> - `build\x64\Debug\GdixSpbProbe.sys`（9,728 字节，KMDF 驱动）
> - `build\x64\Debug\gdix_read.exe`（用户态测试工具）

---

## ⚠️ 先读这一节 —— 风险与红线

**本驱动尚未在本机加载过。加载内核驱动有以下风险：**

| 风险 | 说明 | 缓解 |
|---|---|---|
| **蓝屏 (BSOD)** | 驱动 bug 会导致系统崩溃 | 保存所有工作后再操作 |
| **触控板失灵** | 抢总线可能导致 `hidi2c` 工作异常 | 有回滚步骤（见第 5 节） |
| **测试签名改变启动配置** | `bcdedit` 修改 BCD | 可撤销（有对应命令） |

### 红线（照旧，绝不能碰）

1. 禁批量轮询 `Col04`
2. 单次事务 ≤ 32 字节，间隔 ≥ 500 ms（驱动内已硬编码）
3. 🔴 **红线是四条，不是“三连”**：`00 10` / `00 11` / **`0E 12`（★ 真正写 flash）** / **`0E 13`（重启）** **绝不碰** —— 旧文档漏了 `0E 13`，且常把 `0E 12` 误当“重启”（性质正好说反）
4. 本驱动**只读**，不得移除白名单限制
5. 未确认前不动 `bcdedit`

---

## 方案对比：怎么过签名这关

Windows 内核驱动强制签名。三条路：

| 方案 | 成本 | 风险 | 推荐度 |
|---|---|---|---|
| **A. 测试签名模式** | 0 元 | 改 BCD，桌面右下角出现水印 | ⭐ **开发期唯一现实选项** |
| **B. EV 证书 + 微软签名** | 数千元/年 | 无（正式） | 周期长，以后再说 |
| **C. 禁用驱动强制签名（F8/高级启动）** | 0 | 每次重启都要手选，麻烦 | 不如 A |

**结论：开发阶段走 A。**

---

## 第 1 步：开启测试签名（**需管理员**）

```cmd
bcdedit /set testsigning on
shutdown /r /t 0
```

**这条命令会：**
- 修改 BCD（Boot Configuration Data）
- 重启后桌面右下角出现"测试模式"水印
- 允许加载测试签名的驱动

**⚠️ 这是一次系统级改动。你来定要不要做，我不会自动执行。**

**回滚命令**（之后想恢复）：
```cmd
bcdedit /set testsigning off
```

---

## 第 2 步：给驱动做测试签名

需要一个自签证书。用 WDK 自带的 `makecert` / `pvk2pfx` / `signtool`。

```cmd
REM 1. 生成自签测试证书
makecert -r -pe -ss PrivateCertStore -n "CN=GdixSpbProbeTest" GdixSpbProbeTest.cer

REM 2. 签名驱动
signtool sign /fd SHA256 /s PrivateCertStore /n "GdixSpbProbeTest" GdixSpbProbe.sys

REM 3. 安装证书到受信任根（测试签名需要）
certmgr /add GdixSpbProbeTest.cer /s /r localMachine root
certmgr /add GdixSpbProbeTest.cer /s /r localMachine trustedpublisher
```

> `signtool` 在 `Windows Kits\10\bin\10.0.26100.0\x64\signtool.exe`

---

## 第 3 步：安装驱动

### 选项 A：手工安装（推荐，影响最小）

```cmd
REM 用 PnPUtil 把 INF 加入驱动存储
pnputil /add-driver GdixSpbProbe.inf /install
```

### 选项 B：sc 创建服务（更可控）

```cmd
copy GdixSpbProbe.sys %SystemRoot%\System32\drivers\
sc create GdixSpbProbe type= kernel start= demand binPath= %SystemRoot%\System32\drivers\GdixSpbProbe.sys
sc start GdixSpbProbe
```

---

## 第 4 步：验证

```cmd
REM 先确认驱动活着
gdix_read.exe --status

REM 读寄存器（关键目标）
gdix_read.exe
```

**成功标志：**

| 读到的东西 | 含义 |
|---|---|
| `0x4014` (VER_ADDR) 返回合理字节 | ✅ **通路打通** |
| `0x96F8` (CFG_START_ADDR) 有数据 | ✅ 配置可读 |
| 全是 `read error` / `0x80070005` | ❌ 安装方式或 IO 目标有误 |
| 全 `0x00` 或全 `0xFF` | ⚠️ 可能地址不对，或需要不同时序 |

---

## 第 5 步：出问题怎么回滚

```cmd
REM 停驱动
sc stop GdixSpbProbe
sc delete GdixSpbProbe

REM 删文件
del %SystemRoot%\System32\drivers\GdixSpbProbe.sys

REM （可选）关测试签名
bcdedit /set testsigning off
```

触控板是用 `hidi2c.sys` 工作的，**我们的驱动理论上不会取代它**（`Class=System`，非 HIDClass，硬件 ID 不冲突）。万一触控板失灵：

1. 进设备管理器 → 卸载本驱动
2. 重启
3. 触控板应恢复（`hidi2c` 由 Windows 自动重装）

---

## 当前已知的不确定点

| # | 问题 | 影响 |
|---|---|---|
| 1 | **目标设备名 `\Device\0000008a` 可能变** | 每次枚举 PDO 名可能不同 → `WdfIoTargetOpen` 失败 |
| 2 | **能否与 `hidi2c` 共存** | 可能拒绝共享，需要 `FILE_SHARE_*` 调整或临时停 HID 栈 |
| 3 | **Goodix `_I2C_DIRECT_RW` 在裸 I²C 层是否有效** | 该封装是 HID 层的，裸 I²C 可能需要不同字节序列 |
| 4 | 测试签名是否被 Secure Boot 影响 | 若 Secure Boot 开，需先关或走其他路 |

**第 3 点最关键** —— 我们的包是按 HID 层设计的（`0e 20 ...` 是 HID 报文封装）。
**裸 I²C 层可能不需要这层封装**，直接写寄存器地址即可。

这个问题只有真跑起来才知道。

---

## 一句话

> **编译关已经过了。接下来是部署关，而部署要动 BCD（测试签名）。**
> **这一步由你决定 —— 我不擅自执行 `bcdedit`。**
