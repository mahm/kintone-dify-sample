import logging
import os
from logging.handlers import RotatingFileHandler

import httpx
import yaml
from fastapi import FastAPI, Request
from tenacity import retry, stop_after_attempt, wait_fixed

# logsディレクトリが存在しない場合は作成
os.makedirs("logs", exist_ok=True)

# ログハンドラーの設定
file_handler = RotatingFileHandler(
    "logs/application.log", maxBytes=1024 * 1024, backupCount=5, encoding="utf-8"  # 1MB
)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - [%(session_id)s] - %(message)s")
)

# ルートロガーの設定
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)

# tenacityのログレベルを警告（WARNING）に設定
tenacity_logger = logging.getLogger("tenacity")
tenacity_logger.setLevel(logging.WARNING)
tenacity_logger.addHandler(file_handler)

app = FastAPI()

# 設定読み込み
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# Difyのエンドポイント
DIFY_ENDPOINT = "https://api.dify.ai/v1/workflows/run"


# 新しいカスタムエラークラスを追加
class WebhookProcessingError(Exception):
    pass


def find_pair_by_app_id(app_id):
    for pair in config["pairs"]:
        if str(pair["kintone_app_id"]) == str(app_id):
            return pair
    return None


def get_kintone_field_value(record: dict, field_code: str):
    # kintoneフィールドコードのみで値を取得
    field_data = record.get(field_code)
    if field_data and "value" in field_data:
        return field_data["value"]
    return None


def build_dify_input(record: dict, mapping: dict):
    # kintone_to_difyマッピングに従い、recordからDify入力用JSONを生成
    input_fields = {}
    for dify_key, field_code in mapping.items():
        value = get_kintone_field_value(record, field_code)
        input_fields[dify_key] = value

    dify_input = {
        "inputs": input_fields,
        "response_mode": "blocking",
        "user": "kintone-dify-webhook",
    }
    return dify_input


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def call_dify_workflow(endpoint, api_key, payload):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        error_detail = e.response.text if hasattr(e, "response") else str(e)
        raise WebhookProcessingError(f"Dify APIエラー: {error_detail}")
    except Exception as e:
        raise WebhookProcessingError(f"Dify API接続エラー: {str(e)}")


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def kintone_update(app_id, record_id, fields, token, kintone_base_url):
    try:
        url = f"{kintone_base_url}/k/v1/record.json"
        headers = {"X-Cybozu-API-Token": token, "Content-Type": "application/json"}
        body = {
            "app": app_id,
            "id": record_id,
            "record": {k: {"value": v} for k, v in fields.items() if v is not None},
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.put(url, headers=headers, json=body)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        raise WebhookProcessingError(f"Kintone更新エラー: {str(e)}")


@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()

        # webhookイベントIDをセッションIDとして取得
        session_id = data.get("id", "unknown")

        # LoggerAdapterを使用してセッションIDをログに含める
        session_logger = logging.LoggerAdapter(logger, {"session_id": session_id})

        session_logger.info(f"Webhook received with payload: {data}")

        # 更新者による更新をチェック
        modifier = (
            data.get("record", {}).get("更新者", {}).get("value", {}).get("code", "")
        )
        if modifier == "Administrator":
            session_logger.info("Skipping Administrator update")
            return {"status": "skipped", "message": "Administrator update"}

        app_id = data.get("app", {}).get("id")
        record = data.get("record", {})
        record_id = record.get("$id", {}).get("value")

        if not app_id or not record_id:
            raise WebhookProcessingError(
                "無効なペイロード: app_idまたはrecord_idが見つかりません"
            )

        pair = find_pair_by_app_id(app_id)
        if not pair:
            raise WebhookProcessingError(
                f"app_id {app_id} に対応する設定が見つかりません"
            )

        kintone_to_dify_map = pair["kintone_to_dify"]
        dify_to_kintone_map = pair["dify_to_kintone"]

        dify_input = build_dify_input(record, kintone_to_dify_map)
        session_logger.info(f"Built Dify input: {dify_input}")

        # Difyワークフロー呼び出し
        session_logger.info("Calling Dify workflow...")
        dify_response = await call_dify_workflow(
            DIFY_ENDPOINT, pair["dify_api_key"], dify_input
        )
        session_logger.info(f"Dify workflow response received: {dify_response}")

        # Difyレスポンスから'outputs'を取得
        dify_outputs = dify_response.get("data", {}).get("outputs", {})

        # Kintone更新処理
        kintone_update_fields = {
            k: dify_outputs[v]
            for k, v in dify_to_kintone_map.items()
            if v in dify_outputs
        }

        if kintone_update_fields:
            await kintone_update(
                pair["kintone_app_id"],
                record_id,
                kintone_update_fields,
                pair["kintone_token"],
                config["kintone"]["base_url"],
            )
            session_logger.info("Kintone record updated successfully")

        result_status = "done" if kintone_update_fields else "no_update_needed"
        return {"status": result_status}

    except WebhookProcessingError as e:
        session_logger.error(str(e))
        return {"error": str(e), "status": "error"}, 502
    except Exception as e:
        session_logger.error(f"予期せぬエラー: {str(e)}")
        return {"error": "内部サーバーエラー", "status": "error"}, 502
