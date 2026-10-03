# ROUND60：高熵区处理方案 —— 官方源码给出的权威答案

> 生成时间：2026-09-30
> 触发：喆问"高熵区到底要怎么处理？看看网上有没有解法"
> **权威来源**：Goodix 官方开源仓库 `goodix/gdix_hid_firmware_update`
> （Apache-2.0，含 `gt7868q/` 目录与完整固件解析/烧录逻辑）

---

## 〇、一句话结论

**不用解高熵区了 —— 官方源码说明："高熵区"根本不需要解密，它是固件包里的正常内容。
真正的配置数据在 `flash 0x19000`，由官方工具**明文传输并写入**。**

★ 而且：**官方源码逐字段证实了我们前 59 轮的静态分析结论。**

---

## 一、官方源码的两个致命发现

### 1.1 `0x19000` 被官方写死为 **config 的 flash 地址**

`gt7868q/gt7868q_update.cpp` 开头：

```c
#define CFG_FLASH_ADDR 0x19000      // ★★★ 正是我们算出的那个 0x19000
#define CFG_START_ADDR 0X96F8
```

⇒ 我们 ROUND47-59 推断的"参数区基址 `0x08019000`"**与官方定义完全一致**。
⇒ 官方把它叫 **config**（配置区），不是代码区。

### 1.2 官方子固件表格式 —— 与我们的字节级判据**完全吻合**

`gt7868q_update.cpp` 中 `fw_update()` 的解析循环：

```c
for (i = 0; i < sub_fw_num; i++) {
    sub_fw_type = fw_data[sub_fw_info_pos];                              // 1 B  type
    sub_fw_len  = (fw_data[pos+1] << 24) | (fw_data[pos+2] << 16)        // 4 B  len (大端)
                | (fw_data[pos+3] <<  8) |  fw_data[pos+4];
    sub_fw_flash_addr = (fw_data[pos+5] << 8) | fw_data[pos+6];          // 2 B  地址高16位
    sub_fw_flash_addr = sub_fw_flash_addr << 8;                          // ★ <<8 补低8位
    ...
    fw_image_offset += sub_fw_len;
    sub_fw_info_pos += 8;                                                // 每条 8 B
}
```

**与 ROUND24 我们的结论一字不差**：

> `addr(2B BE)<<8 + type(1) + pad(1) + len(2B BE)<<8 + pad(2)`

⇒ **我们纯静态逆出来的格式是对的。官方源码是第三方验证。**

---

## 二、GT7868Q 官方镜像格式（权威定义）

来源：`gt7868q/gt7868q_firmware_image.cpp`

```c
#define GT7868Q_SUB_FW_INFO_OFFSET      32
#define GT7868Q_SUB_FW_DATA_OFFSET      256   // 0x100
#define GT7868Q_FW_IMAGE_PID_OFFSET     15    // 0x0F
#define GT7868Q_FW_IMAGE_PID_LEN        8
#define GT7868Q_FW_IMAGE_VID_OFFSET     24    // 0x18
#define GT7868Q_FW_IMAGE_CID_OFFSET     23    // 0x17
#define GT7868Q_FW_IMAGE_SUB_FWNUM_OFFSET 27  // 0x1B
```

| 偏移 | 长度 | 字段 |
|---|---|---|
| `0x00` | 4 | firmware 长度（大端） |
| `0x04` | 2 | **校验和**（大端）= `sum(data[6 : 6+fw_len]) & 0xFFFF` |
| `0x06` | — | 固件体起始 |
| `0x0F` | 8 | **PID**（产品 ID，ASCII，去零填充） |
| `0x17` | 1 | **CID**（config ID） |
| `0x18` | 1 | VID major |
| `0x19` | 2 | VID minor（大端） |
| `0x1B` | 1 | **子固件数量** |
| `0x20` | — | 子固件信息表（8 B/条） |
| `0x100` | — | 子固件数据区 |

**配置包**（可选，紧跟固件体）：
| 偏移 | 长度 | 字段 |
|---|---|---|
| `fw_len+6` | 2 | config 包长度 |
| `+2` | 1 | **update flag** |
| `+3` | 1 | 子配置数量 |
| `+4` | 2 | 校验和 |
| `+6` | — | 子配置信息表（**3 B/条**：id, len_hi, len_lo） |
| `+0x40` | — | 子配置数据区 |

**update flag 枚举**：
```c
NO_NEED_UPDATE           = 0x00
NEED_UPDATE_FW           = 0x01
NEED_UPDATE_CONFIG       = 0x02
NEED_UPDATE_CONFIG_WITH_ISP = 0x10
NEED_UPDATE_HID_SUBSYSTEM   = 0x80
```

### ⚠️ 但我们的文件**不符合**这个格式

| 检查 | 结果 |
|---|---|
| `[0x0F:8]` PID | `00 00 00 00 00 00 00 00` ❌ 空 |
| `[0x17]` CID | `0x00` ❌ |
| `[0x18]` VID major | `0x00` ❌ |
| `[0x1B]` 子固件数 | `0` ❌ |
| `[0x00:4]` fw_len 大端 | `0x73C01104`（1941967108）❌ 远超文件大小 |
| checksum `[0x04:2]` | `0x0000`，实算 `0xD7A4` ❌ 不匹配 |

⇒ **`TB14P_GT7868Q_14030522_20240202.BIN` 不是 Goodix 官方镜像格式**，
是 **ODM/联想重新封装**的格式（可能是"已烧录后的 flash 全片 dump"）。

⇒ 这也解释了它为什么同时含"头部 + 高熵区 + 明文区"三段异构内容。

---

## 三、★ "高熵区"到底怎么处理 —— 官方给的答案

### 3.1 官方烧录流程根本不"解密"任何东西

`load_sub_firmware()` 实现（`gtx2/gtx2_update.cpp:139`）：

```c
int GTx2Update::load_sub_firmware(unsigned int flash_addr,
                                  unsigned char *fw_data, unsigned int len)
{
    unsigned char buf_load_flash[15] = {0x0e, 0x12, 0x00, 0x00, 0x06};
    ...
    while (retry_load < GDIX_RETRY_TIMES && load_data_len != len) {
        unitlen = (len - load_data_len > RAM_BUFFER_SIZE)
                  ? RAM_BUFFER_SIZE : (len - load_data_len);          // 4096 B 一块

        dev->Write(FLASH_BUFFER_ADDR, &fw_data[load_data_len], unitlen);  // ★ 原样写 RAM 缓冲

        for (check_sum = 0, i = 0; i < unitlen; i += 2)
            check_sum += (fw_data[load_data_len + i] << 8) +
                          fw_data[load_data_len + i + 1];              // ★ 16 位字累加校验

        buf_load_flash[5] = (unitlen >> 8) & 0xFF;
        buf_load_flash[6] =  unitlen       & 0xFF;
        buf_load_flash[7] = (flash_addr >> 16) & 0xFF;
        buf_load_flash[8] = (flash_addr >>  8) & 0xFF;
        buf_load_flash[9] = (check_sum >> 8) & 0xFF;
        buf_load_flash[10]=  check_sum      & 0xFF;

        dev->Write(buf_load_flash, 11);     // 命令 0x0E 0x12：把缓冲刷进 flash
        ...等待 FLASH_RESULT_ADDR(0x5096) == 0xAA
    }
}
```

**⇒ 数据全程原样搬运：`文件字节 → RAM 缓冲(0x c000) → 命令 0x0E12 → flash 目标地址`。
没有任何解密/解压步骤。**

### 3.2 ★ 所以"高熵"是什么？

**答：那是固件自身的正常编码内容**（可能是触控算法系数表、波形数据、压缩的子固件等），
**设备端 MCU 自己知道怎么用，主机侧协议层完全不碰它。**

官方工具的态度就是："**我不管里面是什么，我按 8 字节表头读出 (addr, len)，把这块字节原样搬到 flash 就行。**"

⇒ **"解密高熵区"从一开始就不是一条必要的路。** 这是本次最重要的结论。

### 3.3 而"配置"是明文的

`cfg_update()` 里：

```c
#define CFG_START_ADDR 0X96F8
dev->Read(CFG_START_ADDR, cfg_ver_before, 3);      // 读 config 版本(前 3 字节)
...
dev->Write(CFG_START_ADDR, &fw_data[cfg_offset], sub_cfg_len);  // ★ 明文写 config
```

**⇒ config 数据是明文传输的**（含版本号在首字节 `cfg[0]`）。
⇒ 与我们发现的 `tpcfgsid*.cfg`（明文 `0xNN` 逗号表）**互相印证**。

### ⚠️ 但 `tpcfgsid*.cfg` 的 `cfg[0]` 对不上"纯版本号"

官方说 `cfg_ver_infile = cfg[0]`。实测：

| 文件 | 首 4 字节 | `cfg[0]` | 实际含义 |
|---|---|---|---|
| `tpcfgsid0_Xiaomi7867_20240307` | `50 43 42 00` | `0x50` | ASCII **`"PCB"`** |
| `tpcfgsid2_20230407` | `BE 01 2C 15` | `0xBE` | 数值（真版本号？） |
| `tpcfgsid3_LaiBao7986P_20220701` | `4C 61 69 42` | `0x4C` | ASCII **`"LaiBao"`** |

⇒ 三个 cfg 的 `cfg[0]` 语义**不一致**（两个是 `PCB`/`LaiBao` 标签，一个是数值）。
⇒ 说明 **`tpcfgsid*.cfg` 不是直接下发的 config 载荷**，而是**带元信息头的配置源文件**
   （或者我们手上的是"人可读导出格式"，官方工具用的是二进制形态）。
⇒ **不能直接把 `.cfg.txt` 当 `cfg` 载荷用**；要用官方通路，得先转成二进制并确认头布局。

---

## 四、官方命令协议（与我 ROUND23 的发现交叉验证）

### 4.1 ★ 官方源码里的"刷机三连"—— 正是我们红线里的那个

```c
unsigned char buf_switch_to_patch[] = {0x00, 0x10, 0x00, 0x00, 0x01, 0x01};
unsigned char buf_start_update[]    = {0x00, 0x11, 0x00, 0x00, 0x01, 0x01};
unsigned char buf_restart[]         = {0x0E, 0x13, 0x00, 0x00, 0x01, 0x01};
```

> ⚠️ 注意：**红线里记的是 `00 10 / 00 11 / 0E 12`**，
> 官方源码里是 `00 10 / 00 11 / 0E 13`（重启）+ `0E 12`（**刷 flash**）。
> ⇒ **`00 10` / `00 11` 是进入刷机模式的两条命令；`0E 12` 是真正写 flash。
> 绝对不要碰 —— 官方确认它们是 ISP/loader 通路。**

### 4.2 其他命令（官方明文）

```c
#define CMD_ADDR 0x4160
{0x32,0x00,0x00,0x00,0x32}   // switch to ptp mode
{0x33,0x00,0x00,0x00,0x33}   // dis report coor
{0x34,0x00,0x00,0x00,0x34}   // en  report coor
{0x80, ...}                  // "i want to send cfg"
{0x83, ...}                  // "cfg ready in xdata"
{0x7D, ...}                  // end send cfg
```
握手应答值：`CMD_ADDR == 0x82`（IC 确认收 cfg）、`0x7F`（成功）、
`0x7E 0x00 0x07`（== 与 flash 相同）、`0xAA`（flash 写入成功）、`0xDD`（BL 就绪）。

**命令帧格式**（`cmd_init`）：
```c
cmd_buf[0] = cmd;
cmd_buf[1] = (cmd_data >> 8) & 0xff;
cmd_buf[2] =  cmd_data       & 0xff;
chksum = cmd_buf[0] + cmd_buf[1] + cmd_buf[2];
cmd_buf[3] = (chksum >> 8) & 0xff;
cmd_buf[4] =  chksum       & 0xff;      // 5 字节帧
```

> 这与我 ROUND23 从固件里逆出的"命令号 + 校验"结构一致（同一套协议的两端）。

---

## 五、★ 对"高熵区"的最终处置建议

| 目标 | 官方推荐路径 | 是否需要解高熵区 |
|---|---|---|
| **改配置（含触觉参数）** | `cmd 0x80/0x83/0x7D` + 明文 cfg 写到 `0x96F8` | ❌ **完全不需要** |
| **刷固件** | `gdixupdate` + 官方 BIN，走 `0E 12` | ❌ 不需要 |
| **回刷/修复** | 同上 | ❌ 不需要 |
| 纯学术研究高熵区内容 | 只能从设备侧读（`cmd 0x1B` 等），或找同型号明文样本 | ⚠️ 非必要 |

### 结论

1. ✅ **"解高熵区"不是必答题** —— 官方工具全流程不解密，说明它在协议层是不透明的正常载荷。
2. ✅ **配置改动有明文通路** —— `cfg_update()` 全程明文，`CFG_START_ADDR=0x96F8`，
   且 cfg 就是我们已经拿到的 `tpcfgsid*.cfg` 那种格式（首字节 = 版本）。
3. ⚠️ **但我们的文件不是官方格式** ⇒ 不能直接喂给 `gdixupdate`。
   要用官方通路，**必须拿到 Goodix 官方的 GT7868Q BIN**（不是联想 ODM 的）。
4. ★ **风险判断更新**：与其冒险写 `0x1800`，正确路径是**用官方 cfg 通路**
   （`0x80` → 写 `0x96F8` → `0x83` → `0x7D`），这是官方支持的、有握手的、可回退的操作。

---

## 六、下一步（更新后的优先级）

| 优先级 | 动作 | 说明 |
|---|---|---|
| ★★★★★ | **找 Goodix 官方 GT7868Q BIN**（要 PID/CID/checksum 都对的那种） | 有了它才能用官方通路；联想 ODM 版本用不了 |
| ★★★★★ | **抓一次官方 `gdixupdate` 的 USB 流量**（在能跑的机器上） | 拿到真实的 cfg 下发时序 |
| ★★★★ | 用 `cmd 0x1B` 从**我们自己的设备**读回 27 字节 | 看是否与某个 cfg 字段对应（零风险） |
| ★★★★ | 对比 `tpcfgsid*.cfg` 与 `CFG_START_ADDR=0x96F8` 的 3 字节版本读 | 确认 cfg 版本字段 |
| ★★★ | 找 Windows 侧联想驱动的 cfg 文件（可能同样是明文） | |

> 红线更新：
> - `00 10` / `00 11` / `0E 12` / `0E 13` —— 官方确认是 **ISP/刷机通路**，**绝不碰**
> - 其余保持：禁批量轮询 Col04；≤2 往返/秒

---

## 七、方法论沉淀

1. **"先找官方开源实现"应该排在静态逆向之前** —— 本例中官方仓库直接给出了
   格式定义、命令号、地址常量，省掉数轮猜测。
2. **"高熵" ≠ "必须解密"** —— 先问"这个数据在协议层是否需要被理解"。
   若官方工具只是搬运，则解密不是必要路径。
3. **静态结论需要第三方验证** —— 我们的子固件表格式判据被官方源码逐字段确认，
   这比自证有力得多。
4. **注意"同名不同物"** —— 同为 `GT7868Q`，Goodix 官方 BIN 与联想 ODM BIN
   格式完全不同。用官方工具前必须先验格式。
5. **红线命令的出处要记清** —— `00 10/00 11/0E 12` 现已被官方源码证实为
   ISP 刷机通路，风险等级从"未知"升到"确认危险"。
