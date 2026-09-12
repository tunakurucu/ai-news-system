# AI News System

A Turkish-language news pipeline that collects articles from RSS feeds, cleans and organizes them, groups related coverage into stories, and publishes a searchable static news site.

## Background

This project was started by [Korhan Onat Ors](https://github.com/mithdreamer). I joined later to help turn the early version into a working product. My work has focused on API integrations, the AI story layer, source reliability, testing, publishing, and a full redesign of the website.

## What it does

- collects articles from configured RSS sources
- cleans malformed content and filters weak or duplicate entries
- assigns categories and importance scores
- groups related articles with deterministic story IDs
- creates source-grounded Turkish summaries when an OpenAI API key is available
- falls back to the original article data when synthesis is unavailable
- generates daily pages, archives, search, statistics, and JSON outputs
- can send a newsletter when email delivery is enabled
- publishes the generated static site from the `docs/` directory

The current sources include BBC Turkce, TRT Haber, and Anadolu Ajansi.

## Project structure

- `src/main.py`: end-to-end pipeline
- `src/services/`: fetching, cleaning, clustering, synthesis, publishing, and newsletter services
- `src/utils/`: file and logging helpers
- `config/`: RSS and category configuration
- `data/`: raw articles, statistics, story data, indexes, and synthesis cache
- `docs/`: generated static website
- `tests/`: focused tests for the pipeline and story features

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python src/main.py
```

The pipeline can run without an OpenAI key. In that case, it skips story synthesis and keeps the source material unchanged.

To enable synthesis, add your own values to `.env`:

```text
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-5-mini
```

Never commit a real API key.

## GitHub automation

The `Daily AI News` workflow can run on a schedule or manually. Generated archive data is stored on the `archive-data` branch.

Add `OPENAI_API_KEY` as a repository secret to enable story synthesis. Newsletter delivery is off by default. To enable it, set the `SEND_NEWSLETTER` repository variable to `true` and add `RESEND_API_KEY` and `NEWSLETTER_TO` as secrets.

Optional repository variables are `OPENAI_MODEL`, `NEWSLETTER_FROM`, and `NEWSLETTER_SITE_URL`.

## Current status

The collection, cleanup, categorization, story clustering, grounded synthesis, archive, search, and publishing flows are implemented. Voice and video generation remain future work.

This is still an active prototype. It should be treated as an editorial tool built on third-party sources, not as an independent source of record.
