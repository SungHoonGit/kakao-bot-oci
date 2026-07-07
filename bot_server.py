import json
import os
import sys
import re
import time
from datetime import datetime

from flask import Flask, request, jsonify

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../job-scraper"))
from extractors.base import BaseExtractor
from kakao_api import KakaoAPI

app = Flask(__name__)
kakao = KakaoAPI()

CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache.json")
CACHE_TTL = 1800  # 30분


def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
            if time.time() - data.get("ts", 0) < CACHE_TTL:
                return data.get("jobs", [])
    return None


def save_cache(jobs):
    with open(CACHE_FILE, "w") as f:
        json.dump({"ts": time.time(), "jobs": jobs}, f)


LOCATIONS = [
    "서울", "경기", "인천", "부산", "대전", "대구", "광주", "울산",
    "세종", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
    "판교", "분당", "강남", "서초", "송파", "마포", "영등포", "구로",
]


def extract_search_params(user_msg: str) -> dict:
    result = {}
    remaining = user_msg

    for loc in LOCATIONS:
        if loc in remaining:
            result["location"] = loc
            remaining = remaining.replace(loc, "", 1)
            break

    career_re = re.search(r"(신입)|(경력\s*(\d+)\s*년(?:\s*이상)?)|(\d+)\s*년차(?:\s*이상)?", remaining)
    if career_re:
        if career_re.group(1):
            result["career_from"] = 0
            result["career_to"] = 0
        else:
            y = int((career_re.group(3) or career_re.group(4) or "0"))
            result["career_from"] = y
            result["career_to"] = y
        remaining = remaining.replace(career_re.group(0), "", 1)

    remaining = re.sub(r"\s*(?:공고|채용|잡|일자리|개발자|알려줘|찾아줘|검색|보여줘)\s*", "", remaining)
    remaining = remaining.strip()
    query = remaining if remaining else user_msg.strip()
    keyword_map = {
        "자바": "Java", "리액트": "React", "타입스크립트": "TypeScript",
        "프론트": "Frontend", "프론트엔드": "Frontend", "백엔드": "Backend",
        "안드로이드": "Android", "파이썬": "Python", "스프링": "Spring",
        "노드": "Node.js", "쿠버네티스": "Kubernetes",
    }
    for ko, en in keyword_map.items():
        if query == ko or query.startswith(ko + " "):
            query = en + query[len(ko):]
            break
    result["query"] = query
    return result


def fast_search(query: str) -> list[dict]:
    import urllib.request
    from bs4 import BeautifulSoup

    url = (
        "https://www.jobkorea.co.kr/Search/"
        f"?stext={urllib.request.quote(query)}&careerType=0"
    )
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    })
    try:
        html = urllib.request.urlopen(req, timeout=8).read()
    except Exception:
        return []

    soup = BeautifulSoup(html, "lxml")
    results = []
    seen = set()
    for a in soup.select('a[href*="Recruit/GI_Read"]'):
        href = a.get("href", "")
        if not href.startswith("http"):
            href = "https://www.jobkorea.co.kr" + href
        href_norm = BaseExtractor.normalize_url(href)
        if href_norm in seen:
            continue
        seen.add(href_norm)

        title = a.get_text(strip=True)
        if len(title) < 5:
            continue

        # Extract company and career from surrounding elements
        parent = a.parent
        company_el = parent.select_one("span") or parent
        company = company_el.get_text(strip=True)[:30] if company_el else ""

        results.append({
            "title": title[:80],
            "company": company,
            "url": href_norm,
            "site": "jobkorea",
            "career": "-",
            "deadline": "-",
        })
        if len(results) >= 5:
            break
    return results


def search_jobs(params: dict) -> list[dict]:
    query = params["query"]
    jobs = fast_search(query)

    career_from = params.get("career_from")
    career_to = params.get("career_to")
    if career_from is not None or career_to is not None:
        filtered = []
        for j in jobs:
            c_min, c_max = BaseExtractor.parse_career_years(j.get("career", ""))
            if c_min is not None:
                if career_from is not None and c_max is not None and c_max < career_from:
                    continue
                if career_to is not None and c_min is not None and c_min > career_to:
                    continue
            filtered.append(j)
        jobs = filtered

    return jobs


def make_kakao_response(jobs: list[dict], params: dict) -> dict:
    query = params["query"]
    label = f"🔍 '{query}'"
    if params.get("location"):
        label += f" {params['location']}"
    if "career_from" in params or "career_to" in params:
        cf = params.get("career_from")
        ct = params.get("career_to")
        if cf == 0 and ct == 0:
            label += " 신입"
        elif cf == ct:
            label += f" {cf}년차"
        elif cf and ct:
            label += f" {cf}~{ct}년차"
        elif cf:
            label += f" {cf}년차 이상"
        elif ct:
            label += f" {ct}년차 이하"

    if not jobs:
        return {
            "version": "2.0",
            "template": {
                "outputs": [
                    {"simpleText": {"text": f'{label} 검색 결과가 없습니다.\n검색어를 바꿔보세요.'}}
                ]
            }
        }

    # Build a text summary with links
    lines = [f"{label} 검색 결과 ({len(jobs)}건)\n"]
    for i, job in enumerate(jobs[:5], 1):
        company = job.get("company", "?")
        title = job.get("title", "")[:30]
        lines.append(f"{i}. [{company}] {title}")
    lines.append(f"\n자세한 링크: {jobs[0]['url']}")

    return {
        "version": "2.0",
        "template": {
            "outputs": [
                {"simpleText": {"text": "\n".join(lines)}}
            ]
        }
    }


@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_json(silent=True) or {}
    user_msg = (
        body.get("userRequest", {}).get("utterance", "")
        or body.get("utterance", "")
        or ""
    )

    params = extract_search_params(user_msg)
    jobs = search_jobs(params)
    resp = make_kakao_response(jobs, params)
    print(f"[webhook] msg={user_msg} jobs={len(jobs)}")
    return resp, 200, {"Content-Type": "application/json; charset=utf-8"}


@app.route("/ping", methods=["POST"])
def ping():
    body = """{"version":"2.0","template":{"outputs":[{"simpleText":{"text":"pong"}}]}}"""
    return body, 200, {"Content-Type": "application/json; charset=utf-8"}


@app.route("/pong", methods=["POST"])
def pong():
    return "{\"version\":\"2.0\",\"template\":{\"outputs\":[{\"simpleText\":{\"text\":\"test ok\"}}]}}", 200, {"Content-Type": "application/json"}


@app.route("/t1", methods=["POST"])
def t1():
    # template 없이
    return "{\"version\":\"2.0\",\"outputs\":[{\"simpleText\":{\"text\":\"t1 ok\"}}]}", 200, {"Content-Type": "application/json"}


@app.route("/t2", methods=["POST"])
def t2():
    # data.output
    return "{\"version\":\"2.0\",\"data\":{\"outputs\":[{\"simpleText\":{\"text\":\"t2 ok\"}}]}}", 200, {"Content-Type": "application/json"}


@app.route("/t3", methods=["POST"])
def t3():
    # data.contents
    return "{\"version\":\"2.0\",\"data\":{\"contents\":[{\"type\":\"text\",\"text\":\"t3 ok\"}]}}", 200, {"Content-Type": "application/json"}


@app.route("/send", methods=["POST"])
def send_manual():
    data = request.get_json(silent=True) or {}
    query = data.get("query", "")
    if not query:
        return jsonify({"error": "query required"}), 400

    params = extract_search_params(query)
    jobs = search_jobs(params)
    alerts = [
        {"company": j.get("company", "?"), "title": j.get("title", ""), "url": j["url"],
         "tech_stack": j.get("tech_stack", [])}
        for j in jobs[:5]
    ]
    kakao.send_job_alert(alerts)
    return jsonify({"sent": len(alerts)})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    print(f"Bot server running on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
