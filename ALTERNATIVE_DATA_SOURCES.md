# Alternative GitHub Repositories for Fresh Tennis Data

## Current Status
Jeff Sackmann's repository (tennis_atp/tennis_wta) has data up to:
- ATP: December 18, 2024
- WTA: November 25, 2024

## Alternative GitHub Repositories

### 1. ⭐ **glad94/infotennis** (RECOMMENDED)
**URL**: https://github.com/glad94/infotennis  
**Last Updated**: January 6, 2026 (TODAY!)  
**Stars**: 35  
**Type**: Web scraper for ATP Tour website

**What it does**:
- Scrapes live data directly from atptour.com
- Supports 6 data types including tournament calendar and match results
- Includes detailed match statistics (Key Stats, Rally Analysis, Stroke Analysis)
- Works for matches from Antwerp 2021 onwards

**Pros**:
- ✅ Active and recently updated
- ✅ Scrapes real-time data from official ATP website
- ✅ Well-documented with examples
- ✅ Python-based (easy to integrate)

**Cons**:
- ⚠️ Requires scraping (slower than API)
- ⚠️ ATP only (no WTA yet)
- ⚠️ Dependent on ATP website structure

**Integration Approach**:
```python
# Install infotennis
pip install git+https://github.com/glad94/infotennis

# Use in your code
from infotennis.scrapers.scrape_match_data import scrape_ATP_match_data
raw_data = scrape_ATP_match_data(2025, 352, "ms005", "key-stats")
```

### 2. ⭐ **mcekovic/tennis-crystal-ball** (Ultimate Tennis Statistics)
**URL**: https://github.com/mcekovic/tennis-crystal-ball  
**Last Updated**: January 5, 2026  
**Stars**: 282  
**Type**: Full tennis statistics platform with database

**What it does**:
- Complete tennis statistics and prediction platform
- Has its own database with historical and current data
- Includes Elo ratings, predictions, and analytics
- Web application with live data

**Pros**:
- ✅ Very popular (282 stars)
- ✅ Comprehensive platform
- ✅ Active development
- ✅ Includes both ATP and WTA

**Cons**:
- ⚠️ More complex (full application, not just data)
- ⚠️ May require running their database
- ⚠️ Heavier integration

**Website**: https://www.ultimatetennisstatistics.com/

### 3. **BigTimeStats/atp-tennis**
**URL**: https://github.com/BigTimeStats/atp-tennis  
**Type**: Historical ATP data (2018-2019)

**Status**: ❌ Not current (data from 2018-2019 only)

### 4. **Tennis Match Charting Project**
**URL**: https://github.com/JeffSackmann/tennis_MatchChartingProject  
**Type**: Detailed shot-by-shot data

**What it does**:
- Crowdsourced shot-by-shot match data
- Over 16,900 matches
- Very detailed but not comprehensive

**Status**: ⚠️ Not suitable for daily match results (specialized data)

## Recommended Solution: Hybrid Approach

### Short-term (Immediate)
Use **glad94/infotennis** to scrape recent ATP matches:

```python
# Add to your download_match_data.py
from infotennis.scrapers import scrape_ATP_tournament

# Scrape recent tournaments
recent_data = scrape_ATP_tournament(year=2025, tournament_id=403)
```

### Medium-term (Better)
Integrate **The Odds API** (already have key) for real-time results:
- Covers both ATP and WTA
- More reliable than scraping
- Already integrated for odds

### Long-term (Best)
Use **Ultimate Tennis Statistics** database or API:
- Most comprehensive
- Both tours
- Active community

## Implementation Priority

1. **Immediate**: Add infotennis scraper for ATP matches
2. **Week 1**: Integrate The Odds API results endpoint
3. **Week 2**: Add WTA scraper or find WTA equivalent
4. **Month 1**: Consider Ultimate Tennis Statistics integration

## Code Integration Example

```python
# src/infrastructure/scrapers.py (NEW FILE)

from infotennis.scrapers import scrape_ATP_calendar, scrape_ATP_tournament
from datetime import datetime, timedelta

class ATPWebScraper:
    """Scrape recent ATP matches from official website."""
    
    def get_recent_matches(self, days_back=7):
        """Get matches from last N days."""
        # Implementation using infotennis
        pass
    
    def get_yesterday_matches(self):
        """Get yesterday's ATP matches."""
        return self.get_recent_matches(days_back=1)
```

Then update your API endpoint to try scraper first, fall back to historical data.

## Notes

- **glad94/infotennis** is the most promising for immediate use
- It was updated TODAY (Jan 6, 2026), showing active maintenance
- The scraper approach is more fragile than APIs but gives access to official data
- Consider caching scraped data to avoid repeated requests
- Respect website rate limits and terms of service

## Next Steps

1. Clone and test infotennis locally
2. Verify it can fetch recent 2025 matches
3. Integrate into your data pipeline
4. Add error handling and fallbacks
5. Set up daily scraping schedule

