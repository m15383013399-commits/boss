---
name: job-apply-assistant
description: Evaluate recruiting-site job postings against the user's current resume, score fit, summarize company and JD details, and draft concise human-sounding recruiter greetings. Use when Codex needs to screen roles on Boss Zhipin, Liepin, or similar sites, prepare high-value outreach for a job search, or stage semi-automated job applications that stop for user confirmation before sending.
---

# Job Apply Assistant

Build a structured job-screening workflow that favors reply rate over volume. Consume the user's current resume and runtime search config, then produce standardized job assessment cards plus delivery tasks that can later feed a confirmed-send automation step.

## Workflow

### 1. Collect runtime inputs

Read the current resume from a runtime path instead of hardcoding personal details into the skill.

Collect or infer these inputs:

- `resume_source`
- `resume_patch`
- `platforms`
- `job_keywords`
- `exclude_keywords`
- `city`
- `salary_range`
- `greeting_style`
- `match_threshold`

Use the defaults in [references/configuration.md](./references/configuration.md) when the user has already agreed to them or does not provide overrides.

### 2. Build the candidate profile

Parse the current resume and optional patch into a normalized candidate profile before reading jobs.

Capture at least:

- target role direction
- years of experience
- product scope
- data-domain tags
- major projects
- measurable outcomes
- technical context terms

If the resume is stale but the user provides a text patch, merge the patch into the profile for the current run. Do not mutate the source resume unless explicitly asked.

### 3. Collect and normalize jobs

Read jobs from the target platforms, then normalize every listing into a shared structure:

- platform
- job id
- job URL
- company info
- recruiter info when available
- title
- city
- salary
- experience requirement
- education requirement
- JD raw text
- JD summary
- requirements
- bonus items

Do not score jobs until the fields are normalized enough to compare across platforms.

### 4. Filter before scoring

Apply hard filters first so the user does not waste attention on weak leads.

Filter out jobs that clearly fail on:

- city
- salary floor
- excluded keywords
- role direction mismatch

Keep the filter logic strict because the goal is reply rate, not application count.

### 5. Score fit

Score only the jobs that survive hard filtering. Use the weighted dimensions in [references/scoring-and-output.md](./references/scoring-and-output.md).

Bias the scoring toward:

- real alignment with B-end data product work
- evidence the user can tell a credible story in interview or recruiter chat
- roles worth spending outreach effort on

Prefer a transparent score breakdown over a single opaque number.

### 6. Write the assessment card

For every job worth keeping, write a standardized card with:

- company info
- role info
- JD summary
- total score
- sub-scores
- recommendation
- fit reasons
- user strengths
- user gaps or risks
- resume adaptation note
- recruiter greeting
- delivery status

Use the output contract in [references/scoring-and-output.md](./references/scoring-and-output.md).

### 7. Create the delivery task

Always create a machine-usable delivery task for recommended jobs, even in phase 1 when the flow still stops before submission.

Include:

- platform id
- job id
- job URL
- recruiter/company identifiers if present
- recommended resume version
- final greeting text
- execution status
- action payload placeholders for later browser automation

Use status values that support a future send step:

- `pending_confirmation`
- `queued_to_send`
- `sent`
- `send_failed`

## Greeting Rules

Keep recruiter greetings short, specific, and restrained.

Always:

- mention one concrete JD point without restating the JD
- connect it to one real piece of resume evidence
- sound like a working professional rather than a cover letter

Never:

- stuff keywords unnaturally
- use exaggerated self-praise
- write generic AI-sounding praise or motivation
- send without explicit user confirmation when the workflow reaches an execution step

If needed, read [references/greeting-style.md](./references/greeting-style.md) before drafting.

## Phase Boundaries

Phase 1:

- read resume
- collect and normalize jobs
- score fit
- generate assessment cards
- generate recruiter greetings
- create delivery tasks

Phase 1 does not:

- auto-edit resumes
- auto-upload attachments
- auto-sync online resume forms
- auto-send without confirmation

Phase 2 can extend the same structure by:

- selecting a resume variant
- generating resume adaptation notes
- handing confirmed delivery tasks to an execution layer such as `scripts/execute_delivery_tasks.py`

## References

- Read [references/configuration.md](./references/configuration.md) for runtime config keys and agreed defaults.
- Read [references/scoring-and-output.md](./references/scoring-and-output.md) for the scoring model, thresholds, and output template.
- Read [references/greeting-style.md](./references/greeting-style.md) when drafting recruiter greetings or reviewing tone.
- Read [references/runtime-usage.md](./references/runtime-usage.md) before running the phase-1 CLI or preparing sample inputs.
