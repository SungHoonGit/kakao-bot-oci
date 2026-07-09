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
│   ├── apache.conf            # Apache 리버스 프록시 설정
│   ├── nginx.conf             # nginx 리버스 프록시 설정
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
| VM | Oracle Cloud Free Tier (VM.Standard.A1.Flex or E2.1.Micro) |
| OS | Ubuntu 22.04+ (Minimal도 무방) |
| SSH | 키 기반 접속 (암호 로그인 불가) |

#### 1-a. VCN 보안목록 오픈 (필수)
OCI 2중 방화벽 — **Security List + VM iptables** 둘 다 열어야 함.

**Security List**: VCN → Security → Default Security List → **Add Ingress Rules**

| Port | Protocol | Source | Stateless | 용도 |
|------|----------|--------|-----------|------|
| 80 | TCP | 0.0.0.0/0 | 해제 | HTTP (Apache/nginx) |
| 443 | TCP | 0.0.0.0/0 | 해제 | HTTPS (SSL) |

*22번(SSH)은 VCN 생성 시 자동 추가됨*

#### 1-b. VM iptables 오픈 (Ubuntu Minimal 필수)
Minimal 이미지는 SSH(22)만 허용하고 나머지 REJECT함.

```bash
ssh ubuntu@<IP>
sudo iptables -I INPUT 4 -p tcp --dport 80 -m state --state NEW -j ACCEPT
sudo iptables -I INPUT 4 -p tcp --dport 443 -m state --state NEW -j ACCEPT
sudo netfilter-persistent save
```

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
# Apache (기본)
chmod +x deploy/setup.sh
sudo ./deploy/setup.sh                       # 도메인 없음
sudo ./deploy/setup.sh your-domain.com        # 도메인 + SSL

# nginx
sudo ./deploy/setup.sh your-domain.com nginx
```

### 4. (선택) 수동 설정

```bash
# Apache
sudo a2enmod proxy proxy_http
sudo cp deploy/apache.conf /etc/apache2/sites-available/kakao-bot.conf
sudo a2ensite kakao-bot.conf
sudo systemctl reload apache2

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

### 6. CI/CD — 자동 배포

main 브랜치에 push하면 **GitHub Actions**가 OCI VM에 자동 배포합니다.

```
push → main
  ↓
GitHub Actions: Deploy to OCI
  ↓
SSH → git pull → sudo systemctl restart kakao-bot
```

**사전 설정 (1회):**
1. https://github.com/SungHoonGit/kakao-bot-oci/settings/secrets/actions
2. **New repository secret** → `OCI_SSH_KEY` = OCI VM SSH 개인키
3. 이후 main에 push할 때마다 자동 배포

**배포 확인:**
```bash
# Actions 탭에서 로그 확인
https://github.com/SungHoonGit/kakao-bot-oci/actions

# 또는 OCI에서 직접 확인
sudo journalctl -u kakao-bot -f
```

### 7. 카카오톡 사용 예시

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
| 외부 접속 안 됨 (timeout) | OCI Security List or iptables | 위 "1-a, 1-b" 항목 확인 |
| 외부 접속 안 됨 (connection refused) | Flask 서버 미실행 | `sudo systemctl status kakao-bot` |
| i.kakao.com "Request timeout after 5000 ms" | 80포트 막힘 | Security List + iptables 둘 다 확인 |

## 관련 프로젝트

- [kakao-bot](https://github.com/SungHoonGit/kakao-bot) — 로컬/cloudflared 개발용
- [job-scraper](https://github.com/SungHoonGit/job-scraper) — 채용공고 수집 + 일일 history
