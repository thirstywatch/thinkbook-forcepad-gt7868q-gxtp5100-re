# tools/third-party —— 第三方工具（**只放说明，不放二进制**）

> 本目录**永远不存放二进制**。第三方工具按各自的许可**不可再分发**，这里只登记获取方式与用法要点。
> 完整出处清单见 [`vendor-refs/links.md`](../../vendor-refs/links.md)；合规声明见 [`NOTICE.md`](../../NOTICE.md)。

| 工具 | 用途 | 获取方式 | 许可 / 注意 |
|---|---|---|---|
| **RWEverything** (`Rw.exe` + `RwDrv.sys`) | MMIO / PCI 配置空间 / SMBus 直读 | `https://rweverything.com/` | ⚠️ 专有免费软件，**不可再分发**；脚本变量名只能是 `Local0`–`LocalF`（纪律 57） |
| **PawnIO** | 签名内核驱动（SMBus / EC / MMIO 原语） | `https://github.com/ZenithDevs/PawnIO` | 开源；**需管理员**（`0x80070005` = 权限不足）；自写模块要么提交上游、要么装 Unrestricted edition（需关 Secure Boot） |
| **ACPICA `iasl`** | AML 反编译 / 重编译 | `https://acpica.org/downloads` | ACPICA 许可；⚠️ 反编译**不能用 `-o <path>`**（纪律 53） |
| **capstone** | 多架构反汇编（本项目 ARM/Thumb 与 8051 相关分析） | `pip install capstone`（5.0.7） | BSD-3 |
| **hidapi / pywin32** | HID 设备访问 / Windows API | `pip install hidapi pywin32` | BSD-3 / PSF-ish |
| **LibreOffice**（可选） | 打开厂商文档的 `.docx` 等 | 官方渠道 | MPL-2.0 |

## 与本项目有关的两个 ".exe" 特别说明

* `GoodixTouchpadTool.exe`（汇顶官方触控板工具）与联想 BIOS/EC 更新包**一律不入库**，获取方式见 [`reproduce/ENVIRONMENT.md`](../../reproduce/ENVIRONMENT.md)。
* 2026-10-13 抓到的**汇顶官方源码快照**（`gdix_hid_firmware_update` / `gtx8_driver_linux` / 主线补丁 / 微软触觉规范 / 3 份厂商 cfg bin）保存在**本地** `poc/gdix-official-missing/`，**同样不入库**；逐文件出处与 sha256 见 [`vendor-refs/links.md`](../../vendor-refs/links.md) §XII。
