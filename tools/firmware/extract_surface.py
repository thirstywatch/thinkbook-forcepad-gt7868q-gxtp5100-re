#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Extract the observed Surface touchpad capsules and rebuild CS40L25 images.

This is a strict parser for the three supplied files, not a general Surface
updater. It never communicates with hardware. WMFW metadata comes from the
SDK reference only after ALL reference download blocks match the capsule.
"""
from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
import uuid
from pathlib import Path

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools/firmware_converter"))
from firmware_converter import address_resolver, fw_block_list
from wmfw_parser import wmfw_parser

FMP_GUID = "6dcbd5ed-e82d-4c44-bda1-7194199ad92a"
PKCS7_GUID = "4aafd29d-68df-49ee-8aa9-347d375665a7"
REFERENCE = REPO / "cs40l25/fw/prince_haptics_ctrl_ram_remap_ext_boost_0A0603.wmfw"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def der(tag, data):
    size = len(data)
    encoded_size = bytes([size]) if size < 128 else size.to_bytes((size.bit_length() + 7) // 8, "big")
    if size >= 128:
        encoded_size = bytes([0x80 | len(encoded_size)]) + encoded_size
    return bytes([tag]) + encoded_size + data


def take(data, offset, size):
    require(0 <= offset <= len(data) and 0 <= size <= len(data) - offset,
            f"Out-of-bounds read at {offset:#x}, size {size:#x}")
    return bytes(data[offset:offset + size])


def unpack(fmt, data, offset):
    return struct.unpack(fmt, take(data, offset, struct.calcsize(fmt)))


def parse_capsule(data):
    require(str(uuid.UUID(bytes_le=take(data, 0, 16))) == FMP_GUID, "Not an FMP capsule")
    header_size, flags, total_size = unpack("<III", data, 16)
    require(header_size >= 28 and total_size == len(data), "Invalid capsule length")
    version, drivers, payloads = unpack("<IHH", data, header_size)
    require((version, drivers, payloads) == (1, 0, 1), "Unsupported FMP item layout")
    relative, = unpack("<Q", data, header_size + 8)
    require(relative >= 16, "FMP item overlaps item table")
    item = header_size + relative
    image_version, = unpack("<I", data, item)
    require(image_version == 2, "Expected FMP image header version 2")
    image_guid = str(uuid.UUID(bytes_le=take(data, item + 4, 16)))
    image_size, vendor_size = unpack("<II", data, item + 24)
    auth = item + 40
    require(auth + image_size + vendor_size == len(data) and vendor_size == 0,
            "FMP image size mismatch")
    monotonic = take(data, auth, 8)
    cert = auth + 8
    cert_size, cert_revision, cert_type = unpack("<IHH", data, cert)
    require(cert_size >= 24 and (cert_revision, cert_type) == (0x200, 0xEF1),
            "Unsupported authentication certificate")
    require(str(uuid.UUID(bytes_le=take(data, cert + 8, 16))) == PKCS7_GUID,
            "Expected PKCS7 authentication")
    signature = take(data, cert + 24, cert_size - 24)
    payload_offset = cert + cert_size
    payload = take(data, payload_offset, len(data) - payload_offset)
    magic, mss_size, fw_version, lowest_version = unpack("<4sIII", payload, 0)
    require(magic == b"MSS1" and mss_size == 16, "Unsupported MSS1 header")
    saml = take(payload, mss_size, len(payload) - mss_size)
    require(take(saml, 0, 4) == b"SAML", "Missing SAML wrapper")
    # These offsets are inferred from the supplied files, not a published SAML ABI.
    records_size, saml_version = unpack("<II", saml, 17)
    require(records_size == len(saml) - 25, "SAML content length mismatch")
    require(saml_version == fw_version, "SAML/MSS1 version mismatch")
    meta = dict(capsule_size=len(data), capsule_flags=hex(flags), image_type_guid=image_guid,
                authentication_offset=auth, signed_payload_offset=payload_offset,
                mss1_version=hex(fw_version), lowest_supported_version=lowest_version,
                saml_offset=payload_offset + mss_size,
                saml_header_hex=saml[:25].hex(),
                cfu_offset=payload_offset + mss_size + 25,
                signature_verification="not attempted", certificate_trust="not evaluated",
                saml_header_unknown_fields="preserved; no checksum claim")
    return meta, signature, payload + monotonic, saml[25:]


def parse_cfu_pairs(data):
    pairs = []
    pos = 0
    while pos < len(data):
        offer_offset = pos
        offer = take(data, pos, 16)
        require(offer[0] in (0, 2) and offer[1] == 0 and offer[2] in (0x11, 0x12, 0x16)
                and offer[3] == 0xB0 and offer[12] in (4, 0x14) and offer[13:] == b"\x01\x3c\x00",
                "Unsupported CFU offer")
        require(not pairs or offer[:12] == pairs[0]["offer"][:12], "CFU offer identity differs")
        pos += 16
        start = pos
        image = bytearray()
        records = []
        while pos < len(data):
            address, length = unpack("<IB", data, pos)
            if length == 0 or length > 16:  # Next offer begins with non-record fields.
                break
            require(address == len(image), "CFU address gap, overlap, or disorder")
            chunk = take(data, pos + 5, length)
            records.append(dict(offset=pos, address=address, size=length))
            image.extend(chunk)
            pos += 5 + length
        require(records, "Empty CFU image")
        pairs.append(dict(offer=offer, image=bytes(image), payload=data[start:pos],
                          offer_offset=offer_offset, records=records))
    require(len(pairs) == 2, "Expected two complete CFU offer/payload pairs")
    require(pairs[0]["image"] == pairs[1]["image"], "The two payload images differ")
    require(pairs[0]["payload"] == pairs[1]["payload"], "CFU record encodings differ")
    return pairs


def parse_component(image):
    header_size, v1, v2, extension, body = unpack("<5I", image, 0)
    require((header_size, v1, v2) == (20, 1, 1), "Unknown component header")
    require(header_size <= extension < body < len(image), "Invalid component body offset")
    return dict(header_size=header_size, extension_offset=extension, body_offset=body,
                body_size=len(image) - body,
                header_fields="observed structure; not all metadata fields interpreted")


def parse_haptic(body):
    revision_address, count = unpack("<II", body, 0)
    require(revision_address == 0x02800010, "Not the expected CS40L25 revision register")
    require(0 < count <= (len(body) - 8) // 14, "Invalid DSP block count")
    pos = 8
    blocks = []
    for index in range(count):
        sequence, address, size, crc = unpack("<IIIH", body, pos)
        require(sequence == index and 0 < size <= 240 and size % 4 == 0,
                f"Invalid DSP block header {index}")
        chunk = take(body, pos + 14, size)
        require(binascii.crc_hqx(chunk, 0xFFFF) == crc, f"DSP block {index} CRC16 failed")
        require(any(base <= address and address + size <= end for base, end in
                    [(0x02000000, 0x02400000), (0x02800000, 0x02C00000),
                     (0x02C00000, 0x03000000), (0x03400000, 0x03800000),
                     (0x03800000, 0x03C00000)]), "Unexpected DSP memory range")
        blocks.append(dict(index=index, offset=pos, address=address, size=size,
                           crc16=crc, crc16_verified=True, data=chunk))
        pos += 14 + size
    require(pos == len(body), "Trailing or missing DSP bytes")
    return blocks


def sdk_blocks(path):
    parsed = wmfw_parser(str(path))
    parsed.parse()
    block_list = fw_block_list(parsed.get_data_blocks(), 240, address_resolver("cs40l25"))
    block_list.rehash_blocks()
    return parsed, [(address, b"".join(data)) for address, data in block_list.blocks]


def coalesce(blocks):
    merged = []
    for block in blocks:
        address, data = block["address"], block["data"]
        if merged and address == merged[-1][0] + len(merged[-1][1]):
            merged[-1] = (merged[-1][0], merged[-1][1] + data)
        else:
            merged.append((address, data))
    return merged


def verify_fw_img(data, expected):
    fields = unpack("<10I", data, 0)
    magic, revision, total, nsyms, nalgs, fw_id, fw_ver, nblocks, maximum, release = fields
    require((magic, revision, total, fw_id, fw_ver) ==
            (0x54B998FF, 2, len(data), 0x1400E1, 0x0A0603), "Invalid fw_img header")
    pos = 40
    symbols = {}
    for _ in range(nsyms):
        symbol, address = unpack("<II", data, pos)
        require(symbol not in symbols and address != 0, "Invalid symbol mapping")
        symbols[symbol] = address
        pos += 8
    pos += nalgs * 4
    actual = []
    for _ in range(nblocks):
        size, address = unpack("<II", data, pos)
        require(0 < size <= maximum and size % 4 == 0, "Invalid fw_img block size")
        actual.append((address, take(data, pos + 8, size)))
        pos += 8 + size
    require(pos + 8 == len(data), "fw_img footer position mismatch")
    footer, checksum = unpack("<II", data, pos)
    require(footer == 0x936BE2A6, "Invalid fw_img footer")
    # fw_img uses little-endian 16-bit Fletcher accumulators modulo 65535.
    sum1 = sum2 = 0
    for (value,) in struct.iter_unpack("<H", data[:-4]):
        sum1 = (sum1 + value) % 65535
        sum2 = (sum2 + sum1) % 65535
    require(checksum == (sum2 << 16 | sum1), "fw_img checksum mismatch")
    require(actual == expected, "fw_img does not reproduce original DSP writes")
    return dict(blocks=nblocks, symbols=nsyms, algorithms=nalgs, max_block_size=maximum,
                firmware_id=hex(fw_id), firmware_revision=hex(fw_ver),
                checksum_verified=True, ordered_writes_match=True, symbol_map=symbols)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_report(output, manifest):
    rows = []
    for item in manifest["sources"]:
        rows.append(f"| `{item['file']}` | {item['size']:,} | {item['pairs'][0]['component_id']} | "
                    f"{item['image_size']:,} | {item['pairs'][0]['records']:,} |")
    report = """# Surface 触摸板固件解包结果

已从 Haptic 更新包重建出可被本项目固件转换器和加载器解析的 CS40L25 固件。
这是离线格式及数据验证结果，尚未在实际 CS40L25/CS40L25B 硬件上运行。

## 三个输入文件

| 输入 | 原始字节数 | CFU component ID | 单份重组镜像字节数 | 单份 CFU 记录数 |
|---|---:|---|---:|---:|
""" + "\n".join(rows) + """

每个文件均包含两份字节相同的载荷，部分 offer 的协议字段不同；这些不是两个不同的固件版本。
Touchpad 和 Force 的组件载荷已完整导出，但不满足 Haptic 的 CS40L25 DSP 块格式，
不能通过改名或添加 WMFW 文件头变成 CS40L25 程序。Touchpad 载荷还包含 `TM3651-0019` 文本。
本次没有对这两个控制器的机器码做完整反汇编，也没有断言其具体 CPU 型号。

## CS40L25 的识别证据

- Haptic body 的第一个字段是 `0x02800010`，对应项目中的固件版本寄存器地址。
- 后续共 167 个块，结构为 `<sequence:u32le, address:u32le, size:u32le, crc:u16le, data>`。
- 全部块的 CRC16/CCITT-FALSE（poly=0x1021，init=0xffff，无反射，xorout=0）校验通过。
- 前 137 个块、30,008 字节的地址和数据，与 SDK 的
  `cs40l25/fw/prince_haptics_ctrl_ram_remap_ext_boost_0A0603.wmfw`
  按 240 字节切分后的下载内容完全一致；包括程序存储器代码。
- 从目标 XM packed 数据解出的 Firmware ID 是 `0x1400E1`，DSP revision 是 `0x0A0603`。
  包名中的 `2.9.139` 是 Surface 更新版本，不是 DSP revision。
- 最后 30 块、6,908 字节是附加数据写入。依据完全匹配参考固件的符号元数据可定位如下：

| 起始总线地址 | 字节数 | 对应内容 | 原始数据文件 |
|---|---:|---|---|
| `0x02800B60` | 2,408 | `VIBEGEN_WAVETABLE` 的写入部分 | `cs40l25/tuning_0_02800b60.bin` |
| `0x03400000` | 4,048 | `VIBEGEN_WAVETABLEYM` 的写入部分 | `cs40l25/tuning_1_03400000.bin` |
| `0x028016D0` | 452 | 56 项寄存器写入及结束标记，见下方边界说明 | `cs40l25/tuning_2_028016d0.bin` |

这三个 `tuning_*.bin` 是带地址说明的裸数据，不是带 WMDR 头的系数文件；不要直接作为
`firmware_converter.py --wmdr` 的输入。

后续 `analyze_components.py` 已将最后 452 字节完整解码为 56 项 WSEQ 和结束标记；
参考 WMFW 元数据中的 388 字节长度及 SDK 48 项主机表与此不同。它跨过参考校准符号的
地址，因此不能把后 64 字节解释为独立校准值，实际 DSP 消费方式尚未硬件验证。
同一分析还从 Touchpad body 原样提取出通过校验的 Synaptics RMI 镜像。详见
[Synaptics 与控制序列记录](../../tools/surface_firmware/SYNAPTICS_AND_CONTROL.zh-CN.md)。

## 可用产物

- [保留 Surface 附加数据的 WMFW](cs40l25/cs40l25_ext_boost_0A0603.surface.wmfw)：43,760 字节。
  完整重现 167 个有序写入块，包含原始波表和配置写入。
- [核心固件 WMFW](cs40l25/cs40l25_ext_boost_0A0603.core.wmfw)：36,828 字节。
  只包含匹配到的核心固件，字节上等同 SDK 参考 WMFW，不含 Surface 附加数据。
- [Surface SDK 二进制镜像](cs40l25/sdk_surface/cs40l25_fw_img.bin)：38,576 字节，`fw_img_v2`。
- [Surface SDK C 数组](cs40l25/sdk_surface/cs40l25_fw_img.c) 和
  [头文件](cs40l25/sdk_surface/cs40l25_fw_img.h)：可接入现有 `bsp_dut_boot()` 加载流程。
- `cs40l25/sdk_core/` 提供核心版本的相同格式，二进制镜像为 31,428 字节。
- [manifest.json](manifest.json)：输入 SHA256、封装偏移、记录数、匹配证据和转换验证结果。
- [haptic_blocks.json](cs40l25/haptic_blocks.json)：全部 DSP 块的地址、长度、CRC16 和 SHA256。
- [native_parser_validation.json](native_parser_validation.json)：执行测试后生成的原版 C 加载器验证记录。

**重建来源说明：** 原始 Surface 包没有 WMFW 头、算法描述或命名符号表。
在确认全部核心下载块完全匹配后，脚本复用了 SDK 参考 WMFW 的头和调试/符号元数据，
再把从 Haptic 中提取的三个附加区域作为 WMFW XM/YM unpacked 块追加。
因此 `.surface.wmfw` 是经过验证的重建容器，不是从更新包中原样切出的原厂 WMFW 文件。

## 复现

在仓库根目录运行，使用 Python 3.10 或更高版本，仅依赖标准库和仓库自带转换器：

```powershell
python -B tools/surface_firmware/extract_surface.py
python -B tools/surface_firmware/test_extract_surface.py
```

若 PATH 中有 OpenSSL，脚本还会验证各包的分离签名；使用 `-noverify` 跳过证书链信任验证，
因此“签名数学验证成功”不表示已检查根证书信任、吊销或当前证书有效期。
原始 SignedData 和补充 ContentInfo 包装后的 PKCS7 均保留在各组件输出目录。
Windows 环境中如有 clang/lld，测试会临时编译未经修改的 `common/fw_img.c`，
用 4、16、64、256、4096 字节以及整幅镜像大小的输入分块验证核心与 Surface 两种产物。
所有数据就绪事件中的地址、长度和数据都与原始 DSP 写入块比较。
这是主机侧执行加载器，没有连接、下载或烧录硬件。

也可单独重新生成 Surface C 数组（在仓库根目录运行；输出目录需已存在）：

```powershell
python -B tools/firmware_converter/firmware_converter.py fw_img_v2 cs40l25 targetbin/unpacked/cs40l25/cs40l25_ext_boost_0A0603.surface.wmfw --sym-input cs40l25/config/cs40l25_sym.h --generic-sym --block-size-limit 240 --output-directory targetbin/unpacked/cs40l25/sdk_surface
```

追加 `--binary-output` 可生成 `.bin`。固定使用项目的 `cs40l25_sym.h` 是为了保持驱动
使用的符号 ID 映射；不能用自动重新编号的符号表代替。两个版本均有 33 项有效符号映射。

## 接入边界

1. 该核心是 **ext_boost 外部升压版本**。项目 Makefile 的外部升压示例要求
   `CONFIG_L25B=1 CONFIG_EXT_BOOST=1`。当前没有确认目标板的芯片修订和供电电路，
   不能据此保证它适用于任意 CS40L25 或内部升压板。
2. 若要保留此次解出的 Surface 数据，选 `sdk_surface`；`sdk_core` 本身不包含这些波表。
   两者的 C 数组都使用 `cs40l25_fw_img` 名称，工程中只能链接其中一个。
3. 原有 Makefile 会自动调用转换器重新生成固件数组。接入时应调整工程输入到重建 WMFW，
   或让工程直接编译选定输出目录的 `.c/.h`，避免下一次构建又使用默认固件。
4. 标准 `cs40l25_boot()` 还会依据 BSP 配置修改上电序列、系统寄存器、事件和 IRQ 配置，
   部分行为会覆盖载荷中的初始设置。因此“写入块完整保留”不等于“完全复现 Surface 运行行为”。
5. Haptic 更新包只含上述运行固件与附加写入，不包含 SDK 单独的校准固件。
   若应用仍使用校准加载流程，还需要保留与工程匹配的校准固件和校准配置。

## 格式依据

- [UEFI Firmware Update and Reporting](https://uefi.org/specs/UEFI/2.10/23_Firmware_Update_and_Reporting.html)：FMP 与固件镜像认证。
- [EDK2 FmpPayloadHeader.py](https://github.com/tianocore/edk2/blob/master/BaseTools/Source/Python/Common/Edk2/Capsule/FmpPayloadHeader.py)：MSS1 头。
- [Microsoft CFU firmware file format](https://github.com/microsoft/CFU/blob/master/Documentation/CFU-Driver/cfu-driver.md#firmware-file-format)：16 字节 offer 和地址/长度/数据记录。
- SAML 私有字段和组件包装的部分字段仅根据这三个文件作了结构推断；未冒充通用格式规范。
- CS40L25 内存布局、符号和固件转换以本仓库源码及匹配参考文件为依据。
"""
    (output / "README.zh-CN.md").write_text(report, encoding="utf-8")


def convert(wmfw, out_dir, expected):
    out_dir.mkdir(parents=True, exist_ok=True)
    base = [sys.executable, "-B", str(REPO / "tools/firmware_converter/firmware_converter.py"),
            "fw_img_v2", "cs40l25", str(wmfw), "--sym-input",
            str(REPO / "cs40l25/config/cs40l25_sym.h"), "--generic-sym",
            "--block-size-limit", "240", "--skip-command-print", "--output-directory", str(out_dir)]
    result = subprocess.run(base, capture_output=True, text=True, check=True)
    (out_dir / "converter.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    result = subprocess.run(base + ["--binary-output"], capture_output=True, text=True, check=True)
    (out_dir / "converter_binary.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    binary = (out_dir / "cs40l25_fw_img.bin").read_bytes()
    check = verify_fw_img(binary, expected)
    c_source = (out_dir / "cs40l25_fw_img.c").read_text()
    c_array = c_source.split("= {", 1)[1].split("};", 1)[0]
    c_array = re.sub(r"//[^\n]*", "", c_array)
    c_bytes = bytes(int(x, 16) for x in re.findall(r"0x([0-9a-fA-F]{2})\b", c_array))
    require(c_bytes == binary, "Generated C array differs from binary image")
    check["c_array_matches_binary"] = True
    write_json(out_dir / "validation.json", check)
    return check


def reconstruct_haptic(image, output):
    component = parse_component(image)
    blocks = parse_haptic(image[component["body_offset"]:])
    reference, reference_writes = sdk_blocks(REFERENCE)
    writes = [(b["address"], b["data"]) for b in blocks]
    require(reference_writes == writes[:len(reference_writes)],
            "SDK reference firmware is not an exact prefix; metadata reuse refused")
    require(reference.fw_id_block.fields["firmware_id"] == 0x1400E1,
            "Unexpected reference firmware ID")
    core_path = output / "cs40l25_ext_boost_0A0603.core.wmfw"
    full_path = output / "cs40l25_ext_boost_0A0603.surface.wmfw"
    core = REFERENCE.read_bytes()
    core_path.write_bytes(core)
    full = bytearray(core)
    tuning = blocks[len(reference_writes):]
    regions = []
    for index, (address, data) in enumerate(coalesce(tuning)):
        if 0x02800000 <= address < 0x02C00000:
            block_type, base = 5, 0x02800000
        elif 0x03400000 <= address < 0x03800000:
            block_type, base = 6, 0x03400000
        else:
            raise ValueError("Unsupported tuning region")
        require((address - base) % 4 == 0, "Unaligned tuning address")
        full.extend(struct.pack("<II", (block_type << 24) | ((address - base) // 4), len(data)))
        full.extend(data)
        filename = f"tuning_{index}_{address:08x}.bin"
        (output / filename).write_bytes(data)
        regions.append(dict(address=hex(address), size=len(data), file=filename, sha256=sha(data)))
    full_path.write_bytes(full)
    _, reconstructed = sdk_blocks(full_path)
    require(reconstructed == writes, "Rebuilt WMFW differs from original ordered writes")
    write_json(output / "haptic_blocks.json",
               [dict(**{k: v for k, v in b.items() if k != "data"}, sha256=sha(b["data"])) for b in blocks])
    core_check = convert(core_path, output / "sdk_core", reference_writes)
    surface_check = convert(full_path, output / "sdk_surface", writes)
    require(core_check["symbol_map"] == surface_check["symbol_map"], "Symbol mappings changed")
    return dict(reference=str(REFERENCE.relative_to(REPO)), reference_sha256=sha(core),
                metadata_provenance="WMFW headers and named controls borrowed from exact SDK reference",
                firmware_id="0x1400e1", firmware_revision="0x0a0603",
                total_blocks=len(blocks), firmware_blocks=len(reference_writes),
                tuning_blocks=len(tuning), crc16_verified=len(blocks),
                data_bytes=sum(b["size"] for b in blocks),
                firmware_bytes=sum(len(d) for _, d in reference_writes),
                tuning_regions=regions, wmfw_ordered_writes_match=True,
                core_validation={k: v for k, v in core_check.items() if k != "symbol_map"},
                surface_validation={k: v for k, v in surface_check.items() if k != "symbol_map"},
                hardware_verified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=REPO / "targetbin")
    parser.add_argument("--output-dir", type=Path, default=REPO / "targetbin/unpacked")
    args = parser.parse_args()
    sources = sorted(args.input_dir.resolve().glob("SurfaceTouchpad*.bin"))
    require(len(sources) == 3, "Expected the three supplied SurfaceTouchpad capsules")
    output = args.output_dir.resolve()
    require(output != args.input_dir.resolve(), "Output must be separate from original inputs")
    output.mkdir(parents=True, exist_ok=True)
    manifest = dict(format_version=1, sources=[])
    for source in sources:
        data = source.read_bytes()
        meta, signature, signed_content, cfu = parse_capsule(data)
        pairs = parse_cfu_pairs(cfu)
        image = pairs[0]["image"]
        component = parse_component(image)
        directory = output / source.stem
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "signature.signed_data.der").write_bytes(signature)
        # UEFI stores raw SignedData; OpenSSL CMS expects a ContentInfo wrapper.
        content_info = der(0x30, bytes.fromhex("06092a864886f70d010702") + der(0xA0, signature))
        (directory / "signature.p7b").write_bytes(content_info)
        (directory / "signed_content.bin").write_bytes(signed_content)
        (directory / "component.reassembled.bin").write_bytes(image)
        (directory / "component.body.bin").write_bytes(image[component["body_offset"]:])
        (directory / "component.cfu.payload.bin").write_bytes(pairs[0]["payload"])
        for index, pair in enumerate(pairs):
            (directory / f"offer{index}.bin").write_bytes(pair["offer"])
        openssl = shutil.which("openssl")
        if openssl:
            result = subprocess.run([openssl, "cms", "-verify", "-binary", "-inform", "DER",
                                     "-in", str(directory / "signature.p7b"), "-content",
                                     str(directory / "signed_content.bin"), "-noverify",
                                     "-out", str(directory / "verified_signed_content.bin")],
                                    capture_output=True, text=True)
            (directory / "signature_verification.log").write_text(result.stdout + result.stderr, encoding="utf-8")
            meta["signature_verification"] = "valid detached signature" if result.returncode == 0 else "failed"
            require(result.returncode == 0, "Detached PKCS7 signature verification failed")
        entry = dict(file=source.name, size=len(data), sha256=sha(data), capsule=meta,
                     component=component, image_size=len(image), image_sha256=sha(image),
                     duplicate_images_identical=True,
                     pairs=[dict(offer_hex=p["offer"].hex(), offer_offset=meta["cfu_offset"] + p["offer_offset"],
                                 component_id=hex(p["offer"][2]), records=len(p["records"])) for p in pairs])
        if "Haptic" in source.name:
            cs_output = output / "cs40l25"
            cs_output.mkdir(exist_ok=True)
            manifest["cs40l25"] = reconstruct_haptic(image, cs_output)
        manifest["sources"].append(entry)
        require(source.read_bytes() == data, "Original input unexpectedly changed")
        print(f"{source.name}: {len(pairs)} identical images, {len(image)} bytes, "
              f"{len(pairs[0]['records'])} CFU records/image")
    write_json(output / "manifest.json", manifest)
    write_report(output, manifest)
    checksums = {str(p.relative_to(output)).replace("\\", "/"): sha(p.read_bytes())
                 for p in sorted(output.rglob("*")) if p.is_file() and p.name != "SHA256SUMS.json"}
    write_json(output / "SHA256SUMS.json", checksums)
    print("CS40L25: all 167 CRC16 values valid; first 137 blocks match SDK ext_boost firmware")
    print(f"Results: {output}")


if __name__ == "__main__":
    main()
