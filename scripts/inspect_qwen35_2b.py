import os
import struct
import sys

GGUF_PATH = r"C:\Users\cheta\.lmstudio\models\Qwen\Qwen3.5-2B-GGUF\Qwen3.5-2B-Q4_K_M.gguf"

def read_str(f):
    l = struct.unpack("<Q", f.read(8))[0]
    return f.read(l).decode("utf-8", errors="replace")

def read_val(f, vtype):
    # GGUF value types:
    # 0: UINT8, 1: INT8, 2: UINT16, 3: INT16, 4: UINT32, 5: INT32, 6: FLOAT32, 7: BOOL
    # 8: STRING, 9: ARRAY, 10: UINT64, 11: INT64, 12: FLOAT64
    if vtype == 0: return struct.unpack("<B", f.read(1))[0]
    if vtype == 1: return struct.unpack("<b", f.read(1))[0]
    if vtype == 2: return struct.unpack("<H", f.read(2))[0]
    if vtype == 3: return struct.unpack("<h", f.read(2))[0]
    if vtype == 4: return struct.unpack("<I", f.read(4))[0]
    if vtype == 5: return struct.unpack("<i", f.read(4))[0]
    if vtype == 6: return struct.unpack("<f", f.read(4))[0]
    if vtype == 7: return struct.unpack("<?", f.read(1))[0]
    if vtype == 8: return read_str(f)
    if vtype == 9:
        sub_type = struct.unpack("<I", f.read(4))[0]
        count = struct.unpack("<Q", f.read(8))[0]
        if sub_type == 8: # array of strings
            arr = [read_str(f) for _ in range(count)]
            if len(arr) > 5: return f"Array(str)[{count}] (sample: {arr[:3]}...)"
            return arr
        else:
            sizes = {0:1, 1:1, 2:2, 3:2, 4:4, 5:4, 6:4, 7:1, 10:8, 11:8, 12:8}
            sz = sizes.get(sub_type, 0)
            f.seek(sz * count, 1)
            return f"Array(type={sub_type})[{count}]"
    if vtype == 10: return struct.unpack("<Q", f.read(8))[0]
    if vtype == 11: return struct.unpack("<q", f.read(8))[0]
    if vtype == 12: return struct.unpack("<d", f.read(8))[0]
    return f"Unknown({vtype})"

def inspect():
    print(f"Inspecting GGUF: {GGUF_PATH}")
    if not os.path.exists(GGUF_PATH):
        print(f"ERROR: File does not exist at {GGUF_PATH}")
        sys.exit(1)
        
    size_bytes = os.path.getsize(GGUF_PATH)
    print(f"File size: {size_bytes} bytes ({size_bytes / (1024**3):.3f} GB / {size_bytes / (1024**2):.2f} MB)")
    
    with open(GGUF_PATH, "rb") as f:
        magic = f.read(4)
        if magic != b"GGUF":
            print(f"ERROR: Magic is {magic!r}, expected b'GGUF'")
            sys.exit(1)
        version = struct.unpack("<I", f.read(4))[0]
        tensor_count = struct.unpack("<Q", f.read(8))[0]
        kv_count = struct.unpack("<Q", f.read(8))[0]
        print(f"Magic: {magic}, GGUF Version: {version}, Tensors: {tensor_count}, Metadata KV pairs: {kv_count}\n")
        
        metadata = {}
        for _ in range(kv_count):
            k = read_str(f)
            vtype = struct.unpack("<I", f.read(4))[0]
            v = read_val(f, vtype)
            metadata[k] = v
            
        print("Key Metadata:")
        keys_to_print = [
            "general.architecture",
            "general.name",
            "general.type",
            "general.version",
            "general.size_label",
            "general.file_type",
            "general.quantization_version",
            "qwen.block_count",
            "qwen.context_length",
            "qwen.embedding_length",
            "qwen.feed_forward_length",
            "qwen.attention.head_count",
            "qwen.attention.head_count_kv",
            "qwen2.block_count",
            "qwen2.context_length",
            "qwen2.embedding_length",
            "qwen2.feed_forward_length",
            "qwen2.attention.head_count",
            "qwen2.attention.head_count_kv",
            "tokenizer.ggml.model",
        ]
        for k in keys_to_print:
            if k in metadata:
                print(f"  {k}: {metadata[k]}")
                
        # Also print any general.* or architecture info
        for k, v in metadata.items():
            if k not in keys_to_print and any(term in k for term in ["arch", "param", "tensor", "model_type", "quant"]):
                print(f"  {k}: {v}")

if __name__ == "__main__":
    inspect()
