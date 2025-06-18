import os
import json
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
    data = request.get_json()

    if not data:
        return "No data received", 400

    try:
        for event in data.get("events", []):
            source = event.get("fromUserAccount")
            destination = event.get("toUserAccount")
token_transfers = event.get("tokenTransfers", [])
if token_transfers:
    for token_transfer in token_transfers:
        token = token_transfer.get("tokenAddress")
        amount = token_transfer.get("amount")

        if token in TARGET_TOKENS:
            message = f"📦 Token Transfer Detected:\nFrom: {source}\nTo: {destination}\nToken: {token}\nAmount: {amount}"
            send_telegram_message(message)

            
            # ✅ Only alert for tokens you're tracking
            if token in TARGET_TOKENS:
                message = f"📦 Token Transfer Detected:\nFrom: {source}\nTo: {destination}\nToken: {token}\nAmount: {amount}"
                send_telegram_message(message)
            

            message = f"📦 Token Transfer Detected:\nFrom: {source}\nTo: {destination}\nToken: {token}\nAmount: {amount}"
            send_telegram_message(message)
    except Exception as e:
        send_telegram_message(f"⚠️ Error processing webhook: {str(e)}")

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
