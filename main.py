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
BIRDEYE_API_KEY = os.environ.get("BIRDEYE_API_KEY")

# Mapping token addresses to human-readable names
TOKEN_NAME_MAP = {
    "5241BVJpTDscdFM5bTmeuchBcjXN5sasBywyF7onkJZP": "PUFF",
    "CnfshwmvDqLrB1jSLF7bLJ3iZF5u354WRFGPBmGz4uyf": "TEMA",
    "CsZFPqMei7DXBfXfxCydAPBN9y5wzrYmYcwBhLLRT3iU": "BLOCKY"
}

# Get real-time token price from Birdeye API
def get_token_price(token_address):
    url = f"https://public-api.birdeye.so/defi/price?address={token_address}"
    headers = {"X-API-KEY": BIRDEYE_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return float(data["data"]["value"])
    except Exception as e:
        print(f"⚠️ Error fetching token price: {e}")
        return None

# Send message via Telegram bot
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
                raw_amount = token_transfer.get("amount")

                print(f"💡 Detected token: {token}")
                print(f"🎯 Target tokens: {TARGET_TOKENS}")

                if token not in TARGET_TOKENS:
                    continue

                # Format amount with commas
                try:
                    amount_float = float(raw_amount)
                    amount_formatted = f"{amount_float:,.0f}"
                except:
                    amount_formatted = raw_amount

                # Get token name
                token_name = TOKEN_NAME_MAP.get(token, token)

                # Determine if it's a BUY or SELL
                if destination in MONITORED_WALLETS:
                    action = "🟢 BUY"
                elif source in MONITORED_WALLETS:
                    action = "🔴 SELL"
                else:
                    action = "⚪ Transfer (Untracked Wallet)"

                # Get price in SOL and estimate USD
                price_per_token = get_token_price(token)
                if price_per_token and amount_float:
                    est_value_sol = price_per_token * amount_float
                    sol_formatted = f"{est_value_sol:,.4f}"
                    # Estimate USD value assuming 1 SOL = 150 USD (or fetch live SOL/USD)
                    usd_value = est_value_sol * 150
                    usd_formatted = f"{usd_value:,.2f}"
                    value_text = f"\nEst. Value: ~{sol_formatted} SOL (~${usd_formatted})"
                else:
                    value_text = ""

                message = (
                    f"{action} DETECTED\n"
                    f"From: {source}\n"
                    f"To: {destination}\n"
                    f"Token: {token_name}\n"
                    f"Amount: {amount_formatted}{value_text}"
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
