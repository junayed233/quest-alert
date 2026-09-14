import json
import os
import requests
from playwright.sync_api import sync_playwright

PROJECTS = [
    {
        "name": "MineBit",
        "slug": "minebit",
        "url": "https://zealy.io/cw/minebit/questboard/sprints",
    },
    {
        "name": "Paydex",
        "slug": "paydex",
        "url": "https://zealy.io/cw/paydex/questboard",
    },
    {
        "name": "Inference",
        "slug": "inference",
        "url": "https://zealy.io/cw/inference/questboard/sprints",
    },
    {
        "name": "SouDian",
        "slug": "soudian",
        "url": "https://zealy.io/cw/soudian/questboard/sprints",
    },
    {
        "name": "BlockBen",
        "slug": "blockben",
        "url": "https://zealy.io/cw/blockben/questboard/sprints",
    },
]

STATE_FILE = "seen_quests.json"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def load_state():
    if not os.path.exists(STATE_FILE):
        return {
            "known": {},
            "active": {}
        }

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # New format
        if isinstance(data, dict):
            return {
                "known": data.get("known", {}),
                "active": data.get("active", {})
            }

        # Migrate old MineBit format
        if isinstance(data, list):
            known = {}

            for quest_id in data:
                known[quest_id] = {
                    "name": "Previously detected quest",
                    "project": "MineBit"
                }

            return {
                "known": known,
                "active": {
                    quest_id: {
                        "name": "Previously detected quest",
                        "project": "MineBit"
                    }
                    for quest_id in data
                }
            }

    except Exception:
        pass

    return {
        "known": {},
        "active": {}
    }


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

    page = browser.new_page(
        viewport={
            "width": 1440,
            "height": 1000
        }
    )

    try:
        page.goto(
            project["url"],
            wait_until="domcontentloaded",
            timeout=120000
        )

        page.wait_for_timeout(6000)

        # Scroll several times so lazy-loaded quests can appear.
        for _ in range(5):
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(1500)

        selector = f'a[href*="/cw/{project["slug"]}/questboard/"]'

        links = page.locator(selector)

        results = []

        for i in range(links.count()):

            link = links.nth(i)

            href = link.get_attribute("href")

            if not href:
                continue

            if href.endswith("/questboard/sprints"):
                continue

            if "/questboard/" not in href:
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

        print(
            f"{project['name']}: found {len(quests)} quests."
        )

        return quests

    except Exception as e:
        print(
            f"{project['name']}: ERROR - {e}"
        )
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

        browser = p.chromium.launch(
            headless=True
        )

        for project in PROJECTS:

            quests = get_quests(project, browser)

            # If scraping failed, don't change this project's
            # previous active state.
            if quests is None:
                continue

            for quest in quests:

                quest_id = quest["id"]

                current_active[quest_id] = {
                    "name": quest["name"],
                    "project": quest["project"],
                    "url": quest["url"]
                }

                # Completely new quest
                if quest_id not in known:

                    newly_found.append(quest)

                    known[quest_id] = {
                        "name": quest["name"],
                        "project": quest["project"]
                    }

                # Previously known but was not active
                elif quest_id not in previous_active:

                    reactivated.append(quest)

        browser.close()

    print()
    print(f"New quests: {len(newly_found)}")
    print(f"Reactivated quests: {len(reactivated)}")

    # Send NEW quest notifications
    for quest in newly_found:

        message = (
            "🆕 NEW QUEST\n\n"
            f"📁 Project: {quest['project']}\n"
            f"📌 {quest['name']}\n\n"
            f"🔗 {quest['url']}"
        )

        print(message)
        send_telegram(message)

    # Send REACTIVATED quest notifications
    for quest in reactivated:

        message = (
            "🔄 QUEST REACTIVATED\n\n"
            f"📁 Project: {quest['project']}\n"
            f"📌 {quest['name']}\n\n"
            f"🔗 {quest['url']}"
        )

        print(message)
        send_telegram(message)

    # Save current active quests
    state["known"] = known
    state["active"] = current_active

    save_state(state)

    if not newly_found and not reactivated:
        print("No new or reactivated quests.")


if __name__ == "__main__":
    main()
