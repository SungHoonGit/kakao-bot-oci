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

    template = {
        "object_type": "text",
        "text": "테스트 메시지입니다.\n채용공고 알림봇이 보냅니다.",
        "link": {"web_url": "https://github.com/SungHoonGit/job-scraper", "mobile_web_url": "https://github.com/SungHoonGit/job-scraper"},
        "button_title": "바로가기",
    }

    print("1. 나에게 보내기")
    print("2. 친구에게 보내기")
    choice = input("\n선택 (1/2): ").strip()

    if choice == "2":
        friends = api.get_friends()
        if not friends:
            print("친구 목록이 비어 있습니다.")
            return
        for i, f in enumerate(friends):
            print(f"  {i+1}. {f.get('profile_nickname', '?')} ({f.get('uuid', '')[:12]}...)")
        sel = input("번호 선택: ").strip()
        try:
            idx = int(sel) - 1
            uuid = friends[idx]["uuid"]
            result = api.send_to_friend(uuid, template)
        except (ValueError, IndexError):
            print("잘못된 선택")
            return
    else:
        result = api.send_to_me(template)

    if result.get("result_code") == 0:
        print("✅ 전송 성공!")
    else:
        print(f"❌ 실패: {result}")


if __name__ == "__main__":
    main()
