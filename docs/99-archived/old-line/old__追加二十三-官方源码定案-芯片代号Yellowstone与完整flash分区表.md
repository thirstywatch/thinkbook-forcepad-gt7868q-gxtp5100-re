# 追加二十三 —— 官方源码定案：芯片代号 Yellowstone · 三套地址空间 · 完整 flash 分区表

> 日期：2026-09-29
> 起因：用户质疑「官网找不到就去论坛找，国内外都看了吗？」
> 结论一句话：**找到了 Goodix 官方源码，把协议层彻底定案；但固件代码区确认加密，读不出内容。**

---

## 零、这一轮的路径（可复用的方法学）

1. **先划清边界**：项目此前已做「Catalog / LVFS / OEM / GitHub / 网页四轮穷尽」（见 `PREFLIGHT-STATE.md §1`、`SESSION-2026-09-14-PM.md`、`TOUCHPAD-RE-REPORT.md`）。
   ⇒ **渠道层面确实穷尽过**，本轮不再重复找"固件"。
2. **换目标**：不找固件，找 **Goodix 触控板/触控芯片的寄存器手册与驱动源码**。
3. **论坛入口**（国内 + 国外一起）：
   - `bbs.deepin.org/post/286821`（同款机 ThinkBook 16 G6+ IMH，走 ty2 驱动）→ 只讲编译，无新料
   - **`forum.archlinuxcn.org/t/topic/13210/26`（同款机帖）→ 命中关键线索**
   - `blog.csdn.net/qingzhuyuxian/article/details/139618788`、`bbs.archlinux.org/viewtopic.php?id=292878`（同款机）
   - 英文检索命中 Goodix 公开文档中心（`www.goodix.com/docview/...`，含 `GT927 Datasheet` 等）
4. **突破口**：archlinuxcn 帖 #26 用户 `xfzfflm` 贴出
   `https://github.com/goodix/gdix_hid_firmware_update`（"这看上去很像官方的驱动哎"）
   ⇒ **项目此前只引用过第三方 `fwupd/plugins/goodix-tp`，从未引用 Goodix 官方组织。**

---

## 一、★ 新资产：Goodix 官方源码（项目此前完全没有）

### 1.1 `goodix/gdix_hid_firmware_update` —— 官方 HID 固件更新工具

**关键：仓库里有专门的 `gt7868q/` 目录（我们这颗芯片）。**

```
gt7868q/gt7868q.h                    934 B    ★ CMD_ADDR = 0x4160
gt7868q/gt7868q.cpp                3,810 B
gt7868q/gt7868q_update.cpp        15,668 B    ★ Run() / fw_update() / cfg_update() / flash_cfg_with_isp()
gt7868q/gt7868q_update.h           1,135 B
gt7868q/gt7868q_firmware_image.cpp 1,930 B
gt7868q/gt7868q_firmware_image.h     974 B
gtx2|gtx3|gtx5|gtx8|gtx9/            —        各代实现（GT7868Q 继承 gtx3）
firmware_image.cpp/h                         容器解析
main.cpp                          13,307 B
gtp_util.h / gtmodel.h / gt_update.cpp
```

**从 `gt7868q.h` / `gt7868q_update.cpp` 直接读到的官方常量：**

```c
#define CMD_ADDR       0x4160     /* GT7868Q 命令寄存器（HID 工具空间） */
#define CFG_FLASH_ADDR 0x19000    /* 配置区 flash 地址 */
#define CFG_START_ADDR 0X96F8     /* 配置区起始地址 */
/* 官方就是这样读配置版本的： */
dev->Read(CFG_START_ADDR, cfg_ver_after, 3);
/* 还有一条： */
dev->Write(CMD_ADDR, buf_en_report_coor, sizeof(buf_en_report_coor));  /* "enable report coord" */
```

### 1.2 `goodix/gtx8_driver_linux` —— 官方 gtx8 系列 Linux 驱动

```
goodix_ts_core.h        19,699 B   ★ 全部寄存器/命令常量
goodix_ts_core.c        53,341 B
goodix_ts_i2c.c         49,679 B   ★ 协议实现
goodix_ts_gesture.c     12,879 B   ★ 手势模块
goodix_cfg_bin.c        18,829 B   ★ 配置包解析
goodix_cfg_bin.h         2,341 B   ★ 配置包结构体
goodix_gtx8_update.c    42,009 B   ★ 更新流程（fwupd 的实现来源）
goodix_ts_tools.c       16,502 B
docs/porting-guide-gsx.txt · docs/goodix-ts-dtsi.txt
```

### 1.3 `goodix/goodix_advance_touch_platform`

描述为 "Goodix Customized **HID-SPI protocol** driver"（尚未细读）。

---

## 二、★ 芯片代号定案：`YELSTO` = **YELLOWSTONE**

```c
/* goodix_ts_core.h */
#define IC_TYPE_NORMANDY      1
#define IC_TYPE_NANJING       2
#define IC_TYPE_YELLOWSTONE   3
```

```c
/* goodix_cfg_bin.c:295 —— 配置包里的 ic_type 字符串匹配 */
} else if (!strncmp(cfg_bin->cfg_pkgs[i].cnst_info.ic_type,
            "yellowstone", strlen("yellowstone"))) {
    ts_dev->ic_type = IC_TYPE_YELLOWSTONE;
}
```

```c
/* goodix_gtx8_update.c —— 大量 Yellowstone 专属分支 */
#define HW_REG_GIO_YS           0x2014
#define HW_REG_CPU_RUN_FROM_YS  0x4000    /* 注释注明：nor_L 用的是 0x4006 */
#define HW_REG_CPU_RUN_FROM     0x4506
/* 以及专属变体： */
if (ts_dev->ic_type == IC_TYPE_YELLOWSTONE) ...
```

**本机固件里的实证：**

| 位置 | 内容 |
|---|---|
| 本机容器 `0x1142` | `59 45 4C 53 54 4F` = **`YELSTO`** |
| 本机容器 `0x114B` | `37 38 36 38 51` = **`7868Q`** |
| Catalog 样本 `0x049E` / `0x04A7` | 同样 `YELSTO` / `7868Q`（间隔同为 9 字节） |

### ★ 这解释了一个悬了很久的异常

项目记录（多处）：「**本机与 fwupd 的 GTX8 / NORMANDYL 布局不一致**」
（`0x452C` 高熵、`0x60DC=0x02`、PID `0x01E9` 不在 fwupd PID 表内）

**⇒ 根因：本机芯片是 `YELLOWSTONE`，而 fwupd 按 `NORMANDY L` 那一支处理。官方代码里这两支走不同常量（例如 `HW_REG_CPU_RUN_FROM` 对 nor_L 是 `0x4006`、对 YS 是 `0x4000`）。**

---

## 三、★ 完整命令集（官方定义，此前只知道 fwupd 的 3 条）

```c
/* goodix_ts_i2c.c —— 寄存器 */
#define TS_REG_COORDS_BASE   0x824E
#define TS_REG_CMD           0x8040     /* 命令寄存器 */
#define TS_REG_REQUEST       0x8044     /* 请求寄存器 */
#define TS_REG_VERSION       0x8240
#define TS_REG_CFG_BASE      0x8050     /* 配置基址 */
#define TS_REG_DOZE_CTRL     0x30F0
#define TS_REG_DOZE_STAT     0x3100
#define TS_REG_ESD_TICK_R    0x3103
#define TEST_ADDR            0x4100     /* goodix_ts_tools.c: TS_REG_COORDS_BASE 也写作 0x4100 */
#define CFG_XMAX_OFFSET      (0x8052 - 0x8050)
#define CFG_YMAX_OFFSET      (0x8054 - 0x8050)

/* 命令码（写 TS_REG_CMD） */
#define COMMAND_SLEEP                0x05
#define COMMAND_CLOSE_HID            0xaa    /* ★ 项目只知道"0xAA 关 HID"，这是官方名 */
#define COMMAND_START_SEND_CFG       0x80
#define COMMAND_SEND_SMALL_CFG       0x81
#define COMMAND_SEND_CFG_PREPARE_OK  0x82
#define COMMAND_END_SEND_CFG         0x83
#define COMMAND_READ_CFG_PREPARE_OK  0x85
#define COMMAND_START_READ_CFG       0x86
#define COMMAND_END_SEND_CFG_YS      0x7D    /* ★ Yellowstone 专用 */

/* 请求码（写 TS_REG_REQUEST） */
#define REQUEST_HANDLED   0x00
#define REQUEST_CONFIG    0x01
#define REQUEST_BAKREF    0x02
#define REQUEST_RESET     0x03
#define REQUEST_RELOADFW  0x05               /* 重载固件 */
#define REQUEST_IDLE      0xff

/* 命令寄存器回读值 */
#define TS_CMD_REG_READY   0xFF
#define TS_CMD_CFG_OK      0x7F
#define TS_CMD_CFG_ERR     0x7E

/* ★ Yellowstone 专属报文参数 */
#define TS_CFG_HEAD_LEN_YS   5      /* 配置头 5 字节（其他芯片 4） */
#define IRQ_HEAD_LEN_YS      8      /* 中断报文头 8 字节（其他芯片 2） */
#define TS_CFG_HEAD_LEN      4
#define IRQ_HEAD_LEN_NOR     2

/* 配置类型 */
#define TS_NORMAL_CFG        0x01
#define TS_HIGH_SENSE_CFG    0x03

/* 配置包回复码 */
enum TS_SEND_CFG_REPLY {
    TS_CFG_REPLY_PKGS_ERR   = 0x01,
    TS_CFG_REPLY_CHKSUM_ERR = 0x02,
    TS_CFG_REPLY_DATA_ERR   = 0x03,
    TS_CFG_REPLY_DATA_EQU   = 0x07,
};
```

---

## 四、★★★ 三套地址空间 —— 这解释了项目所有「地址对不上」的困惑

| 地址空间 | 使用者 | 代表地址 | 证据 |
|---|---|---|---|
| **A. I2C 直连** | `gtx8_driver_linux`（Linux 内核驱动） | `0x8040`（CMD）· `0x8044`（REQUEST）· `0x8050`（CFG_BASE）· `0x824E`（COORDS）· `0x30F0`（DOZE） | `goodix_ts_i2c.c:37-44` |
| **B. HID 更新协议** | `goodix_gtx8_update.c` / fwupd 参考实现 | `0x2014` GIO_YS · `0x4000` CPU_RUN_FROM_YS · `0x6020` SUBSYS_TYPE · `0x6022` FLASH_FLAG · `0xC000` ISP_ADDR · `0x6100` ISP_BUFFER · `0x2180/0x2184` CPU_CTRL/RESET | `goodix_gtx8_update.c:30-49` |
| **C. HID 官方工具空间** | `gt7868q/gt7868q.h`（官方 gdixupdate） | `0x4160` CMD_ADDR · `0x96F8` CFG_START_ADDR · `0x19000` CFG_FLASH_ADDR | `gt7868q.h:23`、`gt7868q_update.cpp:26-27` |
| **D. 第三方 fwupd** | `fwupd/plugins/goodix-tp` | `0x60CC` CMD_ADDR · `0x5095` BL_STATE · `0x5096` FLASH_RESULT · `0xC000` FLASH_BUFFER · `0x452C` fw_info · `0x60DC` cfg 版本 | Goodix 官方源码里**均不出现** |

> ## **⇒ 结论：fwupd 那套（`0x60CC` 等）是第三方自己实现的一套地址，与官方两套（B/C）都不同。**
> **项目此前把 `0x60CC` 当"官方 GTX8 协议"来对照本机，方向本身就偏了。**

---

## 五、★★★ 完整 flash 分区表（12 项，两份固件逐字段一致）

### 5.1 官方结构定义

```c
/* goodix_gtx8_update.c */
#define FW_HEADER_SIZE        256
#define FW_SUBSYS_INFO_SIZE   8
#define FW_SUBSYS_INFO_OFFSET 32
#define FW_SUBSYS_MAX_NUM     28
#define FLASH_SUBSYS_TYPE_CONFIG 0x03
#define FLASH_ADDR_CONFIG_DATA   0x1E000
#define ISP_MAX_BUFFERSIZE    (1024 * 4)

#pragma pack(1)
struct fw_subsys_info { u8 type; u32 size; u16 flash_addr; };
struct firmware_info {
    u32 size;            u16 checksum;
    u8 hw_pid[6];        u8 hw_vid[3];
    u8 fw_pid[8];        u8 fw_vid[4];
    u8 subsys_num;       u8 chip_type;   u8 protocol_ver;  u8 reserved[2];
    struct fw_subsys_info subsys[FW_SUBSYS_MAX_NUM];   /* 32 + 28×8 = 256 = FW_HEADER_SIZE */
};
/* 关键换算（update.c:757）：subsys_base_addr = subsys->flash_addr << 8 */
```

### 5.2 **实测解出的磁盘编码**（本机与 Catalog 样本在共用明文段内一致成立）

| 字节 | 含义 |
|---|---|
| `byte[0]` | `type`（`0x03` = CONFIG，`0x02` = 另一类） |
| `byte[1..4]` | `size`，**big-endian u32**（如 `0x2000` = 8 KB） |
| `byte[4..7]` | `flash_addr`，**big-endian u32 绝对 flash 字节地址** |

**表位置：本机 `0x1164`（`YELSTO`+0x22）· Catalog 样本 `0x04C0`（`YELSTO`+0x22）**

### 5.3 解出的 12 个分区（两份固件**完全相同**）

| idx | type | size | flash_addr | 备注 |
|---|---|---|---|---|
| 0 | 0x03 | 0x2000 | **0x16000** | |
| 1 | 0x03 | 0x2000 | **0x06000** | |
| 2 | 0x03 | 0x2000 | **0x08000** | |
| 3 | 0x03 | 0x2000 | **0x0A000** | |
| 4 | 0x03 | 0x2000 | **0x0C000** | ★ `HW_REG_ISP_ADDR` |
| 5 | 0x03 | 0x2000 | **0x1E000** | ★ **`FLASH_ADDR_CONFIG_DATA`** ← 配置数据 8 KB |
| 6 | 0x03 | 0x2000 | **0x10000** | |
| 7 | 0x02 | 0x3000 | **0x01000** | |
| 8 | 0x02 | 0x1000 | **0x00000** | |
| 9 | 0x03 | 0x2000 | **0x04000** | ★ `HW_REG_CPU_RUN_FROM_YS` |
| 10 | 0x02 | 0x3000 | **0x13000** | |
| 11 | 0x02 | 0x1000 | **0x12000** | |
| 12 | —— | —— | —— | 全零项，表结束 |

**★ 用三个官方常量交叉验证（`0xC000` / `0x1E000` / `0x4000` 全部命中对应分区）⇒ 这张表解对了。**

---

## 六、★ 配置区实测（走 HID 通道，按官方地址直接读）

用本机 **Col04 的 `0x20` 内存读**（4 字节对齐单块读）按官方地址读：

### 6.1 `0x96F8`（官方 `CFG_START_ADDR`）—— 有结构的明文

```
0x96F8: 22 01 1B 00 3E 01 04 65 A7 C3 E1 02 B5 02 1F 14
0x9708: 71 48 93 20 22 04 01 20 01 13 88 0A 09 05 00 00
0x9718: 77 76 77 69 00 00 00 01 77 54 77 58 77 50 77 4A
0x9728: 00 00 00 00 77 62 77 3C 77 46 77 20 00 00 00 00
0x9738: 00 00 00 00 00 00 00 01 77 84 77 80 77 79 77 5B
0x9748: 76 96 76 66 76 AE 77 31 77 31 77 31 77 15 77 A3
0x9758: 00 00 00 00 77 04 77 15 00 00 00 00 00 00 00 00
0x9768: 00 06 00 07 00 06 00 06 00 18 00 14 00 08 00 07
```
16 位值样例：`34, 27, 62, 4, 167, 225, 181, 31, 113, 147, 34, 1, 1, 136, 9, 43, 10, 0, 0, 0, 0, 119, 119, 119, 119 …`（`0x77` 连续段）

### 6.2 `0x19000`（官方 `CFG_FLASH_ADDR`）—— 有符号小增量（标定表）

```
0x19000: FF FA FF FD FF FD 00 01 00 00 00 00 FF FE FF FF
0x19010: 00 00 00 00 00 00 FF FF 00 01 00 07 00 04 00 01
```
16 位值几乎全是 `255(-1)` 与 `±1..±6` ⇒ **增量编码的标定数据**

### 6.3 ⇒ 关键判定

**在这两个活配置区里搜本机已知的触发阈值 `70 (0x46)` 与 `48 (0x30)`：8 位、16 位小端 —— **全部 0 命中**。**

**⇒ 这两个区确实是"可读的活配置"，但**点击阈值不在其中**。**

### 6.4 反证三套地址空间

按官方 I2C 地址读 `0x8040`/`0x8050`/`0x6020`（经 HID 通道）得到的是无关高熵数据
⇒ **印证 §四：HID 通道与 I2C 直连是两套地址空间，不能混用。**

---

## 七、★ 两份 GT7868Q 固件的对齐差分

**样本来源**：Microsoft Update Catalog，`Goodix TouchPad FW Driver` 0.0.0.2（2020-07-14）
`package_2f992792….cab` → `GOODIXTOUCHPADCAPSULE_22001E0D.Cap`（133,716 B）
→ 按 FMP capsule 解析（`Version=1`、`PayloadItemCount=1`、`UpdateImageSize=0x209FC`）
→ **固件载荷 133,628 B**

**对齐**：锚点 `YELSTO`，本机 `@0x1142` ↔ 样本 `@0x049E`，**delta = 0xCA4**

| 项 | 结果 |
|---|---|
| 重叠域 | 133,628 B |
| **逐字节相同** | **32,877 B** |
| 逐字节不同 | 100,751 B |
| 相同率 | **24.6%** |
| 最长连续相同段 | **2,279 B @ 本机 0x1157 / 样本 0x4B3**（含 §五 的分区表） |

**其他较大"完全相同"段**：`0x36E0`(858) · `0x5630`(1034) · `0x84F0`(5450) · `0xBA3C`(**8210**) · `0xF638`(1026)

### ★ 熵检验（判断明文/密文）

| 段 | 熵 |
|---|---|
| 共用 `0x1157` | 7.658 |
| 共用 `0x36E0` | 7.914 |
| 共用 `0x5630` | 7.997 |
| 共用 `0x84F0` | **7.998** |
| 共用 `0xBA3C` | 7.980 |
| 共用 `0xF638` | **7.999** |
| 差异 `0x2C17` | 7.355 |
| 差异 `0x4B3A` | 7.314 |

**⇒ 共用段熵 ≈ 8.0 ⇒ **是密文/压缩数据**，不是明文（ASCII 全是随机片段，16 位值分布均匀）。**

### ★ 两条推论

1. **加密不是"全文件位置相关"**：两份在相差 `0xCA4` 的偏移上仍有 33 KB 逐字节相同
   ⇒ 很可能是**按区块（子系统）独立加密/压缩**，内容相同的区块 → 密文相同。
2. **但这不提供读取能力**：那些区块本身就是密文，差分只能告诉你"哪块相同/哪块不同"，**读不出内容**。

---

## 八、对项目既有结论的影响

### 8.1 强化的（未变）

| 结论 | 本轮证据 |
|---|---|
| 蓝莓描述符无 `0x0E/0x21` | 其 `/About-Goodix-TouchPad.md` 原文："Take **GT7863 in the project** as an example" ⇒ 那份描述符来自**蓝莓手头的模组**，不是华为 MateBook |
| 华为/荣耀的 GXTP7863 无扳机 | Linux `GXTP7863` 补丁串（2026-08-14 起 15 封）**全程不提触觉**，而审阅者 **Benjamin Tissoires** 正是 `hid-haptic.c` 的合入者 |
| 汇顶产品线无 HID 扳机 | 官方 gtx8 驱动全套源码搜 `haptic/vibrate/LRA/motor/waveform` = **0 命中** |
| `0x5B92–0x5BE4`（48/48/70×40）不是生效阈值 | 42/42 全改成 20 后，报文级复测按下中位仍 **141.5**（基线 143） |
| "关闭 HID"类命令存在 | 官方命名 `COMMAND_CLOSE_HID = 0xaa` |

### 8.2 纠正的（本轮的自我纠错，两条）

1. **「本机是 7869、Catalog 样本是 7868Q」—— 错。**
   两份固件的 `YELSTO` 后都是 `7868Q`（`37 38 36 38 51`）。
   `0x4000` 窗口里另有一处 `7869`，是**另一个字段**，不是芯片型号。
2. **「固件加密 ⇒ 完全无法对比」—— 部分错。**
   两份确实有 32,877 B 逐字节相同（同一密钥 + 分区块加密），所以**差分是可行的**；
   但差分结果**读不出内容**，因为区块本身是密文。

### 8.3 新增解释（两条历史悬案）

| 悬案 | 新解释 |
|---|---|
| 「本机与 fwupd 的 GTX8/NORMANDYL 布局不一致」（`0x452C` 高熵、`0x60DC=0x02`、PID `0x01E9` 不在 fwupd 表内） | **本机芯片是 `YELLOWSTONE`（`IC_TYPE=3`），fwupd 按 `NORMANDY L` 那一支处理**。官方代码里两支走不同常量（`HW_REG_CPU_RUN_FROM`：nor_L `0x4006` / YS `0x4000`） |
| 「fwupd 的 `0x60CC` / 官方的 `0x4160` / Linux 的 `0x8040` 一直对不上」 | **三套独立地址空间**（HID-第三方 / HID-官方 / I2C 直连），本就不可互相印证 |

---

## 九、仍然封闭 vs 仍然开放

### 9.1 封闭（本轮进一步封死）

| 方向 | 封闭依据 |
|---|---|
| 用"对比固件异同"读出华为实现 | 固件主体熵 7.95–7.99（密文/压缩）；共用段虽相同但读不出内容 |
| 点击阈值在可读配置区 | `0x96F8`、`0x19000` 两个活配置区实测**无 70/48**；`0x5B80` 区 42/42 写入实测无效 |
| 触觉命令存在 | 官方全套源码 `haptic/vibrate/LRA/motor/waveform` **0 命中** |
| 改 TF100A 固件实现"边缘滑动震动" | TF100A 反汇编里 **无坐标概念**（`0x4149`/`0x0863`/`0x07FF`/`0x0FFF` 全部 0 命中）；它只有 4 路压力（`0x08005BF8`：从 `[src+i*2+2]` 读 4 个 16 位值累加 300 次） |

### 9.2 开放（按可行性排序）

| # | 方向 | 成本 | 能定案什么 |
|---|---|---|---|
| 1 | **逻辑分析仪夹 `PB6/PB7`（I2C1）** | ¥30–100 | ① 判定"按下/阈值判定在 TF100A 还是 GT7868Q" ② 39 条命令表对在跑固件是否成立 ③ 坐标是否经 I2C1 下发 |
| 2 | **把 Goodix 官方 `gtx3/gtx8` 源码用于本机协议验证** | 零（已有源码） | 按官方语义重测 `0x8040`/`0x8044` 命令族（**需先确认 HID 通道是否映射这些地址**） |
| 3 | **`goodix_advance_touch_platform`（HID-SPI 协议驱动）细读** | 零 | 可能有 HID 通道的官方协议定义 |
| 4 | 料板 + 改 TF100A 固件 | ~¥100 + 高风险 | 前提是 1 的结论是"判定在 TF100A" |
| 5 | 换 A 级设备（有 `0x0E/0x21`，如 Surface Laptop 8） | 换机 | 软件层立刻可用"滑动逐格震动" |

---

## 十、资产清单（全部已落盘）

### 工作区 `<LAB>\touchpad-lab\`

| 路径 | 内容 |
|---|---|
| `poc/gdix-hid-fw/` | **官方 HID 更新工具全套**（含 `gt7868q_*` 5 个文件、`gtx3_*`、`gtx8_*`、`main.cpp`、`gtp_util.h`、`gtmodel.h`） |
| `poc/gtx8-official/` | **官方 gtx8 Linux 驱动全套**（14 个文件） |
| `poc/goodix-fw/` | Catalog 下载：`goodix_tp_fw_0.0.0.2.cab` · `GOODIXTOUCHPADCAPSULE_22001E0D.Cap` · **`goodix_tp_payload.bin`（133,628 B，第二份 GT7868Q 固件）** · `GoodixTouchpad.inf` |
| `poc/threshold-probe.ps1` | 阈值区备份/写入/校验/还原（**含对齐单块读法修正**） |
| `poc/reg-diff-probe.ps1` · `poc/uia-thresh-probe.ps1` | 注册表 / UIA 操作 Windows 触控板设置 + 设备内存差分 |
| `poc/win-touchpad-settings.png` | Windows 触控板设置页截图 |
| `re/press-analyze.py` | 报文级点击阈值测定 |
| `re/compare-fw.mjs` | 固件结构/熵对比 |
| `re/parse-cfg-bin.mjs` | 按官方 cfg_bin 格式解析 |
| **`re/flash-table.mjs`** | **★ 解析 flash 分区表（本轮核心工具）** |
| `re/align-diff.mjs` | 两份固件对齐差分 |
| `haptic-capability/` | 能力探测 + 分级支持（HapticCap.cs / probe-haptic.ps1） |

---

## 十一、方法学（可复用，写给下一次）

1. **找固件 ≠ 找源码**。渠道穷尽后，改找**芯片厂商的官方 GitHub 组织 / 公开文档中心**，收益远大于再翻固件库。
2. **论坛的正确用法**：搜"同款机 + 寄存器/驱动"而不是搜"固件"。同款机用户的**驱动编译帖**里常有人贴出官方仓库链接。
3. **交叉验证法**：自己解出的表，必须用**官方常量**去命中（本轮 `0xC000`/`0x1E000`/`0x4000` 三项全部命中，才敢认这张表）。
4. **对齐差分法**：两份同族样本 → 找唯一锚点（如 `YELSTO`）→ 求 delta → 全文件逐字节差分 → 分出"共用"与"按机型"。
5. **熵判据**：差分出的"相同段"必须做熵检验，熵≈8.0 就是密文，**不要误当明文**。
6. **字节序陷阱**（沿用 `追加十一`）：HID 窗口的分块读会出伪影，**必须用"起始地址 == 目标地址"的 4 字节对齐单块读**。

---

## 十二、一句话总结

> **本轮把 GT7868Q 的"协议—寄存器—flash 布局—配置地址"从推测升级为官方源码背书的地图；
> 同时确认：那张地图指向的代码区是加密的，而明文的那颗触觉芯片（TF100A）结构上没有坐标能力。
> 因此"边缘滑动震动"在本机的软件可及范围内仍然封闭 —— 这不再是猜测，而是有官方定义 + 报文级实测双重支撑的定论。**
