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

# Token mapping and decimals
TOKEN_NAME_MAP = {
    "5241BVJpTDscdFM5bTmeuchBcjXN5sasBywyF7onkJZP": "PUFF",
    "CnfshwmvDqLrB1jSLF7bLJ3iZF5u354WRFGPBmGz4uyf": "TEMA",
    "CsZFPqMei7DXBfXfxCydAPBN9y5wzrYmYcwBhLLRT3iU": "BLOCKY"
}

TOKEN_DECIMALS = {
    "5241BVJpTDscdFM5bTmeuchBcjXN5sasBywyF7onkJZP": 6,
    "CnfshwmvDqLrB1jSLF7bLJ3iZF5u354WRFGPBmGz4uyf": 6,
    "CsZFPqMei7DXBfXfxCydAPBN9y5wzrYmYcwBhLLRT3iU": 9
}

SOL_ADDRESS = "So11111111111111111111111111111111111111112"

# Price fetching using /defi endpoint
def get_token_price(token_address):
    url = f"https://public-api.birdeye.so/defi/price?address={token_address}"
    headers = {"X-API-KEY": BIRDEYE_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return float(data["data"]["value"])
    except Exception as e:
        print(f"⚠️ Error fetching price for {token_address}: {e}")
        return None

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

        print("\n🚨 Incoming Webhook Payload:")
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

                # Normalize amount
                decimals = TOKEN_DECIMALS.get(token, 0)
                try:
                    amount_float = float(raw_amount) / (10 ** decimals)
                    amount_formatted = f"{amount_float:,.6f}".rstrip('0').rstrip('.')
                except:
                    amount_float = 0.0
                    amount_formatted = raw_amount

                token_name = TOKEN_NAME_MAP.get(token, token)

                # Determine buy/sell
                if destination in MONITORED_WALLETS:
                    action = "🟢 BUY"
                elif source in MONITORED_WALLETS:
                    action = "🔴 SELL"
                else:
                    action = "⚪ Transfer (Untracked Wallet)"

                # Price fetching
                token_price_sol = get_token_price(token)
                sol_usd_price = get_token_price(SOL_ADDRESS)

                print(f"📈 {token_name} price in SOL: {token_price_sol}")
                print(f"💵 SOL price in USD: {sol_usd_price}")
                sys.stdout.flush()

                if token_price_sol and sol_usd_price and amount_float:
                    est_value_sol = token_price_sol * amount_float
                    est_value_usd = est_value_sol * sol_usd_price
                    sol_formatted = f"{est_value_sol:,.4f}"
                    usd_formatted = f"{est_value_usd:,.2f}"
                    value_text = f"\nEst. Value: ~{sol_formatted} SOL (~${usd_formatted})"
                else:
                    value_text = "\nEst. Value: N/A"

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
