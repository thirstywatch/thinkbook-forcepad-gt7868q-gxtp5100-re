# 主线 `goodix_gtx8` 驱动（[PATCH v2 0/3]，Jens Reidel，2026-02-28）— 第三方独立实现

来源：lore-kernel.gnuweeb.org `phone-devel/20260228-gtx8-v2-*@mainlining.org`
（**未合入主线**：torvalds/linux master 上 `goodix_gtx8.c` 仍 404）

## 与本项目的关系：**两条关键结论的外部门独立确认**

### ① YS 校验算法 —— 与我们反推的官方算法**逐字一致**
```c
static bool goodix_gtx8_checksum_valid_normandy(const u8 *data, int size) {
    u8 cal_checksum = 0;
    for (i = 0; i < size; i++) cal_checksum += data[i];
    return cal_checksum == 0;                                  /* NOR: sum == 0 */
}
static bool goodix_gtx8_checksum_valid_yellowstone(const u8 *data, int size) {
    u16 cal_checksum = 0;
    for (i = 0; i < size - GOODIX_GTX8_CHECKSUM_SIZE; i++) cal_checksum += data[i];
    r_checksum = get_unaligned_be16(&data[i]);
    return cal_checksum == r_checksum;                         /* YS: sum(前 n-2) == BE16(末 2) */
}
```

### ② Yellowstone 地址 —— 与本项目实测 / 官方 cfg bin `reg_info` **三者一致**
```c
#define GOODIX_GTX8_FW_VERSION_ADDR_YELLOWSTONE   0x4022   /* 本机 0x4022 = "7869" */
#define GOODIX_GTX8_TOUCH_DATA_ADDR_YELLOWSTONE   0x4180   /* 本机 0x4180 = 40 01 01 00 */
#define GOODIX_GTX8_FW_VERSION_ADDR_NORMANDY      0x4535
#define GOODIX_GTX8_TOUCH_DATA_ADDR_NORMANDY      0x4100
```

### ③ `product_id` 结构 —— **解释了本机读到的 `"7869"`**
```c
struct goodix_gtx8_fw_version {
    char product_id[4];   /* 4 digits IC number */
    u8 __unknown[4];
    u8 fw_version[4];
};
```
本机 `0x4022` 起 12 B = `37 38 36 39 | 00 00 00 00 | 1C 02 03 05`
⇒ **`product_id = "7869"`（4 位 IC 编号）· `fw_version = 1C.02.03.05`**

### ④ 其它独立印证
- `struct goodix_gtx8_header_yellowstone` = **8 字节** ⇒ 与官方 vendor 驱动的 `IRQ_HEAD_LEN_YS = 8` **一致**
- `product_id` 用于 IC 型号校验（本驱动期望 `9886`/`9896`）⇒ 该字段确为「IC 编号」

## 文件
- `patch_0.txt` / `patch_1.txt` / `patch_2.txt` —— lore 原文（0/3 封面、1/3 dt-bindings、2/3 驱动）
- `drivers_input_touchscreen_goodix_gtx8.c`（562 行）/ `.h`（141 行）—— 从 patch_2 抽出的净源码

## ⚠️ 局限
该驱动**只做基础触屏上报**：无 cfg/config 写入路径、无触觉、无 force、
不支持 Normandy/Nanjing 之外的高级功能。**不能用于本项目的目标**，
但可作为**地址与校验算法的第三方独立交叉验证**。
