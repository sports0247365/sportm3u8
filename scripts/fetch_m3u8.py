import os
import json
import re
import time
import firebase_admin
from firebase_admin import credentials, db
from selenium import webdriver
from selenium.common.exceptions import WebDriverException

# ============ CONFIG ============
# Kaunsi database(s) mein push karna hai - workflow file mein set hota
# hai (default: sab teen). Interactive input() ki zarurat nahi ab.
TARGET_DBS = os.environ.get("TARGET_DBS", "1,2,3")
use_db1 = "1" in TARGET_DBS
use_db2 = "2" in TARGET_DBS
use_db3 = "3" in TARGET_DBS

user_agent = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)

# List of target URLs
target_urls = [
    "https://w4.sportsonlline.click/channels/hd/hd1.php"
]

# Custom node locations for each database (index -> node name)
node_locations_app1 = [0]
node_locations_app2 = [0]
node_locations_app3 = [0]
# =================================


def init_firebase():
    """
    Firebase credentials GitHub Secrets (environment variables) se load
    karta hai - local JSON file path ki jagah, taake keys kabhi repo
    mein commit na hon.
    """
    if use_db1:
        cred1_json = os.environ.get("FIREBASE_CRED_1")
        if not cred1_json:
            raise RuntimeError("FIREBASE_CRED_1 secret set nahi hai")
        cred1 = credentials.Certificate(json.loads(cred1_json))
        firebase_admin.initialize_app(
            cred1,
            {"databaseURL": "https://malik-rizvi-default-rtdb.firebaseio.com/"},
            name="app1",
        )

    if use_db2:
        cred2_json = os.environ.get("FIREBASE_CRED_2")
        if not cred2_json:
            raise RuntimeError("FIREBASE_CRED_2 secret set nahi hai")
        cred2 = credentials.Certificate(json.loads(cred2_json))
        firebase_admin.initialize_app(
            cred2,
            {"databaseURL": "https://livefootballtvstreaminghd.firebaseio.com/"},
            name="app2",
        )

    if use_db3:
        cred3_json = os.environ.get("FIREBASE_CRED_3")
        if not cred3_json:
            raise RuntimeError("FIREBASE_CRED_3 secret set nahi hai")
        cred3 = credentials.Certificate(json.loads(cred3_json))
        firebase_admin.initialize_app(
            cred3,
            {"databaseURL": "https://ticktockfootball.firebaseio.com/"},
            name="app3",
        )


def build_chrome_options():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")  # GitHub Actions ke liye zaroori
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--ignore-ssl-errors")
    options.add_argument("--allow-insecure-localhost")
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-site-isolation-trials")
    options.add_argument(f"user-agent={user_agent}")
    options.set_capability("goog:loggingPrefs", {"performance": "SEVERE"})
    options.add_argument("--blink-settings=imagesEnabled=false")
    return options


def fetch_m3u8_link(target_url):
    options = build_chrome_options()
    # Selenium Manager (Selenium >=4.6) khud sahi chromedriver dhoond ke
    # download kar leta hai - explicit path dena zaroori nahi.
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(target_url)
        m3u8_pattern = re.compile(r"https?://.*\.m3u8.*")
        time.sleep(30)
        logs = driver.get_log("performance")

        for log in logs:
            try:
                message = json.loads(log["message"]).get("message", {})
                if message.get("method") == "Network.responseReceived":
                    url = message["params"]["response"].get("url", "")
                    if m3u8_pattern.search(url):
                        print(f"M3U8 Link Found: {url}")
                        return url
            except Exception:
                continue

        print("No M3U8 link found.")
        return None
    finally:
        driver.quit()


def push_m3u8_link_to_firebase(link, channel_app1, channel_app2, channel_app3):
    if use_db1:
        ref1 = db.reference(
            f"/Channels/{channel_app1}/Url", app=firebase_admin.get_app("app1")
        )
        ref1.set(link)
        print(f"Saved link to first Firebase at /Channels/{channel_app1}/Url")

    if use_db2:
        ref2 = db.reference(
            f"/Channels/{channel_app2}/Url", app=firebase_admin.get_app("app2")
        )
        ref2.set(link)
        print(f"Saved link to second Firebase at /Channels/{channel_app2}/Url")

    if use_db3:
        ref3 = db.reference(
            f"/Channels/{channel_app3}/Url", app=firebase_admin.get_app("app3")
        )
        ref3.set(link)
        print(f"Saved link to third Firebase at /Channels/{channel_app3}/Url")


def main():
    init_firebase()

    # NOTE: purane script mein "while True" + "time.sleep(300)" tha jo
    # har 5 min khud loop karta rehta tha. Ab GitHub Actions cron khud
    # har 10 minute mein ek naya run start karega, isliye script ek
    # dafa (sab target_urls ke liye) chal ke exit ho jata hai.
    for i, target_url in enumerate(target_urls):
        try:
            m3u8_link = fetch_m3u8_link(target_url)
        except WebDriverException as e:
            print(f"WebDriver error for {target_url}: {e}")
            continue

        if m3u8_link:
            custom_node_app1 = (
                node_locations_app1[i] if i < len(node_locations_app1) else i
            )
            custom_node_app2 = (
                node_locations_app2[i] if i < len(node_locations_app2) else i
            )
            custom_node_app3 = (
                node_locations_app3[i] if i < len(node_locations_app3) else i
            )
            push_m3u8_link_to_firebase(
                m3u8_link, custom_node_app1, custom_node_app2, custom_node_app3
            )
        else:
            print(f"No link to save for target URL index {i}.")


if __name__ == "__main__":
    main()
