# My Open Water Race Results Analysis Project
## Usage

```bash
cd 2026/canakkale

py fetch_results.py              # live from RaceResult
py fetch_results.py --offline    # reuse previously archived data

py visualize_results.py --bib 230     # by bib number
py visualize_results.py --time 3073   # or by your finish time (seconds)
py visualize_results.py --show        # also open the charts in a window
```

Outputs:

- `raceresult_data/canakkale_2026_dataset.csv` / `.xlsx` the combined dataset.
- `output/01..05_*.png` five charts:
  1. Finish-time distribution (histogram + KDE, median / top decile / your time)
  2. Age group × gender (violin plots)
  3. ECDF: what time you need to move up 50 / 100 places
  4. Country participation & median pace
  5. Women vs. men finish-time density

## Notes

- **Schema**: each row is one swimmer bib/id, name, nation, birth_year, gender, age_group, official ranks (or computed `*_computed` ranks when the provider doesn't publish them), status (FINISHED / DNS / DNF / DSQ) and time (`time_text` + `swim_seconds`).
- **Snapshots**: each live fetch archives the previous data into `raceresult_data/snapshots/<timestamp>/` before overwriting (last 10 kept change with `snapshot_keep` in `event.py`). To roll back, copy the files from a snapshot back into `raceresult_data/`.
- **API keys**: optional. Set `<KEY>_KEY` (e.g. `CANAKKALE_2026_KEY`) as an environment variable, or drop a `.env` file in the project root with `CANAKKALE_2026_KEY=...`, to provide a fallback key otherwise the key is auto-discovered from the event's config endpoint.