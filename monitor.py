import json
import os
import requests
from playwright.sync_api import sync_playwright

PROJECTS = [
    {"name": "TonMarket", "slug": "tonmarket", "url": "https://zealy.io/cw/tonmarket/questboard"},
    {"name": "Quadcode AI", "slug": "quadcodeaicreators", "url": "https://zealy.io/cw/quadcodeaicreators/questboard"},
    {"name": "TrueCurrent", "slug": "truecurrent", "url": "https://zealy.io/cw/truecurrent/questboard"},
    {"name": "Paydex", "slug": "paydex", "url": "https://zealy.io/cw/paydex/questboard"},
    {"name": "BlockBen", "slug": "blockben", "url": "https://zealy.io/cw/blockben/questboard"},
    {"name": "Temple Digital", "slug": "templedigitalgroup", "url": "https://zealy.io/cw/templedigitalgroup/questboard"},
    {"name": "MineBit", "slug": "minebit", "url": "https://zealy.io/cw/minebit/questboard"},
    {"name": "Inference", "slug": "inference", "url": "https://zealy.io/cw/inference/questboard"},
    {"name": "Binance", "slug": "binance", "url": "https://zealy.io/cw/binance/questboard"}
]

STATE_FILE = "seen_quests.json"
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "active" in data:
            return data["active"]
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(
            url,
            data={"chat_id": CHAT_ID, "text": message, "disable_web_page_preview": True},
            timeout=30
        )
    except Exception as e:
        print(f"Telegram Error: {e}")

def get_quests(project, browser):
    print(f"Checking {project['name']}...")
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    
    api_quests = {}

    def handle_response(response):
        if "api.zealy.io" in response.url and response.status == 200:
            try:
                if response.request.method != "OPTIONS":
                    data = response.json()
                    quest_list = []
                    if isinstance(data, list):
                        quest_list = data
                    elif isinstance(data, dict):
                        if "quests" in data:
                            quest_list = data["quests"]
                        elif "data" in data and isinstance(data["data"], list):
                            quest_list = data["data"]
                    
                    for q in quest_list:
                        if isinstance(q, dict) and "id" in q and ("name" in q or "title" in q):
                            api_quests[q["id"]] = q
            except Exception:
                pass

    page.on("response", handle_response)
    
    try:
        page.goto(project["url"], wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(5000)

        for _ in range(8):
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(1500)

        results = []
        if api_quests:
            for q_id, q_data in api_quests.items():
                name = q_data.get("name") or q_data.get("title")
                results.append({
                    "id": q_id,
                    "name": name.strip(),
                    "url": f"https://zealy.io/cw/{project['slug']}/questboard/{q_id}",
                    "project": project["name"]
                })
        
        unique = {q["id"]: q for q in results}
        final_quests = list(unique.values())
        
        print(f"{project['name']}: found {len(final_quests)} tasks.")
        return final_quests

    except Exception as e:
        print(f"Error fetching {project['name']}: {e}")
        return None
    finally:
        page.close()

def main():
    previous_active = load_state()
    current_active = {}
    new_notifications = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for project in PROJECTS:
            quests = get_quests(project, browser)
            
            if quests is None:
                continue

            for quest in quests:
                quest_id = quest["id"]
                current_active[quest_id] = {
                    "name": quest["name"],
                    "project": quest["project"],
                    "url": quest["url"]
                }

                if quest_id not in previous_active:
                    new_notifications.append(quest)

        browser.close()

    print(f"\nSending {len(new_notifications)} notifications...")

    for quest in new_notifications:
        message = (
            f"🔔 TASK ALERT (New/Re-uploaded)\n\n"
            f"📁 Project: {quest['project']}\n"
            f"📌 {quest['name']}\n\n"
            f"🔗 {quest['url']}\n"
            f"⚠️ (Check if it's locked or unlocked)"
        )
        print(message)
        send_telegram(message)

    save_state(current_active)

if __name__ == "__main__":
    main()
