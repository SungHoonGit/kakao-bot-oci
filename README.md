# Kakao Bot — OCI 배포 버전

Kakao i 오픈빌더 스킬 웹훅 기반 채용공고 검색 챗봇.
JobKorea, 사람인, 원티드를 동시에 검색하여 listCard로 응답합니다.

**Oracle Cloud Free Tier VM**에 배포하는 것을 전제로 합니다.

## 구조

```
kakao-bot-oci/
├── config.json                # Kakao REST API 키 (직접 입력)
├── kakao_api.py               # Kakao REST API 래퍼 (OAuth 전송용)
├── scrapers.py                # 채용 사이트 검색 (3개 사이트 통합)
├── bot_server.py              # Flask 웹훅 서버
│   ├── POST /webhook          # Kakao Skill 응답 (listCard)
│   └── POST /send             # 수동 알림 전송
├── deploy/
│   ├── setup.sh               # OCI 배포 스크립트
│   ├── nginx.conf             # nginx 리버스 프록시 + SSL 설정
│   └── kakao-bot.service      # systemd 서비스
├── scripts/
│   ├── get_token.py           # OAuth 토큰 발급
│   ├── send_test.py           # 메시지 전송 테스트
│   └── send_daily.py          # job-scraper daily 결과 전송
└── requirements.txt
```

## OCI 배포 (Oracle Linux / Ubuntu)

### 1. Oracle Cloud VM 준비

| 항목 | 사양 |
|------|------|
| VM | Oracle Cloud Free Tier (VM.Standard.E2.1.Micro) |
| OS | Ubuntu 22.04+ or Oracle Linux 8+ |
| 방화벽 | VCN 보안 목록에서 **80, 443, 5000** 인바운드 허용 |
| SSH | 전용키로 접속 |

### 2. 저장소 클론 & 설정

```bash
git clone https://github.com/SungHoonGit/kakao-bot-oci.git
cd kakao-bot-oci
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install gunicorn

# config.json 생성 (REST API 키 입력)
cat > config.json << 'EOF'
{
  "kakao": {
    "rest_api_key": "YOUR_REST_API_KEY"
  }
}
EOF
```

### 3. 원클릭 배포

```bash
# 도메인 있는 경우
chmod +x deploy/setup.sh
sudo ./deploy/setup.sh your-domain.com

# 도메인 없는 경우 (IP 직접 사용, SSL 없음)
sudo ./deploy/setup.sh
```

### 4. (선택) 수동 설정

```bash
# nginx
sudo cp deploy/nginx.conf /etc/nginx/sites-available/kakao-bot
sudo ln -s /etc/nginx/sites-available/kakao-bot /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# systemd
sudo cp deploy/kakao-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kakao-bot

# 상태 확인
sudo systemctl status kakao-bot
journalctl -u kakao-bot -f
```

### 5. i.kakao.com 스킬 등록

- **스킬 서버 URL**: `http://<OCI_PUBLIC_IP>/webhook` (또는 `https://your-domain.com/webhook`)
- **응답 유형**: **스킬 데이터** 선택
- 봇테스트로 검증 후 카카오톡 채널에서 테스트

### 6. 카카오톡 사용 예시

```
리액트
자바 서울 3년차
파이썬 신입
```

## 검색 기능

### 키워드 매핑
- `자바` → Java, `리액트` → React, `파이썬` → Python
- `프론트` → Frontend, `백엔드` → Backend
- `스프링` → Spring, `노드` → Node.js

### 경력/지역 필터
- `신입`, `3년차`, `경력 5년` → 경력 필터
- `서울`, `판교`, `강남` → 지역 필터

### 검색 방식
- **실시간 검색**: 요청마다 3개 사이트 동시 스크래핑 (4.5초 타임아웃)
- **캐시**: 동일 검색어 30분간 캐시 (`cache.json`)

## 트러블슈팅

| 문제 | 원인 | 해결 |
|------|------|------|
| 502 Bad Gateway | Flask 서버 미실행 | `sudo systemctl start kakao-bot` |
| 스킬 타임아웃 | 스크래핑 지연 | 검색어 변경 또는 서버 로그 확인 |
| certbot SSL 발급 실패 | 도메인 미설정 | 도메인 DNS 레코드 확인 |
| OCI Public IP 차단됨 | VCN 보안목록 미설정 | OCI 콘솔 → 네트워킹 → 보안목록 수정 |

## 관련 프로젝트

- [kakao-bot](https://github.com/SungHoonGit/kakao-bot) — 로컬/cloudflared 개발용
- [job-scraper](https://github.com/SungHoonGit/job-scraper) — 채용공고 수집 + 일일 history
