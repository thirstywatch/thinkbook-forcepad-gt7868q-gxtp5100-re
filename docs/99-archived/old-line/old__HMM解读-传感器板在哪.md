# HMM 解读 —— 这台机器的"传感器板"到底在哪

- 时间：2026-09-27 · 来源：**联想官方 HMM 原文**
  `https://download.lenovo.com/consumer/mobiles_pub/lenovo_thinkbook_14_gen_6_hmm.pdf`（72 页，13.7 MB，已下载到本目录 `tb14g6_hmm.pdf`）
- 官方页面：`support.lenovo.com/lk/en/solutions/ht516827-...`（21LD 拆装视频列表，2024-09-20 发布，2026-06-09 更新）
- 渲染出的图：`hmm-figs/`（下面用到的两张）

---

## 一、两条硬事实（来自官方 FRU 表）

### 1.1 机身侧（Table 3，整机爆炸图）—— **22 项，没有任何传感器件**

```
LCD module · Upper case · Touchpad · System board · Wi-Fi card cover · Wi-Fi card
CMOS battery · CMOS battery sponge · Heat sink · Fans · Battery pack · Speakers
Lower case · SSD bracket · SSD · I/O board cable · I/O board
Fingerprint board cable · Power button bracket · Acetate tape
Power button (with fingerprint board) · Power button
```

### 1.2 屏幕侧（Table 4，LCD 模组爆炸图）—— **12 项，其中有两项是传感器件**

| # | FRU |
|---|---|
| 1 | Hinge cover |
| 2 | LCD bezel |
| 3 | Hinges |
| 4 | LCD panel |
| 5 | Removable tape |
| 6 | Camera cable |
| 7 | LCD cover |
| **8** | **Sensor board cable** |
| 9 | Camera board |
| **10** | **Sensor board** |
| 11 | Microphone rubbers |
| 12 | EDP cable |

**⇒ 整机唯一一块独立的"传感器板"，在屏幕里。机身侧一个传感器 FRU 都没有**
（这意味着：**若机身侧有传感器，它是焊在主板上的元件，不作为备件单独存在**）。

### 1.3 HMM 全文里**没有**出现这些词

`magnet` / `hall` / `accelerometer` / `G-sensor` / `ALS` / `ambient` —— **官方手册不告诉你传感器是什么类型**。
（这也顺带说明：**没有任何官方文档把"开盖角度"当作一个量来描述**。）

---

## 二、它长什么样、在哪（见渲染图）

### 2.1 `hmm-figs/p30-fig2-LCD模组爆炸图.png`

LCD 模组拆开后的层次（由外到内）：

```
LCD bezel(2)
 └ Hinges(3)
    └ LCD panel(4)
       └ Removable tape(5)
          ├ EDP cable(12)      ← 主排线，通机身
          ├ Microphone rubbers(11)
          ├ Sensor board(10)   ← ★ 就在这一层
          ├ Camera board(9)
          ├ Sensor board cable(8)
          └ Camera cable(6)
             └ LCD cover(7)     ← 最外层背板
```

**从爆炸图的排布看：`Camera board(9)` 与 `Sensor board(10)` 是两块紧邻的小板，位于LCD cover 的【顶部区域】—— 也就是摄像头那一带。**

### 2.2 `hmm-figs/p60-fig50-传感器板模组.png`

官方拆装步骤图（Figure 50）把要拆的地方用**红圈**标出来了：

> **Step 1.** Disconnect the sensor board cable from the camera board and then remove the sensor board module.
> **Note：The sensor board module includes the sensor board, sensor board cable, and camera cable.**

红圈的位置 = **LCD cover 的顶部正中**，即**摄像头所在的那一小块**。
拆装顺序也印证了三者的关系：

```
sensor board ──(sensor board cable)──> camera board ──(camera cable)──> EDP cable ──> 机身
```

**⇒ 这块"传感器板"通过 camera cable → EDP cable 一路回到机身。**

---

## 三、这对"角度项目"意味着什么

### 3.1 已经变得很清楚的

| 结论 | 依据 |
|---|---|
| **机器的显示侧有一块独立的传感器板，位置在顶部正中（摄像头旁）** | 官方 FRU 表 + 拆装图 |
| 它的信号**必须通过排线回到机身**才能被 EC / ISH 读到 | 拆装步骤的连线关系 |
| **机身侧没有独立传感器件** | 官方 FRU 表 22 项 |

### 3.2 仍不能定的（诚实说）

| 问题 | 为什么 HMM 答不了 |
|---|---|
| 那块 sensor board 上**具体有什么**（ALS？麦克风互联？还是盖子检测？） | 手册只说"传感器板"，不给元件表 |
| **盖子检测的霍尔**是在屏幕侧那块板上，还是焊在机身侧主板上 | 手册里 `hall`/`magnet` 零命中 |

**两种布置都还成立**：

| 布置 | 磁铁在哪 | 传感器在哪 |
|---|---|---|
| **甲** | 屏幕（下边框 / 或顶部） | **机身主板**（焊死，非 FRU） |
| **乙** | 机身（触控板附近） | **屏幕的 sensor board** |

—— 而 eevblog 上一位 **Lenovo T580** 用户实测「**触控板附近有磁铁**（金属笔被吸住）」，支持**乙**。

---

## 四、如果还要用磁铁试，这次试对地方

你上次扫的目标是"**哪里吸得住**" —— 那是找磁铁，不是找传感器。**传感器不吸磁铁。**

**这次按这张表扫（都是上次没试过的位置）**：

| 优先 | 位置 | 对应哪种布置 |
|---|---|---|
| **1** | **屏幕顶部正中、摄像头旁边那一小块**（`hmm-figs/p60` 红圈那处） | 若传感器在屏幕的 sensor board 上 |
| **2** | **屏幕下边框中央（下巴）** | 合盖时它压在掌托前缘 |
| **3** | **掌托前缘正中 / 触控板正下方** | 若传感器在机身主板、磁铁在屏幕 |
| **4** | **电源键附近（机身上方靠铰链一侧）** | eevblog 上有人指出霍尔常在电源键那块副板上 |

**姿势**：强钕磁铁（N35+）· **两个面都翻着试**（霍尔对极性敏感）· 每点**停 2–3 秒** · 看**屏幕灭/睡眠**。

---

## 五、但更根本的一句

**其实可以不做磁铁了。**

磁铁只是"便宜的先手"；而 **`0xFE0B0400` 那 4 KB 的 diff 与传感器在哪一侧完全无关** —— 不管霍尔装在屏幕还是机身，只要答案是"只有一个 bit"，结论一样成立；只要有别的字节跟着角度走，就找到了。

**⇒ 优先级重排**：

| 序 | 做什么 | 成本 |
|---|---|---|
| **1** | **读 `0xFE0B0400` × 4096 做合盖 diff** | ¥0 · 重启一次（见 `角度项目-4KB读取执行手册.md`） |
| 2 | 想先做个 10 秒预热判定 → 按第四章的位置表试磁铁（**尤其位置 1**） | ¥0 |
| 3 | 想看实物图 → 直接翻 `hmm-figs/` 或 HMM 第 30 / 60 页 | ¥0 |

---

## 六、顺带：这份 HMM 还有别的用处

| 用途 | 在哪 |
|---|---|
| **整机爆炸图** | p28（Figure 1）—— 看主板/扬声器/触控板的相对位置 |
| **LCD 模组完整爆炸图** | p30（Figure 2） |
| **触控板拆卸步骤** | "Remove the Touchpad" |
| **扬声器拆卸** | "Remove the Speakers" —— 可确认**掌托左右边缘那两块磁铁就是扬声器** |
| **主板拆卸** | "Remove the System Board" —— 若要找焊在板上的霍尔，看这一节的图 |
| **21LD 全部拆装视频** | 官方页面 ht516827 列出 18 个视频（Bottom Cover / Battery / LCD Assembly / Touchpad / Speakers / Hinge Cover / LCD Bezel / Camera Sensor Board and FFC Cable / …） |

**全程只下载了一个 PDF，没拆任何东西。**
