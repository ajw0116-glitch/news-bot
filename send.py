import os
import requests
import feedparser
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

KST = timezone(timedelta(hours=9))

# ========== 설정 (여기만 바꾸면 됩니다) ==========
HOURS = 24          # 최근 몇 시간 내 기사만 볼지
MAX_PER_FEED = 3    # 소스 하나당 최대 몇 건까지 가져올지

FEEDS = [
    # (표시 이름, RSS 주소)
    # --- 한국 ---
    ("연합뉴스 경제",   "https://www.yna.co.kr/rss/economy.xml"),
    ("한국경제 경제",   "https://www.hankyung.com/feed/economy"),
    ("한국경제 금융",   "https://www.hankyung.com/feed/finance"),
    ("매일경제 경제",   "https://www.mk.co.kr/rss/30100041/"),
    ("매일경제 증권",   "https://www.mk.co.kr/rss/50200011/"),
    ("금융위원회",      "http://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0111"),
    # --- 미국 ---
    ("Fed 통화정책",    "https://www.federalreserve.gov/feeds/press_monetary.xml"),
    ("Fed 보도자료",    "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("CNBC 경제",       "https://www.cnbc.com/id/20910258/device/rss/rss.html"),
    ("CNBC 금융시장",   "https://www.cnbc.com/id/10000664/device/rss/rss.html"),
    ("Yahoo Finance",  "https://finance.yahoo.com/news/rssindex"),
]
# ================================================

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"}


def get_published(entry):
    """기사 발행 시각을 꺼낸다. 없으면 None."""
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return None


def fetch_feed(name, url, cutoff):
    """RSS 하나를 읽어 최근 기사만 돌려준다. 실패해도 프로그램을 멈추지 않는다."""
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
        # 발행 시각이 없는 기사는 일단 포함시킨다 (버리면 손해)
        if published is not None and published < cutoff:
            continue

        items.append({
            "source": name,
            "title": (entry.get("title") or "").strip(),
            "link": (entry.get("link") or "").strip(),
            "summary": (entry.get("summary") or "").strip(),  # 4단계에서 사용
            "published": published,
        })

        if len(items) >= MAX_PER_FEED:
            break

    return items, "정상"


def send_telegram(text):
    """텔레그램은 한 번에 4096자까지만 받으므로 길면 나눠 보낸다."""
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
            "disable_web_page_preview": True,  # 링크 미리보기 끄기 (안 그러면 지저분함)
        }
        res = requests.get(url, params=payload)
        result = res.json()
        if not result.get("ok"):
            print("전송 실패:", result)
            raise SystemExit(1)


def main():
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(hours=HOURS)
    now_kst = now_utc.astimezone(KST).strftime("%Y-%m-%d %H:%M")

    all_items = []
    status_lines = []

    for name, url in FEEDS:
        items, status = fetch_feed(name, url, cutoff)
        all_items.extend(items)

        if status == "정상":
            mark = "✅" if items else "⚠️"
            status_lines.append(f"{mark} {name} — {len(items)}건")
        else:
            status_lines.append(f"❌ {name} — {status}")
        print(f"{name}: {status}, {len(items)}건")

    # ----- 메시지 만들기 -----
    lines = [f"📰 뉴스 수집 테스트 ({now_kst} KST)", ""]

    if all_items:
        current_source = None
        for item in all_items:
            if item["source"] != current_source:
                current_source = item["source"]
                lines.append(f"【{current_source}】")
            lines.append(f"· {item['title']}")
            lines.append(f"  {item['link']}")
        lines.append("")
    else:
        lines.append("가져온 기사가 없습니다.")
        lines.append("")

    lines.append("─── 소스 상태 ───")
    lines.extend(status_lines)
    lines.append(f"총 {len(all_items)}건 수집")

    send_telegram("\n".join(lines))
    print(f"전송 완료: {len(all_items)}건")


if __name__ == "__main__":
    main()
