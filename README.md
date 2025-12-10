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
1. Adjust `user_profile.txt` with your preferred leagues, matches, and sensitivities. The script falls back to a built-in example when the file is missing or empty.
2. Update `MATCHES` inside `match_recommender.py` with the fixtures you care about; each entry should have an `id` field since the response matches recommendations by ID.

## Usage
```sh
python match_recommender.py
```
The script loads the user profile, crafts a prompt that combines the profile and the current match list, and asks `gpt-5-nano` for ranked recommendations. Results are printed with the recommended score, match info, and the model’s reasoning.

## Notes
- `football_api.py` is a standalone example that shows how you might retrieve fixtures from `football-data.org` using a bearer token. It is not wired into the recommender yet but can serve as a starting point for fetching real match data.
- Keep `user_profile.txt` and `.env` synced with your interests and credentials so the recommendation output stays meaningful.
