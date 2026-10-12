# ★★★★★★ 2026-10-11 根因定案：`gxmem.write()` **静默截断** —— `0xBB` 与历史 cfg 实验全线受污染的根因

> **触发**：喆「一起做」→ 追查 `0xBB` 语义 + 解剖 UEFI 反汇编
> **性质**：**纯离线**（代码阅读 + 源码比对；**未碰设备**）
> **结果**：**找到 `0xBB` 的官方定义**，并**由代码读出确认根因是我们自己的 bug**。

---

## 0. 一句话

> **`gxmem.Gx._send()` 里 `n = min(len(pkt), 65)` 会把任何 >65 字节的包【静默截断】。**
> **`gxmem.Gx.write(addr, data)` 把整块数据塞进【一个】包 ⇒ 任何 >55 字节的写入，实际只发出前 55 字节，而长度字段却声明真实长度。**
> **⇒ IC 收到的数据校验和 ≠ 声明的校验和 ⇒ `0x5096` 报 `0xBB`（官方语义 = checksum error）。**

---

## 1. `0xBB` 的官方定义（本轮新查到的权威出处）

**来源**：`goodix/gdix_hid_firmware_update` 的 **`marsei/marsei_update.cpp`** 与 **`gtx9/gtx9_update.cpp`**
（**同一寄存器 `0x5096`**；这两个分支由 Goodix 员工 `xulinkun@goodix.com` 于 v1.8.0 / commit `7555a0ae…` 加入）

```c
/* wait update finish */
retry = 10;
while (retry--) {
    usleep(100000);
    ret = dev->Read(0x5096, &flag, 1);
    if (ret == 1 && flag == 0xAA) {
        break;
    } else if (ret == 1 && flag == 0xBB) { //checksum error
        gdix_err("checksum error of the data received by host\n");
        retry = -1; break;
    } else if (ret == 1 && flag == 0xCC) {
        gdix_err("checksum error of the data read back from flash\n");
        retry = -1; break;
    }
}
```

### ★ `0x5096`（`FLASH_RESULT_ADDR`）已知取值全表

| 值 | 含义 | 出处 | 性质 |
|---|---|---|---|
| **`0xAA`** | **成功** | 官方 gtx2/gtx3/gtx5/gtx8/gt7868q/berlin_a/marsei/gtx9 全部只认它 | FACT（多源一致） |
| **`0xBB`** | ★ **IC 收到的数据校验和错误**（`checksum error of the data received by host`） | `marsei/marsei_update.cpp` · `gtx9/gtx9_update.cpp` | FACT（官方唯一出处） |
| **`0xCC`** | IC 从 flash 回读的校验和错误 | 同上 | FACT |
| `0x00` | 成功后被主机清零 | `gtx2_update.cpp:206` `dev->Write(0x5096, &dummy, 1)` | FACT |
| `0x75` | **空闲/复位默认值** | **仅本项目实测**（BIOS 重刷后回到 `0x75`） | ⚠️ 公开材料**查不到** |

> ⚠️ **注意辨析**：`gtx9/gtx9_i2c_update.cpp` 里还有一张 `FLASH_CMD_*` 表，其中 `FLASH_CMD_TYPE_WRITE = 0xBB` —— **那是"命令类型"，不是结果状态**，**不要混淆**。

---

## 2. 根因：`gxmem` 的两处代码（**100% 由代码读出确认**）

### 2.1 `_send()` —— 截断点

```python
def _send(self, pkt):
    b = ctypes.create_string_buffer(65)
    n = min(len(pkt), 65)                 # ★★★ 截断点：>65 字节的包只发前 65
    ctypes.memmove(b, bytes(pkt[:n]), n)
    ctypes.memmove(b, bytes([0x0E]), 1)
    return bool(hid.HidD_SetOutputReport(self.h, ctypes.cast(b, ctypes.c_void_p), 65))
```

### 2.2 `write()` —— 把整块塞进一包

```python
def write(self, addr, data):              # 【修复前】
    data = bytes(data)
    pkt = [0x0E, 0x20, 0x00, 0x00, (len(data) + 5) & 0xFF, 0x00,   # ← len 声明真实长度
           (addr >> 8) & 0xFF, addr & 0xFF,
           (len(data) >> 8) & 0xFF, len(data) & 0xFF] + list(data)  # ← 全部数据塞进一包
    return self._send(pkt)
```

### 2.3 实测核算（离线）

```
gxmem.write(0xC000, 4096 字节)
  → 构造出的包总长 = 4106 字节（头 10 + 数据 4096）
  → _send: n = min(4106, 65) = 65
  → ⇒ 实际只发出 65 字节 = 头 10 + 数据 55
  → 而长度字段声明 4096
  ⇒ IC 算出（55 字节）的校验和 ≠ 我们声明的（4096 字节）的校验和
  ⇒ 0x5096 报 0xBB（checksum error）
```

### 2.4 官方正确做法（`gtx5.cpp:227-276` `GTx5Device::Write`）

```c
int GTx5Device::Write(unsigned int addr, const unsigned char *buf, unsigned int len) {
    unsigned char tmpBuf[65] = {0x0e, _I2C_DIRECT_RW, 0, 0, 5};
    unsigned short current_addr = addr;
    unsigned int pos = 0, transfer_length = 0;
    bool has_follow_pkg = false;
    unsigned char pkg_num = 0;
    while (pos != len) {
        if (len - pos > m_outputReportSize - GDIX_PRE_HEAD_LEN - GDIX_DATA_HEAD_LEN) {
            transfer_length = m_outputReportSize - GDIX_PRE_HEAD_LEN - GDIX_DATA_HEAD_LEN;  /* 55 */
            has_follow_pkg = true;
        } else {
            transfer_length = len - pos;
            has_follow_pkg = false;
        }
        tmpBuf[2] = has_follow_pkg ? 0x01 : 0x00;   /* follow 标志 */
        tmpBuf[3] = pkg_num++;                      /* 包号递增 */
        tmpBuf[4] = (unsigned char)(transfer_length + GDIX_DATA_HEAD_LEN);
        tmpBuf[5] = 0;                              /* 写操作标志 */
        tmpBuf[6] = (current_addr >> 8) & 0xff;     /* 地址 高 */
        tmpBuf[7] = current_addr & 0xff;            /* 地址 低 */
        tmpBuf[8] = (unsigned char)((transfer_length >> 8) & 0xff);
        tmpBuf[9] = (unsigned char)(transfer_length & 0xff);
        memcpy(&tmpBuf[GDIX_PRE_HEAD_LEN + GDIX_DATA_HEAD_LEN], &buf[pos], transfer_length);
        ret = Write(tmpBuf, transfer_length + GDIX_PRE_HEAD_LEN + GDIX_DATA_HEAD_LEN);
        pos += transfer_length;  current_addr += transfer_length;
    }
}
```

**⇒ 官方把 4096 B 拆成 75 包（每包 55 B），`[2]`=follow、`[3]`=包号、地址逐包 +55 —— 我们的 `write()` 完全没做这件事。**

---

## 3. ★★★ 修复（已完成，`gxmem.py`）

已把 `write()` 改为**按官方语义自动拆包**（每包 ≤55 B，`follow`/`pkg_num`/地址递增），并保留旧行为为 `write_single_packet_only()` 供对照。
**备份**：`gxmem.py.bak-20261011`

**离线自检（不碰设备）**：
```
4096 B → 拆成 75 包 ✅
  包0: 头 0e 20 01 00 3c 00 c0 00 00 37   数据 55 B  follow=01 pkg=00
  包1: 头 0e 20 01 01 3c 00 c0 37 00 37   数据 55 B  follow=01 pkg=01   ← 地址 +0x37=+55 ✅
  包2: 头 0e 20 01 02 3c 00 c0 6e 00 37   ...
  末包: follow=00 ✅  pkg=0x4A(74) ✅
  数据总量 = 4096 B ✅
```

---

## 4. ★★★★★ Retroactive 影响：项目历史实验的**污染面**

### 4.1 受影响的写入（>55 B）

| # | 位置 | 写入大小 | 影响 |
|---|---|---|---|
| **1** | **`lab__r13_cfgupdate.py` —— 往 `0x96F8` 写 cfg 记录** | **1084 B（`CFG_BODY_LEN`）** | 🔴 **实际只发 55 B** |
| 2 | `lab__r31`–`lab__r36`（本轮新写） | 4096 B | 🔴 已定位为 `0xBB` 的直接原因 |
| 3 | 其它小写入（`0x4160` 的 5 B 命令） | 5 B | ✅ 一包装得下 ⇒ **不受影响** |

### 4.2 ★ 最要紧的一条：**`0x96F8` 的 cfg 写入一直是 55 字节**

`lab__r13_cfgupdate.py` 自己的注释：
```python
CFG_BODY_LEN = 1084   # ★★★ 2026-10-05 实测定案：真正的 sub_cfg_len = 1084
                      #     写 1024 时 IC 回 `7E 00 02`；写 1084 时回 `7E 00 07`（= 与 flash 一致）
```

**⇒ 该实验【声明】写 1024 / 1084 字节，但实际每次都只发出 55 字节。**
**⇒ "写 1024 回 `7E 00 02`、写 1084 回 `7E 00 07`" 这两个不同的回值，很可能只是【声明长度不同】导致的应答差异，不是"内容是否与 flash 一致"。**

**⇒ 凡以"整条 cfg 写入的结果码"为依据的结论，都需要重新审视。** 具体包括（待复核清单）：
- 《全书》§19.40（第十三轮）"cfg 下发通道打通 —— 全项目首个'主机写入改变设备行为'"中与**长写入**相关的部分
- 登记表 **B9**（"第一个有效旋钮"）· **B17**（`+0x115` 降级）
- `docs/03-firmware/` 里以 `7E 00 02` / `7E 00 07` 为判据的段落

> ⚠️ **注意区分**：**单字节/短写入受影响**（如 `+0x10F`、`+0x115` 的单字节改写 —— 那走的是 5 B 级路径，一包装得下）。**只有"整条 cfg 记录（1084 B）的写入"受影响。**

### 4.3 对 2026-10-10 事件的完整解释

| 现象 | 解释 |
|---|---|
| `0E 12` 稳定报 `0xBB` | ✅ **IC 收到 55 B 而非 4096 B，校验和不符** |
| 命令"确实被处理了"（功能变了） | ✅ **IC 把不完整的 4096 B 区擦掉并写了收到的 55 B（+垃圾）** |
| 功能退化（触觉消失/按压点击失效） | ✅ `idx1`（type 0x03 = `FLASH_SUBSYS_TYPE_CONFIG`）被写坏 |
| 5 字节的 `0x96F8` 写入成功 | ✅ **一包装得下** |
| 官方工具能正常工作 | ✅ **它正确拆包** |
| BIOS 重刷后完全恢复 | ✅ 固件被重新写对 |

**⇒ 结论：`0xBB` 不是 IC 之谜，是我们自己的包长度 bug。** 原"`0xBB` 语义未定"的悬案**已结案**。

---

## 5. 新增纪律（第 133 条）

> **第 133 条** ★★★ **凡"分块/分包的传输层"，必须对【声明长度】与【实际发出长度】做一致性断言。**
> 本项目代价：`_send` 里一行 `min(len, 65)` 造成 **>55 字节的写入全部静默截断**，
> 而长度字段仍声明真实长度 ⇒ 器件按声明长度校验 ⇒ 长期报错/半写，
> 并**污染了两类历史结论**（`0xBB` 语义、cfg 记录写入判读）。
> **⇒ 实施要点**：① 发送函数返回**实际发出的字节数**，调用方断言 `== 期望`；② 任何"组装一包"的地方，**包长必须 ≤ 协议上限**，否则显式拆包（不得依赖意外的截断）。

---

## 6. 下一步

| # | 动作 | 性质 |
|---|---|---|
| **1** | ★★★★★ **复核 §4.2 清单**：所有以"整条 cfg 写入 + 结果码"为依据的结论 | **离线可做** |
| **2** | ★★★★ **用修复后的 `gxmem` 重做 cfg 写入实验**（现在才第一次真正把 1084 B 发全） | 需设备（有 BIOS 安全网） |
| **3** | ★★★ **全项目扫一遍其它工具是否有同类"声明 vs 实际"不一致** | 离线 |
| **4** | ★★ 用修复后的 `gxmem` 重做 `0E 12`（预期得到 `0xAA`）—— **这是 B12 的最终闭环** | 需设备（有安全网） |
| **5** | ★ 把 §1 的 `0x5096` 取值表补进 `docs/07-hid/gtx3-official-command-index.md` | 文档 |

---

## 7. 本轮附带产出

- **`0x5096` 取值表**（`0xAA` 成功 / `0xBB` 收到校验错 / `0xCC` 回读校验错 / `0x00` 清零 / `0x75` 空闲）
- **`0x4160` 取值表**（`0xFF` 空闲 / `0x82` 应答 / `0x7F` 成功 / `0x7E 00 07` 与 flash 一致 / `0x80·0x83·0x7D` 命令码）
- **`0x5095` 只定义了 `0xDD`**（ISP 就绪）；空闲态变值**任何公开材料都查不到**
- `goodix` 官方仓库共 **8 个系列**：`gtx2 / gtx3 / gtx5 / gtx8 / gtx9 / berlin_a / marsei / gt7868q`；
  **只有 `gtx9` 与 `marsei` 定义了 `0xBB/0xCC`**
- `fwupd` 的 `fu-goodixtp-gtx8-device.c` 是**寄存器布局与本机完全一致**的参考实现
  （`CMD_ADDR 0x60CC` / `BL_STATE_ADDR 0x5095` / `FLASH_RESULT_ADDR 0x5096` / `FLASH_BUFFER_ADDR 0xC000` + `0E 12` 帧）
  —— ⚠️ 但它 **每块固定发满 4096（零填充）**，与 gtx2 的"按实际剩余长度"不同

---

# ★★★ 2026-10-11 追加：**污染面复核结果 —— 结论收窄，历史实验【未被污染】**

> 承接 §4.2 的"待复核清单"。本轮**逐脚本审计**了所有调用 `gxmem.write()` 的地方。

## 1. ★ 审计结果（逐脚本）

| 文件 | 写入大小 | 是否受 bug 影响 | 依据 |
|---|---|---|---|
| **`lab__r31_persist_probe.py:144`** | 4096 B | 🔴 是 | `g.write(FLASH_BUFFER_ADDR, buf)` |
| **`lab__r32_official_seq.py:328`** | 4096 B | 🔴 是 | `g.write(FLASH_BUFFER_ADDR, ch)` |
| **`lab__r34_first_write.py:206`** | 4096 B | 🔴 是 | `g.write(FLASH_BUF, data)` ← **即产生 `0xBB` 的那次** |
| **`lab__r35_chunk_write.py:80`** | 4096 B | 🔴 是 | 同上 |
| **`lab__r36_full_update.py:100`** | 4096 B | 🔴 是 | 同上 |
| **`lab__r13_cfgupdate.py`**（**第十三轮 cfg 实验**） | **1084 B** | ✅ **否** | ★ 它**不使用** `gxmem.write()`，而是自写 `write_chunked()`（`CHUNK=55`，逐包构造后**直接 `g._send(pkt)`**）⇒ **正确拆包** |
| `lab__r13_2 / r13_3 / r13_4 / r13_5 / r13_6` | 5 B 命令 | ✅ 否 | 只写 `0x4160` 的 5 字节命令 |
| `lab__r14_persist_check / r17_handshake_read / r18_t2_verify / r19_t2_full_dump` | 5 B 命令 + 只读 | ✅ 否 | 同上 |
| `lab__r30_session_harden.py` | 只读 | ✅ 否 | — |

**★ 关键证据**（`lab__r13_cfgupdate.py`）：
```python
CHUNK = 55                   # 单报告最多携带的数据字节数（65 - 10 头）
def write_chunked(g, addr, data, chunk=CHUNK, ...):
    for i in range(n):
        blk = data[i*chunk:(i+1)*chunk]
        pkt = [0x0E, 0x20, cont, i & 0xFF, (len(blk)+5)&0xFF, 0x00,
               (a>>8)&0xFF, a&0xFF, (len(blk)>>8)&0xFF, len(blk)&0xFF] + list(blk)
        if not g._send(pkt): return False, i, n     # ← ★ 直接 _send，绕过 gxmem.write()
```

## 2. ⇒ 修正后的结论（**收窄**）

> **§4.2 的"历史实验污染面"警告【范围过大】，现予收窄：**
> **受污染的【只有 2026-10-10/11 我自己新写的 `lab__r31`–`lab__r36`】**（它们用 `gxmem.write()` 写 4096 B）。
> **项目历史上的 cfg 实验（§19.40 / 登记表 B9 / B17）【未受该 bug 影响】** —— 它们走的是自写的 `write_chunked()`。
> ⇒ **§4.2 / B25 / §19.46.3 里"待复核清单"按此收窄。** 对 §19.40 等的复核**仍建议做**（因为与下面 §3 的新疑点有关），但**理由不再是"gxmem 截断"，而是"`cont` 语义存疑"**。

## 3. ★★★ 审计中发现的**新疑点**：项目对 `cont`（`[2]` 字段）的结论与官方协议矛盾

**项目自己的注释**（`lab__r13_cfgupdate.py`）：
```
· 第 1 轮：每块都用同一 addr、cont=1/1/…/0  ⇒ IC 回 `7E 00 00`
· 第 2 轮：addr 逐块递增、仍带 cont=1  ⇒ IC 回 `7E 00 02`，且暂存区纹丝不动
  ⇒ cont=1 在【主机→设备】方向不是"续传"语义，带上它反而被判为序列错误
· 第 3 轮（本版本默认）：addr 逐块递增 + 每块 cont=0
```

**官方协议**（`gtx5.cpp:227-276` `GTx5Device::Write`）：
```c
tmpBuf[2] = has_follow_pkg ? 0x01 : 0x00;   /* ★ [2]=1 = 【还有后续包】 */
tmpBuf[3] = pkg_num++;
tmpBuf[6] = (current_addr >> 8) & 0xff;     /* ★ 地址逐包 +transfer_length */
```

**⇒ 项目结论"`cont=1` 是序列错误、不能用"与官方"`[2]=1` 表示还有后续包"【直接矛盾】。**

**可能的解释（均未验证）**：
| # | 假说 |
|---|---|
| (a) | 项目第 2 轮的实验 setup 存在别的问题（如握手缺失、地址算法、包号未递增），`7E 00 02` 的成因**不是** `cont` |
| (b) | `7E 00 02` 是**对 `0x83` 命令**的应答（配置结果），与写入分包无关 —— 需核对该轮代码的因果顺序 |
| (c) | 本 MCU 固件的 `follow` 语义确实与其它 Goodix 系列不同（**可能性最低**，因协议同源） |

**⇒ 待办**：**优先复核 `lab__r13_cfgupdate.py` 第 2 轮的因果链**（`cont` 是否真是 `7E 00 02` 的成因）。
若 (a)/(b) 成立 ⇒ **`gxmem.write()` 的新实现（用 `follow=0x01`）是正确的**；若 (c) 成立 ⇒ 需为本机特判。

## 4. 本轮"审计"的元结论

**"发现一个 bug"之后，必须【逐调用点审计范围】，不能由"存在 bug"直接推出"历史结论被污染"。**
*本次教训*：我一度把污染面写成"项目历史 cfg 实验全线受污染"，**实际逐脚本一看，那些工具用的是自写的正确实现。**
⇒ **新增纪律 134**：★ **发现底层 bug 后，污染面的结论必须【逐调用点审计后再下】**；不得以"某工具链存在缺陷"泛化到"所有使用它的历史结论"。

---

# ★★★ 2026-10-11 追加二：**假说 (b) 由代码因果顺序【确认】**

**证据**（`lab__r13_cfgupdate.py` `do_update()` 的执行顺序）：

```
[5] ★ 写 cfg 到 0x96F8（%d 字节，分 %d 块）      ← cont 字段在这里
      ok, done, total = write_chunked(g, CFG_ADDR, cfg, use_cont=USE_CONT)
      time.sleep(0.10)
[6] 通知 IC：cfg 已就绪 0x83
      g.write(CMD_ADDR, bytes(cmd_init(0x83, 0)))
      time.sleep(0.08)
[7] 读校验结果 (0x4160, 5B)                       ← ★ 结果在这里才读
      … if d and len(d) >= 3 and d[0] in (0x7F, 0x7E): res = bytes(d)
```

**⇒ `7E 00 02` 是在【发完 `0x83` 之后】才读出的 ⇒ 它是 `0x83` 命令（配置结果）的应答。**
**⇒ 把它归因为"`cont=1` 导致序列错误"【缺乏代码支持】—— 属【误归因】。**

### ★ 由此产生的一个更重要的推论（🟡 未验证）

项目最终选择了 **`cont=0`（每块 cont 都置 0）**，理由是"`cont=1` 是序列错误"。
但按**官方协议**，`[2]=0` 的含义是 **"本包是最后一包"** ——
**⇒ 若每一包都声明"我是最后一包"，IC 可能把每个 55 字节包【当成一次独立的完整写】处理，而不是一次连续写。**

**⇒ 这可能是"整条 cfg 写入的行为一直不如预期"的真实原因之一**（不是 gxmem 截断，而是 `follow` 语义用反）。

**⇒ 待办（优先级高）**：
1. 用**修复后的 `gxmem.write()`**（它按官方用 `follow=0x01`）重做 cfg 写入
2. 对比 `follow=0x01`（官方语义）与 `follow=0x00`（项目旧用法）两种下的 IC 应答与暂存区状态
3. ⇒ 由此判定 `cont`/`follow` 的真实语义
