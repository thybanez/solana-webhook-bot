import os
import json
import sys
from flask import Flask, request
import requests

app = Flask(__name__)

# Environment variables
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TARGET_TOKENS = os.environ.get("TARGET_TOKEN_ADDRESSES", "").split(",")
MONITORED_WALLETS = os.environ.get("MONITORED_WALLETS", "").split(",")

# Mapping token addresses to human-readable names
TOKEN_NAME_MAP = {
    "5241BVJpTDscdFM5bTmeuchBcjXN5sasBywyF7onkJZP": "PUFF",
    "CnfshwmvDqLrB1jSLF7bLJ3iZF5u354WRFGPBmGz4uyf": "TEMA",
    "CsZFPqMei7DXBfXfxCydAPBN9y5wzrYmYcwBhLLRT3iU": "BLOCKY"
}

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    response = requests.post(url, json=payload)
    print(f"📬 Telegram response: {response.status_code} {response.text}")

@app.route("/")
def index():
    return "✅ Solana bot is running."

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True, silent=False)

        print("🚨 Incoming Webhook Payload:")
        print(json.dumps(data, indent=2))
        sys.stdout.flush()

        if not data:
            return "No data received", 400

        events = data.get("events", []) if isinstance(data, dict) else data

        for event in events:
            if not isinstance(event, dict):
                continue

            source = event.get("fromUserAccount")
            destination = event.get("toUserAccount")
            token_transfers = event.get("tokenTransfers", [])

            if not isinstance(token_transfers, list) or not token_transfers:
                continue

            for token_transfer in token_transfers:
                if not isinstance(token_transfer, dict):
                    continue

                token = token_transfer.get("tokenAddress")
                amount = token_transfer.get("amount")

                print(f"💡 Detected token: {token}")
                print(f"🎯 Target tokens: {TARGET_TOKENS}")

                if token not in TARGET_TOKENS:
                    continue

                # Get token name
                token_name = TOKEN_NAME_MAP.get(token, token)

                # Determine if it's a BUY or SELL
                if destination in MONITORED_WALLETS:
                    action = "🟢 BUY"
                elif source in MONITORED_WALLETS:
                    action = "🔴 SELL"
                else:
                    action = "⚪ Transfer (Untracked Wallet)"

                message = (
                    f"{action} DETECTED\n"
                    f"From: {source}\n"
                    f"To: {destination}\n"
                    f"Token: {token_name}\n"
                    f"Amount: {amount}"
                )
                send_telegram_message(message)

    except Exception as e:
        error_message = f"⚠️ Error processing webhook: {str(e)}"
        print(error_message)
        send_telegram_message(error_message)
        return error_message, 500

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
