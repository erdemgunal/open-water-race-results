# My Open Water Race Results Analysis Project

## Usage

```bash
cd 2026/canakkale

py fetch_results.py              # live from RaceResult
py fetch_results.py --offline    # reuse previously archived data

# Visualization (5 charts saved to output/)
py visualize_results.py                       # your result (event.py default_bib)
py visualize_results.py --bib 230             # by bib number
py visualize_results.py --bib 628 --show      # view someone else's result without changing my default settings
py visualize_results.py --time 3073           # or by finish time (seconds)
py visualize_results.py --show                # also open the charts in a window
```