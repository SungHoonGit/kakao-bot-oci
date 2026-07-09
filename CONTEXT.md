# Project Context (AI-readable)

## Overview

Kakao i 오픈빌더 스킬 웹훅 기반 채용공고 검색 챗봇.
JobKorea, 사람인, 원티드를 동시에 검색하여 listCard + quickReplies 로 응답.

## Repo Structure

```
C:\Users\KIM\git\kakao-bot\               ← git root
├── CONTEXT.md                             ← 이 파일
├── README.md
├── .gitignore
├── requirements.txt
├── run.sh                                 ← 실행 스크립트
├── cloudflared.exe                        ← 터널링 바이너리 (--protocol http2)
│
├── kakao_api.py                           ← Kakao REST API 래퍼
│   ├── refresh_access_token()             ← 토큰 갱신
│   ├── send_to_me()                       ← 나에게 메시지 전송
│   └── send_job_alert()                   ← feed 템플릿 알림
│
├── scrapers.py                            ← 채용 사이트 검색
│   ├── search_jobkorea()                  ← 잡코리아 (BS4)
│   ├── search_saramin()                   ← 사람인 (BS4)
│   ├── search_wanted()                    ← 원티드 (v4 API + Chaos)
│   └── search_all()                       ← 3개 동시 검색 + 4.5초 타임아웃
│
├── bot_server.py                          ← Flask 웹훅 서버
│   ├── POST /webhook                      ← 스킬 응답 (listCard + quickReplies)
│   │   ├── extract_search_params()        ← 자연어 파싱 (키워드/지역/경력)
│   │   ├── search_jobs()                  ← scrapers 호출 + 경력/지역 필터
│   │   ├── _extract_related_from_jobs()   ← 제목 빈도분석 → 유사 키워드 추출
│   │   └── make_kakao_response()          ← listCard + quickReplies 구성
│   └── POST /send                         ← 수동 알림 전송
│
└── scripts/
    ├── get_token.py                       ← OAuth 토큰 발급
    ├── send_test.py                       ← 메시지 전송 테스트
    └── send_daily.py                      ← job-scraper daily 결과 전송
```

## 실행 흐름

```
사용자 메시지 → KakaoTalk 채널
                     ↓
            i.kakao.com 폴백블록
                     ↓
            cloudflared tunnel (HTTP2)
                     ↓
            bot_server.py POST /webhook
                     ↓
            extract_search_params() → query, location, career
            search_jobs() → scrapers.search_all()
            make_kakao_response() → listCard + quickReplies JSON
                     ↓
            KakaoTalk 채널 응답 (200)
```

## 키워드 매핑

| 한글 | 영문 |
|------|------|
| 자바 | Java |
| 리액트 | React |
| 파이썬 | Python |
| 스프링 | Spring |
| 프론트/프론트엔드 | Frontend |
| 백엔드 | Backend |
| 타입스크립트 | TypeScript |
| 안드로이드 | Android |
| 노드 | Node.js |
| 쿠버네티스 | Kubernetes |

## RELATED 추천 (quickReplies)

검색 결과 공고 제목에서 공통 키워드를 자동 추출하여 동적 생성.
결과 없으면 fallback: 리액트 / 자바 신입

## Config

```json
{
  "kakao": {
    "rest_api_key": "..."
  }
}
```
