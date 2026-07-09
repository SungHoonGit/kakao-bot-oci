# Kakao Bot — 채용공고 검색 챗봇

Kakao i 오픈빌더 스킬 웹훅 기반 채용공고 검색 봇입니다.
JobKorea, 사람인, 원티드를 동시에 검색하여 결과를 listCard로 응답합니다.

## 구조

```
kakao-bot/
├── config.json                # Kakao REST API 키
├── kakao_api.py               # Kakao REST API 래퍼 (OAuth 전송용)
├── scrapers.py                # 채용 사이트 검색 (3개 사이트 통합)
│   ├── search_jobkorea()      # 잡코리아
│   ├── search_saramin()       # 사람인
│   ├── search_wanted()        # 원티드 (v4 API + Chaos API fallback)
│   └── search_all()           # 3개 사이트 동시 검색 + 4.5초 타임아웃
├── bot_server.py              # Flask 웹훅 서버
│   ├── POST /webhook          # Kakao Skill 응답 (listCard)
│   └── POST /send             # 수동 알림 전송 (talk_message)
├── bot_server.py              # Flask 웹훅 서버
│   └── POST /webhook          # Kakao Skill 응답 (listCard)
├── scripts/
│   ├── get_token.py           # OAuth 토큰 발급
│   ├── send_test.py           # 메시지 전송 테스트
│   └── send_daily.py          # job-scraper daily 결과 전송
├── cloudflared.exe            # 터널링 바이너리
└── requirements.txt
```

## 사용법 (Kakao i 오픈빌더 웹훅)

### 1. 사전 준비

| 항목 | 설명 |
|------|------|
| [Kakao Developers](https://developers.kakao.com) 앱 | REST API 키 발급 필요 |
| [Kakao i 오픈빌더](https://i.kakao.com) | 채널 연결 후 스킬 웹훅 등록 |
| 터널링 (cloudflared) | 로컬 서버 외부 노출용 |
| config.json | REST API 키 직접 입력 |

### 2. 카카오 앱 생성
- [Kakao Developers](https://developers.kakao.com) → **애플리케이션 추가**
- 앱 키 → **REST API 키** 복사
- `config.json`에 저장:
```json
{
  "kakao": {
    "rest_api_key": "REST_API_KEY"
  }
}
```

### 3. i 오픈빌더 봇 생성
- [i.kakao.com](https://i.kakao.com) → **새 봇 만들기**
- **채널 연결** (KaKaoTalk 채널 필요, [center-pf.kakao.com](https://center-pf.kakao.com) 에서 무료 생성)
- 봇 생성 후 **시나리오** 탭 → **블록 추가** (예: "채용검색")

### 4. 웹훅 서버 실행
```bash
pip install -r requirements.txt
python bot_server.py 5001
```

### 5. 터널링 (cloudflared, HTTP2 필수)
회사 방화벽 등에서 UDP(QUIC)가 차단된 경우 `--protocol http2` 사용:

```bash
# 일반
cloudflared tunnel --url http://localhost:5001

# HTTP2 강제 (QUIC 차단 환경)
cloudflared tunnel --protocol http2 --url http://localhost:5001
```

생성된 `https://xxxx.trycloudflare.com` URL을 복사합니다.

### 6. 스킬 등록 (i.kakao.com)
- 시나리오 블록 → **스킬** 탭 → **스킬 데이터** 선택
- **스킬 서버 URL**: `https://xxxx.trycloudflare.com/webhook`
- **응답 유형**: **스킬 데이터** (텍스트/카드가 아님)
- 저장 후 **봇테스트**로 검증

### 7. 카카오톡에서 테스트
봇테스트 통과 후 실제 카카오톡 채널 채팅방에서 메시지 전송:

```
리액트
자바 서울 3년차
파이썬 신입
```

## 명령어 예시 / 검색 기능

### 검색 키워드

| 입력 | 검색 결과 |
|------|-----------|
| `리액트` | React 채용공고 |
| `자바` | Java 채용공고 |
| `파이썬 신입` | Python 신입 채용 |
| `자바 서울 3년차` | Java, 서울, 경력 3년 |

자연어에서 키워드 자동 매핑:
- `자바` → Java, `리액트` → React, `타입스크립트` → TypeScript
- `프론트/프론트엔드` → Frontend, `백엔드` → Backend
- `파이썬` → Python, `스프링` → Spring, `노드` → Node.js, `쿠버네티스` → Kubernetes

### 경력/지역 필터
- `신입` → 경력 0년 필터
- `3년차`, `경력 5년` → 해당 경력 필터
- `서울`, `판교`, `강남` 등 → 지역 필터 (지역명이 검색어에 포함된 경우)

### 검색 동작 방식
- **실시간 검색**: 매 요청마다 3개 사이트를 동시에 스크래핑
- **정렬**: 각 사이트 기본 정렬(최신순) + 원티드는 `latest_order` 명시
- **타임아웃**: 4.5초 초과 시 해당 사이트는 제외
- **캐시**: 동일 검색어 30분 내 재요청 시 cache.json 활용 (불필요한 API 호출 방지)
- **이력/DB 없음**: 검색 결과를 저장하거나 누적하지 않음

### 응답 예시 (listCard)
```
┌──────────────────────────────────┐
│ 🔍 'React' 검색 결과 (4건)        │
├──────────────────────────────────┤
│ [JK] 회사명                       │
│ React 개발자 (프리랜서)           │
│ 경력 3년 이상 | 2025.08.31       │
│ (클릭 시 상세 페이지 이동)         │
├──────────────────────────────────┤
│ [SR] 회사명                       │
│ ...                               │
└──────────────────────────────────┘
```

## 트러블슈팅

| 문제 | 원인 | 해결 |
|------|------|------|
| Cloudflare 530 | QUIC/UDP 차단 | `--protocol http2` 옵션 사용 |
| "must be of the same schema" | 텍스트/카드 탭 선택 | 스킬 데이터 탭으로 변경 |
| 스킬 서버 URL 530 에러 | 터널 끊김 | cloudflared 재실행 |
| 검색 결과 0건 | 타임아웃 또는 스크래핑 실패 | 검색어 변경, 서버 로그 확인 |

## OAuth 방식 (talk_message, 보류)

카카오톡 **나에게/친구에게 보내기** API를 사용하려면 `talk_message` 동의항목 필요.
앱 API 검증이 필요하여 현재는 사용하지 않음.

```bash
python scripts/get_token.py       # OAuth 토큰 발급
python scripts/send_test.py       # 메시지 전송 테스트
python scripts/send_daily.py      # 일일 알림
```

## 의존성

- Python 3.10+
- Flask
- beautifulsoup4 + lxml

## 관련 프로젝트

- [job-scraper](https://github.com/SungHoonGit/job-scraper) — 채용공고 수집 + history 저장
