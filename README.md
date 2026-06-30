![Header](header.png)

<div align="center">

# yandex_parser

**Yandex Dzen search scraper with Excel export**

[![License](https://img.shields.io/badge/license-MIT-2C2C2C?style=for-the-badge&labelColor=1E1E1E)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-2C2C2C?style=for-the-badge&logo=python&labelColor=1E1E1E)]()
[![Playwright](https://img.shields.io/badge/playwright-browser-2C2C2C?style=for-the-badge&labelColor=1E1E1E)]()
[![Pandas](https://img.shields.io/badge/pandas-data-2C2C2C?style=for-the-badge&logo=pandas&labelColor=1E1E1E)]()

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

| Component | Technology |
|-----------|------------|
| Browser | Playwright (Chromium) |
| Parsing | BeautifulSoup, lxml |
| Data | pandas, openpyxl |
| Output | Excel (.xlsx) |

## ■ Usage

```bash
make run      # create venv, install deps, install Chromium, run parser
make clean    # remove venv
```

The parser is interactive: it prompts for topics, output filename (default `dzen_export.xlsx`), mobile/headless mode, and per-topic limits.

## ■ License

MIT © [pluttan](https://github.com/pluttan)
