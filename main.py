import os
import json
import sys
from flask import Flask, request
import requests

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TARGET_TOKENS = os.environ.get("TARGET_TOKEN_ADDRESSES", "").split(",")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    requests.post(url, json=payload)

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

        # Return early just for this test
        return "Received and logged", 200

    except Exception as e:
        error_message = f"⚠️ Exception during webhook: {str(e)}"
        print(error_message)
        send_telegram_message(error_message)
        return error_message, 500


    try:
        # Check the structure of the incoming data
        if isinstance(data, dict):
            events = data.get("events", [])
        elif isinstance(data, list):
            events = data
        else:
            send_telegram_message("⚠️ Unexpected webhook format. Data is neither dict nor list.")
            return "Unexpected format", 400

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

                if token in TARGET_TOKENS:
                    message = (
                        f"📦 Token Transfer Detected:\n"
                        f"From: {source}\nTo: {destination}\n"
                        f"Token: {token}\nAmount: {amount}"
                    )
                    send_telegram_message(message)

    except Exception as e:
        send_telegram_message(f"⚠️ Error processing webhook: {str(e)}")

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
