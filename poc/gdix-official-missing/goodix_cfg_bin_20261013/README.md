# 官方 `goodix_cfg_bin` 样本 + 本机 reg_info 核验（2026-10-13 归档）

## 这是什么
汇顶官方 **`goodix_cfg_bin`** 格式的真实样本（3 份），以及从中提取的
**`reg_info` 寄存器地址表** —— 即项目长期寻找的「官方命令表」。

来源（均由 `r10_1_fetch_cfgbin.py` 从各厂商 vendor 仓库拉取）：
- `lfs-moto-cybert.dat`      ← `rahulsnair/proprietary_vendor_motorola_cybert_bak` → `goodix_cfg_group.bin`
- `lfs-moto-dubai-csot.dat`  ← `JoseMCC0705/vendor_motorola_dubai` → `csot_goodix_cfg_group.bin`
- `lfs-xiaomi-manet.dat`     ← `yuanxing109/android_vendor_xiaomi_manet` → `goodix_cfg_group_manet.bin`

## 格式（Rust 参考实现：github.com/sm7150-mainline/goodix-cfg-bin/src/main.rs）
```
head (10 B packed): u32 bin_len | u8 checksum | u8 bin_version[4] | u8 pkg_num
  checksum = sum(data[5..bin_len]) & 0xFF      且  bin_len == 文件长度
+ 6 B 保留                                        → TS_CFG_BIN_HEAD_LEN = 16
pkg_num × u16 LE 偏移表（各 2 B，绝对偏移）
各包 @偏移：
  GoodixCfgPkgConstInfo 56 B: u32 pkg_len | ic_type[15] | cfg_type | sensor_id |
      hw_pid[8] | hw_vid[8] | fw_mask[9] | fw_patch[4] | x_res_offset |
      y_res_offset | trigger_offset
  GoodixCfgPkgRegInfo  65 B: 14 × {u16 addr | u8 r1 | u8 r2} + reserved[9]
  cfg 数据…
```

## 三份样本提取出的 reg_info（三份**完全一致**）
| 角色 | 地址 |
|---|---|
| `version_base` | `0x4014` |
| `pid` | `0x4022` |
| `vid` | `0x402A` |
| `sensor_id` | `0x402F` |
| `cfg_send_flag` | `0x4034` |
| **`command`** | **`0x4160`** |
| `esd` | `0x4166` |
| `coor` / `gesture` / `fw_request` | `0x4180` |
| `proximity` | `0x4182` |
| **`cfg_addr`** | **`0x96F8`** |
| `fw_mask` / `fw_status` | `0x0000`（三份样本均未设） |

## 本机（ThinkBook 14 G6+ / GT7868Q 模组）只读核验 —— **全部响应**
```
0x4014 version_base  = 00 87 00 00
0x4022 pid           = 37 38 36 39 00 00   → ASCII "7869"
0x402A vid           = 1C 02 03
0x402F sensor_id     = 04                  ★ 不是 0
0x4160 command       = FF                  ✓ TS_CMD_REG_READY
0x4166 esd           = FF
0x4180 coor/gesture  = 40 01
0x4182 proximity     = 01 00
0x96F8 cfg_addr      = 22 00 1B 00 3D 01 04 65   ✓
```
⇒ **官方 reg_info 地址表适用于本机**；`command=0x4160` / `cfg_addr=0x96F8`
   与项目靠行为证据锁定的值**一字不差**。

## 文件
- `lfs-*.dat` —— 3 份官方 cfg bin 样本
- `r10_1_fetch_cfgbin.py` —— 拉取+解析脚本（项目原有）
- `r12_2_phonestruc.py` —— 随附脚本（项目原有）
- 扫描工具：`tools/hid/gdix_cfgbin_scan.py`（全盘/内嵌扫描 goodix_cfg_bin）
