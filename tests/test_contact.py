import os
import json
import requests

# ——— Configuration ———
USER_ID = "123"
CLIENT_ID = "12"
SESSION_ID = "123"

API_URL = "http://localhost:8000/extract_contact"

# ——— Helpers ———
def load_transcript(path: str):
    msgs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or ":" not in line:
                continue
            speaker, text = line.split(":", 1)
            msgs.append({"speaker": speaker.strip(), "text": text.strip()})
    return msgs

def main():
    transcript_file = "detailed_transcript.txt"
    messages = load_transcript(transcript_file)
    if not messages:
        print(f"No valid lines found in {transcript_file}.")
        return

    payload = {"messages": messages}
    params = {
        "userId": USER_ID,
        "clientId": CLIENT_ID,
        "sessionId": SESSION_ID
    }

    try:
        resp = requests.post(API_URL, params=params, json=payload, timeout=30)
    except requests.RequestException as e:
        print("Request failed:", e)
        return

    print(f"\nRequest URL: {resp.request.url}")
    print(f"Status Code: {resp.status_code}\n")

    # Try to parse JSON; fallback to raw text
    try:
        data = resp.json()
        print("Response JSON:")
        print(json.dumps(data, indent=2))
    except json.JSONDecodeError:
        print("Non-JSON response:")
        print(resp.text)

if __name__ == "__main__":
    main()
