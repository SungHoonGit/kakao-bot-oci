#!/usr/bin/env python3
"""
job-scraper 의 daily/ 결과를 읽어 카카오톡으로 전송합니다.

Usage:
    python3 scripts/send_daily.py ../job-scraper/daily/react
    python3 scripts/send_daily.py ../job-scraper/daily/react ../job-scraper/daily/java
"""
import json
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kakao_api import KakaoAPI


def read_daily_md(path: str) -> str:
    """daily/*.md 파일을 읽어 요약 텍스트로 반환"""
    files = sorted(os.listdir(path)) if os.path.isdir(path) else []
    md_files = [f for f in files if f.endswith('.md')]
    if not md_files:
        return ""

    latest = md_files[-1]
    content = open(os.path.join(path, latest), encoding='utf-8').read()

    today = latest.replace('.md', '')
    lines = content.strip().split('\n')
    job_lines = [l for l in lines if l.startswith('| ') and not l.startswith('| 회사명') and '---' not in l]

    summary = f"[{today}] {len(job_lines)}건\n"
    for l in job_lines[:10]:
        parts = [p.strip() for p in l.split('|') if p.strip()]
        if len(parts) >= 2:
            company = parts[0]
            title_link = parts[2]
            title = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', title_link)
            deadline = parts[4] if len(parts) > 4 else '-'
            summary += f"  {company} | {title} | ~{deadline}\n"

    if len(job_lines) > 10:
        summary += f"  ...외 {len(job_lines) - 10}건\n"

    return summary


def build_message(profile_dir_map: dict) -> str:
    """프로파일별 daily 결과를 읽어 하나의 텍스트 메시지로 구성"""
    parts = []
    for profile, dir_path in profile_dir_map.items():
        s = read_daily_md(dir_path)
        if s:
            parts.append(f"📋 {profile}\n{s}")
    if not parts:
        return ""

    today_text = os.path.basename(dir_path)
    text = f"🔔 채용공고 업데이트 ({list(profile_dir_map.keys())[0]} 외)\n\n"
    text += "\n".join(parts)
    return text


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <daily_dir> [<daily_dir2> ...]")
        sys.exit(1)

    api = KakaoAPI()
    if not api.access_token:
        if not api.refresh_token:
            print("토큰이 없습니다. get_token.py 를 먼저 실행하세요.")
            sys.exit(1)
        print("  [kakao] 토큰 갱신...")
        api.refresh_access_token()

    profile_dirs = {}
    for d in sys.argv[1:]:
        name = os.path.basename(d.rstrip('/'))
        profile_dirs[name] = d

    text = build_message(profile_dirs)
    if not text:
        print("전송할 데이터가 없습니다. (daily/*.md 없음)")
        sys.exit(0)

    template = {
        "object_type": "text",
        "text": text[:1000],
        "link": {
            "web_url": "https://github.com/SungHoonGit/job-scraper",
            "mobile_web_url": "https://github.com/SungHoonGit/job-scraper"
        },
        "button_title": "채용공고 보기",
    }

    result = api.send_to_me(template)
    if result.get("result_code") == 0:
        print("✅ 카톡 전송 성공!")
    else:
        print(f"❌ 전송 실패: {result}")


if __name__ == "__main__":
    main()
