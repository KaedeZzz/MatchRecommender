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
2. Keep `matches.json` up to date (the recommender reads from it every run and requires valid JSON; otherwise it reports the issue and produces no choices).

## Usage
```sh
python match_recommender.py
```
The script loads the user profile, crafts a prompt that combines the profile and the current match list, and asks `gpt-5-nano` for ranked recommendations. Results are printed with the recommended score, match info, and the model’s reasoning.

## Fetching fixtures
- Add `FOOTBALL_API_TOKEN=…` (and optionally `FOOTBALL_COMPETITIONS=2001,2014`) to `.env` so `football_api.py` can request `/matches`.
- Run `python football_api.py` to fetch scheduled fixtures, normalize them, and merge them into `matches.json`. The script keeps non-football entries intact and sorts the file by kickoff time, making it ready for `match_recommender.py`.
- Update `MATCHES` in `match_recommender.py` to load from `matches.json` once you want to replace the hard-coded list with this generated data.

## Notes
- `football_api.py` is a standalone example that shows how you might retrieve fixtures from `football-data.org` using a bearer token. It is not wired into the recommender yet but can serve as a starting point for fetching real match data.
- Keep `user_profile.txt` and `.env` synced with your interests and credentials so the recommendation output stays meaningful.
