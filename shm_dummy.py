#!/usr/bin/env python3
"""
shm_dummy.py  -  BlobFinder 共有メモリ テスト用ダミープログラム

使い方:
    python shm_dummy.py [コマンド] [オプション]

コマンド:
    stream              カメラストリーム開始指令を送る
    pipeline <name>     画像処理リスト選択指令を送る
    capture [N]         撮影指令を N 回送る (デフォルト 1)
    burst [N] [interval] N 回を interval 秒間隔で連続送信 (デフォルト 10, 0.1)
    status              共有メモリの結果領域を表示
    watch               結果領域を監視し続ける
    help                このヘルプを表示

例:
    python shm_dummy.py stream
    python shm_dummy.py pipeline テスト1
    python shm_dummy.py capture 3
    python shm_dummy.py burst 20 0.05
    python shm_dummy.py watch
"""

import json
import sys
import time
from multiprocessing import shared_memory

# shm/layout.py と同じ定数
SHM_NAME = "blobfinder_shm"
CMD_SIZE = 1024
RES_SIZE = 4 * 1024 * 1024
TOTAL_SIZE = CMD_SIZE + RES_SIZE


def _open_shm() -> shared_memory.SharedMemory:
    try:
        return shared_memory.SharedMemory(name=SHM_NAME, create=False)
    except FileNotFoundError:
        print(f"[ERROR] 共有メモリ '{SHM_NAME}' が見つかりません。")
        print("        BlobFinder サーバーが起動しているか確認してください。")
        sys.exit(1)


def _read_field(buf, offset: int, size: int) -> bytes:
    raw = bytes(buf[offset: offset + size])
    end = raw.find(b"\x00")
    return raw[:end] if end >= 0 else raw


def _write_field(buf, offset: int, size: int, data: bytes):
    if len(data) >= size:
        raise ValueError(f"data too large: {len(data)} >= {size}")
    buf[offset: offset + len(data)] = data
    buf[offset + len(data)] = 0


def _read_cmd(shm) -> dict:
    raw = _read_field(shm.buf, 0, CMD_SIZE)
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def _write_cmd(shm, cmd: dict):
    raw = json.dumps(cmd, ensure_ascii=False).encode("utf-8")
    _write_field(shm.buf, 0, CMD_SIZE, raw)


def _read_result(shm) -> dict:
    raw = _read_field(shm.buf, CMD_SIZE, RES_SIZE)
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def _next_seq(shm) -> int:
    cmd = _read_cmd(shm)
    return (cmd.get("seq", 0) + 1) % 100000


def _send_cmd(shm, **kwargs):
    """現在のコマンドをベースに指定フィールドを上書きして送信"""
    cmd = _read_cmd(shm)
    # フラグをリセット
    cmd.update({
        "stream_start": 0,
        "pipeline_select": 0,
        "capture": 0,
        "pipeline_name": cmd.get("pipeline_name", ""),
    })
    cmd.update(kwargs)
    cmd["seq"] = _next_seq(shm)
    _write_cmd(shm, cmd)
    print(f"[SEND] seq={cmd['seq']}  {kwargs}")


# ------------------------------------------------------------------
# コマンド実装
# ------------------------------------------------------------------

def cmd_stream(shm):
    _send_cmd(shm, stream_start=1)
    print("カメラストリーム開始指令を送信しました")


def cmd_pipeline(shm, name: str):
    _send_cmd(shm, pipeline_select=1, pipeline_name=name)
    print(f"画像処理リスト選択指令を送信しました: {name}")


def cmd_capture(shm, n: int = 1):
    for i in range(n):
        _send_cmd(shm, capture=1)
        if n > 1:
            time.sleep(0.01)
    print(f"撮影指令を {n} 回送信しました")


def cmd_burst(shm, n: int = 10, interval: float = 0.1):
    print(f"バースト送信: {n} 回 / {interval}秒間隔")
    for i in range(n):
        _send_cmd(shm, capture=1)
        print(f"  [{i+1}/{n}] 送信")
        time.sleep(interval)
    print("バースト送信完了")


def cmd_status(shm):
    result = _read_result(shm)
    if not result:
        print("結果領域が空です")
        return
    # base64 画像は長いので省略
    display = {k: (f"<{len(v)} chars>" if k.endswith("_b64") and v else v)
               for k, v in result.items()}
    print(json.dumps(display, ensure_ascii=False, indent=2))


def cmd_watch(shm):
    print("結果領域を監視中... (Ctrl+C で終了)")
    last_seq = None
    try:
        while True:
            result = _read_result(shm)
            seq = result.get("seq")
            if seq != last_seq:
                last_seq = seq
                status = result.get("status", "?")
                error = result.get("error")
                captured_at = result.get("captured_at", "")
                blobs = result.get("blobs")
                blob_count = len(blobs) if isinstance(blobs, list) else "-"
                has_capture = bool(result.get("capture_b64"))
                has_result = bool(result.get("result_b64"))
                print(
                    f"[seq={seq}] status={status}"
                    + (f"  error={error}" if error else "")
                    + (f"  at={captured_at}" if captured_at else "")
                    + f"  blobs={blob_count}"
                    + f"  capture={'✓' if has_capture else '✗'}"
                    + f"  result={'✓' if has_result else '✗'}"
                )
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n監視終了")


def cmd_interactive(shm):
    """対話モード"""
    print("BlobFinder 共有メモリ テストツール (対話モード)")
    print("コマンド: stream / pipeline <name> / capture [N] / burst [N] [interval] / status / watch / quit")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        parts = line.split()
        c = parts[0].lower()
        if c in ("quit", "exit", "q"):
            break
        elif c == "stream":
            cmd_stream(shm)
        elif c == "pipeline":
            name = " ".join(parts[1:]) if len(parts) > 1 else ""
            if not name:
                print("使い方: pipeline <name>")
            else:
                cmd_pipeline(shm, name)
        elif c == "capture":
            n = int(parts[1]) if len(parts) > 1 else 1
            cmd_capture(shm, n)
        elif c == "burst":
            n = int(parts[1]) if len(parts) > 1 else 10
            interval = float(parts[2]) if len(parts) > 2 else 0.1
            cmd_burst(shm, n, interval)
        elif c == "status":
            cmd_status(shm)
        elif c == "watch":
            cmd_watch(shm)
        else:
            print(f"不明なコマンド: {c}")


# ------------------------------------------------------------------
# エントリポイント
# ------------------------------------------------------------------

def main():
    args = sys.argv[1:]

    if not args or args[0] in ("help", "--help", "-h"):
        print(__doc__)
        return

    shm = _open_shm()
    try:
        c = args[0].lower()
        if c == "stream":
            cmd_stream(shm)
        elif c == "pipeline":
            name = " ".join(args[1:]) if len(args) > 1 else ""
            if not name:
                print("使い方: python shm_dummy.py pipeline <name>")
            else:
                cmd_pipeline(shm, name)
        elif c == "capture":
            n = int(args[1]) if len(args) > 1 else 1
            cmd_capture(shm, n)
        elif c == "burst":
            n = int(args[1]) if len(args) > 1 else 10
            interval = float(args[2]) if len(args) > 2 else 0.1
            cmd_burst(shm, n, interval)
        elif c == "status":
            cmd_status(shm)
        elif c == "watch":
            cmd_watch(shm)
        elif c == "interactive":
            cmd_interactive(shm)
        else:
            # 引数なしで起動したら対話モード
            cmd_interactive(shm)
    finally:
        shm.close()


if __name__ == "__main__":
    main()
