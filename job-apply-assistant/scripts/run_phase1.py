from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = {
    "resume_source": str((Path(__file__).resolve().parents[2] / "resume.pdf").resolve()),
    "resume_patch": "",
    "platforms": ["boss", "liepin"],
    "job_keywords": ["B端数据产品经理", "大数据产品经理", "数据中台", "数仓"],
    "exclude_keywords": [],
    "city": "北京",
    "salary_range": "20k-30k",
    "greeting_style": "专业克制",
    "match_threshold": 80,
}

DOMAIN_KEYWORDS = {
    "数据中台": ["数据中台", "中台", "数据平台", "数据服务", "数据门户"],
    "数仓": ["数仓", "数据仓库", "维度建模", "数据模型", "etl", "elt"],
    "指标体系": ["指标体系", "指标口径", "指标平台", "口径管理"],
    "标签体系": ["标签体系", "用户标签", "画像标签"],
    "数据治理": ["数据治理", "主数据", "数据质量", "元数据"],
    "BI报表": ["bi", "报表", "看板", "自助分析"],
    "权限资产": ["权限", "数据资产", "资产目录", "数据权限"],
}

RESPONSIBILITY_KEYWORDS = {
    "需求分析": ["需求分析", "需求调研", "业务调研", "需求拆解"],
    "方案设计": ["方案设计", "产品方案", "原型", "prd"],
    "平台建设": ["平台建设", "平台化", "中台建设", "产品规划"],
    "推进协同": ["跨团队", "协同", "推进", "对接研发", "对接业务"],
    "上线验收": ["上线", "验收", "迭代", "落地"],
    "owner意识": ["owner", "负责", "主导", "牵头"],
}

TECH_KEYWORDS = {
    "SQL": ["sql"],
    "建模": ["建模", "维度建模", "事实表", "维表"],
    "ETL": ["etl", "elt"],
    "离线实时": ["离线", "实时", "实时数仓"],
    "指标口径": ["口径", "指标", "指标口径"],
    "资产权限": ["数据资产", "权限", "数据权限"],
}

BAD_FIT_KEYWORDS = [
    "数据分析师",
    "商业分析师",
    "项目经理",
    "实施顾问",
    "销售",
    "售前",
]


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def lowered(value: str) -> str:
    return normalize_text(value).lower()


def uniq(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def count_matches(text: str, terms: list[str]) -> int:
    text_lower = lowered(text)
    return sum(1 for term in terms if term.lower() in text_lower)


def collect_tags(text: str, mapping: dict[str, list[str]]) -> list[str]:
    tags: list[str] = []
    text_lower = lowered(text)
    for tag, terms in mapping.items():
        if any(term.lower() in text_lower for term in terms):
            tags.append(tag)
    return tags


def parse_k(value: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*[kK]", value or "")
    if match:
        return float(match.group(1))
    plain = re.search(r"(\d+(?:\.\d+)?)", value or "")
    if plain:
        return float(plain.group(1))
    return None


def parse_salary_range(value: str) -> tuple[float | None, float | None]:
    text = normalize_text(value)
    if not text:
        return None, None
    parts = re.split(r"\s*[-~至]\s*", text)
    if len(parts) >= 2:
        return parse_k(parts[0]), parse_k(parts[1])
    one = parse_k(text)
    return one, one


def read_text_file(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("text", b"", 0, 1, f"unsupported encoding for {path}")


def read_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PDF resume parsing requires the 'pypdf' package. "
            "Install it with 'python -m pip install --user pypdf'."
        ) from exc
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def read_resume_source(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return read_text_file(path)
    if suffix == ".json":
        payload = json.loads(read_text_file(path))
        return normalize_text(json.dumps(payload, ensure_ascii=False))
    if suffix == ".pdf":
        return read_pdf_text(path)
    raise ValueError(f"Unsupported resume format: {path.suffix}")


@dataclass
class CandidateProfile:
    resume_source: str
    raw_text: str
    target_directions: list[str]
    domain_tags: list[str]
    responsibility_tags: list[str]
    technical_tags: list[str]
    years_of_experience: str | None
    highlighted_evidence: list[str]


@dataclass
class JobPosting:
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


@dataclass
class MatchBreakdown:
    direction_match: int
    domain_match: int
    responsibility_match: int
    technical_match: int
    industry_match: int
    resume_tellability: int

    @property
    def total(self) -> int:
        return (
            self.direction_match
            + self.domain_match
            + self.responsibility_match
            + self.technical_match
            + self.industry_match
            + self.resume_tellability
        )


@dataclass
class MatchResult:
    total_score: int
    sub_scores: MatchBreakdown
    recommendation: str
    fit_reasons: list[str]
    strengths: list[str]
    risks: list[str]
    resume_note: str
    recruiter_greeting: str


@dataclass
class DeliveryTask:
    platform: str
    job_id: str
    job_url: str
    company_name: str
    title: str
    recruiter_info: str
    recommended_resume_version: str
    final_greeting_text: str
    status: str
    action_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class AssessmentCard:
    company_info: dict[str, str]
    role_info: dict[str, str]
    jd_summary: list[str]
    total_score: int
    sub_scores: dict[str, int]
    recommendation: str
    fit_reasons: list[str]
    strengths: list[str]
    risks: list[str]
    resume_note: str
    recruiter_greeting: str
    status: str


def build_candidate_profile(resume_source: Path, resume_patch: str) -> CandidateProfile:
    raw_text = normalize_text(read_resume_source(resume_source))
    merged = raw_text
    if resume_patch:
        merged = f"{merged}\n{normalize_text(resume_patch)}"

    target_directions = uniq(
        collect_tags(merged, {"B端数据产品": ["b端", "数据产品", "大数据产品"], "数据中台/数仓": ["数据中台", "数仓", "数据仓库"]})
    )
    domain_tags = uniq(collect_tags(merged, DOMAIN_KEYWORDS))
    responsibility_tags = uniq(collect_tags(merged, RESPONSIBILITY_KEYWORDS))
    technical_tags = uniq(collect_tags(merged, TECH_KEYWORDS))
    years = None
    years_match = re.search(r"(\d{1,2})\s*年", merged)
    if years_match:
        years = years_match.group(1)

    evidence_pool = uniq(domain_tags + responsibility_tags + technical_tags)
    highlighted_evidence = evidence_pool[:6]

    return CandidateProfile(
        resume_source=str(resume_source),
        raw_text=merged,
        target_directions=target_directions,
        domain_tags=domain_tags,
        responsibility_tags=responsibility_tags,
        technical_tags=technical_tags,
        years_of_experience=years,
        highlighted_evidence=highlighted_evidence,
    )


def load_jobs(path: Path) -> list[JobPosting]:
    payload = json.loads(read_text_file(path))
    jobs = payload.get("jobs", payload)
    result: list[JobPosting] = []
    for item in jobs:
        jd_text = normalize_text(item.get("jd_text", ""))
        summary = item.get("jd_summary") or summarize_jd(jd_text)
        requirements = item.get("requirements") or []
        bonus_items = item.get("bonus_items") or []
        result.append(
            JobPosting(
                platform=item["platform"],
                job_id=str(item["job_id"]),
                url=item["url"],
                company_name=item["company_name"],
                company_info=item.get("company_info", ""),
                recruiter_info=item.get("recruiter_info", ""),
                title=item["title"],
                city=item.get("city", ""),
                salary=item.get("salary", ""),
                experience_requirement=item.get("experience_requirement", ""),
                education_requirement=item.get("education_requirement", ""),
                jd_text=jd_text,
                jd_summary=summary,
                requirements=requirements,
                bonus_items=bonus_items,
            )
        )
    return result


def summarize_jd(jd_text: str) -> list[str]:
    chunks = re.split(r"[；;。.\n]+", jd_text)
    cleaned = [normalize_text(chunk) for chunk in chunks if normalize_text(chunk)]
    return cleaned[:3]


def passes_hard_filters(job: JobPosting, config: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    target_city = normalize_text(config.get("city", ""))
    if target_city and target_city not in normalize_text(job.city):
        reasons.append(f"city_mismatch:{job.city}")

    user_min, user_max = parse_salary_range(str(config.get("salary_range", "")))
    job_min, job_max = parse_salary_range(job.salary)
    if user_min is not None and job_max is not None and job_max < user_min:
        reasons.append(f"salary_below_floor:{job.salary}")
    if user_max is not None and job_min is not None and job_min > user_max + 10:
        reasons.append(f"salary_far_above_target:{job.salary}")

    target_text = f"{job.title} {job.jd_text}"
    exclude_keywords = config.get("exclude_keywords", []) or []
    for word in exclude_keywords:
        if word and word.lower() in lowered(target_text):
            reasons.append(f"excluded_keyword:{word}")

    if any(word.lower() in lowered(job.title) for word in BAD_FIT_KEYWORDS):
        reasons.append("bad_fit_title")

    return not reasons, reasons


def clamp(value: int, lower: int, upper: int) -> int:
    return max(lower, min(value, upper))


def score_job(profile: CandidateProfile, job: JobPosting) -> MatchResult:
    title_and_jd = f"{job.title} {job.jd_text}"
    direction_raw = count_matches(title_and_jd, ["数据产品", "大数据产品", "数据中台", "数仓", "数据平台", "指标体系"])
    direction_score = clamp(direction_raw * 4 + 4, 0, 20)
    if any(word.lower() in lowered(job.title) for word in BAD_FIT_KEYWORDS):
        direction_score = max(0, direction_score - 8)

    domain_job_tags = collect_tags(title_and_jd, DOMAIN_KEYWORDS)
    domain_overlap = len(set(profile.domain_tags) & set(domain_job_tags))
    domain_score = clamp(domain_overlap * 5 + (5 if domain_job_tags else 0), 0, 20)

    responsibility_job_tags = collect_tags(title_and_jd, RESPONSIBILITY_KEYWORDS)
    responsibility_overlap = len(set(profile.responsibility_tags) & set(responsibility_job_tags))
    responsibility_score = clamp(responsibility_overlap * 4 + (4 if responsibility_job_tags else 0), 0, 20)

    tech_job_tags = collect_tags(title_and_jd, TECH_KEYWORDS)
    tech_overlap = len(set(profile.technical_tags) & set(tech_job_tags))
    technical_score = clamp(tech_overlap * 3 + (3 if tech_job_tags else 0), 0, 15)

    industry_score = 5
    if any(term in title_and_jd for term in ["金融", "供应链", "零售", "制造", "企业服务", "to b", "toB", "B端"]):
        industry_score = 8
    if "B端" in title_and_jd or "企业" in title_and_jd:
        industry_score = 10

    tellability_basis = len(profile.highlighted_evidence) + domain_overlap + responsibility_overlap
    tellability_score = clamp(tellability_basis * 2 + 3, 0, 15)

    breakdown = MatchBreakdown(
        direction_match=direction_score,
        domain_match=domain_score,
        responsibility_match=responsibility_score,
        technical_match=technical_score,
        industry_match=industry_score,
        resume_tellability=tellability_score,
    )

    total_score = breakdown.total
    if total_score >= 80:
        recommendation = "优先沟通"
    elif total_score >= 70:
        recommendation = "可沟通"
    elif total_score >= 60:
        recommendation = "保留观察"
    else:
        recommendation = "不建议投"

    fit_reasons = build_fit_reasons(profile, domain_job_tags, responsibility_job_tags, tech_job_tags, recommendation)
    strengths = build_strengths(profile, domain_job_tags, responsibility_job_tags, tech_job_tags)
    risks = build_risks(profile, job, domain_job_tags, responsibility_job_tags, tech_job_tags)
    resume_note = "当前先使用 base 简历；如果进入高优先级投递，建议把最贴近该岗位的数仓/数据中台经历前置。"
    recruiter_greeting = build_greeting(profile, job)

    return MatchResult(
        total_score=total_score,
        sub_scores=breakdown,
        recommendation=recommendation,
        fit_reasons=fit_reasons,
        strengths=strengths,
        risks=risks,
        resume_note=resume_note,
        recruiter_greeting=recruiter_greeting,
    )


def build_fit_reasons(
    profile: CandidateProfile,
    domain_job_tags: list[str],
    responsibility_job_tags: list[str],
    tech_job_tags: list[str],
    recommendation: str,
) -> list[str]:
    reasons: list[str] = []
    overlap_domains = list(set(profile.domain_tags) & set(domain_job_tags))
    overlap_resp = list(set(profile.responsibility_tags) & set(responsibility_job_tags))
    overlap_tech = list(set(profile.technical_tags) & set(tech_job_tags))
    if overlap_domains:
        reasons.append(f"你的经历和岗位强调的 {', '.join(overlap_domains[:3])} 有直接重合。")
    if overlap_resp:
        reasons.append(f"岗位看重的 {', '.join(overlap_resp[:3])}，你当前简历可以支撑。")
    if overlap_tech:
        reasons.append(f"JD 里的技术语境如 {', '.join(overlap_tech[:3])}，你具备对话基础。")
    if not reasons:
        reasons.append("岗位方向有部分重合，但需要更谨慎确认实际职责。")
    if recommendation == "优先沟通":
        reasons.append("从回复率角度看，这类岗位值得投入沟通成本。")
    return reasons[:4]


def build_strengths(
    profile: CandidateProfile,
    domain_job_tags: list[str],
    responsibility_job_tags: list[str],
    tech_job_tags: list[str],
) -> list[str]:
    strengths: list[str] = []
    if domain_job_tags:
        strengths.append(f"你对 {', '.join(domain_job_tags[:3])} 这类数据产品语境比较熟。")
    if responsibility_job_tags:
        strengths.append(f"岗位需要的 {', '.join(responsibility_job_tags[:3])}，你有可讲经历。")
    if tech_job_tags:
        strengths.append(f"你能直接和招聘方沟通 {', '.join(tech_job_tags[:3])} 这类话题。")
    if not strengths:
        strengths.append("岗位方向和你的目标方向存在基础重合。")
    return strengths[:3]


def build_risks(
    profile: CandidateProfile,
    job: JobPosting,
    domain_job_tags: list[str],
    responsibility_job_tags: list[str],
    tech_job_tags: list[str],
) -> list[str]:
    risks: list[str] = []
    missing_domains = [tag for tag in domain_job_tags if tag not in profile.domain_tags]
    missing_resp = [tag for tag in responsibility_job_tags if tag not in profile.responsibility_tags]
    missing_tech = [tag for tag in tech_job_tags if tag not in profile.technical_tags]
    if missing_domains:
        risks.append(f"JD 提到的 {', '.join(missing_domains[:2])} 在当前简历里不够显性。")
    if missing_resp:
        risks.append(f"如果招聘方特别看重 {', '.join(missing_resp[:2])}，可能会影响首轮判断。")
    if missing_tech:
        risks.append(f"技术语境中的 {', '.join(missing_tech[:2])} 需要沟通时谨慎展开。")
    if "行业经验" in job.jd_text and "行业" not in profile.raw_text:
        risks.append("JD 可能看重特定行业经验，这部分需要现场补充说明。")
    if not risks:
        risks.append("当前没有明显硬伤，主要关注招聘方的具体业务场景要求。")
    return risks[:3]


def build_greeting(profile: CandidateProfile, job: JobPosting) -> str:
    focus = job.jd_summary[0] if job.jd_summary else job.title
    focus = focus[:36]
    evidence = "、".join(profile.highlighted_evidence[:2]) if profile.highlighted_evidence else "数据产品相关项目"
    return (
        f"您好，看了下这个岗位，和我过往做 {evidence} 相关产品的经历比较贴近。"
        f"尤其您这边提到的“{focus}”，我之前有过相近的需求抽象和推进落地经验。"
        "如果方便的话，想进一步了解下这个岗位当前最核心的建设重点。"
    )


def build_card(job: JobPosting, match: MatchResult) -> AssessmentCard:
    return AssessmentCard(
        company_info={
            "company_name": job.company_name,
            "company_info": job.company_info,
            "recruiter_info": job.recruiter_info,
        },
        role_info={
            "platform": job.platform,
            "title": job.title,
            "city": job.city,
            "salary": job.salary,
            "experience_requirement": job.experience_requirement,
            "education_requirement": job.education_requirement,
            "url": job.url,
        },
        jd_summary=job.jd_summary,
        total_score=match.total_score,
        sub_scores=asdict(match.sub_scores),
        recommendation=match.recommendation,
        fit_reasons=match.fit_reasons,
        strengths=match.strengths,
        risks=match.risks,
        resume_note=match.resume_note,
        recruiter_greeting=match.recruiter_greeting,
        status="待确认",
    )


def build_delivery_task(job: JobPosting, match: MatchResult) -> DeliveryTask:
    return DeliveryTask(
        platform=job.platform,
        job_id=job.job_id,
        job_url=job.url,
        company_name=job.company_name,
        title=job.title,
        recruiter_info=job.recruiter_info,
        recommended_resume_version="base",
        final_greeting_text=match.recruiter_greeting,
        status="pending_confirmation",
        action_payload={
            "open_job_url": job.url,
            "fill_greeting": True,
            "select_resume_version": "base",
            "send_requires_confirmation": True,
        },
    )


def render_text_card(card: AssessmentCard) -> str:
    role = card.role_info
    lines = [
        f"【岗位】{card.company_info['company_name']} - {role['title']}",
        f"【基础信息】{role['city']} / {role['salary']} / {role['experience_requirement']} / {role['platform']}",
        "【JD摘要】",
    ]
    lines.extend(f"- {item}" for item in card.jd_summary)
    lines.append(f"【匹配度】{card.total_score}/100，{card.recommendation}")
    lines.append("【匹配原因】")
    lines.extend(f"- {item}" for item in card.fit_reasons)
    lines.append("【你的优势】")
    lines.extend(f"- {item}" for item in card.strengths)
    lines.append("【你的劣势/风险】")
    lines.extend(f"- {item}" for item in card.risks)
    lines.append("【建议打招呼】")
    lines.append(card.recruiter_greeting)
    lines.append("【简历建议】")
    lines.append(f"- {card.resume_note}")
    lines.append("【状态】")
    lines.append(card.status)
    return "\n".join(lines)


def save_output(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json_config(path: Path | None) -> dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    if not path:
        return config
    payload = json.loads(read_text_file(path))
    config.update(payload)
    return config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run phase-1 job application screening.")
    parser.add_argument("--jobs", required=True, help="Path to normalized jobs JSON.")
    parser.add_argument("--config", help="Optional config JSON path.")
    parser.add_argument("--resume-source", help="Override resume source.")
    parser.add_argument("--resume-patch", help="Inline resume patch text.")
    parser.add_argument("--resume-patch-file", help="Path to a text file with resume patch.")
    parser.add_argument("--output-json", default="output/assessments.json", help="Path to output JSON.")
    parser.add_argument("--output-text", default="output/assessments.txt", help="Path to output text summary.")
    args = parser.parse_args()

    config = load_json_config(Path(args.config) if args.config else None)
    if args.resume_source:
        config["resume_source"] = args.resume_source
    if args.resume_patch:
        config["resume_patch"] = args.resume_patch
    if args.resume_patch_file:
        config["resume_patch"] = read_text_file(Path(args.resume_patch_file))

    profile = build_candidate_profile(Path(config["resume_source"]), str(config.get("resume_patch", "")))
    jobs = load_jobs(Path(args.jobs))

    cards: list[AssessmentCard] = []
    tasks: list[DeliveryTask] = []
    skipped: list[dict[str, Any]] = []

    for job in jobs:
        ok, reasons = passes_hard_filters(job, config)
        if not ok:
            skipped.append(
                {
                    "job_id": job.job_id,
                    "title": job.title,
                    "company_name": job.company_name,
                    "reasons": reasons,
                }
            )
            continue
        match = score_job(profile, job)
        card = build_card(job, match)
        cards.append(card)
        if match.total_score >= int(config.get("match_threshold", 80)):
            tasks.append(build_delivery_task(job, match))

    cards.sort(key=lambda item: item.total_score, reverse=True)
    tasks.sort(key=lambda item: item.job_id)

    text_output = "\n\n".join(render_text_card(card) for card in cards)
    Path(args.output_text).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_text).write_text(text_output, encoding="utf-8")

    save_output(
        Path(args.output_json),
        {
            "config": config,
            "profile": asdict(profile),
            "cards": [asdict(card) for card in cards],
            "delivery_tasks": [asdict(task) for task in tasks],
            "skipped_jobs": skipped,
        },
    )

    print(f"Generated {len(cards)} assessment cards.")
    print(f"Queued {len(tasks)} delivery tasks.")
    print(f"Skipped {len(skipped)} jobs after hard filters.")
    print(f"JSON output: {Path(args.output_json).resolve()}")
    print(f"Text output: {Path(args.output_text).resolve()}")


if __name__ == "__main__":
    main()
