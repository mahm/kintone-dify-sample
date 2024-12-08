#!/usr/bin/env bash

# エラーハンドリングとパイプフェイル時の終了
set -euo pipefail

# uvicornとngrokのプロセスIDを格納する変数
UVICORN_PID=""
NGROK_PID=""

# 終了処理用の関数
cleanup() {
    echo "Shutting down..."

    if [ -n "$NGROK_PID" ] && kill -0 "$NGROK_PID" 2>/dev/null; then
        echo "Stopping ngrok (PID: $NGROK_PID)"
        kill "$NGROK_PID"
        wait "$NGROK_PID" 2>/dev/null || true
    fi

    if [ -n "$UVICORN_PID" ] && kill -0 "$UVICORN_PID" 2>/dev/null; then
        echo "Stopping uvicorn (PID: $UVICORN_PID)"
        kill "$UVICORN_PID"
        wait "$UVICORN_PID" 2>/dev/null || true
    fi

    echo "All services stopped."
}

# SIGINTやSIGTERMが来たらcleanupを実行
trap cleanup INT TERM

# uvicorn起動
echo "Starting uvicorn on port 8000..."
uv run uvicorn src.main:app --port 8000 --reload &
UVICORN_PID=$!
echo "uvicorn PID: $UVICORN_PID"

# ngrok起動
echo "Starting ngrok to tunnel port 8000..."
ngrok http 8000 &
NGROK_PID=$!
echo "ngrok PID: $NGROK_PID"

echo "Services running. Press Ctrl+C to stop."

# プロセスが終わるまで待機
wait "$UVICORN_PID"
wait "$NGROK_PID"
