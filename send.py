import os
import requests
from datetime import datetime, timezone, timedelta

# 금고(Secrets)에서 값을 꺼내옵니다. 코드에는 실제 값이 없습니다.
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

# 실행된 시각을 한국시간으로 계산 (서버는 세계표준시로 돌아갑니다)
KST = timezone(timedelta(hours=9))
now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")

message = f"자동 실행 테스트\n실행 시각: {now} (KST)"

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
payload = {
    "chat_id": CHAT_ID,
    "text": message
}

response = requests.get(url, params=payload)
result = response.json()

if result.get("ok"):
    print("전송 성공")
else:
    print("전송 실패")
    print(result)
    raise SystemExit(1)   # 실패하면 GitHub 화면에 빨간 X로 표시됩니다
