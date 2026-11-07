# The Couch Coach

The Couch Coach is a beginner-friendly Streamlit dashboard that suggests an
American football play based on the current game situation. It uses Google
Gemini when an API key is configured and the service is available; otherwise,
it can provide a clearly labeled, rule-based offline demo recommendation.

## Features

- Enter the quarter, time remaining, down and distance, field position, and score.
- Choose from all 32 NFL teams to theme the dashboard with team colors.
- Get a streamed play recommendation and compact ASCII formation diagram from
  the configured Gemini model (`gemini-3.8-flash`).
- Use offline demo recommendations when no API key is configured, Gemini
  returns a quota error, or Gemini remains unavailable after retries. Demo
  results are labeled as rule-based and **not AI-generated**.

## Requirements

- Python 3.12 (the version used to validate this project)
- A Google Gemini API key for AI-generated recommendations. The offline demo
  works without one.

## Run locally

From the project directory, create and activate a virtual environment, then
install the project dependencies:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows, use:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

Start the app:

```bash
streamlit run couch_coach.py
```

Streamlit will print a local URL (usually `http://localhost:8501`) to open in
your browser.

## Configure your Gemini API key

For local development, store the key in Streamlit's secrets file rather than
in the Python code or README:

1. Create the `.streamlit` directory if it does not already exist.
2. Create `.streamlit/secrets.toml` with:

   ```toml
   GEMINI_API_KEY = "paste-your-key-here"
   ```

3. Keep this file private. The project `.gitignore` excludes it. Never commit
   or share your key; if it is exposed, revoke it and create a replacement.
4. Restart Streamlit after adding or changing the secret.

The app also reads `GEMINI_API_KEY` from the process environment. If you use
that option, configure it through your operating system or deployment
platform's secret manager instead of writing it into source code.

Gemini requests use the model configured in `couch_coach.py`. Without a key,
or when the Gemini quota or service availability prevents a response, the app
uses its offline demo mode.
