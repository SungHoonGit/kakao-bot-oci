# Kakao Bot — 채용공고 알림 챗봇

KakaoTalk API를 활용한 채용공고 검색 및 알림 봇입니다.

## 구조
```
kakao-bot/
├── config.json          # Kakao API 키 (git ignored)
├── kakao_api.py         # Kakao REST API 래퍼
├── bot_server.py        # Flask 웹훅 서버
├── scripts/
│   ├── get_token.py     # OAuth 토큰 발급
│   └── send_test.py     # 메시지 전송 테스트
└── requirements.txt
```

## 사용법

### 1. 설정
```bash
pip install -r requirements.txt
cp config.example.json config.json  # config.json 수정
```

### 2. 토큰 발급
```bash
python scripts/get_token.py
```

### 3. 메시지 전송
```bash
python scripts/send_test.py
```

### 4. 웹훅 서버 (챗봇)
```bash
source .venv/bin/activate
python bot_server.py 5001
cloudflared tunnel --url http://localhost:5001
```

## 의존성
- Python 3.10+
- Flask 3.x
- requests
- beautifulsoup4 + lxml

## 관련 프로젝트
- [job-scraper](https://github.com/SungHoonGit/job-scraper) — 채용공고 수집 모듈
