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

# Token config: name + decimals
TOKEN_INFO = {
    "5241BVJpTDscdFM5bTmeuchBcjXN5sasBywyF7onkJZP": {"name": "PUFF", "decimals": 6},
    "CnfshwmvDqLrB1jSLF7bLJ3iZF5u354WRFGPBmGz4uyf": {"name": "TEMA", "decimals": 6},
    "CsZFPqMei7DXBfXfxCydAPBN9y5wzrYmYcwBhLLRT3iU": {"name": "BLOCKY", "decimals": 6}
}

# Fetch price from Birdeye
def get_token_price(token_address):
    url = f"https://public-api.birdeye.so/public/price?address={token_address}"
    headers = {"X-API-KEY": BIRDEYE_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return float(data["data"]["value"])
    except Exception as e:
        print(f"⚠️ Error fetching token price for {token_address}: {e}")
        return None

def get_sol_price():
    sol_address = "So11111111111111111111111111111111111111112"
    return get_token_price(sol_address)

# Send Telegram message
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

                if token not in TARGET_TOKENS:
                    continue

                token_info = TOKEN_INFO.get(token, {})
                token_name = token_info.get("name", token)
                decimals = token_info.get("decimals", 0)

                try:
                    amount_float = float(raw_amount)
                    amount_formatted = f"{amount_float:,.0f}"
                except:
                    amount_float = 0
                    amount_formatted = str(raw_amount)

                # Determine action type
                if destination in MONITORED_WALLETS:
                    action = "🟢 BUY"
                elif source in MONITORED_WALLETS:
                    action = "🔴 SELL"
                else:
                    action = "⚪ Transfer (Untracked Wallet)"

                # Get token price + live SOL price
                token_price_in_sol = get_token_price(token)
                sol_price_usd = get_sol_price()
                if token_price_in_sol and amount_float:
                    value_in_sol = token_price_in_sol * amount_float
                    sol_formatted = f"{value_in_sol:,.4f}"
                    usd_value = value_in_sol * sol_price_usd if sol_price_usd else None
                    usd_formatted = f"{usd_value:,.2f}" if usd_value else "N/A"
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
