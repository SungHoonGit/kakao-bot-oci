#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kakao_api import KakaoAPI


def main():
    api = KakaoAPI()
    if not api.access_token:
        print("access_token 이 없습니다. scripts/get_token.py 를 먼저 실행하세요.")
        sys.exit(1)

    print("친구 목록 조회 중...")
    friends = api.get_friends()

    if not friends:
        print("\n조회된 친구가 없습니다.")
        print("→ talk_friends scope 으로 토큰 재발급 필요할 수 있음")
        print("→ 같은 앱을 인증한 사용자만 목록에 나타남")
        return

    print(f"\n총 {len(friends)}명의 친구:")
    for f in friends:
        print(f"  - {f.get('profile_nickname', '?')} (uuid: {f.get('uuid', '?')[:12]}...)")


if __name__ == "__main__":
    main()
