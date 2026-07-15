import json
import os
import sys
import re
import time
import logging

from flask import Flask, request, jsonify

from kakao_api import KakaoAPI
import scrapers

logger = logging.getLogger("kakao-bot")

app = Flask(__name__)
kakao = KakaoAPI()

CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache.json")
CACHE_TTL = 1800


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

    remaining = re.sub(r"\s*(?:공고|채용|잡|일자리|개발자|알려줘|찾아줘|검색|보여줘|지방|쪽|근처)\s*", "", remaining)
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


def search_jobs(params: dict) -> list[dict]:
    query = params["query"]
    if params.get("location"):
        query += " " + params["location"]
    jobs = scrapers.search_all(query, max_per_site=5)

    career_from = params.get("career_from")
    career_to = params.get("career_to")
    if career_from is not None or career_to is not None:
        filtered = []
        for j in jobs:
            c_min, c_max = scrapers.parse_career_years(j.get("career", ""))
            if c_min is not None:
                if career_from is not None and c_max is not None and c_max < career_from:
                    continue
                if career_to is not None and c_min is not None and c_min > career_to:
                    continue
            filtered.append(j)
        jobs = filtered
    return jobs


STOP_WORDS = {"개발자", "채용", "구인", "모집", "프리랜서", "정규직", "계약직",
              "주니어", "시니어", "중급", "고급", "초급", "신입", "경력",
              "프로젝트", "가능", "우대", "필수", "담당", "업무", "조건"}

FALLBACK_REPLIES = ["리액트", "자바 신입"]


def _extract_related_from_jobs(jobs: list[dict], exclude_query: str) -> list[str]:
    exclude_lower = exclude_query.lower()
    word_counts = {}
    for job in jobs:
        for w in re.split(r"[\s\[\]\(\)\/,|·‧:]+", job.get("title", "")):
            w = w.strip().strip("-")
            if not w or len(w) < 2:
                continue
            if w.lower() == exclude_lower or w.lower() in STOP_WORDS:
                continue
            if re.match(r"^\d+$", w):
                continue
            word_counts[w] = word_counts.get(w, 0) + 1
    return [w for w, _ in sorted(word_counts.items(), key=lambda x: -x[1])[:2]]


def _build_quick_replies(user_msg: str, query: str, jobs: list[dict]) -> list[dict]:
    replies = [
        {"label": "🔄 동일 검색", "action": "message", "messageText": user_msg},
    ]
    for r in _extract_related_from_jobs(jobs, query) or FALLBACK_REPLIES:
        replies.append({"label": r, "action": "message", "messageText": r})
    return replies


def make_kakao_response(jobs: list[dict], params: dict, user_msg: str = "") -> dict:
    query = params["query"]
    label = f"'{query}'"
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

    quick_replies = _build_quick_replies(user_msg, query, jobs)
    related = _extract_related_from_jobs(jobs, query) or FALLBACK_REPLIES

    if not jobs:
        return {
            "version": "2.0",
            "template": {
                "outputs": [
                    {"simpleText": {
                        "text": f"🔍 {label} 검색 결과가 없습니다.\n검색어를 바꿔보세요.\n추천: " + " · ".join(related)
                    }}
                ],
                "quickReplies": quick_replies
            }
        }

    site_names = {"jobkorea": "잡코리아", "saramin": "사람인", "wanted": "원티드"}
    site_icons = {"jobkorea": "JK", "saramin": "SR", "wanted": "WT"}

    grouped = {}
    for job in jobs:
        site = job.get("site", "other")
        grouped.setdefault(site, []).append(job)

    # 카카오 listCard 는 항목 수 제한(최대 5개)이 있고,
    # carousel 은 quickReplies 터치 영역 오정렬을 유발하므로
    # 여러 사이트 결과를 라운드로빈으로 섞어 단일 listCard(최대 5건)로 구성한다.
    def _build_item(job, site):
        parts = []
        if job.get("career") and job["career"] != "-":
            parts.append(job["career"])
        if job.get("deadline") and job["deadline"] != "-":
            parts.append(job["deadline"])
        desc = job.get("title", "")[:60]
        if parts:
            desc += "\n" + " | ".join(parts)
        return {
            "title": f"[{site_icons[site]}] {job.get('company', '?')}",
            "description": desc,
            "link": {"web": job["url"]},
        }

    items = []
    idx = {s: 0 for s in ["jobkorea", "saramin", "wanted"]}
    for _ in range(5):
        progressed = False
        for site in ["jobkorea", "saramin", "wanted"]:
            site_jobs = grouped.get(site, [])
            if idx[site] < len(site_jobs) and len(items) < 5:
                items.append(_build_item(site_jobs[idx[site]], site))
                idx[site] += 1
                progressed = True
        if not progressed:
            break

    header_title = f"🔍 {label} 검색 결과 ({len(jobs)}건)"
    if len(jobs) > len(items):
        header_title += f" · 상위 {len(items)}건"

    output = {"listCard": {"header": {"title": header_title}, "items": items}}

    # 별도 simpleText 출력은 카카오톡에서 listCard/carousel 과 함께 쓸 때
    # quickReplies 터치 영역이 시각 위치와 어긋나는 버그를 유발하므로,
    # 추천 검색어(유사단어)는 첫 카드 본문(description)에만 넣는다.
    if related:
        tip = "추천: " + " · ".join(related)
        first = output["listCard"]
        if first.get("items"):
            first["items"][0]["description"] = (
                first["items"][0].get("description", "") + "\n" + tip
            ).strip()
        else:
            first["header"] = {"title": first["header"]["title"] + " · " + tip}

    return {
        "version": "2.0",
        "template": {
            "outputs": [output],
            "quickReplies": quick_replies
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
    resp = make_kakao_response(jobs, params, user_msg)
    logger.info("webhook msg=%s jobs=%d", user_msg, len(jobs))
    return resp, 200, {"Content-Type": "application/json; charset=utf-8"}


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
    logger.info("send manual query=%s sent=%d", query, len(alerts))
    return jsonify({"sent": len(alerts)})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    logger.info("Bot server starting on http://0.0.0.0:%d", port)
    app.run(host="0.0.0.0", port=port, debug=True)
