> 📌 **本文中的文件路径均为撰写时的本机路径**，指向的 `surface/` 等分析产物目录
> 未随本仓库归档（属第三方厂商提取的中间产物，按 §不入库红线排除）。
> 下列路径已改为纯文本保留，仅作线索参考，不再是可点击链接。

# Surface MSI 解包与 SAM 中的 CS40L25 主机控制逻辑

记录日期：2026-09-13。

最新完整归档：SAM 控制逻辑恢复（`SAM_CONTROL_LOGIC.zh-CN.md`，未入库）。包括两变体启动 RAM 解压、HID 强度描述符、BuckBoost 与触摸板生命周期状态表、I²C 设备地址、Flash 读取回调及异常路径。

后续进展：SAM 强度设置与按压振动逻辑（`SAM_INTENSITY_AND_PRESS.zh-CN.md`，未入库） 已追通设置值到按下/释放波形索引对的分档映射，并补充本层 `0xD1` 设置/读回及命令触发路径。下文两个低 8 位参数的阶段性未知说明以该后续记录为准；完整压力状态机仍未恢复。

**本次已在 MSI 携带的 SurfaceSAM 固件中定位到直接控制 CS40L25 的 ARM Thumb 代码。** 已经恢复下载块格式、内置/外部固件选择、两套初始化寄存器表、DSP 启动、mailbox 波形触发和部分运行时控制写入。结果是原始机器码的静态分析与伪代码记录，不是厂商 C 源码，也不是经过上板测试的 MCU 移植工程。

这里的“主机”是相对于 CS40L25 的设备侧控制器 SAM。Windows 上层请求如何一路映射到 SAM 的具体事件、压力阈值和点击/释放状态机，尚未完整追踪。

## 1. MSI 完整解包结果

输入：`surface/SurfaceLaptopStudio_Win11_22631_26.073.29264.0.msi`

| 项目 | 结果 |
|---|---|
| MSI 大小 | 2,063,159,296 字节 |
| MSI SHA256 | `522c70e53a44211e5c55a3635109a8c7c6d314f69a4b51fa439d4b4cbfb0184c` |
| 嵌入 CAB | `cab1.cab`、`cab2.cab`、`cab3.cab` |
| MSI File 表项目数 | 1,290 |
| 恢复文件数 | 1,290，全部与 File 表大小相符，无未映射 CAB 成员 |
| 恢复文件总大小 | 4,860,070,578 字节 |
| 是否安装驱动/执行 CustomAction | 否 |

解包目录：surface/unpacked/payload/SurfaceUpdate（`../../surface/unpacked/payload/SurfaceUpdate`，未入库）。清单：surface/unpacked/manifest.json（`../../surface/unpacked/manifest.json`，未入库），每个文件均记录 SHA256。

`extract_msi.py` 使用只读 `MsiOpenDatabaseW` 读取 File、Component、Directory、Media 等表，通过 7-Zip 解压三个 CAB。CAB 内的 `fil...` 键按 MSI 表恢复长文件名和目录。移动文件前验证源、目标的解析后绝对路径均处于解包目录，拒绝目录循环、输出碰撞和路径逃逸。

未使用 `msiexec /i`，也没有执行包内调用 `pnputil` 的安装脚本。MSI 的 CustomAction 只是作为分析数据记录在 `msi_tables.json`。

## 2. 为什么转向 SAM

先扫描 631 个选定扩展名文件，累计 2,696,802,749 字节，查找 ASCII/UTF-16LE 的 `cs40l25`、`cs40l2`、`cirrus`、`haptic`、`touchpad`、`synaptics`、`vibegen`、`poweronsequence`。扫描结果与范围见 keyword_scan.json（`../../surface/analysis/keyword_scan.json`，未入库）。

结果与 INF、PE 导入表交叉核对：

| 组件 | 实际发现 | 判断范围 |
|---|---|---|
| SurfaceTouchpadHaptic | INF 注册 `UEFI\\RES_{0C7BB439-599A-4B49-BA8B-083D98102638}`，复制 `.bin` 到 Firmware 目录 | 这是固件资源更新包；该目录没有对应常驻 `.sys` |
| SurfaceCFUOverHid.dll | HID firmware-update Usage `FF0B:0101`，导入 `HidP_GetCaps` 等 API，含 DMF CFU 传输模块名称 | 通用 HID 固件更新传输；未识别到 CS40L25 专用控制代码 |
| SurfaceHidMiniDriver.sys | GenericHid、`DMF_SamCommunicationViaSsh_*`，INF 绑定 SAM/KIP HID 类别 | 存在 SAM HID 转发链路，尚不能把每个通道都归于触摸板 |
| SurfaceIntegrationDriver.sys | PrecisionTouchPad 注册表路径 | 该字符串不能证明直接控制芯片 |
| TouchPenProcessor0C1B.dll | TouchPadRectAnt、SetTouchpadData 等面板几何/姿态相关信息 | 未据此认定是触觉驱动 |
| SurfaceSAM_9.101.139.bin | TOUCHPAD、ActuateHaptic、HAPTIC_DRIVER 等被 CFU 记录头分隔的文本 | 进一步重组后找到了直接 CS40L25 下载与控制实现 |

五个候选 Windows 二进制的 PE 信息和反汇编保存在 surface/analysis/pe（`../../surface/analysis/pe`，未入库）。包内未发现 `.pdb` 文件；二进制中的 PDB 名称和 GUID 仅是调试目录信息，未获取外部符号。关键词缺失不能排除剥离字符串或压缩后的代码，所以本报告不以搜索零命中作为“不存在”的证明。

UEFI `.bin` 也做了初步检查：7-Zip 可识别部分 firmware volume，但直接打开整份 Capsule 会报告 Headers Error 和尾部数据。未把这次不完整视图当成 UEFI 全量解包成功。SAM 中已经得到直接证据，本次控制逻辑分析聚焦于 SAM。

## 3. SAM 两份载荷必须分别保留

SAM Capsule 沿用 FMP/MSS1/SAML/CFU 外层，但有两点与此前 Touchpad 包不同：

1. 证书区已含完整 CMS ContentInfo，不需要再补 SignedData 外壳。
2. 两组 offer 的载荷不同，不是冗余副本。

`analyze_sam.py` 对已知版本的 offer 严格匹配，逐条检查 CFU 地址连续、数据完整，分别输出两份组件和 body，不修改旧的 `parse_cfu_pairs()` 对原三个 Touchpad 样本的约束。

| 项目 | 变体 0 | 变体 1 |
|---|---|---|
| offer | `020000b08b6500090100000004023c00` | `020000b08b6500090100000014023c00` |
| CFU 记录数 | 32,871 | 32,871 |
| 组件大小 | 525,932 | 525,932 |
| body 偏移 | `0x66C` | `0x66C` |
| body 大小 | 524,288 | 524,288 |
| 复位向量 | `0x000E4D75` | `0x000E6705` |

OpenSSL 分离签名验证通过；证书信任链未评估。两份 offer 的具体平台选择语义尚未确认，因此只称“变体 0/1”，不称为 A/B 分区或 debug/release。

原始产物与证据：

- SAM manifest.json（`../../surface/analysis/sam/manifest.json`，未入库）
- body_0.bin（`../../surface/analysis/sam/body_0.bin`，未入库）、body_1.bin（`../../surface/analysis/sam/body_1.bin`，未入库）
- 变体 0 字符串及指针引用（`../../surface/analysis/sam/body_0.strings.json`，未入库）
- 签名验证日志（`../../surface/analysis/sam/signature_verification.log`，未入库）

## 4. 地址映射与反汇编依据

采用 `body_offset + 0x80000` 作为分析地址，依据包括：

- 变体 0 复位向量指向 `0xE4D74` 的有效 Thumb 启动代码。
- 该启动代码将 `0x80000` 写入 ARM VTOR 地址 `0xE000ED08`。
- `ActuateHaptic` 位于 body `0xDC20`，代码 literal 引用值为 `0x8DC20`。
- DSP 数据描述符中的指针按这个基址可以正确取出数据，并与 Haptic 更新包交叉匹配。

脚本构造了 ELF32 包装供工具识别：body_0.analysis.elf（`../../surface/analysis/sam/body_0.analysis.elf`，未入库）、body_1.analysis.elf（`../../surface/analysis/sam/body_1.analysis.elf`，未入库）。ELF 的 `.text` 从 `0x80000` 映射，原始 body 逐字节保留在文件偏移 `0x1000`。这些 ELF 是分析辅助物，不能视为原厂构建产物或直接刷写文件。

LLVM 以 `thumbv7m-none-eabi` 反汇编；这是解码模式选择，不等于已经确认具体 MCU 型号。完整线性反汇编会把数据和 literal pool 也当作指令，不能据此自动判定所有函数。已人工追踪的片段单独保存在 reviewed_functions.asm（`../../surface/analysis/sam/reviewed_functions.asm`，未入库），地址、分析命名及字节指纹在 reviewed_functions.json（`../../surface/analysis/sam/reviewed_functions.json`，未入库）。

## 5. 直接下载 CS40L25 的函数

下文地址均为变体 0 的分析地址，函数名称由分析赋予。

| 地址 | 已确认行为 |
|---|---|
| `0x000903F8` | 总线纯写入包装，继续调用公共传输例程 |
| `0x00090414` | 总线写入后读取包装 |
| `0x000DCBC0` | 遍历 12 字节下载描述符，拼大端地址及原始 payload，逐块发送 |
| `0x000DCC4E` | 按 137、11、2 块顺序下载内置核心、波表和序列 |
| `0x000DCCC4` | 从外部镜像接口取得单个块并发送 |
| `0x000DCD54` | 从外部镜像读取块数，循环下载 |
| `0x000DCDFA` | 初始化主流程，尝试外部镜像，必要时回退内置镜像 |

内置描述符格式为三个小端 u32：

```c
struct DownloadBlock {
    uint32_t size;
    uint32_t cs40l25_address;
    uint32_t sam_data_pointer;
};
```

`0xDCBC0` 对应的数据操作可以写成：

```c
// 分析伪代码：bus_write 为原 SAM 总线包装，ctx 为原设备上下文。
status = 0x80000000;
for (i = 0; i < count && (status & 0x82000000) == 0x80000000; ++i) {
    packet[0..3] = big_endian_u32(blocks[i].cs40l25_address);
    memcpy(packet + 4, sam_memory(blocks[i].sam_data_pointer), blocks[i].size);
    status = bus_write(ctx, packet, blocks[i].size + 4);
}
return status;
```

这是由字节重排指令、两次复制、`size+4` 和总线调用共同确认的行为。状态成功判断是 `(status & 0x82000000) == 0x80000000`，不能按 SDK 的返回 0 成功直接代用。

| 变体 0 表地址 | 项数 | 内容 |
|---|---:|---|
| `0x00082E90` | 137 | 核心 DSP 下载数据 |
| `0x0008C3D4` | 11 | 内置波表数据 |
| `0x0008D688` | 2 | 452 字节 WSEQ |

变体 1 也有 137+11+2 项，但波表、序列表和数据指针位置不同。所有描述符和原始数据已导出至 body_0.dsp_tables.json（`../../surface/analysis/sam/body_0.dsp_tables.json`，未入库） 及 body_1.dsp_tables.json（`../../surface/analysis/sam/body_1.dsp_tables.json`，未入库）。

### 内置固件与独立 Haptic 更新包的关系

按本地 SDK 的 packed-to-u24 解码规则，SAM 内置固件 ID 是 `0x1400E1`，revision 是 `0x0A0601`；此前独立 Haptic 包的 revision 是 `0x0A0603`。

137 个核心描述符的地址、大小一致；132 个数据块完全相同，差异位于从零编号 `0、11、12、54、90`。两份 SAM 变体均得到这一结果。不能把内置固件当成 0A0603 的逐字节副本。

内置波表为 11 块，独立 Haptic 更新包的波表为 28 块；两个 WSEQ 块却逐字节相同。因此原 SAM 代码本身已证实会下载这 452 字节序列，进一步排除了“解包时意外多取了 64 字节” 的解释。它与 SDK 48 项主机表的差异仍然存在，移植时需协调，而不是截断原序列。

## 6. 初始化主流程与外部镜像优先策略

`0xDCDFA` 的主要路径如下，省略诊断日志，保留影响结果的条件：

```text
pre_download_prepare(ctx)
  写 0x00000020 = 0x5A000000
  成功后写 0x02800190 = 1
  调用等待例程，参数 15
    ↓ 成功
apply_register_init_table(ctx)
  平台选择器返回值 >= 2 → 表 0x841EC，71 项
  否则                    → 表 0x8442C，70 项
    ↓ 成功
若提供外部镜像接口，且读出第一个头字段非零：
  尝试下载外部镜像全部块
  若成功，跳过内置镜像
若未成功采用外部镜像：
  下载内置 137 + 11 + 2 块
    ↓ 成功
部分平台分支写 0x028018DC = 1
写 0x02BC1000 = 0x00000101，启动 DSP
随后设置两个运行参数及其他 DSP/IRQ 控制项
```

两套初始化表以 big-endian `(address,value)` 的 8 字节记录保存，以两个零 u32 结束。完整有序内容见 body_0.init_tables.json（`../../surface/analysis/sam/body_0.init_tables.json`，未入库）。它们包含 DSP 时钟禁用、寄存器保护键、路由、功放及内存访问配置；不能与 56 项 WSEQ 混为一张表。

两表部分差异包括 `MSM_BLOCK_ENABLES` 的 `0x3701/0x3321` 初始值和寄存器 `0x6C04` 的 `0x293/0x273`。平台选择器的实际硬件含义尚未确认，不把它直接命名为芯片修订或升压模式。

外部镜像解析函数进一步证实读取一个 8 字节总头：`0xE1AA8` 取第二个 u32 作为块数，`0xE1ACE` 取第一个 u32。`0xE1AF4` 读取 14 字节块头；数据读取例程也跳过 14 字节再读 payload。这与前面 Haptic body 的布局相符。外部镜像接口的底层存储来源尚未完整追踪。

等待函数 `0x90786` 最终执行 `svc #0x11`，本次未确认系统 tick 与实际时间换算，所以报告保留参数 15、3、150，不直接把它们写成毫秒。

## 7. 已恢复的触发与运行控制

### 波形索引触发：0xDCFD8

该函数把第二个参数左移 24 位后按小端存入发送缓冲，等价于将参数低 8 位作为大端 u32 的值，写到 `0x00013020`。本地 SDK 将此寄存器命名为 `DSP_VIRTUAL1_MBOX_DSP_VIRTUAL1_MBOX_1_REG`。

```c
// 分析伪代码，非原始函数名；不包含调用方的触发条件。
trigger_index(ctx, index) {
    uint8_t packet[8] = {0x00, 0x01, 0x30, 0x20, 0, 0, 0, (uint8_t)index};
    return bus_write(ctx, packet, 8);
}
```

例如 index=3 时发送 `00 01 30 20 00 00 00 03`。该函数本身没有轮询 ACK 的循环，不应自动补写成“原函数会等待 ACK”。它的 Thumb 函数指针 `0xDCFD9` 出现在表地址 `0xD8620`，说明存在间接调用路径；调用方如何选择点击/释放索引还需要继续追踪。

### 其他已确认的寄存器访问

| 函数地址 | 行为 |
|---|---|
| `0xDCF92` | 读取 `0x0280000C` 的 4 字节并转为主机字节序 |
| `0xDD086` | 向 `0x0280167C` 写入第二参数的低 8 位 |
| `0xDD0A0` | 向 `0x0280168C` 写入第二参数的低 8 位 |
| `0xDCFF2` | 写 `0x10910=0xFFFFFFFF`、`0x10914=0xFFFFFFFF`，随后向 `0x1302C` 写 1 |
| `0xDD048` | 向 `0x1302C` 写 2，调用等待例程参数 3，再写 `0x10910=0x7FFDFFFF` |
| `0xDD0BA` | 写 `0x02802B08=0x00FFFFFF`，向 `0x1302C` 写 2，等待参数 150，读取前述 DSP 字并作整数缩放 |

最后一项的计算为 32 位乘法结果除以 100000，乘数为 `0x1175`（4469）；未证实对应物理量，不能直接命名为电阻、频率或校准结果。两个低 8 位参数后续已与 0A0603 SDK 的按下/释放波形索引首项对应起来，并恢复成对选择逻辑，见文首后续记录。它们不是两个直接幅值参数，也不是压力阈值。

## 8. 移植时可直接利用与仍需核对的内容

可利用的确定信息：

- 32 位寄存器地址采用大端序，下载 payload 保持原样。
- 最大内置下载 payload 为 240 字节，发送时另加 4 字节地址。
- 外部更新镜像存在优先路径，失败/不可用时存在内置固件回退路径。
- 内置初始化表和 WSEQ 是不同用途、不同格式的两组数据。
- DSP 核启动写入与 mailbox 索引触发寄存器均已定位。

仍需核对：

- 实际 I²C 设备地址、总线实例、RESET/IRQ/VAMP 等与具体板子的映射。
- 两个 SAM 变体及初始化表选择器对应的硬件条件。
- 等待参数的时间单位、供电建立时间及异常恢复。
- 上层事件、压力阈值、点击/释放波形索引和持续时间的映射。
- SDK 控制符号、48 项 WSEQ 表与 Surface 的 56 项序列如何协调。

Windows 的公开 HID 触觉文档把设备主动按下/释放反馈与主机主动触发区分开；这支持分析时保留两个层次，但不能替代本机私有协议证据。文档中的现代 HID 能力也不能直接当作 2021 年本机固件已经实现的能力。Microsoft 输入设备触觉说明（`https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/input-haptics-implementation-guide`，未入库）

## 9. 验证、复现与工具限制

新增 7 项测试已通过：两变体完整性、损坏 offer/CFU/尾部拒绝、核心差异位置与 WSEQ 等价、越界数据指针拒绝、ELF 保留原 body、初始化表顺序，以及 MSI 输出路径约束。

最终复核：MSI 中三个 `SurfaceTouchpad*.bin` 均与原 `targetbin` 输入逐字节相同；SAM 输出清单中的 24 个文件均通过 SHA256 复核。已标注 24 个函数/代码片段范围，相关文档的本地链接和新增 Python 工具语法检查均通过。

```powershell
# 第一步仅在新的空目录执行，需要 Windows、Python 3.11+ 和 7-Zip。
python -B tools/surface_firmware/extract_msi.py surface/SurfaceLaptopStudio_Win11_22631_26.073.29264.0.msi surface/unpacked

# 后续步骤可复现；SAM 比较使用此前 unpacked 中的 Haptic body。
python -B tools/surface_firmware/scan_msi_payload.py surface/unpacked/payload surface/analysis/keyword_scan.json
python -B tools/surface_firmware/analyze_sam.py
python -B tools/surface_firmware/test_analyze_sam.py
```

`analyze_sam.py` 在 OpenSSL 可用时验签，在 LLVM objdump 可用时生成反汇编；当前环境两者均可用，实际验证日志和反汇编已经生成。分析函数地址与表偏移针对这个 SAM 版本，不能直接套用于其他版本或变体 1。全量反汇编含数据区，后续应以 reviewed_functions 中的范围、literal 值和调用上下文为依据。

本次未修改原始 MSI、三个 targetbin 输入固件或芯片驱动实现；没有加载任何提取出来的驱动、更新设备、执行 SAM 固件或进行硬件播放。
