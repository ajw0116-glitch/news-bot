# ============================================================
#  설정 파일 — 앞으로 바꿀 일이 있으면 이 파일만 열면 됩니다.
#  send.py 는 건드리지 않아도 됩니다.
# ============================================================

# ----- 1. AI 모델 -----
MODEL = "gemini-2.0-flash"   # 쓸 수 있는 이름 확인: 아래 '모델 확인' 참고
TEMPERATURE = 0.3            # 0에 가까울수록 일관되게, 1에 가까울수록 자유롭게


# ----- 2. 수집 범위 -----
HOURS = 24          # 최근 몇 시간 내 기사만 볼지
MAX_PER_FEED = 6    # 소스 하나당 최대 몇 건까지 가져올지
TARGET_COUNT = 10   # 최종 브리핑에 담을 뉴스 개수


# ----- 3. 뉴스 소스 -----
# 형식: ("표시 이름", "RSS 주소"),
# 빼고 싶으면 줄 맨 앞에 # 을 붙이세요. 나중에 되살리기 쉽습니다.
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


# ----- 4. 관심 분야 -----
# 브리핑에 들어갈 카테고리. 순서대로 출력됩니다.
# 해당 뉴스가 없는 카테고리는 자동으로 생략됩니다.
CATEGORIES = [
    "금리/통화정책",
    "환율",
    "채권",
    "증시",
    "원자재",
]

# 무조건 버릴 것. 실제로 걸러지지 않는 유형이 보이면 여기에 한 줄 추가하세요.
EXCLUDE = [
    "연예, 스포츠, 생활, 지역행사, 인사발령",
    "기업 홍보성 보도, 신제품 출시, 수상 소식",
    "숫자나 새로운 사실이 없는 단순 시황 기사",
]

# 자리가 부족할 때 위쪽부터 남깁니다.
PRIORITY = [
    "중앙은행·정부의 공식 발표 (기준금리, 통화정책방향, FOMC, 재정정책)",
    "주요 지표 발표 (물가, 고용, GDP, 무역수지)",
    "금리·환율·유가의 뚜렷한 방향 전환",
    "채권 발행·수급, 기관 자금 흐름",
    "개별 기업·섹터 이슈",
]


# ----- 5. 브리핑 제목 -----
TITLE = "📈 모닝 브리핑"
