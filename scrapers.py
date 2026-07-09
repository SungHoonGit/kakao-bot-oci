import json
import re
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup


def normalize_url(url: str) -> str:
    url = re.sub(r"\?.*", "", url)
    url = re.sub(r"#.*", "", url)
    return url.rstrip("/")


def parse_career_years(career_str: str):
    m = re.search(r"(\d+)\s*~\s*(\d+)", career_str)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d+)\s*년\s*이상", career_str)
    if m:
        return int(m.group(1)), None
    m = re.search(r"(\d+)\s*년", career_str)
    if m:
        y = int(m.group(1))
        return y, y
    return None, None


def _fetch(url: str, timeout: int = 8) -> str | None:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    })
    try:
        return urllib.request.urlopen(req, timeout=timeout).read()
    except Exception:
        return None


def search_jobkorea(query: str, max_results: int = 5) -> list[dict]:
    url = (
        "https://www.jobkorea.co.kr/Search/"
        f"?stext={urllib.parse.quote(query)}&careerType=0"
    )
    html = _fetch(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    results = []
    seen = set()
    for a in soup.select('a[href*="Recruit/GI_Read"]'):
        href = a.get("href", "")
        if not href.startswith("http"):
            href = "https://www.jobkorea.co.kr" + href
        href_norm = normalize_url(href)
        if href_norm in seen:
            continue
        seen.add(href_norm)

        title = a.get_text(strip=True)
        if len(title) < 5:
            continue

        parent = a.parent
        company_el = parent.select_one("span") or parent
        company = company_el.get_text(strip=True)[:30] if company_el else ""

        results.append({
            "title": title[:80],
            "company": company,
            "url": href,
            "site": "jobkorea",
            "career": "-",
            "deadline": "-",
        })
        if len(results) >= max_results:
            break
    return results


def search_saramin(query: str, max_results: int = 5) -> list[dict]:
    url = (
        "https://www.saramin.co.kr/zf_user/jobs/list/job-category"
        f"?cat_kewd=235&keyword={urllib.parse.quote(query)}"
    )
    html = _fetch(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    results = []
    seen = set()

    for item in soup.select("div.list_item"):
        company = ""
        el = item.select_one("div.col.company_nm a.str_tit")
        if el:
            company = el.get_text(strip=True)

        title = ""
        item_url = ""
        el = item.select_one("div.job_tit a.str_tit")
        if el:
            title = el.get_text(strip=True)
            el_href = el.get("href", "")
            item_url = el_href if el_href.startswith("http") else "https://www.saramin.co.kr" + el_href

        if not title or not item_url:
            continue

        url_norm = normalize_url(item_url)
        if url_norm in seen:
            continue
        seen.add(url_norm)

        tech_stack = []
        for span in item.select("div.job_meta span.job_sector span"):
            t = span.get_text(strip=True)
            if t and t not in ("", ","):
                tech_stack.append(t)

        career = ""
        el = item.select_one("p.career")
        if el:
            career = el.get_text(strip=True)

        deadline = ""
        el = item.select_one("span.date")
        if el:
            deadline = el.get_text(strip=True)

        results.append({
            "title": title[:80],
            "company": company,
            "url": item_url,
            "site": "saramin",
            "career": career,
            "deadline": deadline,
            "tech_stack": tech_stack,
        })
        if len(results) >= max_results:
            break

    return results


def search_wanted(query: str, max_results: int = 5) -> list[dict]:
    kw_lower = query.lower()

    results = _search_wanted_v4(kw_lower, max_results)
    if results:
        return results

    return _search_wanted_chaos(kw_lower, max_results)


def _search_wanted_v4(kw_lower: str, max_results: int) -> list[dict]:
    url = (
        "https://www.wanted.co.kr/api/v4/jobs"
        f"?country=kr&locations=all&years=-1"
        f"&limit=50&offset=0&job_sort=job.latest_order"
    )
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Referer": "https://www.wanted.co.kr/",
    })
    try:
        resp = urllib.request.urlopen(req, timeout=8)
        data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []

    results = []
    seen = set()

    for job in data.get("data", []):
        jid = job.get("id", "")
        if not jid:
            continue

        title = job.get("position", "") or ""
        company = ""
        if isinstance(job.get("company"), dict):
            company = job.get("company", {}).get("name", "") or ""

        match_str = (title + " " + company).lower()
        if kw_lower not in match_str:
            continue

        href = f"https://www.wanted.co.kr/wd/{jid}"
        if href in seen:
            continue
        seen.add(href)

        full_title = f"[{company}] {title}" if company else title

        annual_from = job.get("annual_from")
        annual_to = job.get("annual_to")
        career = ""
        if annual_from is not None and annual_to is not None:
            career = f"경력{annual_from}~{annual_to}년"
        elif annual_from is not None:
            career = f"경력{annual_from}년~"

        deadline = job.get("due_time", "-") or "-"

        results.append({
            "title": full_title[:80],
            "company": company,
            "url": href,
            "site": "wanted",
            "career": career,
            "deadline": deadline,
        })
        if len(results) >= max_results:
            break

    return results


def _search_wanted_chaos(kw_lower: str, max_results: int) -> list[dict]:
    url = (
        "https://www.wanted.co.kr/api/chaos/navigation/v1/results"
        f"?job_group_id=518&years=-1&locations=all&country=kr"
        f"&job_sort=job.latest_order&limit=50&offset=0"
    )
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Referer": "https://www.wanted.co.kr/",
    })
    try:
        resp = urllib.request.urlopen(req, timeout=8)
        data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []

    results = []
    seen = set()

    for job in data.get("data", []):
        jid = job.get("id", "")
        if not jid:
            continue
        href = f"https://www.wanted.co.kr/wd/{jid}"

        title = job.get("position", "") or ""
        company = ""
        if isinstance(job.get("company"), dict):
            company = job.get("company", {}).get("name", "") or ""

        match_str = (title + " " + company).lower()
        tags = [t or "" for t in job.get("tags", [])]
        if kw_lower not in match_str and not any(kw_lower in t.lower() for t in tags):
            continue

        if href in seen:
            continue
        seen.add(href)

        full_title = f"[{company}] {title}" if company else title

        annual_from = job.get("annual_from")
        annual_to = job.get("annual_to")
        career = ""
        if annual_from is not None and annual_to is not None:
            career = f"경력{annual_from}~{annual_to}년"
        elif annual_from is not None:
            career = f"경력{annual_from}년~"

        results.append({
            "title": full_title[:80],
            "company": company,
            "url": href,
            "site": "wanted",
            "career": career,
            "deadline": "-",
        })
        if len(results) >= max_results:
            break

    return results


def search_all(query: str, max_per_site: int = 5) -> list[dict]:
    """3개 사이트를 동시에 검색 (최대 4.5초)"""
    results = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(search_jobkorea, query, max_per_site): "jobkorea",
            executor.submit(search_saramin, query, max_per_site): "saramin",
            executor.submit(search_wanted, query, max_per_site): "wanted",
        }
        try:
            for future in as_completed(futures, timeout=4.5):
                try:
                    results.extend(future.result())
                except Exception:
                    pass
        except TimeoutError:
            pass
    return results
