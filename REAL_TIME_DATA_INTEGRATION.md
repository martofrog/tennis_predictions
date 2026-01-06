# Real-Time Tennis Match Data Integration Guide

## Current Situation

The tennis predictions application currently uses **Jeff Sackmann's GitHub repository** for historical match data:
- **ATP Data**: Up to December 18, 2024
- **WTA Data**: Up to November 25, 2024
- **Update Frequency**: Irregular, typically weeks/months behind real-time

This is excellent for training the Elo rating model but insufficient for real-time match results.

## Why Yesterday's Matches Don't Show

**The Problem**: You're 100% correct that there were ATP matches yesterday (January 5, 2026), but the data source only has matches up to December 18, 2024 - that's a **13-month gap**.

**The Solution**: Integrate a real-time data source.

## Options for Real-Time Data

### 1. The Odds API (Recommended - Already Partially Integrated)

**Status**: Already integrated for betting odds  
**Cost**: Free tier available (500 requests/month)  
**What to Add**: Match results endpoint

Pros:
- Already have API key configured
- Reliable and well-documented
- Covers major tournaments

Cons:
- Limited free tier
- May not have all ATP/WTA matches

### 2. SofaScore API

**Cost**: Free (unofficial API)  
**Coverage**: Comprehensive tennis coverage  
**Real-time**: Yes

Example endpoint: `https://api.sofascore.com/api/v1/sport/tennis/scheduled-events/{date}`

### 3. ATP/WTA Official APIs

**Cost**: Requires partnership/subscription  
**Coverage**: Complete official data  
**Real-time**: Yes

### 4. Web Scraping

**Cost**: Free  
**Reliability**: Lower (site changes break scrapers)

Potential sources:
- https://www.atptour.com/en/scores/results-archive
- https://www.wtatennis.com/scores
- https://www.flashscore.com/tennis/

## Quick Workaround (To See Historical Matches)

The API now supports a `days_ago` parameter to view matches from when data was available:

```bash
# See matches from December 18, 2024 (latest ATP data)
curl "http://localhost:8000/api/v2/matches/yesterday?days_ago=384&tour=atp"
```

## New Data Status Endpoint

Check what data is available:

```bash
curl "http://localhost:8000/api/v2/data-status"
```

Returns:
```json
{
  "tours": {
    "atp": {
      "total_matches": 13174,
      "earliest_date": "2020-01-06",
      "latest_date": "2024-12-18"
    },
    "wta": {
      "total_matches": 8093,
      "earliest_date": "2022-01-03",
      "latest_date": "2024-11-25"
    }
  }
}
```

## Recommended Implementation

The architecture (SOLID principles, dependency injection) makes it easy to add real-time sources:

1. Implement `IMatchDataRepository` interface for real-time source
2. Add adapter in `src/infrastructure/adapters.py`
3. Update dependency container to use new source
4. Add caching to minimize API calls

The rating system will continue to work with historical data for training. Real-time data is only needed for "yesterday's matches" and current betting odds.

