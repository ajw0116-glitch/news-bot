import os
import requests
import feedparser
from datetime import datetime, timezone, timedelta

import config   # ← 설정은 전부 config.py 에서 가져옵니다

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

KST = timezone(timedelta(hours=9))
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"}


def build_prompt(article_text):
    """config.py 의 설정을 읽어 프롬프트를 조립한다."""
    exclude = "\n".join(f"- {x}" for x in config.EXCLUDE)
    priority = "\n".join(f"{i}) {x}" for i, x in enumerate(config.PRIORITY, 1))
    topics = ", ".join(config.CATEGORIES)
    form = "\n\n".join(f"[{c}]\n· 요약 문장.\n  링크" for c in config.CATEGORIES)

    return f"""너는 한국 금융권 종사자를 위한 아침 마켓 브리핑 편집자다.
아래 [기사 목록]만을 근거로 브리핑을 작성한다.

[1. 관심 분야]
{topics}
이와 무관한 기사는 모두 버린다.

[2. 제외 대상]
{exclude}
단, 변동폭이 크거나 원인이 설명된 시황은 남긴다.

[3. 중복 처리]
같은 사건을 다룬 기사는 반드시 하나로 합친다.
- 발표 주체·수치·정책명이 동일하면 같은 사건이다.
- 합칠 때는 가장 구체적인 기사 하나의 링크만 쓴다.
- 국내 기사와 해외 기사가 같은 사건을 다루면 하나로 합친다.
- 의심스러우면 합쳐라. 중복을 남기는 것보다 합치는 쪽이 낫다.

[4. 우선순위]
자리가 부족하면 위쪽을 먼저 남긴다.
{priority}

[5. 작성 규칙]
- 총 {config.TARGET_COUNT}건 내외. 한국 관련과 해외 관련이 한쪽으로 쏠리지 않게 한다.
- 각 뉴스는 한국어 1~2문장, 한 문장 60자 내외로 짧게.
- 기사 제목을 그대로 옮기지 말고 핵심을 다시 쓴다.
- 숫자(금리 수준, 환율, 등락률, 규모, 기간)가 기사에 있으면 반드시 포함한다.
- [기사 목록]에 없는 내용은 절대 쓰지 않는다. 전망·해석·배경설명을 지어내지 않는다.
- 링크는 해당 기사에 적힌 주소를 글자 하나 바꾸지 말고 그대로 쓴다.
  요약한 기사와 다른 링크를 붙이는 것은 치명적 오류다.

[6. 출력 형식]
아래 형식만 출력한다. 머리말, 맺음말, 설명, 총평을 붙이지 않는다.
별표(*), 샵(#), 하이픈(-) 등 마크다운 기호를 쓰지 않는다.
해당 뉴스가 없는 카테고리는 카테고리명까지 통째로 생략한다.
카테고리 순서는 아래 그대로 유지한다.

{form}

--- 기사 목록 ---
{article_text}
"""


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

        summary = (entry.get("summary") or "").strip().replace("\n", " ")[:200]
        items.append({
            "source": name,
            "title": (entry.get("title") or "").strip(),
            "link": (entry.get("link") or "").strip(),
            "summary": summary,
        })

        if len(items) >= config.MAX_PER_FEED:
            break

    return items, "정상"


def build_article_text(items):
    lines = []
    for i, item in enumerate(items, 1):
        lines.append(f"{i}. [{item['source']}] {item['title']}")
        if item["summary"]:
            lines.append(f"   내용: {item['summary']}")
        lines.append(f"   링크: {item['link']}")
    return "\n".join(lines)


def summarize(items):
    prompt = build_prompt(build_article_text(items))

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.MODEL}:generateContent"
    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json",
    }
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": config.TEMPERATURE},
    }

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
    cutoff = now_utc - timedelta(hours=config.HOURS)
    now_kst = now_utc.astimezone(KST).strftime("%Y-%m-%d (%a) %H:%M")

    all_items = []
    dead_feeds = []

    for name, url in config.FEEDS:
        items, status = fetch_feed(name, url, cutoff)
        all_items.extend(items)
        if status not in ("정상", "기사 없음"):
            dead_feeds.append(name)
        print(f"{name}: {status}, {len(items)}건")

    header = f"{config.TITLE} · {now_kst} KST"

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
