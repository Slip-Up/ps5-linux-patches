import argparse
import struct
import zlib
from pathlib import Path


PATCHES = (
    # Skip the SMU wait during boot.
    (0xFD2D, b"\x16\xfe\x0e", b"\xf0\x20\x00"),
    # Return from the runtime SMU helper without sending a request.
    (0x10977, b"\x8c\x28", b"\x3d\xf0"),
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    firmware = bytearray(args.source.read_bytes())

    for offset, before, after in PATCHES:
        end = offset + len(before)
        if firmware[offset:end] != before:
            raise SystemExit(f"Unexpected instruction at {offset:#x}")
        firmware[offset:end] = after

    payload_size, payload_offset = struct.unpack_from("<II", firmware, 20)
    if payload_offset != 256 or payload_offset + payload_size != len(firmware):
        raise SystemExit("Unexpected firmware payload size")

    payload_crc = zlib.crc32(firmware[payload_offset:])
    struct.pack_into("<I", firmware, 28, payload_crc)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(firmware)


if __name__ == "__main__":
    main()
