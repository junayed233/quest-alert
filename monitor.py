import json
import os
import requests
from playwright.sync_api import sync_playwright

PROJECTS = [
    {
        "name": "MineBit",
        "slug": "minebit",
        "url": "https://zealy.io/cw/minebit/questboard",
    },
    {
        "name": "Paydex",
        "slug": "paydex",
        "url": "https://zealy.io/cw/paydex/questboard",
    },
    {
        "name": "Inference",
        "slug": "inference",
        "url": "https://zealy.io/cw/inference/questboard",
    },
    {
        "name": "BlockBen",
        "slug": "blockben",
        "url": "https://zealy.io/cw/blockben/questboard",
    },
    {
        "name": "Quadcode AI Creators",
        "slug": "quadcodeaicreators",
        "url": "https://zealy.io/cw/quadcodeaicreators/questboard",
    },
    {
        "name": "TonMarket",
        "slug": "tonmarket",
        "url": "https://zealy.io/cw/tonmarket/questboard",
    },
    {
        "name": "TrueCurrent",
        "slug": "truecurrent",
        "url": "https://zealy.io/cw/truecurrent/questboard",
    },
    {
        "name": "Temple Digital Group",
        "slug": "templedigitalgroup",
        "url": "https://zealy.io/cw/templedigitalgroup/questboard",
    }
]

STATE_FILE = "seen_quests.json"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"known": {}, "active": {}}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {
                "known": data.get("known", {}),
                "active": data.get("active", {})
            }
    except Exception:
        pass
    return {"known": {}, "active": {}}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message,
            "disable_web_page_preview": False,
        },
        timeout=30,
    )
    response.raise_for_status()


def get_quests(project, browser):
    print(f"Checking {project['name']}...")
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    
    api_quests = []

    # Hidden API Interceptor: Zealy-r raw data theke shob task (locked/unlocked) catch korbe
    def handle_response(response):
        if "api.zealy.io" in response.url and response.status == 200:
            try:
                if response.request.method != "OPTIONS":
                    data = response.json()
                    if isinstance(data, list):
                        api_quests.extend(data)
                    elif isinstance(data, dict):
                        if "quests" in data:
                            api_quests.extend(data["quests"])
                        elif "data" in data and isinstance(data["data"], list):
                            api_quests.extend(data["data"])
            except Exception:
                pass

    page.on("response", handle_response)

    try:
        page.goto(project["url"], wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(5000)

        # Scroll deeply so all APIs are triggered
        for _ in range(12):
            page.mouse.wheel(0, 4000)
            page.wait_for_timeout(1500)

        results = []
        
        # 1. API Data processing (Ekhane shob pawa jabe)
        if api_quests:
            for q in api_quests:
                quest_id = q.get("id")
                name = q.get("name") or q.get("title")
                if quest_id and name:
                    href = f"https://zealy.io/cw/{project['slug']}/questboard/{quest_id}"
                    results.append({
                        "id": quest_id,
                        "name": name.strip(),
                        "url": href,
                        "project": project["name"]
                    })
        
        # 2. Fallback (Jodi kono karone API fail kore, tokhon normal UI scan korbe)
        if not results:
            selector = f'a[href*="/cw/{project["slug"]}/questboard/"]'
            links = page.locator(selector)
            for i in range(links.count()):
                link = links.nth(i)
                href = link.get_attribute("href")
                if not href or href.endswith("/sprints") or "/questboard/" not in href:
                    continue
                text = link.inner_text().strip()
                if not text:
                    continue
                if href.startswith("/"):
                    href = "https://zealy.io" + href
                quest_id = href.split("?")[0].rstrip("/")
                results.append({
                    "id": quest_id,
                    "name": " ".join(text.split()),
                    "url": href,
                    "project": project["name"]
                })

        # Remove duplicates
        unique = {}
        for quest in results:
            unique[quest["id"]] = quest

        quests = list(unique.values())
        print(f"{project['name']}: found {len(quests)} quests.")
        return quests

    except Exception as e:
        print(f"{project['name']}: ERROR - {e}")
        return None

    finally:
        page.close()


def main():
    state = load_state()
    known = state["known"]
    previous_active = state["active"]

    current_active = {}
    newly_found = []
    reactivated = []

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

                if quest_id not in known:
                    newly_found.append(quest)
                    known[quest_id] = {
                        "name": quest["name"],
                        "project": quest["project"]
                    }
                elif quest_id not in previous_active:
                    reactivated.append(quest)

        browser.close()

    print(f"\nNew quests: {len(newly_found)}")
    print(f"Reactivated quests: {len(reactivated)}")

    for quest in newly_found:
        message = (
            "🆕 NEW QUEST\n\n"
            f"📁 Project: {quest['project']}\n"
            f"📌 {quest['name']}\n\n"
            f"🔗 {quest['url']}"
        )
        print(message)
        send_telegram(message)

    for quest in reactivated:
        message = (
            "🔄 QUEST REACTIVATED\n\n"
            f"📁 Project: {quest['project']}\n"
            f"📌 {quest['name']}\n\n"
            f"🔗 {quest['url']}"
        )
        print(message)
        send_telegram(message)

    state["known"] = known
    state["active"] = current_active
    save_state(state)

    if not newly_found and not reactivated:
        print("No new or reactivated quests.")


if __name__ == "__main__":
    main()
