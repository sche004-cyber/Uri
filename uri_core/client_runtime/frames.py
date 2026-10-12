"""C3 bounded local stdio frames. Partial reads are handled explicitly."""
import json
import struct

from uri_core.client_contracts import FRAME_LIMIT, canonical


class FrameError(ValueError):
    pass


def exact(stream, size):
    result = bytearray()
    while len(result) < size:
        data = stream.read(size - len(result))
        if not data:
            if not result:
                return None
            raise FrameError("FRAME_TRUNCATED")
        result.extend(data)
    return bytes(result)


def read_frame(stream):
    header = exact(stream, 4)
    if header is None:
        return None
    size = struct.unpack(">I", header)[0]
    if not 0 < size <= FRAME_LIMIT:
        raise FrameError("FRAME_LIMIT")
    data = exact(stream, size)
    if data is None:
        raise FrameError("FRAME_TRUNCATED")
    try:
        result = json.loads(data.decode("utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (UnicodeError, ValueError):
        raise FrameError("FRAME_INVALID") from None
    if not isinstance(result, dict):
        raise FrameError("FRAME_OBJECT_REQUIRED")
    return result


def write_frame(stream, value):
    data = canonical(value)
    if not 0 < len(data) <= FRAME_LIMIT:
        raise FrameError("FRAME_LIMIT")
    stream.write(struct.pack(">I", len(data)) + data)
    stream.flush()
