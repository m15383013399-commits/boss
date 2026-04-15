# Runtime Usage

Use the phase-1 runner to score normalized job JSON against the current resume and produce:

- a machine-readable JSON result
- a text summary of job assessment cards

## Command

```powershell
python "./job-apply-assistant/scripts/run_phase1.py" `
  --jobs "./job-apply-assistant/scripts/sample_jobs.json"
```

## Notes

- The jobs input is currently a normalized JSON file. Browser scraping is not implemented yet.
- PDF resume parsing requires `pypdf`.
- If `pypdf` is missing, use a text resume source temporarily or install the dependency.
- Delivery tasks are created only for jobs at or above the configured threshold.
