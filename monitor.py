import json
import os
import requests

PROJECTS = [
    {"name": "TonMarket", "slug": "tonmarket"},
    {"name": "Quadcode AI", "slug": "quadcodeaicreators"},
    {"name": "TrueCurrent", "slug": "truecurrent"},
    {"name": "Paydex", "slug": "paydex"},
    {"name": "BlockBen", "slug": "blockben"},
    {"name": "Temple Digital", "slug": "templedigitalgroup"},
    {"name": "MineBit", "slug": "minebit"},
    {"name": "Inference", "slug": "inference"},
    {"name": "Binance", "slug": "binance"}
]

STATE_FILE = "seen_quests.json"
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Origin": "https://zealy.io",
    "Referer": "https://zealy.io/"
}

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

def get_quests(project):
    print(f"Checking {project['name']}...")
    url = f"https://api.zealy.io/communities/{project['slug']}/quests"
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        if response.status_code != 200:
            print(f"API Error {response.status_code} for {project['name']}")
            return None
        
        quests_data = response.json()
        results = []
        
        quest_list = []
        if isinstance(quests_data, list):
            quest_list = quests_data
        elif isinstance(quests_data, dict) and "quests" in quests_data:
            quest_list = quests_data["quests"]
            
        for q in quest_list:
            if isinstance(q, dict):
                q_id = q.get("id")
                name = q.get("name") or q.get("title")
                if q_id and name:
                    results.append({
                        "id": q_id,
                        "name": name.strip(),
                        "url": f"https://zealy.io/cw/{project['slug']}/questboard/{q_id}",
                        "project": project["name"]
                    })
        
        print(f"{project['name']}: Found {len(results)} quests.")
        return results
    except Exception as e:
        print(f"Error for {project['name']}: {e}")
        return None

def main():
    previous_active = load_state()
    current_active = {}
    new_notifications = []

    for project in PROJECTS:
        quests = get_quests(project)
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

    print(f"\nSending {len(new_notifications)} notifications...")

    for quest in new_notifications:
        message = (
            f"🔔 TASK ALERT (New/Re-uploaded)\n\n"
            f"📁 Project: {quest['project']}\n"
            f"📌 {quest['name']}\n\n"
            f"🔗 {quest['url']}"
        )
        print(message)
        send_telegram(message)

    save_state(current_active)

if __name__ == "__main__":
    main()
