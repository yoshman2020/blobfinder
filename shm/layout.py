"""
共有メモリレイアウト定義

[0      : CMD_SIZE ]  コマンド領域  (JSON, UTF-8, null-terminated)
[CMD_SIZE: CMD_SIZE+RES_SIZE]  結果領域  (JSON, UTF-8, null-terminated)

コマンド JSON スキーマ:
{
  "stream_start":    0 or 1,   # 立ち上がりフラグ
  "pipeline_select": 0 or 1,   # 立ち上がりフラグ
  "pipeline_name":   str,      # pipeline_select=1 のとき有効
  "capture":         0 or 1,   # 立ち上がりフラグ
  "seq":             int        # コマンドシーケンス番号（変化で検出）
}

結果 JSON スキーマ:
{
  "status":       "idle"|"ok"|"error"|"streaming"|"processing",
  "error":        str or null,
  "seq":          int,          # 対応するコマンドの seq
  "captured_at":  ISO8601 str or null,
  "capture_b64":  base64 JPEG or null,
  "result_b64":   base64 JPEG or null,
  "blobs":        list or null
}
"""

SHM_NAME = "blobfinder_shm"
CMD_SIZE = 1024          # bytes
RES_SIZE = 4 * 1024 * 1024  # 4 MB
TOTAL_SIZE = CMD_SIZE + RES_SIZE


def read_json_field(shm_buf, offset: int, size: int) -> bytes:
    """共有メモリの指定領域から null-terminated バイト列を読む"""
    raw = bytes(shm_buf[offset: offset + size])
    end = raw.find(b"\x00")
    return raw[:end] if end >= 0 else raw


def write_json_field(shm_buf, offset: int, size: int, data: bytes):
    """共有メモリの指定領域に null-terminated バイト列を書く"""
    if len(data) >= size:
        raise ValueError(f"data too large: {len(data)} >= {size}")
    shm_buf[offset: offset + len(data)] = data
    shm_buf[offset + len(data)] = 0  # null terminate
