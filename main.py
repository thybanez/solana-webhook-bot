import os
import json
import sys
import time
from flask import Flask, request
import requests

app = Flask(__name__)

# Env variables
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TARGET_TOKENS = os.environ.get("TARGET_TOKEN_ADDRESSES", "").split(",")
MONITORED_WALLETS = os.environ.get("MONITORED_WALLETS", "").split(",")
BIRDEYE_API_KEY = os.environ["BIRDEYE_API_KEY"]

# Token display name
TOKEN_NAME_MAP = {
    "5241BVJpTDscdFM5bTmeuchBcjXN5sasBywyF7onkJZP": "PUFF",
    "CnfshwmvDqLrB1jSLF7bLJ3iZF5u354WRFGPBmGz4uyf": "TEMA",
    "CsZFPqMei7DXBfXfxCydAPBN9y5wzrYmYcwBhLLRT3iU": "BLOCKY"
}

# Token decimals
TOKEN_DECIMALS = {
    "5241BVJpTDscdFM5bTmeuchBcjXN5sasBywyF7onkJZP": 6,
    "CnfshwmvDqLrB1jSLF7bLJ3iZF5u354WRFGPBmGz4uyf": 6,
    "CsZFPqMei7DXBfXfxCydAPBN9y5wzrYmYcwBhLLRT3iU": 9
}

# SOL price caching
cached_sol_price = None
last_sol_fetch_time = 0
SOL_TOKEN_ADDRESS = "So11111111111111111111111111111111111111112"
SOL_CACHE_DURATION = 300  # seconds (5 minutes)

def fetch_price_from_birdeye(token_address):
    url = f"https://public-api.birdeye.so/defi/price?address={token_address}"
    headers = {"X-API-KEY": BIRDEYE_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return float(response.json()["data"]["value"])
    except Exception as e:
        print(f"⚠️ Error fetching price for {token_address}: {e}")
        return None

def get_sol_usd_price():
    global cached_sol_price, last_sol_fetch_time
    now = time.time()
    if cached_sol_price and now - last_sol_fetch_time < SOL_CACHE_DURATION:
        return cached_sol_price
    else:
        price = fetch_price_from_birdeye(SOL_TOKEN_ADDRESS)
        if price:
            cached_sol_price = price
            last_sol_fetch_time = now
        return price

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    response = requests.post(url, json=payload)
    print(f"📬 Telegram: {response.status_code} {response.text}")

@app.route("/")
def index():
    return "✅ Bot is running."

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)

        print("🚨 Webhook Payload:")
        print(json.dumps(data, indent=2))
        sys.stdout.flush()

        for event in data.get("events", []):
            source = event.get("fromUserAccount")
            dest = event.get("toUserAccount")
            transfers = event.get("tokenTransfers", [])

            for t in transfers:
                token = t.get("tokenAddress")
                raw_amount = t.get("amount")

                if token not in TARGET_TOKENS:
                    continue

                # Token metadata
                token_name = TOKEN_NAME_MAP.get(token, token)
                decimals = TOKEN_DECIMALS.get(token, 0)

                # Show raw amount (e.g. 123456), but use decimals for calc
                try:
                    raw_int = int(raw_amount)
                    amount_float = raw_int / (10 ** decimals)
                    amount_display = f"{raw_int:,}"
                except:
                    amount_float = 0
                    amount_display = raw_amount

                # Determine type
                if dest in MONITORED_WALLETS:
                    action = "🟢 BUY"
                elif source in MONITORED_WALLETS:
                    action = "🔴 SELL"
                else:
                    action = "⚪ Transfer"

                # Get prices
                token_price_sol = fetch_price_from_birdeye(token)
                sol_usd_price = get_sol_usd_price()

                print(f"📈 {token_name} price (SOL): {token_price_sol}")
                print(f"💰 SOL price (USD): {sol_usd_price}")
                sys.stdout.flush()

                if token_price_sol and sol_usd_price:
                    value_sol = token_price_sol * amount_float
                    value_usd = value_sol * sol_usd_price
                    value_text = f"\nEst. Value: ~{value_sol:,.4f} SOL (~${value_usd:,.2f})"
                else:
                    value_text = "\nEst. Value: N/A"

                message = (
                    f"{action} DETECTED\n"
                    f"From: {source}\n"
                    f"To: {dest}\n"
                    f"Token: {token_name}\n"
                    f"Amount: {amount_display}{value_text}"
                )

                send_telegram_message(message)

    except Exception as e:
        err = f"⚠️ Error: {str(e)}"
        print(err)
        send_telegram_message(err)
        return err, 500

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
