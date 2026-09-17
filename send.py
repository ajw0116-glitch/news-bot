import os
import json
import requests
import feedparser
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

KST = timezone(timedelta(hours=9))

# ========== 설정 (여기만 바꾸면 됩니다) ==========
MODEL = "gemini-2.0-flash"   # ← 작업 2에서 확인한 이름으로 바꾸세요
HOURS = 24                   # 최근 몇 시간 내 기사만 볼지
MAX_PER_FEED = 6             # 소스 하나당 최대 몇 건까지 가져올지
TARGET_COUNT = 10            # 최종 브리핑에 담을 뉴스 개수

FEEDS = [
    # --- 한국 ---
    ("연합뉴스 경제",   "https://www.yna.co.kr/rss/economy.xml"),
    ("한국경제 경제",   "https://www.hankyung.com/feed/economy"),
    ("한국경제 금융",   "https://www.hankyung.com/feed/finance"),
    ("매일경제 경제",   "https://www.mk.co.kr/rss/30100041/"),
    ("금융위원회",      "http://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0111"),
    # --- 미국 ---
    ("Fed 통화정책",    "https://www.federalreserve.gov/feeds/press_monetary.xml"),
    ("Fed 보도자료",    "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("CNBC 경제",       "https://www.cnbc.com/id/20910258/device/rss/rss.html"),
    ("CNBC 금융시장",   "https://www.cnbc.com/id/10000664/device/rss/rss.html"),
    ("Yahoo Finance",  "https://finance.yahoo.com/news/rssindex"),
]
# ↑ 3단계에서 ❌ 나온 줄은 지우거나 맨 앞에 # 을 붙이세요

PROMPT = """너는 한국 금융권 종사자를 위한 아침 마켓 브리핑 편집자다.
아래는 지난 24시간 동안 수집된 기사 목록이다.

[선별 기준]
- 금리/통화정책, 환율, 채권시장, 국내외 증시, 원자재 관련만 고른다.
- 연예, 스포츠, 생활, 지역행사, 기업 홍보성 보도는 제외한다.
- 같은 사건을 다룬 기사가 여러 개면 하나로 합치고, 가장 정보량이 많은 링크를 쓴다.
- "코스피 강보합 마감" 같은 단순 시황 반복 기사는 실질적 변화가 있을 때만 남긴다.
- 총 {target}건 내외로 추린다.

[작성 규칙]
- 각 뉴스는 1~2문장 한국어 요약. 기사 제목을 그대로 베끼지 말고 핵심을 쓴다.
- 숫자(금리 수준, 환율, 등락률, 발행 규모)가 있으면 반드시 살린다.
- 추측이나 전망을 지어내지 말고, 기사에 있는 내용만 쓴다.
- 카테고리 순서: 금리/통화정책 → 환율 → 채권 → 증시 → 원자재 → 기타
- 해당 뉴스가 없는 카테고리는 통째로 생략한다.

[출력 형식]
마크다운 기호(*, #, - 등)를 쓰지 말고 아래 형식 그대로 출력한다.
설명이나 머리말 없이 본문만 출력한다.

[금리/통화정책]
· 요약 문장.
  링크

[환율]
· 요약 문장.
  링크

--- 기사 목록 ---
{articles}
"""
# ================================================

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"}


def get_published(entry):
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return None


def fetch_feed(name, url, cutoff):
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        parsed = feedparser.parse(res.content)
    except Exception as e:
        return [], f"접속 실패 ({type(e).__name__})"

    if not parsed.entries:
        return [], "기사 없음"

    items = []
    for entry in parsed.entries:
        published = get_published(entry)
        if published is not None and published < cutoff:
            continue

        summary = (entry.get("summary") or "").strip()
        summary = summary.replace("\n", " ")[:200]   # 너무 길면 자른다

        items.append({
            "source": name,
            "title": (entry.get("title") or "").strip(),
            "link": (entry.get("link") or "").strip(),
            "summary": summary,
        })

        if len(items) >= MAX_PER_FEED:
            break

    return items, "정상"


def build_article_text(items):
    """AI에게 넘길 기사 목록을 한 덩어리 글로 만든다."""
    lines = []
    for i, item in enumerate(items, 1):
        lines.append(f"{i}. [{item['source']}] {item['title']}")
        if item["summary"]:
            lines.append(f"   내용: {item['summary']}")
        lines.append(f"   링크: {item['link']}")
    return "\n".join(lines)


def summarize(items):
    """Gemini에게 요약을 시킨다. 실패하면 None을 돌려준다."""
    prompt = PROMPT.format(target=TARGET_COUNT, articles=build_article_text(items))

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json",
    }
    body = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        res = requests.post(url, headers=headers, json=body, timeout=90)
        if res.status_code != 200:
            print("AI 응답 오류:", res.status_code, res.text[:500])
            return None
        data = res.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print("AI 호출 실패:", type(e).__name__, e)
        return None


def fallback_text(items):
    """AI가 실패했을 때 쓸 비상용 원본 목록."""
    lines = ["(AI 요약 실패 — 원본 목록을 보냅니다)", ""]
    current = None
    for item in items:
        if item["source"] != current:
            current = item["source"]
            lines.append(f"[{current}]")
        lines.append(f"· {item['title']}")
        lines.append(f"  {item['link']}")
    return "\n".join(lines)


def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    LIMIT = 3500

    chunks = []
    while len(text) > LIMIT:
        cut = text.rfind("\n", 0, LIMIT)
        if cut == -1:
            cut = LIMIT
        chunks.append(text[:cut])
        text = text[cut:]
    chunks.append(text)

    for chunk in chunks:
        payload = {
            "chat_id": CHAT_ID,
            "text": chunk,
            "disable_web_page_preview": True,
        }
        res = requests.get(url, params=payload)
        if not res.json().get("ok"):
            print("전송 실패:", res.json())
            raise SystemExit(1)


def main():
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(hours=HOURS)
    now_kst = now_utc.astimezone(KST).strftime("%Y-%m-%d (%a) %H:%M")

    all_items = []
    dead_feeds = []

    for name, url in FEEDS:
        items, status = fetch_feed(name, url, cutoff)
        all_items.extend(items)
        if status not in ("정상", "기사 없음"):
            dead_feeds.append(name)
        print(f"{name}: {status}, {len(items)}건")

    header = f"📈 모닝 브리핑 · {now_kst} KST"

    if not all_items:
        send_telegram(f"{header}\n\n수집된 기사가 없습니다. 소스를 점검하세요.")
        return

    body = summarize(all_items)
    if body is None:
        body = fallback_text(all_items)

    footer = f"\n\n───\n수집 {len(all_items)}건 → 선별 완료"
    if dead_feeds:
        footer += f"\n⚠️ 응답 없는 소스: {', '.join(dead_feeds)}"

    send_telegram(f"{header}\n\n{body}{footer}")
    print("전송 완료")


if __name__ == "__main__":
    main()
