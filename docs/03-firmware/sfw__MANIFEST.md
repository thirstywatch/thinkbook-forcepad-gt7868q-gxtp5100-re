# Surface Laptop Studio 1964 触摸板 / 触觉固件清单

来源：ESP32-Haptic-Precision-TouchPad 项目（`barryblueice`）所用硬件 =
**Surface Laptop Studio 1964 Synaptics S96U7 触摸板 + CS40L25 触觉 DSP +
Surface Aggregator（SAM，即本项目的「EC」）**。

## 一、原始固件（官方 UEFI FMP 胶囊）

从 Microsoft 官方驱动固件包
`SurfaceLaptopStudio_Win11_22631_26.073.29264.0.msi`
中解出。MSI 本身 SHA-256 =
`522c70e53a44211e5c55a3635109a8c7c6d314f69a4b51fa439d4b4cbfb0184c`
（与项目逆向记录中的官方数值一致）。

| 文件 | 字节 | SHA-256 | 作用 |
|---|---:|---|---|
| `SurfaceSAM_9.101.139.bin` | 1,382,917 | `b08729c69e6174b2bc5fa589515e3ef262623db043fe378c23150726be6292f2` | **EC / SAM 控制器固件**：直接驱动 CS40L25，含触觉强度映射、按键/压力状态机、Flash 双槽读取 |
| `SurfaceTouchpad_4.12.139.bin` | 364,693 | `0e7e1bb2d575694c4fe5d261b5075750a75ef7a02ce5e57e81722d8be424ac3b` | 触摸板主固件（Synaptics S96U7 侧） |
| `SurfaceTouchpadForce_10.0.156.bin` | 63,117 | `dd2b4d237f142b7a2bba589f456bae582bae3ef299ddfae7f516c5825a03bf26` | 压感 Force Sensor 固件 |
| `SurfaceTouchpadHaptic_2.9.139.bin` | 105,591 | `e06ae4cd8aa6dd99bf07066756f3b5339477760f228d7db3a683baca230e8616` | **CS40L25 触觉 DSP 固件**（本项目逆向的主要对象） |

> 三个 Touchpad 固件同时可从 `barryblueice/mcu-drivers` 的 `targetbin/` 直接取得，
> 两处副本 SHA-256 逐字节一致（已交叉校验）。

## 二、CS40L25 触觉固件解包产物

`SurfaceTouchpadHaptic_2.9.139.bin` 的五层剥离：
`FMP → auth(PKCS7) → MSS1 → SAML → CFU → Component → body`

| 文件 | 字节 | SHA-256 | 说明 |
|---|---:|---|---|
| `component.reassembled.bin` | 39,370 | `d418621ebd34bdc65f08da5700f35b627b896a9231080802945964d6c066565b` | 去掉 CFU 分帧后重组的连续 Component |
| `component.cfu.payload.bin` | 51,675 | `46398c532796435185957ff047bf8e306261cbbbc04cb88b0752b49accbc9c1e` | 带 5 字节记录头的单份 CFU payload |
| `component.body.bin` | 39,262 | `cdafedaf6461fab702c6b016581f513630a39fe3fedae3a22dae8b5d37638c4c` | Component 头（`body@0x6C`）之后的 Haptic body |
| `offer0.bin` / `offer1.bin` | 16 each | — | 两组 CFU offer；载荷字节相同，仅 offer 协议字段不同 |
| `signature.p7b` | 2,048 | `0f71e51a61f09b7081a9fa93e0553f3e86de4d73bd97648290f0860062e1a4c5` | WIN_CERTIFICATE_UEFI_GUID 原始签名字节（未验签） |
| `haptic_blocks.json` | 30,244 | `a8f41a80e0dd8644a5f0283fb514ae8266ec3b168bf46ae531108d675d3e7f65` | 167 个 DSP 写入块的 seq/地址/长度/CRC16/SHA-256 |
| `capsule_meta.json` | 598 | — | FMP/Capsule 头部元数据与各层偏移 |

### DSP 写入块分解

body 头：`revision=0x02800010`，`block_count=167`，**全部 167 块 CRC16/CCITT-FALSE 校验通过**。

| 区段 | 块序号 | 内容 |
|---|---|---|
| core | 0–136（137 块） | 与 Cirrus 参考固件 `prince_haptics_ctrl_ram_remap_ext_boost_0A0603.wmfw` 逐块一致 |
| Surface 追加 | 137–166（30 块） | Microsoft 追加的 waveform / WSEQ |

HALO ID：`firmware_id=0x1400E1`，`firmware_revision=0x0A0603`，
算法 `0xBD VIBEGEN` + `0x111 DYNAMIC_F0`。

### 三个调参区（Surface 追加部分，按地址合并）

| 文件 | 字节 | 基址 | 对应控制 |
|---|---:|---|---|
| `tuning_02800b60.bin` | 2,408 | `0x02800B60` | VIBEGEN XM wavetable（控制容量 2,480，未写尾部 72 B） |
| `tuning_03400000.bin` | 4,048 | `0x03400000` | VIBEGEN YM wavetable（控制容量 7,000，未写尾部 2,952 B） |
| `tuning_028016d0.bin` | 452 | `0x028016D0` | CS40L25 WSEQ |

## 三、仓库内嵌的等价物

`barryblueice/ESP32-Haptic-Precision-TouchPad` 仓库里没有独立 `.bin`，固件以 C 数组内嵌：

| 文件 | 说明 |
|---|---|
| `Main/main/I2C/SUB_DEV/mcu-drivers/fw_img/cs40l25_fw_img.c` | 逆向重建的 `fw_img_v2`，38,609 字节（IMG_SIZE 字段 38,576） |
| `.../cs40l25_cal_fw_img.c` | CS40L25 标定固件，10,117 字节 |
| `.../cs40l25/bsp/surface_fw_metadata.h` | 元数据：`SURFACE_FW_ID 0x1400E1`、`REVISION 0x0A0603`、XM 25 / YM 53 waves |

已从 C 数组还原为 `SurfaceTouchpadHaptic_2.9.139_sdk_surface_fw_img_v2.bin`
（38,609 字节，SHA-256 `6dffabce400bc3d64e9412cbb4f6e356f71916d2ad5ddc1fcef4ed405593c266`）。

## 四、工具脚本

| 脚本 | 作用 |
|---|---|
| `extract_haptic.py` | 严格解包 FMP→CFU→body，校验 CRC 与全部结构不变量 |
| `msi_decode.py` | 解码 MSI 的 string pool 与表流，还原 `fil*` 键 → 长文件名 |
| `dl.sh` | 16 线程分段下载 1.9 GB MSI（单线程仅约 100 KB/s） |

## 五、校验结论

- MSI 大小与 SHA-256 **与项目逆向记录中的官方数值完全一致**
- 三个 Touchpad 固件的 MSI 副本与 GitHub 副本 **SHA-256 逐字节一致**
- 2461 条 CFU 记录 / 39,370 字节 Component / 167 块 / 137+30 拆分 /
  2,408 + 4,048 + 452 三区 —— **全部复现项目 wiki 记录的数字**
- `SurfaceSAM_9.101.139.bin` 头部自洽：`TotalSize` 与文件长度相等，
  FMP v1 / 0 driver / 1 payload，image header v2，PKCS7 认证区完整
