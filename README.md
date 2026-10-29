# Scholarship Scout 🎓

A Python + Streamlit MVP that uses TinyFish Search and Fetch to discover scholarship pages, extract available details, compare requirements against a student profile, and track saved opportunities.

## Features

- Student profile form (state, course, marks, annual household income, preferences)
- Live scholarship discovery via TinyFish Search
- Page extraction via TinyFish Fetch
- Conservative, explainable preliminary eligibility matching
- Source links and visible unknown fields
- SQLite tracker for saved scholarships and application status

## Requirements

- Python 3.10+
- TinyFish API key
- Internet access

## Setup (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Set `TINYFISH_API_KEY` in `.env` to your key. Do not commit `.env` or share screenshots containing it.

## Run

```powershell
streamlit run app.py
```

## Tests

```powershell
pytest -q
```

## TinyFish APIs used

- Search: `GET https://api.search.tinyfish.ai` with `X-API-Key`
- Fetch: `POST https://api.fetch.tinyfish.ai` with `X-API-Key` and a JSON body containing `urls`

See the official TinyFish docs:
- https://docs.tinyfish.ai/search-api
- https://docs.tinyfish.ai/fetch-api
- https://docs.tinyfish.ai/authentication

## Important limitations

- Search results may include third-party pages. Confirm the provider is legitimate before relying on any listing.
- The extraction module uses lightweight patterns, not a legal/official eligibility determination or a fully general LLM parser.
- The app deliberately displays `Unknown` when it cannot confidently extract a field.
- Eligibility status is preliminary. Students must verify the current notification, full terms, deadline, and application link with the official provider.
- No applications are submitted and no student documents are uploaded.
- The deadline field is not automatically verified against an authoritative date parser yet. Scheduled change monitoring is a next milestone.

## Suggested next milestones

1. Add explicit official-domain prioritization and source trust labels.
2. Improve extraction with TinyFish Agent structured output for complex pages.
3. Parse dates and distinguish expired/open/unknown based on current date.
4. Add a scheduled recheck job with change detection.
5. Add tests against real pages and a clearer provenance panel.


## Phase 2 eligibility matching

The matching engine now returns a preliminary 0–100 criteria-coverage score, a status
(`Strong match`, `Potential match`, `Needs verification`, or `Likely ineligible`),
supporting evidence, unresolved questions, and possible mismatches. The score is
**not** a probability of winning a scholarship. Extraction from web pages is
imperfect, so confirm mandatory rules, current deadlines, and application details
on the official provider website.


## Phase 3 detailed scholarship profiles

Discovery cards expose additional extracted details: provider, academic criteria, eligibility text, possible application cycle, benefits, required documents, and income conditions. CSV exports include these fields. A separate application link is shown only when the fetch response explicitly includes one; otherwise the source page is offered for manual verification. All extracted fields may be incomplete or outdated and must be checked on the provider's official site.


## Phase 4: deadlines and in-app reminders

- Add reminders from any saved scholarship in **My tracker**.
- Review pending, overdue, due-today, upcoming, and completed reminders in **Deadlines & reminders**.
- Mark reminders complete, reopen them, or delete them.
- Reminders are stored in the local SQLite database.

**Limitations:** This version provides in-app reminders only. It does not send email/SMS/push notifications, run scheduled background jobs, or automatically monitor scholarship websites. Always verify deadlines on the official provider website.


## Phase 5: Scholarship Assistant

The assistant tab answers questions using scholarship records currently in the app.
Without an LLM key, it uses a local source-grounded fallback that surfaces extracted
fields and relevant source records. To enable generative answers, optionally add
`GEMINI_API_KEY=your_new_key` to your local `.env` file; `GEMINI_MODEL` is optional
and defaults to `gemini-2.5-flash`. Never commit `.env` or share API keys. When Gemini
is enabled, the assistant sends the question, relevant profile fields, and selected
scholarship source excerpts to the Gemini API. Do not enter sensitive personal identifiers.

The assistant is not an official scholarship authority. Verify requirements, deadlines,
and application routes with the official provider.
