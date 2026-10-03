"""把 OpenCore 组装成一个可直接启动的 U 盘内容，并只做我们需要的两处改动。

思路：以 OpenCore 官方 Docs/Sample.plist 为基准（已知可用），只改：
  1. ACPI -> Patch  : 加入我们的 DSDT 补丁（Find/Replace 16 字节，已在离线 AML 执行中验证）
  2. PlatformInfo -> Automatic = False : 禁止注入 SMBIOS，避免影响 Windows
  并裁掉样版里我们没随包提供的 Drivers（只留必需的 OpenRuntime.efi），
  否则 OpenCore 会因为找不到驱动而报错。

产物：<staging>/EFI/{BOOT,OC/**,Tpad/**}
用法：python build_oc_usb.py
"""
import os
import plistlib
import shutil
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
OUT = os.path.join(PKG, "open-core-usb")
ZIP_CANDIDATES = [
    os.path.join(os.environ.get("TEMP", r"C:\Windows\Temp"), "oc.zip"),
    r"<HOME>\AppData\Local\Temp\oc.zip",
    "/tmp/oc.zip",
    r"C:\tmp\oc.zip",
    os.path.join(PKG, "oc.zip"),
    os.path.join(HERE, "oc.zip"),
]

FIND = bytes.fromhex("0A040A2C0A200D475854503531303000")
REPLACE = bytes.fromhex("0AFE0A2C0A200D4D5346543030303100")
assert len(FIND) == len(REPLACE) == 16

# 我们要随包提供的文件（源 zip 路径 -> 目标相对路径）
FILES = [
    ("X64/EFI/BOOT/BOOTx64.efi", "EFI/BOOT/BOOTx64.efi"),
    ("X64/EFI/OC/OpenCore.efi", "EFI/OC/OpenCore.efi"),
    ("X64/EFI/OC/Drivers/OpenRuntime.efi", "EFI/OC/Drivers/OpenRuntime.efi"),
]
DIRS = ["EFI/OC/ACPI", "EFI/OC/Kexts"]


def find_zip():
    for p in ZIP_CANDIDATES:
        if os.path.exists(p):
            return p
    raise SystemExit("找不到 OpenCore 包（oc.zip），请先下载")


def main():
    zp = find_zip()
    print("使用 OpenCore 包:", zp)
    z = zipfile.ZipFile(zp)

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT, exist_ok=True)
    for d in DIRS:
        os.makedirs(os.path.join(OUT, d), exist_ok=True)

    for src, dst in FILES:
        data = z.read(src)
        path = os.path.join(OUT, dst)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        print(f"  {len(data):>9,}  {dst}")

    # ---- 基于官方 Sample.plist 生成 config.plist ----
    sample = plistlib.loads(z.read("Docs/Sample.plist"))

    # 1) ACPI -> Patch
    sample["ACPI"]["Add"] = []
    sample["ACPI"]["Delete"] = []
    sample["ACPI"]["Patch"] = [{
        "Comment": "TPAD: force Goodix row hit (index 04 -> FE) + HID str MSFT0001",
        "Enabled": True,
        "Find": FIND,
        "Replace": REPLACE,
        "TableSignature": b"DSDT",
        "Count": 0,
        "Skip": 0,
        "Limit": 0,
        "Base": "",
        "BaseSkip": 0,
        "Mask": b"",
        "ReplaceMask": b"",
        "OemTableId": b"",
        "TableLength": 0,
    }]
    for k in list(sample["ACPI"]["Quirks"].keys()):
        sample["ACPI"]["Quirks"][k] = False

    # 2) PlatformInfo -> 不注入 SMBIOS（避免 Windows 被伪装/蓝屏）
    sample["PlatformInfo"]["Automatic"] = False

    # 3) UEFI -> Drivers 只留我们随包提供的那个，否则 OC 会因缺驱动报错
    sample["UEFI"]["Drivers"] = ["OpenRuntime.efi"]

    # 4) 允许扫描所有类型分区（确保能找到 Windows 的 ESP）
    sample["Misc"]["Security"]["ScanPolicy"] = 0
    sample["Misc"]["Security"]["SecureBootModel"] = "Disabled"
    sample["Misc"]["Security"]["Vault"] = "Optional"
    # 显示选择菜单，能看见 Windows 入口
    sample["Misc"]["Boot"]["ShowPicker"] = True
    sample["Misc"]["Boot"]["Timeout"] = 10

    cfg_path = os.path.join(OUT, "EFI/OC/config.plist")
    with open(cfg_path, "wb") as f:
        plistlib.dump(sample, f, sort_keys=False)
    print(f"  {os.path.getsize(cfg_path):>9,}  EFI/OC/config.plist  （由官方 Sample.plist 改）")

    print()
    print("=== 目录内容 ===")
    total = 0
    for root, _d, files in os.walk(OUT):
        for f in sorted(files):
            p = os.path.join(root, f)
            total += os.path.getsize(p)
            print(f"  {os.path.getsize(p):>10,}  {os.path.relpath(p, OUT)}")
    print(f"  合计 {total:,} 字节")


if __name__ == "__main__":
    main()
