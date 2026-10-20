# The Morning Ledger

A daily markets newspaper that writes and publishes itself every weekday at 7am New York time.

Every morning, GitHub runs a small program that:

1. downloads prices for about 85 markets from Yahoo Finance: stock indexes around the world, bond yields, currencies, commodities, crypto, US sectors, Big Tech, banks, and themes on the come-up;
2. draws the charts;
3. asks Claude to write the day's article, using web search to find out *why* things moved;
4. turns it all into a newspaper-style web page and publishes it on GitHub Pages.

Past editions are kept in an archive at `archive.html`.

## What's in this folder

| File | What it does |
|---|---|
| `config.yaml` | **Your settings.** Paper name, time zone, publishing time, and every market tracked. Edit this freely. |
| `make_edition.py` | The main program. Runs every step above. |
| `newsroom/market_data.py` | Downloads prices and works out the daily, weekly, monthly and year-to-date moves |
| `newsroom/charts.py` | Draws the charts |
| `newsroom/writer.py` | The instructions Claude follows when writing the article |
| `newsroom/page.py` + `newsroom/templates/` | Builds the web pages and controls how they look |
| `.github/workflows/daily-edition.yml` | The alarm clock: tells GitHub when to run everything |
| `docs/` | The finished website (created by the program; don't edit by hand) |

## One-time setup

### 1. Get a Claude API key
1. Go to <https://console.anthropic.com> and sign up.
2. Under **Billing**, add some credit (a few dollars goes a long way) and set a monthly spending limit.
3. Under **API keys**, create a key and copy it. Keep it secret: anyone with it can spend your credit.

### 2. Put the project on GitHub
1. On github.com, click **+** (top right), then **New repository**. Name it e.g. `market-daily`, choose **Public**, and click **Create repository**.
2. On the new repository's page, click **uploading an existing file** and drag in everything from this folder, **including the hidden `.github` folder**. Then click **Commit changes**.

### 3. Give GitHub your Claude key
In your repository: **Settings → Secrets and variables → Actions → New repository secret**.
- Name: `ANTHROPIC_API_KEY`
- Secret: paste your key

### 4. Turn on the website
**Settings → Pages → Build and deployment → Source: GitHub Actions**.

### 5. Publish your first edition
Go to the **Actions** tab, click **Daily edition** on the left, then **Run workflow**. After a few minutes your paper is live at `https://<your-username>.github.io/<repository-name>/`.

Finally, paste that address into `site_url` in `config.yaml`, so LinkedIn shows a chart as the preview image when you share the link.

From now on a new edition appears every weekday at 7am New York time.

## Changing things
- **Track a different stock:** add it to a group in `config.yaml` using its Yahoo Finance symbol (search the company on finance.yahoo.com).
- **Different time or time zone:** change `timezone` and `publish_hour` in `config.yaml`. If you pick a very different time, also change the `cron` line in the workflow file, since GitHub's clock runs on UTC.
- **Cheaper:** set `model: claude-sonnet-5-5` in `config.yaml`.

*For information and education only. Not financial advice.*
