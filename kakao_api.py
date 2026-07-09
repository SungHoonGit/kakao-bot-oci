import json
import os
from typing import Optional

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(data):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


class KakaoAPI:
    AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
    TOKEN_URL = "https://kauth.kakao.com/oauth/token"
    SEND_ME_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    SEND_FRIEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/send"
    FRIENDS_URL = "https://kapi.kakao.com/v1/api/talk/friends"

    def __init__(self):
        cfg = load_config()
        k = cfg.get("kakao", {})
        self.rest_api_key = k.get("rest_api_key", "")
        self.access_token = k.get("access_token", "")
        self.refresh_token = k.get("refresh_token", "")

    def _auth_header(self) -> Optional[dict]:
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        return None

    def get_auth_url(self, scope: str = "talk_message") -> str:
        return (
            f"{self.AUTH_URL}"
            f"?client_id={self.rest_api_key}"
            f"&redirect_uri=https://localhost"
            f"&response_type=code"
            f"&scope={scope}"
        )

    def exchange_code(self, code: str) -> dict:
        payload = {
            "grant_type": "authorization_code",
            "client_id": self.rest_api_key,
            "redirect_uri": "https://localhost",
            "code": code,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        resp = requests.post(self.TOKEN_URL, data=payload, headers=headers, timeout=15)
        result = resp.json()
        if resp.status_code == 200 and "access_token" in result:
            self.access_token = result["access_token"]
            self.refresh_token = result.get("refresh_token", "")
            self._save_token()
        return result

    def refresh_access_token(self) -> bool:
        """refresh_token 으로 access_token 갱신"""
        if not self.refresh_token:
            print("  [kakao] refresh_token 없음")
            return False
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.rest_api_key,
            "refresh_token": self.refresh_token,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        resp = requests.post(self.TOKEN_URL, data=payload, headers=headers, timeout=15)
        result = resp.json()
        if resp.status_code == 200 and "access_token" in result:
            self.access_token = result["access_token"]
            if result.get("refresh_token"):
                self.refresh_token = result["refresh_token"]
            self._save_token()
            print("  [kakao] 토큰 갱신 성공")
            return True
        print(f"  [kakao] 토큰 갱신 실패: {resp.status_code} {result}")
        return False

    def _save_token(self):
        cfg = load_config()
        cfg.setdefault("kakao", {})
        cfg["kakao"]["access_token"] = self.access_token
        cfg["kakao"]["refresh_token"] = self.refresh_token
        save_config(cfg)

    def get_friends(self) -> list[dict]:
        auth = self._auth_header()
        if not auth:
            return []
        resp = requests.get(self.FRIENDS_URL, headers=auth, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("elements", [])
        print(f"  [kakao] friends API error: {resp.status_code} {resp.text}")
        return []

    def send_to_me(self, template: dict, auto_refresh: bool = True) -> dict:
        auth = self._auth_header()
        if not auth:
            return {"error": "no token"}
        resp = requests.post(
            self.SEND_ME_URL,
            headers={**auth, "Content-Type": "application/x-www-form-urlencoded"},
            data={"template_object": json.dumps(template, ensure_ascii=False)},
            timeout=15,
        )
        result = resp.json()
        if auto_refresh and result.get("result_code") == -401 and self.refresh_token:
            print("  [kakao] 토큰 만료, 갱신 후 재시도...")
            if self.refresh_access_token():
                return self.send_to_me(template, auto_refresh=False)
        return result

    def send_to_friend(self, friend_uuid: str, template: dict, auto_refresh: bool = True) -> dict:
        auth = self._auth_header()
        if not auth:
            return {"error": "no token"}
        resp = requests.post(
            self.SEND_FRIEND_URL,
            headers={**auth, "Content-Type": "application/x-www-form-urlencoded"},
            data={
                "receiver_uuids": json.dumps([friend_uuid]),
                "template_object": json.dumps(template, ensure_ascii=False),
            },
            timeout=15,
        )
        result = resp.json()
        if auto_refresh and result.get("result_code") == -401 and self.refresh_token:
            print("  [kakao] 토큰 만료, 갱신 후 재시도...")
            if self.refresh_access_token():
                return self.send_to_friend(friend_uuid, template, auto_refresh=False)
        return result

    def send_job_alert(self, alerts: list[dict], to_friends: list[str] = None):
        count = len(alerts)
        first = alerts[0]
        if count == 1:
            description = f"{first['company']} - {first['title']}"
        else:
            description = f"외 {count - 1}건 · {first['company']}, {alerts[1]['company']} 등"

        items = []
        for a in alerts[:5]:
            tech = ", ".join(a.get("tech_stack", [])[:3]) if a.get("tech_stack") else ""
            items.append({"item": a["company"], "item_op": f"{a['title'][:30]} {tech}"})

        template = {
            "object_type": "feed",
            "content": {
                "title": f"채용공고 알림 ({count}건)",
                "description": description[:150],
                "link": {"web_url": first["url"], "mobile_web_url": first["url"]},
            },
            "item_content": {"items": items},
            "buttons": [
                {
                    "title": "자세히 보기",
                    "link": {"web_url": first["url"], "mobile_web_url": first["url"]},
                }
            ],
        }

        result = self.send_to_me(template)
        if result.get("result_code") == 0:
            print(f"  [kakao] sent to me ({count} jobs)")

        if to_friends:
            for uuid in to_friends:
                r = self.send_to_friend(uuid, template)
                status = "ok" if r.get("result_code") == 0 else f"fail: {r}"
                print(f"  [kakao] sent to friend {uuid[:8]}... ({status})")
