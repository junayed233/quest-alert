import json
import os
import requests
from playwright.sync_api import sync_playwright

MINEBIT_URL = "https://zealy.io/cw/minebit/questboard/sprints"
STATE_FILE = "seen_quests.json"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def load_seen():
    if not os.path.exists(STATE_FILE):
        return set()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(quests):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(quests), f, indent=2)


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


def get_quests():
    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1000
            }
        )

        page.goto(
            MINEBIT_URL,
            wait_until="networkidle",
            timeout=120000
        )

        # Give Zealy's frontend extra time to render.
        page.wait_for_timeout(5000)

        links = page.locator(
            'a[href*="/cw/minebit/questboard/"]'
        )

        results = []

        for i in range(links.count()):

            link = links.nth(i)

            href = link.get_attribute("href")
            text = link.inner_text().strip()

            if not href:
                continue

            # Ignore the general questboard/sprints navigation link.
            if href.endswith("/questboard/sprints"):
                continue

            # Only keep actual quest-like links.
            if "/questboard/" not in href:
                continue

            if not text:
                continue

            if href.startswith("/"):
                href = "https://zealy.io" + href

            results.append({
                "id": href,
                "name": " ".join(text.split()),
                "url": href
            })

        browser.close()

        # Remove duplicates
        unique = {}

        for quest in results:
            unique[quest["id"]] = quest

        return list(unique.values())


def main():

    seen = load_seen()
    send_telegram("✅ MineBit monitor is working!")
    quests = get_quests()

    print(f"Found {len(quests)} quests.")

    if not quests:
        print("No quests detected.")
        return

    current_ids = set(q["id"] for q in quests)

    # First run:
    # Don't spam you with every existing quest.
    if not seen:

        save_seen(current_ids)

        print(
            f"First run: saved {len(current_ids)} existing quests."
        )

        return

    new_quests = [
        q for q in quests
        if q["id"] not in seen
    ]

    if new_quests:

        for quest in new_quests:

            message = (
                "🔔 NEW MINEBIT QUEST\n\n"
                f"📌 {quest['name']}\n\n"
                f"🔗 {quest['url']}"
            )

            print(message)

            send_telegram(message)

    else:

        print("No new quests.")

    # Keep the current list.
    save_seen(current_ids)


if __name__ == "__main__":
    main()
