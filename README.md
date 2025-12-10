# MatchRecommender
Lightweight CLI script that combines football and esports fixtures with an OpenAI-backed scoring prompt to deliver personalized match recommendations.

## Prerequisites
- Python 3.8+ (any modern Python 3 release should work).
- `pip install -r requirements.txt` is not provided, so install the needed packages manually:
  ```sh
  pip install openai python-dotenv requests
  ```
- Create a `.env` file in the repo root with `OPENAI_API_KEY=sk-...` so the recommender can call the OpenAI Responses API.

## Setup
1. Adjust `user_profile.txt` with your preferred leagues, matches, and sensitivities—this file must exist and contain non-empty text or the recommender won’t have any context.
2. Set football API credentials (see below); matches are fetched on every run, so no local `matches.json` is needed anymore.

## Usage
```sh
python match_recommender.py
```
The script loads the user profile, fetches fixtures from the football API, crafts a prompt that combines the profile and the fresh match list, and asks `gpt-5-nano` for ranked recommendations. Results are printed with the recommended score, match info, and the model’s reasoning.

## Fetching fixtures
- Add `FOOTBALL_API_TOKEN=…` (and optionally `FOOTBALL_COMPETITIONS=2001,2014`) to `.env` so the app can request `/matches` at startup.
- On every run, `match_recommender.py` fetches scheduled fixtures, normalizes them, and feeds them straight to the recommender (no `matches.json` persisted).
- If fetching fails (missing token, network, or API error), the run exits without recommendations; fix the issue and rerun.

## Notes
- `football_api.py` contains the fetch/normalize helpers used by the main script.
- Keep `user_profile.txt` and `.env` synced with your interests and credentials so the recommendation output stays meaningful.
