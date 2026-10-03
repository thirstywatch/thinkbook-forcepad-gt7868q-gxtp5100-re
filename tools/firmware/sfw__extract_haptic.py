#!/usr/bin/env python3
"""Unwrap a Surface touchpad FMP capsule and dump the CS40L25 haptic body.

Structure and every assertion follow barryblueice/mcu-drivers
tools/surface_firmware/extract_surface.py, which is a strict parser for these
specific capsules rather than a general Surface updater:

    FMP capsule -> auth (PKCS7) -> MSS1 -> SAML (25-byte header) -> CFU
    CFU         -> 2x (16-byte offer + records)  -> Component -> body

Nothing here talks to hardware. Any structural violation raises instead of
returning a partial result, because a "best effort" image would silently make
the waveform addresses and payload bytes untrustworthy.
"""
from __future__ import annotations

import binascii
import hashlib
import json
import struct
import sys
import uuid
from pathlib import Path

FMP_GUID = "6dcbd5ed-e82d-4c44-bda1-7194199ad92a"
PKCS7_GUID = "4aafd29d-68df-49ee-8aa9-347d375665a7"

HERE = Path(__file__).resolve().parent
BIN = HERE / "bin"
OUT = HERE / "unpacked"


def require(cond, msg):
    if not cond:
        raise ValueError(msg)


def take(data, offset, size):
    require(0 <= offset <= len(data) and 0 <= size <= len(data) - offset,
            f"out-of-bounds read at {offset:#x} size {size:#x}")
    return bytes(data[offset:offset + size])


def unpack(fmt, data, offset):
    return struct.unpack(fmt, take(data, offset, struct.calcsize(fmt)))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def split_capsule(data):
    """Capsule -> CFU byte stream. Returns (metadata, cfu_stream)."""
    require(str(uuid.UUID(bytes_le=take(data, 0, 16))) == FMP_GUID, "not an FMP capsule")
    header_size, flags, total_size = unpack("<III", data, 16)
    require(header_size >= 28 and total_size == len(data), "invalid capsule length")
    version, drivers, payloads = unpack("<IHH", data, header_size)
    require((version, drivers, payloads) == (1, 0, 1), "unsupported FMP item layout")
    relative, = unpack("<Q", data, header_size + 8)
    require(relative >= 16, "FMP item overlaps item table")
    item = header_size + relative
    image_version, = unpack("<I", data, item)
    require(image_version == 2, "expected FMP image header v2")
    image_guid = str(uuid.UUID(bytes_le=take(data, item + 4, 16)))
    image_size, vendor_size = unpack("<II", data, item + 24)
    auth = item + 40
    require(auth + image_size + vendor_size == len(data) and vendor_size == 0,
            "FMP image size mismatch")

    monotonic = take(data, auth, 8)
    cert = auth + 8
    cert_size, cert_revision, cert_type = unpack("<IHH", data, cert)
    require(cert_size >= 24 and (cert_revision, cert_type) == (0x200, 0xEF1),
            "unsupported authentication certificate")
    require(str(uuid.UUID(bytes_le=take(data, cert + 8, 16))) == PKCS7_GUID,
            "expected PKCS7 authentication")
    signature = take(data, cert + 24, cert_size - 24)

    payload_offset = cert + cert_size
    payload = take(data, payload_offset, len(data) - payload_offset)
    magic, mss_size, fw_version, lowest_version = unpack("<4sIII", payload, 0)
    require(magic == b"MSS1" and mss_size == 16, "unsupported MSS1 header")
    saml = take(payload, mss_size, len(payload) - mss_size)
    require(take(saml, 0, 4) == b"SAML", "missing SAML wrapper")
    # Offsets inferred from the sample files, not a published SAML ABI.
    records_size, saml_version = unpack("<II", saml, 17)
    require(records_size == len(saml) - 25, "SAML content length mismatch")
    require(saml_version == fw_version, "SAML/MSS1 version mismatch")

    meta = dict(capsule_size=len(data), capsule_flags=hex(flags), image_type_guid=image_guid,
                authentication_offset=auth, signed_payload_offset=payload_offset,
                mss1_version=hex(fw_version), lowest_supported_version=lowest_version,
                saml_offset=payload_offset + mss_size, saml_header_hex=saml[:25].hex(),
                cfu_offset=payload_offset + mss_size + 25,
                signature_bytes=len(signature), monotonic_hex=monotonic.hex(),
                signature_verification="not attempted", certificate_trust="not evaluated",
                saml_header_unknown_fields="preserved; no checksum claim")
    return meta, saml[25:]


def parse_cfu_pairs(data):
    """CFU stream -> the two byte-identical offer/payload pairs."""
    pairs, pos = [], 0
    while pos < len(data):
        offer_offset = pos
        offer = take(data, pos, 16)
        require(offer[0] in (0, 2) and offer[1] == 0 and offer[2] in (0x11, 0x12, 0x16)
                and offer[3] == 0xB0 and offer[12] in (4, 0x14) and offer[13:] == b"\x01\x3c\x00",
                "unsupported CFU offer")
        require(not pairs or offer[:12] == pairs[0]["offer"][:12], "CFU offer identity differs")
        pos += 16
        start = pos
        image = bytearray()
        records = []
        while pos < len(data):
            address, length = unpack("<IB", data, pos)
            if length == 0 or length > 16:  # next offer starts with non-record fields
                break
            require(address == len(image), "CFU address gap, overlap, or disorder")
            image.extend(take(data, pos + 5, length))
            records.append(dict(offset=pos, address=address, size=length))
            pos += 5 + length
        require(records, "empty CFU image")
        pairs.append(dict(offer=offer, image=bytes(image), payload=data[start:pos],
                          offer_offset=offer_offset, records=records))
    require(len(pairs) == 2, "expected two complete CFU offer/payload pairs")
    require(pairs[0]["image"] == pairs[1]["image"], "the two payload images differ")
    require(pairs[0]["payload"] == pairs[1]["payload"], "CFU record encodings differ")
    return pairs


def parse_component(image):
    header_size, v1, v2, extension, body = unpack("<5I", image, 0)
    require((header_size, v1, v2) == (20, 1, 1), "unknown component header")
    require(header_size <= extension < body < len(image), "invalid component body offset")
    return dict(header_size=header_size, extension_offset=extension, body_offset=body,
                body_size=len(image) - body,
                header_fields="observed structure; not all metadata fields interpreted")


def parse_body(body):
    """CS40L25 body -> 167 CRC16-checked DSP write blocks."""
    revision, count = unpack("<II", body, 0)
    require(revision == 0x02800010, f"unexpected body revision {revision:#010x}")
    pos, blocks = 8, []
    while pos < len(body):
        seq, address, size, crc = unpack("<IIIH", body, pos)
        payload = take(body, pos + 14, size)
        require(binascii.crc_hqx(payload, 0xFFFF) == crc, f"CRC16 mismatch at block {seq}")
        blocks.append((seq, address, payload))
        pos += 14 + size
    require(pos == len(body), f"trailing bytes: stopped at {pos:#x} of {len(body):#x}")
    require([s for s, _, _ in blocks] == list(range(count)),
            "sequence numbers are not 0..n-1 contiguous")
    require(count == len(blocks), "block count header mismatch")
    return blocks


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else BIN / "SurfaceTouchpadHaptic_2.9.139.bin"
    data = src.read_bytes()
    print(f"[1] {src.name}  {len(data)} bytes  sha256={sha(data)}")

    meta, cfu_stream = split_capsule(data)
    print(f"[2] capsule: flags={meta['capsule_flags']} mss1={meta['mss1_version']} "
          f"saml@{meta['saml_offset']:#x} cfu@{meta['cfu_offset']:#x} "
          f"sig={meta['signature_bytes']}B")

    pairs = parse_cfu_pairs(cfu_stream)
    comp = pairs[0]["image"]
    print(f"[3] CFU: 2 offers, {len(pairs[0]['records'])} records/image, "
          f"component {len(comp)} bytes, both payloads byte-identical")
    print(f"    offer0={pairs[0]['offer'].hex()}  offer1={pairs[1]['offer'].hex()}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "component.reassembled.bin").write_bytes(comp)
    (OUT / "offer0.bin").write_bytes(pairs[0]["offer"])
    (OUT / "offer1.bin").write_bytes(pairs[1]["offer"])
    (OUT / "component.cfu.payload.bin").write_bytes(pairs[0]["payload"])
    (OUT / "signature.p7b").write_bytes(take(data, meta["authentication_offset"] + 8 + 24,
                                              meta["signature_bytes"]))
    (OUT / "capsule_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    cinfo = parse_component(comp)
    body = comp[cinfo["body_offset"]:]
    (OUT / "component.body.bin").write_bytes(body)
    print(f"[4] component: header={cinfo['header_size']} ext@{cinfo['extension_offset']:#x} "
          f"body@{cinfo['body_offset']:#x} -> body {len(body)} bytes  sha256={sha(body)}")

    blocks = parse_body(body)
    addrs = sorted({a for _, a, _ in blocks})
    print(f"[5] body: revision=0x02800010 blocks={len(blocks)}  all CRC16/CCITT-FALSE verified")
    print(f"    address window 0x{addrs[0]:08X}..0x{addrs[-1]:08X}")

    (OUT / "haptic_blocks.json").write_text(json.dumps(
        [dict(sequence=s, address=a, length=len(d), crc16=binascii.crc_hqx(d, 0xFFFF),
              sha256=sha(d)) for s, a, d in blocks], indent=2), encoding="utf-8")

    # Core blocks match the Cirrus 0A0603 reference; the rest are Surface additions.
    core = [b for b in blocks if b[0] < 137]
    extra = [b for b in blocks if b[0] >= 137]
    print(f"    core blocks (0..136) = {len(core)}, Surface-appended (137..) = {len(extra)}")

    # Merge the appended writes into contiguous regions, keyed by DSP address.
    regions = []
    for seq, address, payload in extra:
        if regions and address == regions[-1][0] + len(regions[-1][1]):
            regions[-1][1].extend(payload)
        else:
            regions.append([address, bytearray(payload)])
    for address, buf in regions:
        name = f"tuning_{address:08x}.bin"
        (OUT / name).write_bytes(buf)
        print(f"    {name}  {len(buf)} bytes  base=0x{address:08X}  sha256={sha(buf)[:16]}...")


if __name__ == "__main__":
    main()
