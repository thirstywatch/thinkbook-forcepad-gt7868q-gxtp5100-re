# 触控板重启 → 重读描述符（B11 最后一个分支）

> 目的：排除「HID 描述符被 Windows 枚举缓存」这个候选。
> 前置（已完成，字节级确证）：
>   我发 `+0x10F = 0x1037` → T2 读回 `10 37` → **IC 确实收到了**
> 但描述符 `X LogicalMax` 仍是 4149。
> ⇒ 现在只有一个变量没排除：**Windows 是否缓存了描述符**。

---

## 步骤

### 1. 先写入改动（我来做，已在上一轮验证通过）

```bash
cd tools/hid
python lab__r13_cfgupdate.py write --patch 0x10F:1037 \
  --image "C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
```

期望结果码：`7E 00 02`（与 flash 不同 ⇒ 生效）
备份文件：`lab__cfg_backup_<ts>.bin`

### 2. ★ 重启触控板设备（需要管理员权限，请你手动执行）

设备实例路径（本机实测）：

```
HID\GXTP5100&Col01\5&52a7aed&0&0000
HID\GXTP5100&Col02\5&52a7aed&0&0001
HID\GXTP5100&Col03\5&52a7aed&0&0002
HID\GXTP5100&Col04\5&52a7aed&0&0003
```

**方式 A（推荐，最彻底）：直接重启电脑**
最干净的"重新枚举"，排除一切驱动侧缓存。

**方式 B（快，不用重启系统）：以管理员身份运行**

```powershell
# 逐条执行（触控板会短暂失效，几秒后恢复）
pnputil /restart-device "HID\GXTP5100&Col01\5&52a7aed&0&0000"
pnputil /restart-device "HID\GXTP5100&Col02\5&52a7aed&0&0001"
pnputil /restart-device "HID\GXTP5100&Col03\5&52a7aed&0&0002"
pnputil /restart-device "HID\GXTP5100&Col04\5&52a7aed&0&0003"
```

若 `pnputil` 不支持 `/restart-device`（旧版），改用设备管理器：
「人体学输入设备」→ 找到 **HID-compliant touchpad / GXTP5100** → 右键「禁用设备」→ 再「启用设备」。

> ⚠️ 触控板失效期间无法用触摸板操作，请用键盘/鼠标完成。

### 3. 重启后立刻读描述符（我来做）

```bash
python lab__r14_xlogicalmax.py --json
```

看 `COL02` 的 `UMin=0x30`（X）那条的 `LogMax`。

---

## 判读表

| 重启后 X `LogMax` | 结论 | B11 结案 |
|---|---|---|
| **4150** | 描述符**读的是 cfg**，之前不变是 **Windows 枚举缓存** | 结案：`+0x10F` = X 点数**成立**（定名恢复） |
| **4149**（不变） | 真源在**别处**，`+0x10F` 与描述符量程**无因果** | 结案：`+0x10F` = X 点数**永久撤回** |

无论哪个结果，B11 都能关闭。

---

## 4. 收尾：恢复原样（无论结果如何都做）

```bash
python lab__r13_cfgupdate.py restore \
  --image "C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
```

期望结果码：`7E 00 07`（与 flash 完全一致）
然后 `python lab__r13_cfgupdate.py probe` 确认 5/5。

---

## 安全说明

- 写入路径**已字节级验证**（T2 读回 64/64 一致），无未知操作
- `0x10F` 在 cfg 里仅是**一个 u16**，改的是 4150→4151（差 1）
- 全程不触碰 `0x0E` 类、不发未知 opcode
- 有 `restore` 与 5 份备份可回滚
