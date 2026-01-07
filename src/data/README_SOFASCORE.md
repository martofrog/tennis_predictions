# SofaScore API Integration

## Overview

The SofaScore client provides real-time tennis match results to supplement the static data from tennis-data.co.uk.

## Features

✅ **Real-time match results** - Get completed matches from recent days
✅ **Rate limiting** - Configurable requests per minute (default: 20)
✅ **Automatic retries** - Handles transient errors
✅ **Data conversion** - Converts to Jeff Sackmann CSV format
✅ **Duplicate handling** - Merges with existing data files

## Usage

### Fetch Recent Matches

```python
from src.data.sofascore_client import fetch_recent_matches_from_sofascore
from pathlib import Path

# Fetch last 7 days of ATP matches
df = fetch_recent_matches_from_sofascore(
    days=7, 
    tour="atp",
    save_to_file=Path("data/atp/atp_matches_2025_sofascore.csv")
)

print(f"Retrieved {len(df)} matches")
```

### Manual Client Usage

```python
from src.data.sofascore_client import SofaScoreClient
from datetime import datetime, timedelta

client = SofaScoreClient(requests_per_minute=20)

# Get matches from yesterday
yesterday = datetime.now() - timedelta(days=1)
matches = client.get_matches_by_date(yesterday, tour="atp")

# Convert to DataFrame
df = client.to_dataframe(matches)
```

## Integration with Daily Updates

The SofaScore client is automatically integrated into the daily update mechanism:

1. **6am Daily**: Scheduler triggers `update_match_data()`
2. **Step 1a**: Fetch last 7 days from SofaScore (real-time results)
3. **Step 1b**: Download bulk data from tennis-data.co.uk (historical)
4. **Step 2**: Merge and deduplicate data
5. **Step 3**: Retrain model incrementally

## Anti-Bot Protection

### The Challenge

SofaScore implements anti-bot protection that can result in:
- **403 Forbidden** errors
- **Captcha challenges**
- **IP-based rate limiting**

### Solutions

#### 1. Basic (Current Implementation)
- Proper headers mimicking browser requests
- Session-based requests with cookies
- Conservative rate limiting (20 req/min)
- Graceful error handling

#### 2. Intermediate (Recommended for Production)
Use a proxy/scraping service:

```python
# Example with ScraperAPI
import os
# Replace YOUR_API_KEY_HERE with your actual ScraperAPI key
api_key = os.getenv("SCRAPER_API_KEY", "YOUR_API_KEY_HERE")
proxies = {
    'http': f'http://scraperapi:{api_key}@proxy-server.scraperapi.com:8001',
    'https': f'http://scraperapi:{api_key}@proxy-server.scraperapi.com:8001'
}

client = SofaScoreClient()
client.session.proxies.update(proxies)
```

#### 3. Advanced (Most Reliable)
Use browser automation:

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Configure headless Chrome
options = Options()
options.add_argument('--headless')
driver = webdriver.Chrome(options=options)

# Navigate and extract data
driver.get('https://www.sofascore.com/...')
# ... extract match data from rendered page
```

## Rate Limiting Best Practices

| Scenario | Requests/Min | Notes |
|----------|--------------|-------|
| Development/Testing | 10-15 | Conservative, safe |
| Production (no proxy) | 15-20 | Monitor for 403s |
| Production (with proxy) | 30-60 | Depends on proxy service |
| Batch processing | 5-10 | For large date ranges |

## Error Handling

The client handles various error scenarios:

```python
try:
    matches = client.get_recent_matches(days=7, tour="atp")
except Exception as e:
    logger.warning(f"SofaScore unavailable: {e}")
    # Fall back to tennis-data.co.uk
    matches = fetch_from_tennis_data_co_uk()
```

## Data Format

### SofaScore Response → Jeff Sackmann Format

| SofaScore Field | Jeff Sackmann Field | Notes |
|-----------------|---------------------|-------|
| `startTimestamp` | `tourney_date` | Converted to YYYYMMDD |
| `tournament.name` | `tourney_name` | Tournament name |
| `tournament.groundType` | `surface` | Hard/Clay/Grass |
| `homeTeam.name` | `winner_name` | Based on score |
| `awayTeam.name` | `loser_name` | Based on score |
| `homeScore.periodX` | `score` | Set scores combined |

### Missing Fields

Some Jeff Sackmann fields are not available from SofaScore:
- Player IDs, rankings, ages
- Match statistics (aces, double faults, etc.)
- Seed information
- Draw size, tournament level

These fields are left empty and can be enriched from other sources.

## Monitoring

### Success Indicators
- ✅ Matches retrieved > 0
- ✅ No 403 errors
- ✅ Data successfully merged
- ✅ Model retrained with new data

### Failure Indicators
- ❌ Consistent 403 errors → Anti-bot triggered
- ❌ 429 errors → Rate limit exceeded
- ❌ Empty results for recent dates → API issue

### Logging

```python
import logging

# Enable debug logging for SofaScore
logging.getLogger('src.data.sofascore_client').setLevel(logging.DEBUG)
```

## Alternatives

If SofaScore becomes unreliable, consider:

1. **Tennis Abstract** - Jeff Sackmann's live results
2. **FlashScore** - Similar to SofaScore, different API
3. **Official ATP/WTA APIs** - If available
4. **Tennis Explorer** - Match results and statistics
5. **Oddsportal** - Match results with betting odds

## Troubleshooting

### 403 Forbidden Errors

**Symptoms**: All requests return 403
**Causes**: 
- Too many requests
- IP flagged
- Missing/incorrect headers

**Solutions**:
1. Reduce rate limit to 10 req/min
2. Add longer delays between requests
3. Use proxy service
4. Switch to browser automation

### No Matches Found

**Symptoms**: Empty results for recent dates
**Causes**:
- No matches scheduled that day
- API endpoint changed
- Data not yet available

**Solutions**:
1. Check SofaScore website manually
2. Try different date ranges
3. Fall back to tennis-data.co.uk

### Duplicate Matches

**Symptoms**: Same match appears multiple times
**Causes**:
- Multiple data sources
- Re-running updates

**Solutions**:
- Deduplication is automatic (by date, winner, loser)
- Keep `keep='last'` to prefer newer data

## Configuration

### Environment Variables

```bash
# Optional: Configure proxy
SOFASCORE_PROXY_URL=http://proxy-server:8001
SOFASCORE_PROXY_KEY=your_key

# Optional: Adjust rate limits
SOFASCORE_REQUESTS_PER_MINUTE=20
```

### Code Configuration

```python
# In src/api/main.py - update_match_data()

# Adjust lookback period (default: 7 days)
df = fetch_recent_matches_from_sofascore(days=14, tour="atp")

# Adjust rate limiting
client = SofaScoreClient(requests_per_minute=15)
```

## Future Enhancements

- [ ] Add proxy support via environment variables
- [ ] Implement browser automation fallback
- [ ] Add player ranking enrichment
- [ ] Cache successful requests
- [ ] Add match statistics extraction
- [ ] Support live/in-progress matches
- [ ] Add tournament filtering
- [ ] Implement webhook notifications for new matches

