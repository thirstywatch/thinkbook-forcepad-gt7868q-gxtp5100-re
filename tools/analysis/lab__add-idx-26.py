#!/usr/bin/env python3
# add-idx-26.py —— 把 追加二十六 的索引行追加到总表 §九
import os

p = r"<WORKSPACE>"
txt = open(p, encoding="utf-8").read()

if "追加二十六" in txt:
    print("索引行已存在，跳过")
    raise SystemExit

row = (
    "| **`追加二十六-X9-15线收束与马达归属定案.md`** | \u2605\u2605\u2605 "
    "**X9-15 线收束 + 马达归属定案**："
    "**① X9-15 线换来什么（5 条）**：证明芯片家族本就能主机触发 / 证明**无独立触觉驱动 IC**"
    "（dmesg 全机仅一个 HID 设备 `0018:27C6:01EB.0001`）/ 证明换模块非即插即用 / "
    "把卡点定位到 **ACPI 初始化** / 给出参照系；"
    "**② 硬件对照**：PID `01E9`(本机) vs `01EA`/`01EB`(X9-15) vs `01E0`(ThinkBook 14+ 2025)；"
    "执行器 = 小 LRA(FRU `5T60S94326`) vs **Nidec TapSense**(丝印 `NIDEC 55F0410`)；"
    "**\u2605 Nidec 官方规格谐振 = 200 Hz \u21d2 纠正「200 Hz 是巧合」的判断**"
    "（TIM2 PSC=119/ARR=1999 正是 200 Hz，刻意设计）；"
    "**③ Code 10 的 ACPI 机理定案**：`TPID` 五厂商表（SYNA2BA6/ELAN06FA/CIRQ1080/GXTP5100/占位 0xFF）"
    " + `TPDS` 按【硬件上报的厂商索引】查表 \u21d2 未命中落占位项(地址 0xFF) \u21d2 读不到描述符 \u21d2 代码 10；"
    "**④ \u2605 新解出 `IICBADR0` 真身**：全 30 张表**只有 3 处引用、0 处定义**，"
    "实际是 `IICB`+`ADR0` 两个 NameSeg；反编译证明 = `Name(BUF0,Buffer)` + "
    "**`CreateDWordField(BUF0,4,ADR0)`**（模板偏移 4 = I2C 从机地址）+ `CreateWordField(IBUF,5,IRQN)` "
    "\u21d2 **地址是运行时拼出来的**；"
    "**⑤ \u2605\u2605\u2605 马达归属定案：在 GT7868Q 侧，不在 TF100A** —— "
    "用**两种独立方法**（字面量 + **结构体间接**）证明 TF100A 的 **CCR 运行期恒定**"
    "（只有 SetCompare HAL 内部 4 条，该 HAL 全固件仅 1 个调用者）"
    "\u21d2「若 TIM2 驱动马达就会一直震」矛盾 \u21d2 **马达由 GT7868Q 驱动**；"
    "**⑥ 否掉「派发器」线索**：`0x080110BC` 是蹦床，真身 `0x08011304` = **vsnprintf/printf** "
    "\u21d2 `0x28` 链终点是**调试打印**，确认该路死亡；"
    "**⑦ 四条路最终裁定表**；"
    "**⑧ 新增工具 6 个**（`AllCaps.cs`+`dump-all-caps.ps1` · `aligned-read-probe.ps1` · "
    "`tf100a-tim-write-scan.py` · `ccr-hits.py`/`ccer-hits.py` · `acpi-iicb-scan.py` · `dsdt-crs-dump.py`）；"
    "**⑨ \u2605 HID 全量 caps**：解出 4 个厂商 feature 报表 `0xFF00/0xC4`(RID13,4B) / `0xC7`(RID11,66B) / "
    "`0xC6`(RID12,736B) / `0xC5`(RID6,256B)；"
    "**⑩ 对齐单块读实测**：11/11 成功、4/4 一致 \u21d2 通道可靠；固件区读出**密文**"
    "（印证 ECB，也说明「从设备 dump 明文固件」同样被堵）；"
    "**⑪ \u2605 X9-15 BIOS 资产已获取**：真实包名 **`n4cuj`**（不是 n4cet），"
    "`n4cuj09w.exe`(38.3MB) + `n4cur09w.iso`(121.4MB) 存于 `x9bios\\`；"
    "实测两份包 ACPI 均**压缩存放**（7 处 FACP 全伪命中）；"
    "**⑫ 可复用解包工具**：`bios\\extract\\uefi_scan.py`/`ffs_scan.py`"
    "（LZMA GUID `EE4E5898-3914-4259-9D6E-DC7BD79403CF`）+ "
    "ACPI 表存储 GUID `7E374E25-8E01-4FEE-87F2-390C23C606CD` | \u2705 有效（权威） |"
)

if not txt.endswith("\n"):
    txt += "\n"
txt += row + "\n"
open(p, "w", encoding="utf-8", newline="").write(txt)
print("已追加 追加二十六 索引行")
print("文件大小:", os.path.getsize(p), "B")
print("行数:", txt.count("\n"))
