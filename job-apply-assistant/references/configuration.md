# Configuration

Use runtime configuration instead of hardcoding user profile details into the skill.

## Required Inputs

### `resume_source`

- Type: file path
- Meaning: current active resume file
- Suggested default:
  - `./resume.pdf`

### `job_keywords`

- Type: string array
- Meaning: target search keywords
- Default for this user:
  - `B端数据产品经理`
  - `大数据产品经理`
  - `数据中台`
  - `数仓`

## Optional Inputs

### `resume_patch`

- Type: free text or structured notes
- Meaning: latest experience not yet reflected in the resume file
- Default: empty

### `platforms`

- Type: string array
- Meaning: recruiting platforms to search
- Default:
  - `boss`
  - `liepin`

### `city`

- Type: string
- Meaning: target city
- Default:
  - `北京`

### `salary_range`

- Type: string
- Meaning: accepted salary range
- Default:
  - `20k-30k`

### `exclude_keywords`

- Type: string array
- Meaning: hard-exclude role or domain keywords
- Default: empty

### `greeting_style`

- Type: enum-like string
- Meaning: tone for recruiter greetings
- Default:
  - `专业克制`

### `match_threshold`

- Type: integer or threshold bucket
- Meaning: minimum score for recommended outreach
- Suggested default:
  - recommend at `80+`

### `company_preferences`

- Type: object
- Meaning: future extension for preferred industries, company sizes, or funding stages
- Default: empty

## Candidate Profile Normalization

Normalize the current resume and patch into these fields before scoring:

- target directions
- years of experience
- product scope tags
- data-domain tags
- industry tags
- project summaries
- measurable results
- technical context terms

Treat the normalized profile as a run-scoped artifact. Rebuild it whenever the resume changes.
