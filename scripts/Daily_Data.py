import requests
import time
import os
import random
import json

# -------------------------------
# Configuration & Constant
# -------------------------------

STRIKE_API_URL = "https://api-prod.strike.money/v1/api/marketdata/current-activity"

# !! IMPORTANT !!
# !! YOU MUST UPDATE THIS PLACEHOLDER !!
# Inspect the JSON response from STRIKE_API_URL.
# Find the key in the top-level dictionary that holds the list of stock data arrays.
# Examples: "data", "results", "items", "stockDataList", etc.
STRIKE_DATA_LIST_KEY = "data" # e.g., "data" or "results"

API_CALL_DELAY = 0.05 

INPUT_JSON_FILE = os.path.join("scripts", "Sector_Industry.json")
OUTPUT_JSON_FILE = os.path.join("static", "data", "stock_universe.json")

# Full list of field names from the Strike API, IN THE ORDER THEY APPEAR in each inner list.
# This is used for parsing the API response correctly.
STRIKE_API_FULL_FIELD_ORDER = [
    "open", "high", "low", "current_price", "day_open", "day_high", "day_low",
    "previous_close", "change_percentage", "day_volume", "volume", "datetime",
    "symbol", "security_code", "previous_date", "previous_day_open",
    "previous_day_high", "previous_day_low", "fifty_two_week_high", "fifty_two_week_low"
]

STRIKE_FIELDS_TO_APPEND = [
    "current_price", "day_open", "day_high", "day_low", "previous_close",
    "change_percentage", "day_volume", "fifty_two_week_high", "fifty_two_week_low"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/111.0.0.0 Safari/537.36"
]

try:
    SYMBOL_INDEX_IN_STRIKE_API = STRIKE_API_FULL_FIELD_ORDER.index("symbol")
except ValueError:
    print("CRITICAL ERROR: 'symbol' not found in STRIKE_API_FULL_FIELD_ORDER.")
    exit()

def fetch_json_data(url, context_message="", max_retries=3, delay_between_retries=1):
    for attempt in range(1, max_retries + 1):
        try:
            headers = {"Accept": "application/json", "User-Agent": random.choice(USER_AGENTS)}
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"⚠️ [{context_message}] Attempt {attempt} failed: {e}")
            if attempt < max_retries:
                time.sleep(delay_between_retries * attempt)
    print(f"❌ Giving up on {context_message} after {max_retries} attempts.")
    return None

def load_json_file(path):
    if not os.path.exists(path):
        print(f"❌ File not found: {path}")
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json_file(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

# -------------------------------
# START
# -------------------------------
print(f"🚀 Starting Daily_Data.py (Optimized version)")

# Load Sector_Industry and apply filter immediately
print("📄 Loading Sector_Industry.json and filtering...")
base_data = load_json_file(INPUT_JSON_FILE)
if base_data is None:
    exit()

filtered_base_data = [
    stock for stock in base_data
    if stock.get("SME Stock?", "No") != "Yes" and stock.get("Market Cap", 1) != 0
]
print(f"✅ Retained {len(filtered_base_data)} out of {len(base_data)} stocks after filtering.")

# Fetch Strike data
print("🌐 Fetching Strike API data...")
strike_response = fetch_json_data(STRIKE_API_URL, "Strike Bulk")
if not strike_response or STRIKE_DATA_LIST_KEY not in strike_response:
    print("❌ Invalid response from Strike API.")
    exit()

strike_raw_list = strike_response[STRIKE_DATA_LIST_KEY]
strike_data_map = {}
for row in strike_raw_list:
    if not isinstance(row, list) or len(row) != len(STRIKE_API_FULL_FIELD_ORDER):
        continue
    if row[STRIKE_API_FULL_FIELD_ORDER.index("day_volume")] == 0:
        continue  # skip dead stocks (mcap equivalent = 0)
    symbol = row[SYMBOL_INDEX_IN_STRIKE_API].upper()
    stock_data = {k: row[i] for i, k in enumerate(STRIKE_API_FULL_FIELD_ORDER)}
    strike_data_map[symbol] = stock_data

print(f"🔍 Processed {len(strike_data_map)} stocks from Strike.")

# Merge with base
final_data = []
match_count = 0
for stock in filtered_base_data:
    symbol = stock.get("Symbol", "").upper()
    if not symbol:
        continue
    strike_entry = strike_data_map.get(symbol)
    if not strike_entry:
        continue
    current_price = strike_entry.get("current_price", None)
    high_52w = strike_entry.get("fifty_two_week_high", None)
    low_52w = strike_entry.get("fifty_two_week_low", None)

    # Calculate percentage logic safely
    down_from_52wh = 0
    up_from_52wl = 0

    try:
        if isinstance(current_price, (int, float)) and isinstance(high_52w, (int, float)) and high_52w > 0:
            down_from_52wh = max(0, round((high_52w - current_price) / high_52w * 100, 2))
        if isinstance(current_price, (int, float)) and isinstance(low_52w, (int, float)) and low_52w > 0:
            up_from_52wl = round((current_price - low_52w) / low_52w * 100, 2)
    except:
        pass  # Avoid crashing on weird values
    new_data = {**stock}
    for field in STRIKE_FIELDS_TO_APPEND:
        new_data[field] = strike_entry.get(field, "N/A")

    new_data["Down from 52W High (%)"] = down_from_52wh
    new_data["Up from 52W Low (%)"] = up_from_52wl
    
    final_data.append(new_data)
    match_count += 1

# Save
save_json_file(final_data, OUTPUT_JSON_FILE)
print(f"✅ Done. {match_count} stocks saved to {OUTPUT_JSON_FILE}")