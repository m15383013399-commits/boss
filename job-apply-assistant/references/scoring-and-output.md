# Scoring And Output

## Scoring Model

Use a 100-point model with transparent sub-scores.

### Direction Match: 20

Check whether the role is truly aligned with:

- B-end data product manager
- big data product manager
- data middle platform
- data warehouse or related platform work

Penalize roles that are actually closer to:

- generic product manager
- pure data analyst
- pure BI delivery
- pure project management

### Domain Match: 20

Score for domain overlap with the resume and patch:

- metric system
- label system
- data governance
- data services
- BI or reporting platform
- master data
- permissions
- data assets

### Responsibility Match: 20

Look for:

- requirement analysis
- solution design
- platform construction
- cross-team coordination
- launch and acceptance
- ownership

### Technical Context Match: 15

Check for enough shared language to support a credible recruiter conversation:

- SQL
- warehouse modeling
- ETL or ELT
- offline or realtime context
- metric definition
- data asset or permission context

### Industry Or Scenario Match: 10

Score higher when the job's business scenario is close enough to the user's background to improve recruiter confidence.

### Resume Tellability: 15

Check whether the user can tell a concrete, defensible story from the current resume.

This dimension matters because reply rate depends on the recruiter immediately seeing why the conversation is worth having.

## Recommendation Thresholds

- `80+`: 优先沟通
- `70-79`: 可沟通
- `60-69`: 保留观察
- `<60`: 不建议投

## Output Contract

Each retained job should produce a structured card with these sections:

- company info
- role info
- JD summary
- total match score
- sub-scores
- recommendation
- fit reasons
- strengths
- gaps or risks
- resume adaptation note
- recruiter greeting
- execution status

## Suggested Display Template

```text
【岗位】公司名 - 岗位名
【基础信息】城市 / 薪资 / 经验要求 / 平台
【JD摘要】
- ...

【匹配度】82/100，建议优先沟通
【匹配原因】
- ...

【你的优势】
- ...

【你的劣势/风险】
- ...

【建议打招呼】
您好，...

【简历建议】
- 当前使用 base 简历

【状态】
待确认
```

## Delivery Task Contract

For recommended jobs, also keep a machine-usable delivery task with:

- platform
- job id
- job URL
- recruiter or company identifiers when available
- recommended resume version
- final greeting text
- status
- action payload placeholders

Keep the delivery task even in phase 1 so later automation only needs to attach an execution layer.
