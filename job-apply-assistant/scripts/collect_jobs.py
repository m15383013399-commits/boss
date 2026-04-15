from __future__ import annotations

import argparse
import json
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)


@dataclass
class NormalizedJob:
    platform: str
    job_id: str
    url: str
    company_name: str
    company_info: str
    recruiter_info: str
    title: str
    city: str
    salary: str
    experience_requirement: str
    education_requirement: str
    jd_text: str
    jd_summary: list[str]
    requirements: list[str]
    bonus_items: list[str]


def normalize_text(value: str | None) -> str:
    return " ".join((value or "").split()).strip()


def text_of(node: Tag | None) -> str:
    if not node:
        return ""
    return normalize_text(node.get_text(" ", strip=True))


def first_text(card: Tag, selectors: Iterable[str]) -> str:
    for selector in selectors:
        node = card.select_one(selector)
        text = text_of(node)
        if text:
            return text
    return ""


def first_href(card: Tag, selectors: Iterable[str], base_url: str) -> str:
    for selector in selectors:
        node = card.select_one(selector)
        if node and node.get("href"):
            return urljoin(base_url, node["href"])
    return ""


def split_info_line(value: str) -> tuple[str, str, str]:
    parts = [part.strip() for part in value.replace("|", " ").split() if part.strip()]
    city = parts[0] if len(parts) >= 1 else ""
    experience = parts[1] if len(parts) >= 2 else ""
    education = parts[2] if len(parts) >= 3 else ""
    return city, experience, education


def build_job_id(platform: str, url: str, title: str, company_name: str) -> str:
    seed = f"{platform}|{url}|{title}|{company_name}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def summarize_text(text: str) -> list[str]:
    chunks = []
    for raw in text.replace("；", "。").replace(";", "。").split("。"):
        clean = normalize_text(raw)
        if clean:
            chunks.append(clean)
    return chunks[:3]


def parse_boss_html(html: str, source_url: str = "https://www.zhipin.com/") -> list[NormalizedJob]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("li.job-card-box")
    jobs: list[NormalizedJob] = []
    for card in cards:
        title = text_of(card.select_one(".job-name"))
        salary = text_of(card.select_one(".job-salary"))
        company_name = text_of(card.select_one(".boss-name"))
        company_info = ""
        recruiter_info = ""
        city = text_of(card.select_one(".company-location"))
        tag_items = [text_of(node) for node in card.select(".tag-list li")]
        experience_requirement = tag_items[0] if len(tag_items) >= 1 else ""
        education_requirement = tag_items[1] if len(tag_items) >= 2 else ""
        jd_text = ""
        url = first_href(card, [".job-name", "a[href*='job_detail']"], source_url)
        if not title or not url:
            continue
        jobs.append(
            NormalizedJob(
                platform="boss",
                job_id=build_job_id("boss", url, title, company_name),
                url=url,
                company_name=company_name,
                company_info=company_info,
                recruiter_info=recruiter_info,
                title=title,
                city=city,
                salary=salary,
                experience_requirement=experience_requirement,
                education_requirement=education_requirement,
                jd_text=jd_text,
                jd_summary=summarize_text(jd_text),
                requirements=[],
                bonus_items=[],
            )
        )

    detail_box = soup.select_one(".job-detail-box")
    if detail_box and jobs:
        detail_summary = []
        detail_requirements = []
        detail_bonus = []
        detail_title = text_of(detail_box.select_one(".job-detail-info .job-name"))
        detail_salary = text_of(detail_box.select_one(".job-detail-info .job-salary"))
        detail_tags = [text_of(node) for node in detail_box.select(".job-detail-info .tag-list li")]
        desc_node = detail_box.select_one(".job-detail-body .desc")
        desc_text = text_of(desc_node)
        if desc_text:
            detail_summary = summarize_text(desc_text)
            detail_requirements = [
                item for item in detail_summary if any(word in item for word in ["要求", "熟悉", "具备", "负责", "经验"])
            ][:6]
        company_extra = text_of(detail_box.select_one(".job-detail-body"))
        if company_extra:
            detail_bonus = [item for item in summarize_text(company_extra) if any(word in item for word in ["加分", "优先", "bonus"])]

        jobs[0] = NormalizedJob(
            platform=jobs[0].platform,
            job_id=jobs[0].job_id,
            url=jobs[0].url,
            company_name=jobs[0].company_name,
            company_info=jobs[0].company_info,
            recruiter_info=jobs[0].recruiter_info,
            title=detail_title or jobs[0].title,
            city=detail_tags[0] if len(detail_tags) >= 1 else jobs[0].city,
            salary=detail_salary or jobs[0].salary,
            experience_requirement=detail_tags[1] if len(detail_tags) >= 2 else jobs[0].experience_requirement,
            education_requirement=detail_tags[2] if len(detail_tags) >= 3 else jobs[0].education_requirement,
            jd_text=desc_text or jobs[0].jd_text,
            jd_summary=detail_summary or jobs[0].jd_summary,
            requirements=detail_requirements or jobs[0].requirements,
            bonus_items=detail_bonus or jobs[0].bonus_items,
        )

    return dedupe_jobs(jobs)


def parse_liepin_html(html: str, source_url: str = "https://www.liepin.com/") -> list[NormalizedJob]:
    soup = BeautifulSoup(html, "html.parser")
    jobs: list[NormalizedJob] = []

    cards = soup.select(
        ".job-card-pc-container, .job-list-box .job-card-box, .sojob-item-main, .job-list-item, .card-box"
    )
    for card in cards:
        title = first_text(card, [".job-title", "[class*='job-title']", "h3", "a"])
        salary = first_text(card, [".job-salary", ".salary", "[class*='salary']"])
        company_name = first_text(card, [".company-name", "[class*='company-name']", ".company-info a"])
        company_info = first_text(card, [".company-tags-box", ".company-info", "[class*='company-tags']"])
        recruiter_info = first_text(card, [".recruiter-info", ".recruit-info", "[class*='recruiter']"])
        info_line = first_text(card, [".job-labels-box", ".job-dq-box", ".job-info", "[class*='job-label']"])
        city, experience_requirement, education_requirement = split_info_line(info_line)
        jd_text = first_text(card, [".job-detail-box", ".ellipsis-2", ".job-tags-box", "p"])
        url = first_href(card, ["a[href*='job']", "a"], source_url)
        if title and url:
            jobs.append(
                NormalizedJob(
                    platform="liepin",
                    job_id=build_job_id("liepin", url, title, company_name),
                    url=url,
                    company_name=company_name,
                    company_info=company_info,
                    recruiter_info=recruiter_info,
                    title=title,
                    city=city,
                    salary=salary,
                    experience_requirement=experience_requirement,
                    education_requirement=education_requirement,
                    jd_text=jd_text,
                    jd_summary=summarize_text(jd_text),
                    requirements=[],
                    bonus_items=[],
                )
            )

    if jobs:
        return dedupe_jobs(jobs)

    # Fallback for generic liepin pages where each job/company appears as adjacent links.
    links = soup.find_all("a")
    buffer: list[tuple[str, str]] = []
    for link in links:
        text = text_of(link)
        href = link.get("href") or ""
        if text and href:
            buffer.append((text, urljoin(source_url, href)))
    for idx in range(len(buffer) - 1):
        job_text, job_url = buffer[idx]
        company_text, _company_url = buffer[idx + 1]
        if "k" not in job_text.lower():
            continue
        if len(company_text.split()) < 2:
            continue
        title = job_text.split(" ")[0]
        jobs.append(
            NormalizedJob(
                platform="liepin",
                job_id=build_job_id("liepin", job_url, title, company_text),
                url=job_url,
                company_name=company_text.split(" ")[0],
                company_info=" ".join(company_text.split(" ")[1:]),
                recruiter_info="",
                title=title,
                city="",
                salary=extract_salary(job_text),
                experience_requirement=extract_experience(job_text),
                education_requirement=extract_education(job_text),
                jd_text=job_text,
                jd_summary=summarize_text(job_text),
                requirements=[],
                bonus_items=[],
            )
        )
    return dedupe_jobs(jobs)


def extract_salary(text: str) -> str:
    for token in text.split():
        if "k" in token.lower() or "薪资面议" in token:
            return token
    return ""


def extract_experience(text: str) -> str:
    for token in text.split():
        if "年" in token or "经验不限" in token:
            return token
    return ""


def extract_education(text: str) -> str:
    keywords = ("本科", "硕士", "博士", "大专", "学历不限", "统招本科")
    for token in text.split():
        if any(word in token for word in keywords):
            return token
    return ""


def dedupe_jobs(jobs: list[NormalizedJob]) -> list[NormalizedJob]:
    seen: set[str] = set()
    result: list[NormalizedJob] = []
    for job in jobs:
        if not job.url or job.url in seen:
            continue
        seen.add(job.url)
        result.append(job)
    return result


def fetch_url(url: str, cookie_header: str = "") -> str:
    headers = {"User-Agent": USER_AGENT}
    if cookie_header:
        headers["Cookie"] = cookie_header
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def parse_platform_html(platform: str, html: str, source_url: str) -> list[NormalizedJob]:
    if platform == "boss":
        return parse_boss_html(html, source_url=source_url)
    if platform == "liepin":
        return parse_liepin_html(html, source_url=source_url)
    raise ValueError(f"Unsupported platform: {platform}")


def capture_with_browser(
    urls: list[str],
    browser: str,
    manual_login: bool,
    wait_seconds: float,
    driver_path: str = "",
    browser_binary: str = "",
    headless: bool = False,
    user_data_dir: str = "",
    profile_directory: str = "",
    debugger_address: str = "",
) -> list[tuple[str, str]]:
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service as ChromeService
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.edge.service import Service as EdgeService
        from selenium.webdriver.edge.options import Options as EdgeOptions
    except ModuleNotFoundError as exc:
        raise RuntimeError("Browser capture requires selenium.") from exc

    if browser == "chrome":
        options = ChromeOptions()
        service = ChromeService(executable_path=driver_path) if driver_path else ChromeService()
        if debugger_address:
            options.debugger_address = debugger_address
            driver = webdriver.Chrome(service=service, options=options)
        else:
            options.binary_location = browser_binary or r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--remote-debugging-port=9222")
            if headless:
                options.add_argument("--headless=new")
                options.add_argument("--disable-gpu")
            if user_data_dir:
                options.add_argument(f"--user-data-dir={user_data_dir}")
            if profile_directory:
                options.add_argument(f"--profile-directory={profile_directory}")
            driver = webdriver.Chrome(service=service, options=options)
    elif browser == "edge":
        options = EdgeOptions()
        service = EdgeService(executable_path=driver_path) if driver_path else EdgeService()
        if debugger_address:
            options.debugger_address = debugger_address
            driver = webdriver.Edge(service=service, options=options)
        else:
            options.binary_location = browser_binary or r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--remote-debugging-port=9222")
            if headless:
                options.add_argument("--headless=new")
                options.add_argument("--disable-gpu")
            if user_data_dir:
                options.add_argument(f"--user-data-dir={user_data_dir}")
            if profile_directory:
                options.add_argument(f"--profile-directory={profile_directory}")
            driver = webdriver.Edge(service=service, options=options)
    else:
        raise ValueError(f"Unsupported browser: {browser}")

    try:
        captured: list[tuple[str, str]] = []
        for index, url in enumerate(urls):
            if url:
                driver.get(url)
            if manual_login and index == 0:
                input("Please finish login in the browser, then press Enter here to continue...")
            time.sleep(wait_seconds)
            captured.append((url, driver.page_source))
        return captured
    finally:
        driver.quit()


def collect_boss_jobs_live(
    driver_path: str,
    debugger_address: str,
    browser_binary: str = "",
    max_jobs: int = 15,
    wait_seconds: float = 1.0,
) -> list[NormalizedJob]:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.by import By

    options = ChromeOptions()
    options.debugger_address = debugger_address
    if browser_binary:
        options.binary_location = browser_binary
    service = ChromeService(executable_path=driver_path) if driver_path else ChromeService()
    driver = webdriver.Chrome(service=service, options=options)
    try:
        jobs: list[NormalizedJob] = []
        cards = driver.find_elements(By.CSS_SELECTOR, "li.job-card-box")
        total = min(len(cards), max_jobs)
        for index in range(total):
            cards = driver.find_elements(By.CSS_SELECTOR, "li.job-card-box")
            card = cards[index]
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
            time.sleep(0.3)

            title_node = card.find_element(By.CSS_SELECTOR, ".job-name")
            url = title_node.get_attribute("href") or ""
            title = normalize_text(title_node.text)
            salary = normalize_text(card.find_element(By.CSS_SELECTOR, ".job-salary").text)
            tag_nodes = card.find_elements(By.CSS_SELECTOR, ".tag-list li")
            tags = [normalize_text(node.text) for node in tag_nodes]
            experience_requirement = tags[0] if len(tags) >= 1 else ""
            education_requirement = tags[1] if len(tags) >= 2 else ""
            company_name = normalize_text(card.find_element(By.CSS_SELECTOR, ".boss-name").text)
            city = normalize_text(card.find_element(By.CSS_SELECTOR, ".company-location").text)

            driver.execute_script("arguments[0].click();", card)
            time.sleep(wait_seconds)

            detail_title = title
            detail_salary = salary
            detail_city = city
            detail_exp = experience_requirement
            detail_edu = education_requirement
            detail_text = ""
            detail_summary: list[str] = []
            detail_requirements: list[str] = []
            detail_bonus: list[str] = []

            detail_boxes = driver.find_elements(By.CSS_SELECTOR, ".job-detail-box")
            if detail_boxes:
                detail_box = detail_boxes[0]
                try:
                    node = detail_box.find_element(By.CSS_SELECTOR, ".job-detail-info .job-name")
                    detail_title = normalize_text(node.text) or detail_title
                except Exception:
                    pass
                try:
                    node = detail_box.find_element(By.CSS_SELECTOR, ".job-detail-info .job-salary")
                    detail_salary = normalize_text(node.text) or detail_salary
                except Exception:
                    pass
                try:
                    detail_tags = [normalize_text(n.text) for n in detail_box.find_elements(By.CSS_SELECTOR, ".job-detail-info .tag-list li")]
                    detail_city = detail_tags[0] if len(detail_tags) >= 1 else detail_city
                    detail_exp = detail_tags[1] if len(detail_tags) >= 2 else detail_exp
                    detail_edu = detail_tags[2] if len(detail_tags) >= 3 else detail_edu
                except Exception:
                    pass
                try:
                    desc = detail_box.find_element(By.CSS_SELECTOR, ".job-detail-body .desc")
                    detail_text = normalize_text(desc.text)
                except Exception:
                    detail_text = ""

                if detail_text:
                    detail_summary = summarize_text(detail_text)
                    detail_requirements = [
                        item for item in detail_summary if any(word in item for word in ["要求", "熟悉", "具备", "负责", "经验"])
                    ][:6]
                    detail_bonus = [item for item in detail_summary if any(word in item for word in ["优先", "加分"])]

            jobs.append(
                NormalizedJob(
                    platform="boss",
                    job_id=build_job_id("boss", url, detail_title or title, company_name),
                    url=url,
                    company_name=company_name,
                    company_info="",
                    recruiter_info="",
                    title=detail_title or title,
                    city=detail_city or city,
                    salary=detail_salary or salary,
                    experience_requirement=detail_exp or experience_requirement,
                    education_requirement=detail_edu or education_requirement,
                    jd_text=detail_text,
                    jd_summary=detail_summary,
                    requirements=detail_requirements,
                    bonus_items=detail_bonus,
                )
            )
        return dedupe_jobs(jobs)
    finally:
        driver.quit()


def save_jobs(output_path: Path, jobs: list[NormalizedJob]) -> None:
    payload = {"jobs": [asdict(job) for job in jobs]}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_snapshots(snapshot_dir: Path, captured_pages: list[tuple[str, str]]) -> None:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    for index, (url, html) in enumerate(captured_pages, start=1):
        path = snapshot_dir / f"page-{index:02d}.html"
        path.write_text(html, encoding="utf-8")
        meta = snapshot_dir / f"page-{index:02d}.url.txt"
        meta.write_text(url, encoding="utf-8")


def launch_browser_session(
    browser_binary: str,
    start_url: str,
    remote_debugging_port: int,
    user_data_dir: str,
) -> int:
    if not browser_binary:
        raise ValueError("browser_binary is required for session-launch mode")
    args = [
        browser_binary,
        f"--remote-debugging-port={remote_debugging_port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        start_url,
    ]
    process = subprocess.Popen(args)
    return process.pid


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect normalized job postings from HTML or browser pages.")
    parser.add_argument("--platform", choices=["boss", "liepin"], required=True)
    parser.add_argument("--mode", choices=["html", "url", "browser"], default="html")
    parser.add_argument("--html-files", nargs="*", help="HTML snapshot files to parse.")
    parser.add_argument("--urls", nargs="*", help="URLs to fetch or open in the browser.")
    parser.add_argument("--cookie-header", default="", help="Optional Cookie header for authenticated fetches.")
    parser.add_argument("--browser", choices=["chrome", "edge"], default="chrome")
    parser.add_argument("--driver-path", default="", help="Optional path to chromedriver/msedgedriver.")
    parser.add_argument("--browser-binary", default="", help="Optional path to browser binary.")
    parser.add_argument("--debugger-address", default="", help="Attach to an existing browser debugging address like 127.0.0.1:9222.")
    parser.add_argument("--session-launch", action="store_true", help="Launch a visible browser session with remote debugging and exit.")
    parser.add_argument("--live-extract", action="store_true", help="Use Selenium against the current browser page instead of parsing saved HTML.")
    parser.add_argument("--remote-debugging-port", type=int, default=9222, help="Remote debugging port for launch/attach flows.")
    parser.add_argument("--max-jobs", type=int, default=15, help="Maximum number of jobs to collect in live browser mode.")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode.")
    parser.add_argument("--user-data-dir", default="", help="Optional browser user data dir to reuse login state.")
    parser.add_argument("--profile-directory", default="", help="Optional Chrome/Edge profile directory name.")
    parser.add_argument("--manual-login", action="store_true", help="Pause after opening the first page for manual login.")
    parser.add_argument("--wait-seconds", type=float, default=3.0, help="Seconds to wait after page load in browser mode.")
    parser.add_argument("--snapshot-dir", help="Optional directory to save browser-captured HTML snapshots.")
    parser.add_argument("--output", required=True, help="Path to normalized jobs JSON.")
    args = parser.parse_args()

    if args.session_launch:
        start_url = args.urls[0] if args.urls else "https://www.bosszhipin.com/"
        profile_dir = args.user_data_dir or str(Path("browser-profile").resolve())
        pid = launch_browser_session(
            browser_binary=args.browser_binary,
            start_url=start_url,
            remote_debugging_port=args.remote_debugging_port,
            user_data_dir=profile_dir,
        )
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(
            json.dumps(
                {
                    "status": "browser_session_launched",
                    "pid": pid,
                    "debugger_address": f"127.0.0.1:{args.remote_debugging_port}",
                    "user_data_dir": profile_dir,
                    "start_url": start_url,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Launched browser session with debugger at 127.0.0.1:{args.remote_debugging_port}")
        print(f"Profile dir: {profile_dir}")
        return

    if args.live_extract:
        if args.platform != "boss":
            raise SystemExit("--live-extract is currently implemented only for boss")
        if not args.debugger_address:
            raise SystemExit("--debugger-address is required with --live-extract")
        jobs = collect_boss_jobs_live(
            driver_path=args.driver_path,
            debugger_address=args.debugger_address,
            browser_binary=args.browser_binary,
            max_jobs=args.max_jobs,
            wait_seconds=args.wait_seconds,
        )
        save_jobs(Path(args.output), jobs)
        print(f"Collected {len(jobs)} jobs into {Path(args.output).resolve()}")
        return

    pages: list[tuple[str, str]] = []
    if args.mode == "html":
        if not args.html_files:
            raise SystemExit("--html-files is required in html mode")
        for file_path in args.html_files:
            path = Path(file_path)
            pages.append((path.as_uri(), path.read_text(encoding="utf-8")))
    elif args.mode == "url":
        if not args.urls:
            raise SystemExit("--urls is required in url mode")
        for url in args.urls:
            pages.append((url, fetch_url(url, cookie_header=args.cookie_header)))
    else:
        if not args.urls and not args.debugger_address:
            raise SystemExit("--urls is required in browser mode")
        browser_urls = args.urls or [""]
        pages = capture_with_browser(
            browser_urls,
            args.browser,
            args.manual_login,
            args.wait_seconds,
            driver_path=args.driver_path,
            browser_binary=args.browser_binary,
            headless=args.headless,
            user_data_dir=args.user_data_dir,
            profile_directory=args.profile_directory,
            debugger_address=args.debugger_address,
        )
        if args.snapshot_dir:
            save_snapshots(Path(args.snapshot_dir), pages)

    jobs: list[NormalizedJob] = []
    for source_url, html in pages:
        jobs.extend(parse_platform_html(args.platform, html, source_url))

    save_jobs(Path(args.output), dedupe_jobs(jobs))
    print(f"Collected {len(dedupe_jobs(jobs))} jobs into {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
