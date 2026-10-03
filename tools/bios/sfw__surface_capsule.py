#!/usr/bin/env python3
"""Shared strict parser for Surface UEFI FMP firmware capsules.

Layering (per barryblueice/mcu-drivers tools/surface_firmware):

    FMP capsule
      -> GUID + header + FMP item table
      -> auth: MonotonicCount(8) + WIN_CERTIFICATE_UEFI_GUID(PKCS7)
      -> payload: MSS1 header(16) + SAML header(25) + CFU stream
      -> CFU: 2x (16-byte offer + records)
      -> Component (contiguous, reassembled)
      -> body (Component header + body_offset)

Differences between the samples are handled explicitly rather than guessed:

  * Touchpad capsules carry two byte-identical payloads; SAM carries two
    *different* variants. `require_identical` selects which contract applies.
  * The SAML 25-byte header and the CFU record layout are inferred from the
    sample files, not from a published ABI, so they are length-checked.

Any structural violation raises. A "best effort" image would silently make
downstream waveform addresses and payload bytes untrustworthy.
"""
from __future__ import annotations

import binascii
import hashlib
import struct
import uuid
from pathlib import Path

FMP_GUID = "6dcbd5ed-e82d-4c44-bda1-7194199ad92a"
PKCS7_GUID = "4aafd29d-68df-49ee-8aa9-347d375665a7"

# CFU record: uint32 component_offset_le ; uint8 length ; uint8 data[length]
MAX_RECORD = 16
SAML_HEADER = 25
MSS1_HEADER = 16


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


class Capsule:
    """Parsed FMP capsule: metadata, signature blob and the two CFU images."""

    def __init__(self, data: bytes, name: str = ""):
        self.name = name
        self.data = data
        self.meta: dict = {}
        self.signature = b""
        self.monotonic = b""
        self.pairs: list[dict] = []

    # -- layer 1: FMP item + authentication -----------------------------
    def split(self) -> bytes:
        d = self.data
        require(str(uuid.UUID(bytes_le=take(d, 0, 16))) == FMP_GUID, "not an FMP capsule")
        header_size, flags, total_size = unpack("<III", d, 16)
        require(header_size >= 28 and total_size == len(d), "invalid capsule length")
        version, drivers, payloads = unpack("<IHH", d, header_size)
        require((version, drivers, payloads) == (1, 0, 1), "unsupported FMP item layout")
        relative, = unpack("<Q", d, header_size + 8)
        require(relative >= 16, "FMP item overlaps item table")
        item = header_size + relative
        image_version, = unpack("<I", d, item)
        require(image_version == 2, "expected FMP image header v2")
        image_guid = str(uuid.UUID(bytes_le=take(d, item + 4, 16)))
        image_size, vendor_size = unpack("<II", d, item + 24)
        auth = item + 40
        require(auth + image_size + vendor_size == len(d) and vendor_size == 0,
                "FMP image size mismatch")

        self.monotonic = take(d, auth, 8)
        cert = auth + 8
        cert_size, cert_revision, cert_type = unpack("<IHH", d, cert)
        require(cert_size >= 24 and (cert_revision, cert_type) == (0x200, 0xEF1),
                "unsupported authentication certificate")
        require(str(uuid.UUID(bytes_le=take(d, cert + 8, 16))) == PKCS7_GUID,
                "expected PKCS7 authentication")
        self.signature = take(d, cert + 24, cert_size - 24)

        payload_offset = cert + cert_size
        payload = take(d, payload_offset, len(d) - payload_offset)
        magic, mss_size, fw_version, lowest = unpack("<4sIII", payload, 0)
        require(magic == b"MSS1" and mss_size == MSS1_HEADER, "unsupported MSS1 header")
        saml = take(payload, mss_size, len(payload) - mss_size)
        require(take(saml, 0, 4) == b"SAML", "missing SAML wrapper")
        records_size, saml_version = unpack("<II", saml, 17)
        require(records_size == len(saml) - SAML_HEADER, "SAML content length mismatch")
        require(saml_version == fw_version, "SAML/MSS1 version mismatch")

        self.meta = dict(
            capsule_size=len(d), capsule_sha256=sha(d), capsule_flags=hex(flags),
            header_size=header_size, image_type_guid=image_guid,
            image_size=image_size, vendor_size=vendor_size,
            authentication_offset=auth, signed_payload_offset=payload_offset,
            mss1_version=hex(fw_version), lowest_supported_version=lowest,
            saml_offset=payload_offset + mss_size, saml_header_hex=saml[:SAML_HEADER].hex(),
            cfu_offset=payload_offset + mss_size + SAML_HEADER,
            signature_bytes=len(self.signature), monotonic_hex=self.monotonic.hex(),
            signature_verification="not attempted", certificate_trust="not evaluated",
            saml_header_unknown_fields="preserved; no checksum claim",
        )
        return saml[SAML_HEADER:]

    # -- layer 2: CFU offers + records ----------------------------------
    def parse_cfu(self, stream: bytes, require_identical: bool = True) -> list[dict]:
        """Walk the CFU stream.

        Offer layout (16 B), as observed across four independent capsules:
            [0]      0 or 2        variant / direction
            [1]      0
            [2]      component id  0x16 on the touchpad samples, 0x00 on SAM
            [3]      0xB0
            [4:8]    build / size-ish, differs per capsule
            [8:12]   flags, zero in every sample
            [12]     0x04 or 0x14  -- the low bit distinguishes the two offers
            [13]     0x01 (touchpad) or 0x02 (SAM)
            [14:16]  3C 00         constant in every sample seen

        Only [3] and [14:16] are treated as hard invariants; the remaining bytes
        are recorded in the report rather than asserted, because they legitimately
        differ between the SAM and touchpad capsules and between their two offers.
        The invariant actually enforced across a capsule's two offers is that
        bytes 0..12 agree (the "offer identity" check from the project notes).
        """
        pairs, pos = [], 0
        while pos < len(stream):
            offer_offset = pos
            offer = take(stream, pos, 16)
            require(offer[1] == 0 and offer[3] == 0xB0 and offer[14:] == b"\x3c\x00",
                    f"unsupported CFU offer {offer.hex()}")
            require(offer[0] in (0, 2), f"unexpected offer variant byte {offer[0]}")
            require(not pairs or offer[:12] == pairs[0]["offer"][:12],
                    "CFU offer identity differs")
            pos += 16
            start = pos
            image = bytearray()
            records = []
            while pos < len(stream):
                address, length = unpack("<IB", stream, pos)
                if length == 0 or length > MAX_RECORD:
                    break  # next offer begins with non-record fields
                require(address == len(image), "CFU address gap, overlap, or disorder")
                image.extend(take(stream, pos + 5, length))
                records.append(dict(offset=pos, address=address, size=length))
                pos += 5 + length
            require(records, "empty CFU image")
            pairs.append(dict(offer=offer, offer_offset=offer_offset,
                              image=bytes(image), payload=stream[start:pos],
                              records=records))
        require(len(pairs) == 2, "expected two complete CFU offer/payload pairs")
        if require_identical:
            require(pairs[0]["image"] == pairs[1]["image"], "the two payload images differ")
            require(pairs[0]["payload"] == pairs[1]["payload"],
                    "CFU record encodings differ")
        return pairs

    # -- layer 3: Component header --------------------------------------
    @staticmethod
    def parse_component(image: bytes) -> dict:
        header_size, v1, v2, extension, body = unpack("<5I", image, 0)
        require((header_size, v1, v2) == (20, 1, 1), "unknown component header")
        require(header_size <= extension < body < len(image), "invalid component body offset")
        return dict(header_size=header_size, extension_offset=extension,
                    body_offset=body, body_size=len(image) - body,
                    header_fields="observed structure; not all metadata fields interpreted")


def load(path: Path, name: str = "") -> Capsule:
    c = Capsule(path.read_bytes(), name or path.name)
    c.split()
    return c


def cs40l25_blocks(body: bytes) -> list[tuple[int, int, bytes]]:
    """Parse a CS40L25 haptic body into (seq, dsp_address, payload) triples."""
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
