# Unified Update Process

## Overview

The tennis predictions system uses a **unified update process** that works identically for both API startup and daily updates.

## How It Works

### 1. Check Historical Data
- Scans for CSV files from years 2020-2025
- If any years are missing, downloads from Jeff Sackmann repository
- Ensures complete historical dataset is available

### 2. Download Recent Data
- Fetches last 7 days of matches from SofaScore API
- Updates CSV files for current year (both ATP and WTA)
- Deduplicates automatically (no re-downloading of existing matches)

### 3. Train Model
- Processes **all available matches** (2020-present)
- Updates player Elo ratings for all surfaces
- Saves updated ratings to `data/ratings.json`

## Process Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    UNIFIED UPDATE PROCESS                    │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Historical Data                                     │
│  - Check years 2020-2025                                    │
│  - Download missing years from Jeff Sackmann               │
│  - Status: Downloaded OR Already Present                    │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Recent Data (Last 7 Days)                          │
│  - Fetch from SofaScore API                                 │
│  - Update ATP/WTA CSV files                                 │
│  - Deduplicate automatically                                │
│  - Result: X new ATP matches, Y new WTA matches            │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Train Model                                         │
│  - Load all matches (2020-present)                          │
│  - Update Elo ratings for all players                       │
│  - Save to data/ratings.json                                │
│  - Result: Z players rated                                  │
└─────────────────────────────────────────────────────────────┘
```

## When It Runs

### On API Startup
- Runs automatically when API server starts
- Ensures fresh data even after system restarts
- Takes ~3-4 minutes for full dataset (26K+ matches)

### Daily at 6:00 AM
- Scheduled automatic update
- Downloads yesterday's matches
- Retrains model with updated data
- No manual intervention needed

### Manual Run
```bash
bin/python update_with_sofascore.py
```
Or with historical re-download:
```bash
bin/python update_with_sofascore.py --force-historical
```

## Data Sources

| Data | Source | Years | Update Frequency |
|------|--------|-------|------------------|
| Historical | Jeff Sackmann GitHub | 2020-2025 | On-demand (if missing) |
| Current Year | SofaScore API | 2026+ | Last 7 days, daily |
| Ratings | Calculated | All | After each update |

## Performance

| Operation | Time | Matches Processed |
|-----------|------|-------------------|
| Historical Download | 1-2 sec per year | Varies by year |
| SofaScore Fetch (7 days) | ~5 seconds | ~500-1500 |
| Model Training | ~3-4 minutes | 26,000+ total |
| **Total Startup** | **3-5 minutes** | All available |

## Files Created/Updated

```
data/
├── atp/
│   ├── atp_matches_2020.csv  ← Historical (Jeff Sackmann)
│   ├── atp_matches_2021.csv
│   ├── atp_matches_2022.csv
│   ├── atp_matches_2023.csv
│   ├── atp_matches_2024.csv
│   ├── atp_matches_2025.csv
│   └── atp_matches_2026.csv  ← Current + SofaScore
├── wta/
│   ├── wta_matches_2020.csv  ← Historical (Jeff Sackmann)
│   ├── wta_matches_2021.csv
│   ├── wta_matches_2022.csv
│   ├── wta_matches_2023.csv
│   ├── wta_matches_2024.csv
│   ├── wta_matches_2025.csv
│   └── wta_matches_2026.csv  ← Current + SofaScore
└── ratings.json               ← Elo ratings (all players)
```

## Benefits

✅ **Fresh Installation**: Automatically downloads everything needed
✅ **Consistent**: Same process for startup and daily updates
✅ **Up-to-Date**: Always has latest 7 days from SofaScore
✅ **Complete**: Trains on full historical dataset
✅ **Reliable**: Deduplicates automatically, no manual intervention
✅ **Transparent**: Detailed logging of each step

## Optimization Options

If startup time is a concern, you can:

1. **Skip startup training**: Load existing ratings, only train on daily update
2. **Incremental training**: Train only on new matches, not full dataset
3. **Cached ratings**: Check if data changed before retraining

Current implementation prioritizes **data accuracy** over startup speed.

## Troubleshooting

### Startup takes too long
- Expected: 3-4 minutes for 26K+ matches
- Normal behavior: Training is CPU-intensive
- Solution: Runs in background, API becomes available when ready

### Missing data for current year
- SofaScore provides last 7 days only
- Historical data from Jeff Sackmann may lag
- Gap period: Use SofaScore for recent, wait for Sackmann for complete

### Duplicate matches in CSV
- Automatically handled by deduplication
- Uses `(tourney_date, winner_name, loser_name)` as key
- Keeps most recent version (SofaScore over historical)

## Monitoring

Check update status:
```bash
# View API logs
tail -f api.log

# Check data status
curl http://localhost:8000/api/v2/data-status

# Manual update with verbose output
bin/python src/scripts/unified_update.py
```

## Implementation

- **Main Module**: `src/scripts/unified_update.py`
- **API Integration**: `src/api/main.py` (startup_event, run_daily_update)
- **Manual Script**: `update_with_sofascore.py`
- **Scheduler**: APScheduler (daily at 6:00 AM)

