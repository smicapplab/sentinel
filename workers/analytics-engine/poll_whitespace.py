import os
import sys
import time
import signal
import requests
from dotenv import load_dotenv

load_dotenv()

from src.whitespace_radar import run_whitespace_radar

POLL_INTERVAL_SECONDS = int(os.getenv("WHITESPACE_POLL_INTERVAL", "15"))
running = True

def handle_signal(sig, frame):
    global running
    print(f"\n[Sentinel Poller] Received signal {sig}. Initiating graceful shutdown...")
    running = False

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

def poll_and_process():
    birdseye_url = os.getenv("BIRDSEYE_URL", "http://localhost:5190")
    internal_secret = os.getenv("INTERNAL_API_SECRET")
    if not internal_secret:
        print("[Sentinel Poller] Error: INTERNAL_API_SECRET is unset. Cannot poll Birdseye.")
        return 0

    try:
        resp = requests.get(
            f"{birdseye_url}/api/internal/lgus?status=PENDING_COMPUTATION",
            headers={"x-internal-secret": internal_secret},
            timeout=10.0
        )
        if resp.status_code != 200:
            print(f"[Sentinel Poller] Birdseye returned status {resp.status_code}: {resp.text}")
            return 0

        data = resp.json()
        pending_lgus = data.get("data", [])
        if not pending_lgus:
            return 0

        print(f"[Sentinel Poller] Found {len(pending_lgus)} LGU(s) awaiting computation.")
        processed = 0

        for lgu in pending_lgus:
            lgu_code = lgu.get("lguCode")
            lgu_name = lgu.get("lguName")
            print(f"[Sentinel Poller] Computing Whitespace Radar for {lgu_name} ({lgu_code})...")
            try:
                run_whitespace_radar(company_id="comp-1", trigger_webhook=True, lgu_code=lgu_code)
                processed += 1
                print(f"[Sentinel Poller] Successfully scored and synchronized {lgu_name}.")
            except Exception as err:
                print(f"[Sentinel Poller] Error computing {lgu_name}: {err}")
                try:
                    fail_resp = requests.post(
                        f"{birdseye_url}/api/internal/lgus/{lgu_code}/fail",
                        json={"errorMessage": str(err)},
                        headers={"x-internal-secret": internal_secret},
                        timeout=5.0
                    )
                    if fail_resp.status_code != 200:
                        print(f"[Sentinel Poller] Failed to report failure for {lgu_name} to Birdseye. Status: {fail_resp.status_code}")
                except Exception as net_err:
                    print(f"[Sentinel Poller] Failed to reach Birdseye to report failure for {lgu_name}: {net_err}")

        return processed

    except requests.exceptions.ConnectionError:
        # Birdseye might be booting or temporarily offline in local dev
        return 0
    except Exception as e:
        print(f"[Sentinel Poller] Unexpected polling error: {e}")
        return 0

def main():
    print(f"[Sentinel Poller] Starting Whitespace Radar polling daemon (Interval: {POLL_INTERVAL_SECONDS}s)...")
    while running:
        poll_and_process()
        for _ in range(POLL_INTERVAL_SECONDS):
            if not running:
                break
            time.sleep(1)
    print("[Sentinel Poller] Daemon exited cleanly.")

if __name__ == "__main__":
    main()
