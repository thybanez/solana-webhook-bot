import os
import json
import sys
import time
from flask import Flask, request
import requests

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TARGET_TOKENS = os.environ.get("TARGET_TOKEN_ADDRESSES", "").split(",")
MONITORED_WALLETS = os.environ.get("MONITORED_WALLETS", "").split(",")
BIRDEYE_API_KEY = os.environ["BIRDEYE_API_KEY"]

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

SOL_TOKEN_ADDRESS = "So11111111111111111111111111111111111111112"
SOL_CACHE_DURATION = 1800

cached_sol_price = None
last_sol_fetch_time = 0
token_price_cache = {}
api_call_count = 0

def get_sol_usd_price():
    global cached_sol_price, last_sol_fetch_time
    now = time.time()
    if cached_sol_price and (now - last_sol_fetch_time) < SOL_CACHE_DURATION:
        return cached_sol_price

    url = f"https://public-api.birdeye.so/defi/price?address={SOL_TOKEN_ADDRESS}"
    headers = {"X-API-KEY": BIRDEYE_API_KEY}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        price = float(response.json()["data"]["value"])
        cached_sol_price = price
        last_sol_fetch_time = now
        return price
    except Exception as e:
        print(f"⚠️ Error fetching SOL price: {e}")
        return None

def fetch_price_from_birdeye(token_address):
    global api_call_count

    if token_address in token_price_cache:
        return token_price_cache[token_address]

    url = f"https://public-api.birdeye.so/defi/price?address={token_address}"
    headers = {"X-API-KEY": BIRDEYE_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        price = float(response.json()["data"]["value"])
        token_price_cache[token_address] = price
        api_call_count += 1
        return price
    except Exception as e:
        print(f"⚠️ Error fetching price for {token_address}: {e}")
        return None

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload)

@app.route("/")
def index():
    return "✅ Bot is running."

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("🚨 Incoming Webhook Payload:")
        print(json.dumps(data, indent=2))
        sys.stdout.flush()

        transactions = data if isinstance(data, list) else [data]

        for tx in transactions:
            for transfer in tx.get("tokenTransfers", []):
                token = transfer.get("mint")
                source = transfer.get("fromUserAccount")
                dest = transfer.get("toUserAccount")
                raw_amount = transfer.get("tokenAmount")

                if token not in TARGET_TOKENS:
                    continue

                token_name = TOKEN_NAME_MAP.get(token, token)
                decimals = TOKEN_DECIMALS.get(token, 0)
                raw_int = int(float(raw_amount) * (10 ** decimals))
                amount_float = raw_int / (10 ** decimals)
                amount_display = f"{raw_int:,}"

                # Direction
                if dest in MONITORED_WALLETS:
                    action = "🟢 *BUY*"
                elif source in MONITORED_WALLETS:
                    action = "🔴 *SELL*"
                else:
                    action = "⚪ *Transfer*"

                token_price_sol = fetch_price_from_birdeye(token)
                sol_price_usd = get_sol_usd_price()

                if token_price_sol and sol_price_usd:
                    value_sol = token_price_sol * amount_float
                    value_usd = value_sol * sol_price_usd
                    value_text = f"\n*Est. Value:* ~{value_sol:,.4f} SOL (~\\${value_usd:,.2f})"
                else:
                    value_text = "\n*Est. Value:* N/A"

                message = (
                    f"{action}\n"
                    f"*From:* `{source}`\n"
                    f"*To:* `{dest}`\n"
                    f"*Token:* `{token_name}`\n"
                    f"*Amount:* `{amount_display}`{value_text}"
                )

                send_telegram_message(message)

    except Exception as e:
        error = f"⚠️ Error: {str(e)}"
        print(error)
        send_telegram_message(error)
        return error, 500

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
