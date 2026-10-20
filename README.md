# The Morning Ledger

A daily markets newspaper that writes and publishes itself every weekday at 7am New York time.

Every morning, GitHub runs a small program that:

1. downloads prices for about 80 markets from Yahoo Finance: stock indexes around the world, bond yields, currencies, commodities, crypto, US sectors, Big Tech, banks, and themes on the come-up;
2. draws the charts;
3. has Claude Code write the day's article, using web search to find out *why* things moved. This runs on a Claude Pro subscription, so there's no extra cost;
4. turns it all into a newspaper-style web page and publishes it on GitHub Pages.

If Claude can't write the article on a given day, for example because the subscription's usage limit has been reached, the paper still comes out with the numbers and charts.

Past editions are kept in an archive at `archive.html`.

## What's in this folder

| File | What it does |
|---|---|
| `config.yaml` | **Your settings.** Paper name, time zone, publishing time, and every market tracked. Edit this freely. |
| `make_edition.py` | The main program. `prepare` gets prices and draws charts; `publish` builds the pages. |
| `newsroom/market_data.py` | Downloads prices and works out the daily, weekly, monthly and year-to-date moves |
| `newsroom/charts.py` | Draws the charts |
| `newsroom/writer.py` | The brief Claude follows when writing the article: sections, tone and rules |
| `newsroom/page.py` + `newsroom/templates/` | Builds the web pages and controls how they look |
| `.github/workflows/daily-edition.yml` | The alarm clock: tells GitHub when to run everything |
| `docs/` | The finished website (created automatically; don't edit by hand) |

## One-time setup

### 1. Put the project on GitHub
1. On github.com, click **+** (top right), then **New repository**. Name it e.g. `market-daily`, choose **Public**, and click **Create repository**.
2. Click **uploading an existing file** and drag in everything from this folder, **including the `.github` folder**. Then click **Commit changes**.

### 2. Connect your Claude subscription
1. Install Claude Code on your computer, then in a terminal run `claude setup-token`.
2. Sign in with your Claude account in the browser window that opens. The terminal then shows a long token.
3. In your repository, go to **Settings → Secrets and variables → Actions → New repository secret**.
   - Name: `CLAUDE_CODE_OAUTH_TOKEN`
   - Secret: paste the token

Keep the token secret: it lets anyone use your Claude subscription.

### 3. Turn on the website
**Settings → Pages → Build and deployment → Source: GitHub Actions**.

### 4. Publish your first edition
Go to the **Actions** tab, click **Daily edition** on the left, then **Run workflow**. After about 10 minutes your paper is live at `https://<your-username>.github.io/<repository-name>/`.

Finally, paste that address into `site_url` in `config.yaml`, so LinkedIn shows a chart as the preview image when you share the link.

From now on a new edition appears every weekday at 7am New York time.

## Changing things
- **Track a different stock:** add it to a group in `config.yaml` using its Yahoo Finance symbol (search the company on finance.yahoo.com).
- **Different time or time zone:** change `timezone` and `publish_hour` in `config.yaml`. If you pick a very different time, also change the `cron` line in the workflow file, since GitHub's clock runs on UTC.
- **The article itself:** edit the brief in `newsroom/writer.py`.

*For information and education only. Not financial advice.*
