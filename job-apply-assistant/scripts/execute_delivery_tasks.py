from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

from collect_jobs import (
    attach_chrome_driver,
    normalize_job_url,
    scroll_boss_job_list,
    wait_for_boss_job_cards,
)


@dataclass
class ExecutionResult:
    job_url: str
    company_name: str
    send_mode: str
    status: str
    note: str
    timestamp: float


def read_json(path: Path) -> Any:
    for encoding in ("utf-8", "utf-8-sig"):
        try:
            return json.loads(path.read_text(encoding=encoding))
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("text", b"", 0, 1, f"unsupported encoding for {path}")


def load_delivery_tasks(path: Path, required_status: str, job_url: str = "", max_tasks: int = 0) -> list[dict[str, Any]]:
    payload = read_json(path)
    if isinstance(payload, dict):
        tasks = payload.get("delivery_tasks") or payload.get("tasks") or []
    elif isinstance(payload, list):
        tasks = payload
    else:
        raise ValueError(f"Unsupported task payload in {path}")

    target_url = normalize_job_url(job_url) if job_url else ""
    selected: list[dict[str, Any]] = []
    for item in tasks:
        if required_status and item.get("status") != required_status:
            continue
        current_url = normalize_job_url(str(item.get("job_url", "")))
        if target_url and current_url != target_url:
            continue
        selected.append(item)
        if max_tasks > 0 and len(selected) >= max_tasks:
            break
    return selected


def normalize_jobs_url(url: str) -> str:
    if not url:
        return "https://www.zhipin.com/web/geek/jobs"
    parsed = urlparse(url)
    path = parsed.path or "/web/geek/jobs"
    if not path.startswith("/web/geek/jobs"):
        path = "/web/geek/jobs"
    return urlunparse((parsed.scheme or "https", parsed.netloc or "www.zhipin.com", path, "", "", ""))


def page_contains_browser_check(driver) -> bool:
    try:
        source = driver.page_source or ""
    except Exception:
        return False
    return "browser-check.js" in source or "BOSSֱƸ" in source


def jobs_page_has_cards(driver) -> bool:
    from selenium.webdriver.common.by import By

    try:
        if "/web/geek/jobs" not in driver.current_url or "_security_check" in driver.current_url:
            return False
    except Exception:
        return False

    try:
        cards = driver.find_elements(By.CSS_SELECTOR, "li.job-card-box")
    except Exception:
        return False
    return len(cards) > 0


def wait_for_jobs_page_ready(driver, timeout: float = 12.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if jobs_page_has_cards(driver):
            return True
        time.sleep(0.5)
    return False


def safe_navigate(driver, url: str, timeout: float = 15.0) -> None:
    try:
        driver.set_page_load_timeout(timeout)
    except Exception:
        pass

    try:
        driver.get(url)
    except Exception:
        try:
            driver.execute_script("window.stop();")
        except Exception:
            pass


def ensure_jobs_page(driver, jobs_url: str) -> None:
    normalized_jobs_url = normalize_jobs_url(jobs_url)
    fallback_jobs_url = "https://www.zhipin.com/web/geek/jobs"

    if jobs_page_has_cards(driver):
        return

    for candidate_url in [normalized_jobs_url, fallback_jobs_url]:
        safe_navigate(driver, candidate_url, timeout=12.0)
        if wait_for_jobs_page_ready(driver, timeout=12.0):
            return

    current_url = ""
    try:
        current_url = driver.current_url
    except Exception:
        pass
    if page_contains_browser_check(driver):
        raise RuntimeError(
            "Boss results page fell back to browser-check mode. Refresh the result page in Chrome and retry."
        )
    raise RuntimeError(f"Boss results page did not finish loading: {current_url or normalized_jobs_url}")


def return_to_jobs_page(driver, jobs_url: str) -> None:
    normalized_jobs_url = normalize_jobs_url(jobs_url)

    if jobs_page_has_cards(driver):
        return

    try:
        driver.back()
    except Exception:
        pass
    time.sleep(1.5)
    if wait_for_jobs_page_ready(driver, timeout=8.0):
        return

    safe_navigate(driver, normalized_jobs_url, timeout=12.0)
    if wait_for_jobs_page_ready(driver, timeout=12.0):
        return

    try:
        wait_for_boss_job_cards(driver, timeout=8.0)
        if jobs_page_has_cards(driver):
            return
    except Exception:
        pass

    if page_contains_browser_check(driver):
        raise RuntimeError("Boss results page needs a manual refresh because browser-check interrupted navigation.")

    raise RuntimeError("Unable to return to the Boss jobs page.")


def detail_box_snapshot(driver) -> tuple[str, str]:
    from selenium.webdriver.common.by import By

    try:
        detail_box = driver.find_element(By.CSS_SELECTOR, ".job-detail-box")
    except Exception:
        return "", ""

    detail_text = normalize_text(detail_box.text)
    try:
        detail_title = normalize_text(detail_box.find_element(By.CSS_SELECTOR, ".job-detail-info .job-name").text)
    except Exception:
        detail_title = ""
    return detail_title, detail_text


def page_text(driver) -> str:
    from selenium.webdriver.common.by import By

    try:
        bodies = driver.find_elements(By.TAG_NAME, "body")
        if not bodies:
            return ""
        return normalize_text(bodies[0].text)
    except Exception:
        return ""


def click_element(driver, element, strategy: str) -> None:
    from selenium.webdriver.common.action_chains import ActionChains

    driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", element)
    time.sleep(0.2)

    if strategy == "native":
        element.click()
        return
    if strategy == "action":
        ActionChains(driver).move_to_element(element).pause(0.15).click(element).perform()
        return
    if strategy == "js":
        driver.execute_script("arguments[0].click();", element)
        return
    raise ValueError(f"Unsupported click strategy: {strategy}")


def wait_for_job_detail(
    driver,
    expected_title: str,
    expected_company: str,
    previous_snapshot: tuple[str, str],
    timeout: float = 4.0,
) -> bool:
    normalized_expected_title = normalize_text(expected_title)
    normalized_expected_company = normalize_text(expected_company)
    previous_title, previous_text = previous_snapshot
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            current_title, current_text = detail_box_snapshot(driver)
        except Exception:
            current_title, current_text = "", ""

        if normalized_expected_title and current_title == normalized_expected_title:
            if not normalized_expected_company or normalized_expected_company in current_text:
                return True

        if normalized_expected_company and normalized_expected_company in current_text:
            if not normalized_expected_title or normalized_expected_title in current_text:
                return True

        if current_text and current_text != previous_text and current_title != previous_title:
            return True

        time.sleep(0.35)
    return False


def current_page_matches_job(driver, expected_title: str, expected_company: str) -> bool:
    normalized_expected_title = normalize_text(expected_title)
    normalized_expected_company = normalize_text(expected_company)
    text = page_text(driver)
    if not text:
        return False
    if normalized_expected_title and normalized_expected_title not in text:
        return False
    if normalized_expected_company and normalized_expected_company not in text:
        return False
    return True


def card_matches_task(card, target_url: str, company_name: str, title: str) -> bool:
    from selenium.webdriver.common.by import By

    normalized_target = normalize_job_url(target_url)
    normalized_company = normalize_text(company_name)
    normalized_title = normalize_text(title)

    try:
        title_node = card.find_element(By.CSS_SELECTOR, ".job-name")
        href = normalize_job_url(title_node.get_attribute("href") or "")
        card_title = normalize_text(title_node.text)
    except Exception:
        href = ""
        card_title = ""

    try:
        company_node = card.find_element(By.CSS_SELECTOR, ".boss-name")
        card_company = normalize_text(company_node.text)
    except Exception:
        card_company = ""

    if normalized_target and href == normalized_target:
        return True
    if normalized_company and card_company == normalized_company:
        if not normalized_title or not card_title or card_title == normalized_title:
            return True
    if normalized_title and card_title == normalized_title:
        if not normalized_company or not card_company or card_company == normalized_company:
            return True
    return False


def find_card_index_for_task(
    driver,
    task: dict[str, Any],
    idle_rounds: int,
    scroll_pause: float,
    scroll_timeout: float,
) -> int | None:
    from selenium.webdriver.common.by import By

    target_url = normalize_job_url(str(task.get("job_url", "")))
    company_name = str(task.get("company_name", ""))
    title = str(task.get("title", ""))
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.8)

    stalled_rounds = 0
    while True:
        cards = driver.find_elements(By.CSS_SELECTOR, "li.job-card-box")
        for index in range(len(cards)):
            cards = driver.find_elements(By.CSS_SELECTOR, "li.job-card-box")
            if index >= len(cards):
                break
            try:
                if card_matches_task(cards[index], target_url=target_url, company_name=company_name, title=title):
                    return index
            except Exception:
                continue

        if scroll_boss_job_list(driver, pause_seconds=scroll_pause, timeout=scroll_timeout):
            stalled_rounds = 0
            continue

        stalled_rounds += 1
        if stalled_rounds >= max(1, idle_rounds):
            return None


def open_job_detail(
    driver,
    card_index: int,
    expected_title: str = "",
    expected_company: str = "",
    expected_url: str = "",
) -> None:
    from selenium.webdriver.common.by import By

    cards = driver.find_elements(By.CSS_SELECTOR, "li.job-card-box")
    if card_index >= len(cards):
        raise IndexError(f"job card index out of range: {card_index}")

    card = cards[card_index]
    previous_snapshot = detail_box_snapshot(driver)

    targets: list[Any] = []
    for selector in (".job-name", ".job-info"):
        try:
            candidate = card.find_element(By.CSS_SELECTOR, selector)
        except Exception:
            continue
        if candidate not in targets:
            targets.append(candidate)
    targets.append(card)

    last_error: Exception | None = None
    for target in targets:
        for strategy in ("native", "action", "js"):
            try:
                click_element(driver, target, strategy)
                if wait_for_job_detail(
                    driver,
                    expected_title=expected_title,
                    expected_company=expected_company,
                    previous_snapshot=previous_snapshot,
                    timeout=4.0,
                ):
                    return
            except Exception as exc:
                last_error = exc
                continue

    current_title, current_text = detail_box_snapshot(driver)
    if expected_url:
        safe_navigate(driver, expected_url, timeout=12.0)
        if "/job_detail/" in driver.current_url and not page_contains_browser_check(driver):
            if current_page_matches_job(driver, expected_title=expected_title, expected_company=expected_company):
                return

    if last_error:
        raise RuntimeError(
            f"Unable to activate job detail for '{expected_title or expected_company}'. "
            f"Current detail: {current_title or current_text[:80]}"
        ) from last_error
    raise RuntimeError(f"Unable to activate job detail for '{expected_title or expected_company}'.")


def wait_for_chat_page(driver, previous_handles: set[str], timeout: float = 12.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if "/web/geek/chat" in driver.current_url:
                return True
        except Exception:
            pass

        try:
            current_handles = driver.window_handles
        except Exception:
            current_handles = []
        for handle in current_handles:
            if handle not in previous_handles:
                try:
                    driver.switch_to.window(handle)
                except Exception:
                    continue
                try:
                    if "/web/geek/chat" in driver.current_url:
                        return True
                except Exception:
                    continue

        if chat_input_available(driver):
            return True

        time.sleep(0.35)
    return False


def open_chat_from_detail(driver) -> None:
    from selenium.webdriver.common.by import By

    if "/web/geek/chat" in driver.current_url:
        return

    button_candidates: list[Any] = []
    for selector in (
        ".job-detail-box .op-btn.op-btn-chat",
        ".job-detail-box [ka*='chat']",
        ".op-btn.op-btn-chat",
        "[ka*='chat']",
    ):
        for candidate in driver.find_elements(By.CSS_SELECTOR, selector):
            try:
                if candidate.is_displayed():
                    button_candidates.append(candidate)
            except Exception:
                continue

    if not button_candidates:
        xpath = (
            "//*[self::a or self::button or self::div or self::span]"
            "[contains(normalize-space(), '立即沟通') or contains(normalize-space(), '聊一聊')]"
        )
        for candidate in driver.find_elements(By.XPATH, xpath):
            try:
                if candidate.is_displayed():
                    button_candidates.append(candidate)
            except Exception:
                continue

    if not button_candidates:
        raise RuntimeError("Could not find the Boss chat button in the job detail panel.")

    previous_handles = set(driver.window_handles)
    last_error: Exception | None = None
    for button in button_candidates:
        for strategy in ("native", "action", "js"):
            try:
                click_element(driver, button, strategy)
                if wait_for_chat_page(driver, previous_handles, timeout=12.0):
                    return
            except Exception as exc:
                last_error = exc
                continue

    if last_error:
        raise RuntimeError("Failed to open the Boss chat page from the detail panel.") from last_error
    raise RuntimeError("Failed to open the Boss chat page from the detail panel.")


def find_chat_input(driver):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    selectors = [
        "#chat-input",
        "div.chat-input[contenteditable='true']",
        "[contenteditable='true'][id='chat-input']",
        "[contenteditable='true']",
        "textarea",
    ]

    def locate(current):
        for selector in selectors:
            matches = current.find_elements(By.CSS_SELECTOR, selector)
            for candidate in matches:
                try:
                    if candidate.is_displayed():
                        return candidate
                except Exception:
                    continue
        return False

    return WebDriverWait(driver, 20).until(locate)


def chat_input_available(driver) -> bool:
    from selenium.webdriver.common.by import By

    selectors = [
        "#chat-input",
        "div.chat-input[contenteditable='true']",
        "[contenteditable='true'][id='chat-input']",
        "[contenteditable='true']",
        "textarea",
    ]
    for selector in selectors:
        for candidate in driver.find_elements(By.CSS_SELECTOR, selector):
            try:
                if candidate.is_displayed():
                    return True
            except Exception:
                continue
    return False


def read_editor_text(driver, element) -> str:
    return driver.execute_script(
        """
        const el = arguments[0];
        if (!el) return '';
        if (typeof el.value === 'string') return el.value;
        return (el.innerText || el.textContent || '').trim();
        """,
        element,
    )


def collect_message_item_texts(driver) -> list[str]:
    from selenium.webdriver.common.by import By

    texts: list[str] = []
    for item in driver.find_elements(By.CSS_SELECTOR, ".im-list .message-item"):
        try:
            text = normalize_text(item.text)
        except Exception:
            continue
        if text:
            texts.append(text)
    return texts


def find_matching_message_after(before_texts: list[str], after_texts: list[str], drafted_message: str) -> bool:
    drafted_norm = normalize_text(drafted_message)
    if not drafted_norm:
        return False

    probe = drafted_norm[: min(24, len(drafted_norm))]
    previous = before_texts[:]
    for text in after_texts:
        if previous and text == previous[0]:
            previous.pop(0)
            continue
        if probe and probe in normalize_text(text):
            return True
    return False


def write_chat_message(driver, element, message: str) -> None:
    from selenium.webdriver.common.keys import Keys

    driver.execute_script(
        """
        const el = arguments[0];
        if (!el) return;
        el.focus();
        if (el.isContentEditable) {
            el.innerHTML = '';
        } else if (typeof el.value === 'string') {
            el.value = '';
        }
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        """,
        element,
    )

    element.click()
    try:
        element.send_keys(Keys.CONTROL, "a")
        element.send_keys(Keys.DELETE)
    except Exception:
        pass

    lines = message.splitlines() or [message]
    for index, line in enumerate(lines):
        if line:
            element.send_keys(line)
        if index < len(lines) - 1:
            element.send_keys(Keys.SHIFT, Keys.ENTER)

    written = read_editor_text(driver, element)
    if normalize_text(written) == normalize_text(message):
        return

    driver.execute_script(
        """
        const el = arguments[0];
        const text = arguments[1];
        el.focus();
        if (el.isContentEditable) {
            el.innerHTML = '';
            const lines = text.split('\\n');
            lines.forEach((line, idx) => {
                if (idx > 0) {
                    el.appendChild(document.createElement('div'));
                }
                const target = idx > 0 ? el.lastChild : el;
                if (line) {
                    target.appendChild(document.createTextNode(line));
                } else {
                    target.appendChild(document.createElement('br'));
                }
            });
        } else if (typeof el.value === 'string') {
            el.value = text;
        }
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        """,
        element,
        message,
    )


def send_chat_message(driver, element) -> None:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys

    send_selectors = [
        "button.send-btn",
        "a.send-btn",
        ".btn-send",
        "[ka*='send']",
    ]
    for selector in send_selectors:
        matches = driver.find_elements(By.CSS_SELECTOR, selector)
        for candidate in matches:
            try:
                if candidate.is_displayed():
                    driver.execute_script("arguments[0].click();", candidate)
                    return
            except Exception:
                continue

    xpath = "//*[self::button or self::a or self::div or self::span][normalize-space()='发送']"
    matches = driver.find_elements(By.XPATH, xpath)
    for candidate in matches:
        try:
            if candidate.is_displayed():
                driver.execute_script("arguments[0].click();", candidate)
                return
        except Exception:
            continue

    element.click()
    element.send_keys(Keys.ENTER)


def wait_for_message_commit(
    driver,
    element,
    drafted_message: str,
    before_messages: list[str],
    timeout_seconds: float = 0.0,
) -> tuple[str, str]:
    started = time.time()
    grace_empty_since: float | None = None

    while True:
        current_input = normalize_text(read_editor_text(driver, element))
        current_messages = collect_message_item_texts(driver)

        if find_matching_message_after(before_messages, current_messages, drafted_message):
            return "confirmed_sent", "Greeting was sent manually from the web chat page."

        if not current_input:
            if grace_empty_since is None:
                grace_empty_since = time.time()
            elif time.time() - grace_empty_since >= 1.5:
                return "cleared_skipped", "Chat input was cleared without detecting a sent message, so this task was skipped."
        else:
            grace_empty_since = None

        if timeout_seconds > 0 and time.time() - started >= timeout_seconds:
            return "confirm_timeout", "Timed out while waiting for manual confirmation in the browser."

        time.sleep(0.5)


def normalize_text(value: str) -> str:
    return " ".join((value or "").split()).strip()


def handle_task(
    driver,
    task: dict[str, Any],
    jobs_url: str,
    send_mode: str,
    idle_rounds: int,
    scroll_pause: float,
    scroll_timeout: float,
    confirm_timeout: float,
) -> ExecutionResult:
    target_url = normalize_job_url(str(task.get("job_url", "")))
    company_name = str(task.get("company_name", ""))

    try:
        ensure_jobs_page(driver, jobs_url)
        index = find_card_index_for_task(
            driver,
            task=task,
            idle_rounds=idle_rounds,
            scroll_pause=scroll_pause,
            scroll_timeout=scroll_timeout,
        )
        if index is None:
            return ExecutionResult(
                job_url=target_url,
                company_name=company_name,
                send_mode=send_mode,
                status="not_found_in_results",
                note="Current jobs page did not expose this job card after scrolling to the end.",
                timestamp=time.time(),
            )

        open_job_detail(
            driver,
            index,
            expected_title=str(task.get("title", "")),
            expected_company=company_name,
            expected_url=target_url,
        )
        open_chat_from_detail(driver)
        chat_input = find_chat_input(driver)
        before_messages = collect_message_item_texts(driver)
        write_chat_message(driver, chat_input, str(task.get("final_greeting_text", "")).strip())

        if send_mode == "send":
            send_chat_message(driver, chat_input)
            time.sleep(1.0)
            status = "sent"
            note = "Greeting sent from the web chat page."
        elif send_mode == "confirm":
            status, note = wait_for_message_commit(
                driver,
                element=chat_input,
                drafted_message=str(task.get("final_greeting_text", "")).strip(),
                before_messages=before_messages,
                timeout_seconds=confirm_timeout,
            )
        else:
            status = "draft_ready"
            note = "Greeting filled into the chat box and left unsent for manual review."

        return ExecutionResult(
            job_url=target_url,
            company_name=company_name,
            send_mode=send_mode,
            status=status,
            note=note,
            timestamp=time.time(),
        )
    except Exception as exc:
        return ExecutionResult(
            job_url=target_url,
            company_name=company_name,
            send_mode=send_mode,
            status="failed",
            note=f"{type(exc).__name__}: {exc!r}",
            timestamp=time.time(),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute Boss delivery tasks by opening chat, filling greetings, and optionally sending them.")
    parser.add_argument("--tasks", required=True, help="Path to a phase-1 JSON output or a JSON array of delivery tasks.")
    parser.add_argument("--driver-path", default="", help="Optional path to chromedriver.")
    parser.add_argument("--debugger-address", default="127.0.0.1:9222", help="Existing browser debugging address, for example 127.0.0.1:9222.")
    parser.add_argument("--browser-binary", default="", help="Optional path to chrome.exe.")
    parser.add_argument("--jobs-url", default="", help="Optional Boss jobs result URL to return to between sends. Defaults to the current jobs page or https://www.zhipin.com/web/geek/jobs.")
    parser.add_argument("--task-status", default="pending_confirmation", help="Only execute tasks with this status.")
    parser.add_argument("--job-url", default="", help="Only execute the task that matches this normalized job URL.")
    parser.add_argument("--max-tasks", type=int, default=0, help="Maximum number of tasks to execute. Defaults to all matching tasks.")
    parser.add_argument("--send-mode", choices=["draft", "confirm", "send"], default="draft", help="draft fills one chat box and stops; confirm waits for you to send manually in the browser and then advances; send actually sends the greeting.")
    parser.add_argument("--idle-rounds", type=int, default=3, help="Stop card lookup after this many scroll rounds without new jobs.")
    parser.add_argument("--scroll-pause", type=float, default=1.2, help="Seconds to wait between scroll checks while locating a target job card.")
    parser.add_argument("--scroll-timeout", type=float, default=8.0, help="Maximum seconds to wait for newly loaded jobs after each bottom scroll.")
    parser.add_argument("--confirm-timeout", type=float, default=0.0, help="Optional timeout in seconds while waiting for manual browser confirmation. Use 0 to wait indefinitely.")
    parser.add_argument("--output", default="job-apply-assistant/output/delivery-execution.json", help="Path to the execution report JSON.")
    args = parser.parse_args()

    tasks = load_delivery_tasks(
        path=Path(args.tasks),
        required_status=args.task_status,
        job_url=args.job_url,
        max_tasks=args.max_tasks,
    )
    if not tasks:
        raise SystemExit("No delivery tasks matched the current filters.")

    if args.send_mode == "draft" and len(tasks) > 1:
        tasks = tasks[:1]

    driver = attach_chrome_driver(
        driver_path=args.driver_path,
        debugger_address=args.debugger_address,
        browser_binary=args.browser_binary,
    )
    try:
        current_jobs_url = args.jobs_url
        if not current_jobs_url:
            current_jobs_url = driver.current_url if "/web/geek/jobs" in driver.current_url else "https://www.zhipin.com/web/geek/jobs"
        current_jobs_url = normalize_jobs_url(current_jobs_url)

        results: list[ExecutionResult] = []
        for index, task in enumerate(tasks):
            result = handle_task(
                driver,
                task=task,
                jobs_url=current_jobs_url,
                send_mode=args.send_mode,
                idle_rounds=args.idle_rounds,
                scroll_pause=args.scroll_pause,
                scroll_timeout=args.scroll_timeout,
                confirm_timeout=args.confirm_timeout,
            )
            results.append(result)
            print(f"[{index + 1}/{len(tasks)}] {result.company_name or result.job_url} -> {result.status}")
            if args.send_mode == "draft":
                break
            if result.status in {"confirm_timeout", "failed"}:
                break
            return_to_jobs_page(driver, current_jobs_url)

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                {
                    "send_mode": args.send_mode,
                    "jobs_url": current_jobs_url,
                    "results": [asdict(item) for item in results],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Execution report: {output_path.resolve()}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
