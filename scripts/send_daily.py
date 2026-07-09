#!/usr/bin/env python3
"""
job-scraper 의 daily/ 결과를 읽어 카카오톡으로 전송합니다.

Usage:
    python3 scripts/send_daily.py ../job-scraper/daily                  # flat 구조
    python3 scripts/send_daily.py ../job-scraper/daily/react ../job-scraper/daily/java  # profile 구조
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kakao_api import KakaoAPI


def read_md_files(path: str) -> list:
    """디렉토리에서 *.md 파일 목록 반환 (최신순)"""
    if not os.path.isdir(path):
        return []
    files = sorted((f for f in os.listdir(path) if f.endswith('.md') and not f.endswith('_backup.md')), reverse=True)
    return files


def summarize_md(path: str, filename: str) -> str:
    """md 파일 하나를 요약"""
    content = open(os.path.join(path, filename), encoding='utf-8').read()
    today = filename.replace('.md', '')
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


def collect_daily_results(daily_root: str) -> str:
    """
    daily_root 아래에서 결과를 수집합니다.
    - flat: .md 파일이 직접 있음
    - profile: react/, java/ 등 서브디렉토리가 있음
    """
    if not os.path.isdir(daily_root):
        return ""

    entries = os.listdir(daily_root)
    subdirs = sorted([d for d in entries if os.path.isdir(os.path.join(daily_root, d)) and not d.startswith('.')])

    parts = []
    if subdirs:
        for sd in subdirs:
            sd_path = os.path.join(daily_root, sd)
            mds = read_md_files(sd_path)
            if mds:
                s = summarize_md(sd_path, mds[0])
                if s:
                    parts.append(f"📋 {sd}\n{s}")
    else:
        mds = read_md_files(daily_root)
        if mds:
            s = summarize_md(daily_root, mds[0])
            if s:
                parts.append(s)

    return "\n".join(parts)


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <daily_dir> [<daily_dir2> ...]")
        sys.exit(1)

    api = KakaoAPI()
    if not api.access_token and not api.refresh_token:
        print("토큰이 없습니다. get_token.py 를 먼저 실행하세요.")
        sys.exit(1)

    # 일일 cron에서는 access_token이 만료되었을 가능성이 높으므로 우선 갱신
    if api.refresh_token:
        print("  [kakao] 토큰 갱신...")
        api.refresh_access_token()

    all_parts = []
    for d in sys.argv[1:]:
        text = collect_daily_results(d)
        if text:
            all_parts.append(text)

    if not all_parts:
        print("전송할 데이터가 없습니다. (daily/*.md 없음)")
        sys.exit(0)

    full_text = "🔔 채용공고 업데이트\n\n" + "\n\n".join(all_parts)

    template = {
        "object_type": "text",
        "text": full_text[:1000],
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
