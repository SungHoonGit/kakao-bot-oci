#!/usr/bin/env python3
import sys
import os
import webbrowser
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kakao_api import KakaoAPI


def main():
    scope = "talk_message,talk_friends"
    if "--me-only" in sys.argv:
        scope = "talk_message"

    api = KakaoAPI()
    if not api.rest_api_key:
        print("config.json 에 rest_api_key 를 먼저 입력하세요.")
        sys.exit(1)

    auth_url = api.get_auth_url(scope)
    print(f"\nREST API 키: {api.rest_api_key[:8]}...{api.rest_api_key[-4:]}")
    print(f"Scope: {scope}")
    print(f"\n인증 URL:\n{auth_url}\n")
    print("1. 브라우저에서 위 URL 열기 (또는 엔터 시 자동)")
    input("2. 로그인 후 https://localhost 로 리다이렉트됨")
    webbrowser.open(auth_url)

    url = input("\n3. 리다이렉트된 전체 URL 붙여넣기:\n").strip()
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    code = params.get("code", [None])[0]

    if not code:
        print("URL 에서 code 를 찾을 수 없습니다.")
        sys.exit(1)

    result = api.exchange_code(code)
    if "access_token" in result:
        print(f"\n✅ 토큰 발급 완료! (scope: {scope})")
    else:
        print(f"\n❌ 실패: {result}")


if __name__ == "__main__":
    main()
