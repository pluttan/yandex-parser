<div align="center">

# yandex_parser

**Скрапер поиска Yandex Dzen с экспортом в Excel**

</div>

Собирает результаты поиска Yandex Dzen с помощью Playwright и Chromium. Для каждой темы выполняет поиск по Dzen, определяет URL каналов и статей, загружает HTML статей и экспортирует собранные строки в книгу Excel с цветным логированием в терминале.

## ■ Возможности

- ❖ **Скрапинг поиска Dzen** — запрашивает `dzen.ru/search` по каждой теме и собирает ссылки на статьи
- ❖ **Определение каналов/статей** — различает страницы каналов Dzen и статьи по эвристике URL
- ❖ **Headless-браузер** — Playwright + Chromium с флагами против автоматизации, поддержка прокси и эмуляция мобильного устройства
- ❖ **Имитация поведения человека** — случайные задержки между действиями для имитации реального просмотра
- ❖ **Экспорт в Excel** — строки (url, title, html, topic, fetched_at) через pandas + openpyxl, опциональные листы по темам
- ❖ **Цветное логирование** — ANSI-цветные уровни (INFO/OK/WARN/ERROR/PROGRESS/STATS), colorama включена на Windows

## ■ Стек

<div align="center">

| Компонент | Технология |
|-----------|------------|
| Браузер | Playwright (Chromium) |
| Парсинг | BeautifulSoup, lxml |
| Данные | pandas, openpyxl |
| Вывод | Excel (.xlsx) |

</div>

## ■ Как это работает

```
1. Интерактивно запрашивает темы, имя выходного файла, режим mobile/headless и лимиты по темам.
2. Для каждой темы открывает dzen.ru/search через Playwright + Chromium с флагами против автоматизации.
3. Собирает ссылки на статьи, различая страницы каналов и статьи по эвристике URL; применяет случайные задержки между действиями.
4. Загружает HTML каждой статьи с помощью BeautifulSoup + lxml.
5. Экспортирует собранные строки (url, title, html, topic, fetched_at) в книгу Excel через pandas + openpyxl.
```

## ■ Использование

```bash
make run      # create venv, install deps, install Chromium, run parser
make clean    # remove venv
```

Парсер интерактивен: запрашивает темы, имя файла (по умолчанию `dzen_export.xlsx`), режим mobile/headless и лимиты по темам.

## ■ Лицензия

MIT © [pluttan](https://github.com/pluttan)
