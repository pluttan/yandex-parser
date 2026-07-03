<div align="center">

# yandex_parser

**Yandex Dzen search scraper with Excel export**

</div>

Scrapes Yandex Dzen search results using Playwright with Chromium. For each topic it runs a Dzen search, detects channel and article URLs, fetches article HTML, and exports the collected rows to an Excel workbook with colored terminal logging.

## ■ Features

- ❖ **Dzen search scraping** — queries `dzen.ru/search` per topic and collects article links
- ❖ **Channel/article detection** — distinguishes Dzen channel pages from articles via URL heuristics
- ❖ **Headless browser** — Playwright + Chromium with anti-automation flags, proxy and mobile emulation
- ❖ **Human-like pacing** — randomized delays between actions to mimic real browsing
- ❖ **Excel export** — rows (url, title, html, topic, fetched_at) via pandas + openpyxl, optional per-topic sheets
- ❖ **Colored logging** — ANSI-colored levels (INFO/OK/WARN/ERROR/PROGRESS/STATS), colorama enabled on Windows

## ■ Stack

<div align="center">

| Component | Technology |
|-----------|------------|
| Browser | Playwright (Chromium) |
| Parsing | BeautifulSoup, lxml |
| Data | pandas, openpyxl |
| Output | Excel (.xlsx) |

</div>

## ■ How It Works

```
1. Prompts interactively for topics, output filename, mobile/headless mode, and per-topic limits.
2. For each topic, opens dzen.ru/search via Playwright + Chromium with anti-automation flags.
3. Collects article links, distinguishing channel pages from articles via URL heuristics; applies randomized delays between actions.
4. Fetches each article's HTML using BeautifulSoup + lxml.
5. Exports collected rows (url, title, html, topic, fetched_at) to an Excel workbook via pandas + openpyxl.
```

## ■ Usage

```bash
make run      # create venv, install deps, install Chromium, run parser
make clean    # remove venv
```

The parser is interactive: it prompts for topics, output filename (default `dzen_export.xlsx`), mobile/headless mode, and per-topic limits.

## ■ License

MIT © [pluttan](https://github.com/pluttan)
