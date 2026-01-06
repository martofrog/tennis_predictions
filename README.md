# Tennis Predictions & Value Betting System 🎾

An advanced ATP and WTA match prediction and value betting system using adjusted Elo ratings. This system analyzes player performance, predicts match outcomes, and identifies profitable betting opportunities by comparing predictions against live bookmaker odds.

## Features

- **Adjusted Elo Ratings**: Advanced player rating system that accounts for:
  - Surface specialization (hard, clay, grass)
  - Set-based margin of victory
  - Recent performance trends
  
- **Live Odds Integration**: Fetches real-time odds from multiple bookmakers via The Odds API

- **Value Bet Detection**: Automatically identifies matches where the model's predictions suggest positive expected value

- **Multi-Bookmaker Comparison**: Find the best odds across different bookmakers

- **ATP & WTA Support**: Handles both men's (ATP) and women's (WTA) tours

- **Surface-Specific Ratings**: Separate ratings for different court surfaces

- **Automated Updates**: Daily scripts to download new matches and update ratings

## Quick Start

### First Time Setup

1. **Clone and install:**
   ```bash
   git clone <your-repo-url>
   cd tennis_predictions
   pip install -r requirements.txt
   ```

2. **Configure API key:**
   ```bash
   cp env.example .env
   # Edit .env and add your API key from https://the-odds-api.com/
   ```

3. **Initialize data:**
   ```bash
   python src/data/download_tennis_data.py 2023 2024 --tour atp
   python src/data/download_tennis_data.py 2023 2024 --tour wta
   python src/data/update_data.py --years 2023 2024
   ```

### Daily Usage

Run the automated daily update:
```bash
python src/scripts/daily_update.py
```

This automatically:
- Downloads new match results
- Updates player ratings
- Finds today's value bets

## REST API (SOLID Architecture)

Start the JSON REST API server with SOLID architecture:

```bash
python run_api.py                # Default: SOLID architecture on port 8000
python run_api.py --port 8080    # Custom port
python run_api.py --reload       # Development mode with auto-reload
```

Access the API at http://localhost:8000 with interactive docs at http://localhost:8000/docs

**Features:**
- ✅ Dependency Injection
- ✅ Repository Pattern
- ✅ Service Layer
- ✅ SOLID Principles

## Key Commands

```bash
# Get today's value bets
python src/scripts/daily_value_bets.py

# Predict any matchup
python src/prediction/predict.py "Novak Djokovic" "Rafael Nadal" --surface clay

# Update ratings from match data
python src/data/update_data.py --years 2023 2024 --tour atp
```

## Project Structure

```
tennis_predictions/
├── src/
│   ├── api/                       # REST API
│   │   ├── main.py                # FastAPI application
│   │   └── __init__.py
│   ├── core/                      # Core domain logic
│   │   ├── constants.py           # Constants and enums
│   │   ├── domain_models.py       # Domain models
│   │   ├── interfaces.py          # Abstract interfaces
│   │   ├── exceptions.py          # Custom exceptions
│   │   └── tennis_utils.py        # Tennis utilities
│   ├── data/                      # Data fetching and management
│   │   ├── data_loader.py         # Load historical match data
│   │   ├── download_tennis_data.py # Download match data
│   │   ├── odds_fetcher.py        # Fetch live odds from API
│   │   └── update_data.py         # Update ratings with new matches
│   ├── prediction/                # Prediction and analysis
│   │   ├── elo_rating_system.py   # Tennis Elo rating system
│   │   └── predict.py             # Match prediction tool
│   ├── services/                  # Business logic services
│   │   ├── rating_service.py      # Rating management
│   │   ├── betting_service.py     # Value betting analysis
│   │   └── dependency_container.py # Dependency injection
│   ├── infrastructure/            # Infrastructure adapters
│   │   ├── repositories.py        # Data repositories
│   │   ├── adapters.py            # External API adapters
│   │   └── load_env.py            # Environment loader
│   └── scripts/                   # Utility scripts
│       ├── daily_update.py         # Daily update script
│       └── daily_value_bets.py    # Daily value bets finder
├── run_api.py                     # Start REST API server
├── requirements.txt                # Python dependencies
└── data/                          # Historical match data
```

## How It Works

### 1. Elo Rating System
The adjusted Elo system calculates player strength based on:
- **Win/Loss record** with set-based margin adjustments
- **Surface specialization** (hard, clay, grass)
- **Recent form** through continuous rating updates

### 2. Match Predictions
For any matchup, the system:
- Retrieves current Elo ratings for both players
- Adjusts for surface specialization
- Calculates win probability using logistic function
- Generates expected outcome predictions

### 3. Value Bet Detection
Value bets are identified when:
- Model's implied probability > Bookmaker's implied probability
- Positive expected value (EV) after accounting for vig
- Edge exceeds configurable threshold (default: 5%)

### 4. Bookmaker Comparison
When multiple bookmakers offer odds:
- Compare implied probabilities
- Calculate expected value for each
- Identify best available odds
- Highlight arbitrage opportunities (rare)

## API Requirements

This project uses [The Odds API](https://the-odds-api.com/) for live betting odds.

- **Free Tier**: 500 requests/month
- **Cost**: Free (with limitations)
- **Setup**: Sign up and add your API key to `.env`

**Important**: The `.env` file containing your API key is automatically excluded from Git commits.

## Requirements

- Python 3.8+
- Dependencies listed in `requirements.txt`:
  - pandas
  - requests
  - fastapi
  - uvicorn
  - pydantic
  - apscheduler

## Contributing

When contributing:
1. Never commit `.env` files
2. Update documentation for new features
3. Test changes with sample data
4. Follow existing code style

## License

This project is for educational and research purposes. 

**Disclaimer**: This tool is for informational purposes only. Gambling involves risk. Always gamble responsibly and within your means.

## Support

For issues or questions:
1. Check the documentation files
2. Ensure your API key is properly configured
3. Verify data files are in the correct format

---

**Remember**: Past performance doesn't guarantee future results. Use this tool as one factor in your betting decisions, not the only factor. 🎲
