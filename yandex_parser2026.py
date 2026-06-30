import argparse
import asyncio
import random
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit, urlencode, parse_qsl, quote_plus

import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import secrets
import string

import os
import sys
import re


def init_console():
    if os.name == 'nt':
        try:
            import colorama
            colorama.init()
        except ImportError:
            pass


def log_info(msg):
    print(f"\033[36m[INFO]\033[0m {msg}")


def log_success(msg):
    print(f"\033[32m[OK]\033[0m {msg}")


def log_warning(msg):
    print(f"\033[33m[WARN]\033[0m {msg}")


def log_error(msg):
    print(f"\033[31m[ERROR]\033[0m {msg}")


def log_progress(msg):
    print(f"\033[35m[PROGRESS]\033[0m {msg}")


def log_stats(msg):
    print(f"\033[34m[STATS]\033[0m {msg}")


def now_iso():
    try:
        return datetime.now().astimezone().isoformat(timespec="seconds")
    except Exception:
        return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def is_channel_url(url):
    if not url:
        return False

    channel_indicators = [
        '?tab=longs',
        '?tab=shorts',
        '?tab=articles',
        '?tab=videos',
        '?tab=posts',
        '?tab=content',
        '?lang=ru&country_code=ru&parent_rid=',
        '?from_parent_id=',
        '?from_parent_type=',
        '?from_page=other_page'
    ]

    for indicator in channel_indicators:
        if indicator in url:
            return True

    if '/elvira_skarain' in url or '/b17.ru' in url or '/skywell' in url or '/jaya' in url or '/05031973' in url:
        return True

    if url in ['https://m.dzen.ru/', 'https://dzen.ru/', 'https://www.dzen.ru/']:
        return True

    if '/video' in url or '/channel' in url or '/user' in url or '/profile' in url:
        return True

    if url.endswith('/') and ('dzen.ru' in url or 'm.dzen.ru' in url):
        if not '/a/' in url and not 'aK_' in url:
            return True

    return False


def is_article_url(url):
    if not url:
        return False

    if is_channel_url(url):
        return False

    article_indicators = [
        '/a/',
        'aK_',
        '/media/'
    ]

    for indicator in article_indicators:
        if indicator in url:
            return True

    return False


def normalize_url(href, base="https://dzen.ru"):
    try:
        url = urljoin(base, href)
        pr = urlsplit(url)

        if "/a/" in pr.path:
            article_id = pr.path.split("/a/")[1].split("?")[0].split("/")[0]
            normalized_url = f"https://dzen.ru/a/{article_id}"
            return normalized_url

        if "aK_" in pr.path:
            article_id = pr.path.split("aK_")[1].split("?")[0].split("/")[0]
            normalized_url = f"https://dzen.ru/a/{article_id}"
            return normalized_url

        if "/media/" in pr.path:
            media_id = pr.path.split("/media/")[1].split("?")[0].split("/")[0]
            normalized_url = f"https://dzen.ru/media/{media_id}"
            return normalized_url

        qs = [(k, v) for k, v in parse_qsl(pr.query, keep_blank_values=True)
              if k.lower()[:3] != "utm" and k.lower() not in
              ("yclid", "from", "feed_exp", "integration", "place", "secdata",
               "rid", "referrer_clid", "sid", "save_query", "type_filter")]
        new_query = urlencode(qs, doseq=True)
        pr = pr._replace(query=new_query, fragment="")
        return urlunsplit(pr)
    except Exception as e:
        print(f"Ошибка при нормализации URL {href}: {e}")
        return href


def human_delay(ms_from=500, ms_to=1200):
    time.sleep(random.uniform(ms_from / 1000.0, ms_to / 1000.0))


def open_search_results(page, query):
    try:
        print("Сначала заходим на раздел статей Яндекс.Дзен...")
        entry_urls = [
            "https://dzen.ru/articles",
            "https://www.dzen.ru/articles",
            "http://dzen.ru/articles",
            "https://dzen.ru",
            "https://www.dzen.ru",
            "http://dzen.ru",
            "https://ya.ru",
            "https://yandex.ru"
        ]
        opened = False
        for attempt in range(3):
            for u in entry_urls:
                try:
                    print(f"Открываю: {u}")
                    page.goto(u, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_selector("body", timeout=15000)
                    opened = True
                    break
                except Exception as e:
                    print(f"Не удалось открыть {u}: {e}")
                    human_delay(800, 1400)
            if opened:
                break
            human_delay(1200 + attempt * 500, 2000 + attempt * 700)
        if not opened:
            raise RuntimeError("Не удалось открыть dzen.ru после нескольких попыток")
        human_delay(3000, 4000)

        print("Главная страница загружена, теперь ищем поиск...")

        print("Проверяю наличие баннера геолокации...")
        try:
            geo_banner_selectors = [
                'button[aria-label*="закрыть"]',
                'button[aria-label*="close"]',
                'button[class*="close"]',
                'button[class*="dismiss"]',
                'button[class*="geo"]',
                'button[class*="location"]',
                'div[class*="geo"] button',
                'div[class*="location"] button',
                'div[class*="banner"] button',
                'div[class*="popup"] button',
                'button:has-text("✕")',
                'button:has-text("×")',
                'button:has-text("X")',
                'button:has-text("Закрыть")',
                'button:has-text("Close")',
                'button:has-text("Отмена")',
                'button:has-text("Cancel")',
                '[data-qa*="close"]',
                '[data-testid*="close"]'
            ]

            for selector in geo_banner_selectors:
                try:
                    close_button = page.locator(selector).first
                    if close_button.count() > 0:
                        print(f"Найден баннер геолокации, закрываю: {selector}")
                        close_button.click(timeout=5000)
                        human_delay(1000, 1500)
                        break
                except Exception:
                    continue
        except Exception as e:
            print(f"Ошибка при закрытии баннера геолокации: {e}")

        print("Проверяю наличие модальных окон...")
        try:
            modal_selectors = [
                'div[data-testid="modal-overlay"]',
                'div[class*="modal"]',
                'div[class*="overlay"]',
                'div[class*="popup"]',
                'div[class*="dialog"]',
                'div[role="dialog"]',
                'div[aria-modal="true"]',
                'div[class*="dzen-desktop--modal"]'
            ]

            for selector in modal_selectors:
                try:
                    modal = page.locator(selector).first
                    if modal.count() > 0:
                        print(f"Найден модальный оверлей, закрываю: {selector}")
                        page.keyboard.press("Escape")
                        human_delay(1000, 1500)
                        break
                except Exception:
                    continue
        except Exception as e:
            print(f"Ошибка при закрытии модального окна: {e}")

        current_url = page.url
        print(f"Текущий URL после входа на Дзен: {current_url}")

        if "captcha" in current_url.lower() or "smartcaptcha" in current_url.lower() or "block" in current_url.lower():
            print("Обнаружена капча или блокировка на главной странице!")
            return False

        print("Главная страница загружена, теперь ищем поиск...")

        search_button_selectors = [
            'button[aria-label*="поиск"]',
            'button[title*="поиск"]',
            'button[class*="search"]',
            'button[data-qa*="search"]',
            'button:has-text("Поиск")',
            'button:has-text("Search")',
            'a[href*="search"]',
            'a[class*="search"]',
            'div[class*="search"]',
            'span[class*="search"]',
            '[role="search"]',
            '[data-qa="search-button"]',
            '[data-testid="search-button"]'
        ]

        search_button = None
        for selector in search_button_selectors:
            try:
                search_button = page.locator(selector).first
                if search_button.count() > 0:
                    print(f"Найдена кнопка поиска: {selector}")
                    break
            except Exception:
                continue

        if search_button and search_button.count() > 0:
            print("Кликаю по кнопке поиска...")
            try:
                search_button.click(timeout=10000)
                human_delay(2000, 3000)

                print("Проверяю наличие баннера геолокации после клика...")
                try:
                    geo_banner_selectors = [
                        'button[aria-label*="закрыть"]',
                        'button[aria-label*="close"]',
                        'button[class*="close"]',
                        'button[class*="dismiss"]',
                        'button[class*="geo"]',
                        'button[class*="location"]',
                        'div[class*="geo"] button',
                        'div[class*="location"] button',
                        'div[class*="banner"] button',
                        'div[class*="popup"] button',
                        'button:has-text("✕")',
                        'button:has-text("×")',
                        'button:has-text("X")',
                        'button:has-text("Закрыть")',
                        'button:has-text("Close")',
                        'button:has-text("Отмена")',
                        'button:has-text("Cancel")',
                        '[data-qa*="close"]',
                        '[data-testid*="close"]'
                    ]

                    for selector in geo_banner_selectors:
                        try:
                            close_button = page.locator(selector).first
                            if close_button.count() > 0:
                                print(f"Найден баннер геолокации после клика, закрываю: {selector}")
                                close_button.click(timeout=5000)
                                human_delay(1000, 1500)
                                break
                        except Exception:
                            continue
                except Exception as e:
                    print(f"Ошибка при закрытии баннера геолокации после клика: {e}")

            except Exception as e:
                print(f"Ошибка при клике по кнопке поиска: {e}")
                try:
                    page.click(selector, timeout=5000)
                    human_delay(2000, 3000)
                except Exception as e2:
                    print(f"Альтернативный клик тоже не сработал: {e2}")
                    print("Пробую работать с iframe...")
                    try:
                        iframe_selectors = [
                            'iframe[aria-label*="Поиск"]',
                            'iframe[class*="search"]',
                            'iframe[class*="dzen-search"]',
                            'iframe[id*="search"]',
                            'iframe[src*="search"]',
                            'iframe[src*="dzen"]'
                        ]

                        iframe = None
                        iframe_selector_used = None
                        for iframe_selector in iframe_selectors:
                            try:
                                iframe = page.frame_locator(iframe_selector).first
                                iframe_selector_used = iframe_selector
                                print(f"Найден iframe поиска: {iframe_selector}")
                                break
                            except Exception:
                                continue

                        if iframe:
                            print("Работаю с iframe...")
                            iframe_input_selectors = [
                                'input[type="text"]',
                                'input[type="search"]',
                                'input[placeholder*="поиск"]',
                                'input[placeholder*="найти"]',
                                'input[placeholder*="Что"]',
                                'input[placeholder*="что"]',
                                'input[name="text"]',
                                'input[class*="input"]',
                                'input[class*="search"]'
                            ]

                            search_input_iframe = None
                            input_selector_used = None
                            for input_selector in iframe_input_selectors:
                                try:
                                    search_input_iframe = iframe.locator(input_selector).first
                                    input_selector_used = input_selector
                                    print(f"Найдено поле поиска в iframe: {input_selector}")
                                    break
                                except Exception:
                                    continue

                            if search_input_iframe:
                                print("Пробую переключиться на iframe напрямую...")
                                try:
                                    frames = page.frames
                                    target_frame = None
                                    for frame in frames:
                                        try:
                                            f_url = (frame.url or "").lower()
                                        except Exception:
                                            continue
                                        if "dzensearch" in f_url or "portal/dzensearch" in f_url:
                                            target_frame = frame
                                            print(f"Найден подходящий frame: {frame.url}")
                                            break

                                    if target_frame:
                                        print("Переключаюсь на frame...")
                                        human_delay(1000, 1500)

                                        selector_inp = 'input[name="text"], input[type="search"], input[type="text"]'
                                        try:
                                            target_frame.wait_for_selector(selector_inp, timeout=10000)
                                        except Exception:
                                            pass

                                        print("Кликаю по полю поиска в frame...")
                                        input_element = target_frame.locator(selector_inp).first
                                        try:
                                            input_element.click(timeout=8000)
                                        except Exception:
                                            pass
                                        human_delay(800, 1200)

                                        print("Очищаю поле поиска в frame...")
                                        try:
                                            input_element.fill("", timeout=8000)
                                        except Exception:
                                            pass
                                        human_delay(400, 700)

                                        print(f"Ввожу запрос в frame: {query}")
                                        try:
                                            input_element.type(query, delay=100, timeout=10000)
                                        except Exception:
                                            try:
                                                input_element.fill(query, timeout=10000)
                                            except Exception:
                                                raise
                                        human_delay(800, 1200)

                                        print("Нажимаю Enter в frame...")
                                        try:
                                            input_element.press("Enter", timeout=8000)
                                        except Exception:
                                            try:
                                                target_frame.keyboard.press("Enter")
                                            except Exception:
                                                pass
                                        human_delay(2500, 3500)

                                        current_url = page.url
                                        print(f"URL после поиска в frame: {current_url}")

                                        if "search" in current_url.lower() or "text=" in current_url.lower():
                                            print("Поиск в frame выполнен успешно")
                                            return True
                                        else:
                                            print("Поиск в frame не сработал")
                                    else:
                                        print("Не найден подходящий frame")
                                except Exception as e:
                                    print(f"Ошибка при работе с frame напрямую: {e}")

                                print("Пробую JavaScript метод...")
                                try:
                                    result = page.evaluate("""
                                        (() => {
                                            const iframe = document.querySelector('iframe[aria-label*="Поиск"]');
                                            if (iframe && iframe.contentDocument) {
                                                const input = iframe.contentDocument.querySelector('input[type="text"], input[type="search"], input[placeholder*="поиск"]');
                                                if (input) {
                                                    input.focus();
                                                    input.value = '';
                                                    input.value = arguments[0];
                                                    input.dispatchEvent(new Event('input', { bubbles: true }));
                                                    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
                                                    return true;
                                                }
                                            }
                                            return false;
                                        })()
                                    """, query)

                                    if result:
                                        print("JavaScript поиск выполнен")
                                    else:
                                        print("JavaScript поиск не сработал")
                                    human_delay(3000, 4000)

                                    current_url = page.url
                                    print(f"URL после JavaScript поиска: {current_url}")

                                    if "search" in current_url.lower() or "text=" in current_url.lower():
                                        print("JavaScript поиск выполнен успешно")
                                        return True
                                    else:
                                        print("JavaScript поиск не сработал")
                                except Exception as e:
                                    print(f"Ошибка при JavaScript поиске: {e}")

                                print("Пробую стандартный метод с iframe...")
                                print("Кликаю по полю поиска в iframe...")
                                try:
                                    search_input_iframe.click()
                                    human_delay(1000, 1500)
                                except Exception as e:
                                    print(f"Ошибка при клике по полю в iframe: {e}")

                                print("Очищаю поле поиска в iframe...")
                                try:
                                    search_input_iframe.fill("")
                                    human_delay(500, 800)
                                except Exception as e:
                                    print(f"Ошибка при очистке поля в iframe: {e}")

                                print(f"Ввожу запрос в iframe: {query}")
                                try:
                                    search_input_iframe.type(query, delay=100)
                                    human_delay(1000, 1500)
                                except Exception as e:
                                    print(f"Ошибка при вводе в iframe: {e}")
                                    try:
                                        search_input_iframe.fill(query)
                                        human_delay(1000, 1500)
                                    except Exception as e2:
                                        print(f"Ошибка при заполнении в iframe: {e2}")

                                print("Нажимаю Enter в iframe...")
                                try:
                                    search_input_iframe.press("Enter")
                                    human_delay(3000, 4000)
                                except Exception as e:
                                    print(f"Ошибка при нажатии Enter в iframe: {e}")

                                current_url = page.url
                                print(f"URL после поиска в iframe: {current_url}")

                                if "search" in current_url.lower() or "text=" in current_url.lower():
                                    print("Поиск в iframe выполнен успешно")
                                    return True
                                else:
                                    print("Поиск в iframe не сработал")

                                    print("Пробую альтернативный метод с iframe...")
                                    try:
                                        page.keyboard.press("Enter")
                                        human_delay(2000, 3000)
                                        current_url = page.url
                                        print(f"URL после Enter: {current_url}")

                                        if "search" in current_url.lower() or "text=" in current_url.lower():
                                            print("Альтернативный поиск в iframe сработал")
                                            return True
                                    except Exception as e:
                                        print(f"Ошибка при альтернативном поиске в iframe: {e}")
                    except Exception as e3:
                        print(f"Ошибка при работе с iframe: {e3}")
                        print("Iframe не работает, перехожу к альтернативному методу...")
                        return perform_search_alternative(page, query)

        print("Ищем поле ввода поиска...")

        search_input_selectors = [
            'input[type="search"]',
            'input[placeholder*="поиск"]',
            'input[placeholder*="найти"]',
            'input[placeholder*="Что"]',
            'input[placeholder*="что"]',
            'input[placeholder*="Search"]',
            'input[placeholder*="search"]',
            'input[aria-label*="поиск"]',
            'input[name="text"]',
            'input[class*="search"]',
            'input[data-qa*="search"]',
            'input[data-qa="search-input"]',
            'input[data-testid*="search"]',
            'input[class*="input"]',
            'input[type="text"]',
            'textarea[placeholder*="поиск"]',
            'textarea[placeholder*="найти"]',
            'input[class*="dzen-search"]',
            'input[class*="search-input"]',
            'input[class*="search-field"]',

            'form[action*="search"] input',
            'header input[type="search"]',
            'div[class*="search"] input[type="text"]'
        ]

        search_input = None
        for selector in search_input_selectors:
            try:
                search_input = page.locator(selector).first
                if search_input.count() > 0:
                    print(f"Найдено поле поиска: {selector}")
                    break
            except Exception:
                continue

        if not search_input or search_input.count() == 0:
            print("Поле поиска не найдено, пробую альтернативный метод...")
            return perform_search_alternative(page, query)

        print("Кликаю по полю поиска...")
        try:
            search_input.click(timeout=10000)
            human_delay(1000, 1500)
        except Exception as e:
            print(f"Ошибка при клике по полю поиска: {e}")
            try:
                page.click(selector, timeout=5000)
                human_delay(1000, 1500)
            except Exception as e2:
                print(f"Альтернативный клик по полю поиска тоже не сработал: {e2}")

        print("Очищаю поле поиска...")
        try:
            search_input.fill("")
            human_delay(500, 800)
        except Exception as e:
            print(f"Ошибка при очистке поля поиска: {e}")

        print(f"Ввожу запрос: {query}")
        try:
            search_input.type(query, delay=100, timeout=10000)
            human_delay(1000, 1500)
        except Exception as e:
            print(f"Ошибка при вводе запроса: {e}")
            try:
                search_input.fill(query, timeout=10000)
                human_delay(1000, 1500)
            except Exception as e2:
                print(f"Ошибка при заполнении запроса: {e2}")
                return perform_search_alternative(page, query)

        print("Нажимаю Enter для поиска...")
        try:
            search_input.press("Enter", timeout=10000)
            human_delay(3000, 4000)
        except Exception as e:
            print(f"Ошибка при нажатии Enter: {e}")
            try:
                page.keyboard.press("Enter")
                human_delay(3000, 4000)
            except Exception as e2:
                print(f"Альтернативное нажатие Enter тоже не сработало: {e2}")

        current_url = page.url
        print(f"URL после поиска: {current_url}")

        if "search" not in current_url.lower() and "text=" not in current_url.lower():
            print("Поиск не сработал через Enter, пробую найти кнопку поиска...")

            submit_button_selectors = [
                'button[type="submit"]',
                'button[class*="search"]',
                'button[data-qa*="search"]',
                'button[aria-label*="поиск"]',
                'button[title*="поиск"]',
                'button:has-text("Найти")',
                'button:has-text("Поиск")',
                'button:has-text("Search")',
                'input[type="submit"]',
                '[data-qa="search-submit"]',
                '[data-testid="search-submit"]'
            ]

            for button_selector in submit_button_selectors:
                try:
                    button = page.locator(button_selector).first
                    if button.count() > 0:
                        print(f"Найдена кнопка отправки: {button_selector}")
                        button.click(timeout=10000)
                        human_delay(3000, 4000)
                        break
                except Exception as e:
                    print(f"Ошибка при клике по кнопке {button_selector}: {e}")
                    continue

            current_url = page.url
            print(f"URL после клика по кнопке отправки: {current_url}")

            if "search" not in current_url.lower() and "text=" not in current_url.lower():
                print("Поиск не сработал, пробую альтернативный метод...")
                return perform_search_alternative(page, query)

        current_url = page.url
        print(f"Финальный URL: {current_url}")

        if "captcha" in current_url.lower() or "block" in current_url.lower():
            print("Обнаружена капча или блокировка после поиска!")
            return False

        page_content = page.content()
        if len(page_content) < 1000:
            print("Страница поиска слишком короткая")
            return False

        if "search" not in current_url.lower() and "text=" not in current_url.lower():
            print("Поиск не сработал, пробую альтернативный метод...")
            return perform_search_alternative(page, query)

        print("Поиск выполнен успешно")

        print("Жду загрузки результатов поиска...")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        human_delay(2000, 3000)
        return True

    except Exception as e:
        print(f"Ошибка при открытии страницы поиска для '{query}': {e}")
        return False


def perform_search_alternative(page, query):
    try:
        print("Пробую альтернативный метод поиска через URL...")
        encoded = quote_plus(query)

        urls_to_try = [
            f"https://dzen.ru/search?text={encoded}",
            f"https://dzen.ru/search?text={encoded}&clid=225",
            f"https://dzen.ru/search?text={encoded}&clid=225&win=579",
            f"https://dzen.ru/search?text={encoded}&clid=225&win=579&src=desktop",
            f"https://dzen.ru/search?text={encoded}&clid=225&win=579&src=desktop&lr=213",
            f"https://dzen.ru/search?text={encoded}&clid=225&win=579&src=desktop&lr=213&p=0"
        ]

        for url in urls_to_try:
            try:
                print(f"Пробую URL: {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_selector("body", timeout=15000)
                human_delay(800, 1600)

                print("Проверяю наличие баннера геолокации на странице поиска...")
                try:
                    geo_banner_selectors = [
                        'button[aria-label*="закрыть"]',
                        'button[aria-label*="close"]',
                        'button[class*="close"]',
                        'button[class*="dismiss"]',
                        'button[class*="geo"]',
                        'button[class*="location"]',
                        'div[class*="geo"] button',
                        'div[class*="location"] button',
                        'div[class*="banner"] button',
                        'div[class*="popup"] button',
                        'button:has-text("✕")',
                        'button:has-text("×")',
                        'button:has-text("X")',
                        'button:has-text("Закрыть")',
                        'button:has-text("Close")',
                        'button:has-text("Отмена")',
                        'button:has-text("Cancel")',
                        '[data-qa*="close"]',
                        '[data-testid*="close"]'
                    ]

                    for selector in geo_banner_selectors:
                        try:
                            close_button = page.locator(selector).first
                            if close_button.count() > 0:
                                print(f"Найден баннер геолокации на странице поиска, закрываю: {selector}")
                                close_button.click(timeout=5000)
                                human_delay(1000, 1500)
                                break
                        except Exception:
                            continue
                except Exception as e:
                    print(f"Ошибка при закрытии баннера геолокации на странице поиска: {e}")

                human_delay(2000, 3000)

                print("Проверяю наличие баннера геолокации повторно...")
                try:
                    for selector in geo_banner_selectors:
                        try:
                            close_button = page.locator(selector).first
                            if close_button.count() > 0:
                                print(f"Найден баннер геолокации при повторной проверке, закрываю: {selector}")
                                close_button.click(timeout=5000)
                                human_delay(1000, 1500)
                                break
                        except Exception:
                            continue
                except Exception as e:
                    print(f"Ошибка при повторной проверке баннера геолокации: {e}")

                current_url = page.url
                print(f"Текущий URL: {current_url}")

                if "captcha" in current_url.lower() or "block" in current_url.lower():
                    print("Обнаружена капча или блокировка!")
                    continue

                page_content = page.content()
                if len(page_content) < 1000:
                    print("Страница слишком короткая, пробую следующий URL")
                    continue

                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass

                print("Страница успешно загружена")
                return True

            except Exception as e:
                print(f"Ошибка при загрузке {url}: {e}")
                continue

        print("Не удалось загрузить ни одну страницу поиска")
        return False

    except Exception as e:
        print(f"Ошибка при альтернативном поиске: {e}")
        return False


def collect_and_parse_articles(page, query, max_scrolls, empty_limit, scroll_step_px, max_articles_per_topic,
                               per_article_delay_ms, max_retries, min_content_length, topic, output_path,
                               per_topic_sheet, no_content=False):
    if not open_search_results(page, query):
        log_error(f"Не удалось открыть страницу поиска для запроса: {query}")
        return []

    seen_urls = set()
    seen_titles = set()
    seen_content_hashes = set()
    processed_urls = set()
    parsed_articles = []
    empty_runs = 0
    total_scrolls = 0
    batch_size = 10
    last_article_count = 0
    consecutive_no_new_articles = 0
    max_consecutive_no_new = 3

    log_info(f"Начинаю сбор статей для темы: {topic}")
    log_info("Жду появления результатов поиска...")
    try:
        page.wait_for_selector('a[href^="https://dzen.ru/a/"], a[href^="/a/"]', timeout=15000)
        log_success("Результаты поиска загружены")
    except PlaywrightTimeoutError:
        try:
            page.wait_for_selector('a[href*="/a/"]', timeout=10000)
            log_success("Результаты поиска загружены (альтернативный селектор)")
        except PlaywrightTimeoutError:
            try:
                page.wait_for_selector('a[href*="dzen.ru"]', timeout=8000)
                log_success("Результаты поиска загружены (общий селектор)")
            except PlaywrightTimeoutError:
                log_warning(f"Не найдены ссылки на статьи для запроса: {query}")
                log_info("Пробую альтернативные селекторы...")

        alternative_selectors = [
            'a[href*="/a/"]',
            'a[href*="dzen.ru/a/"]',
            'a[data-qa*="article"]',
            'a[class*="article"]',
            'a[class*="link"]',
            'a[class*="card"]',
            'a[class*="item"]',
            'a[class*="result"]',
            'div[class*="article"] a',
            'div[class*="card"] a',
            'div[class*="item"] a',
            'div[class*="result"] a',
            'a[href*="article"]',
            'a[href*="post"]',
            'a[href*="story"]',
            'a[href*="entry"]',
            'a[href*="content"]',
            'a[href*="text"]',
            'a[href*="body"]',
            'a[href*="main"]',
            'a[href*="section"]',
            'a[href*="div"]',
            'a[href*="span"]',
            'a[href*="p"]',
            'a[href*="h1"]',
            'a[href*="h2"]',
            'a[href*="h3"]',
            'a[href*="h4"]',
            'a[href*="h5"]',
            'a[href*="h6"]',
            'a[href*="ul"]',
            'a[href*="ol"]',
            'a[href*="li"]',
            'a[href*="blockquote"]',
            'a[href*="pre"]',
            'a[href*="code"]',
            'a[href*="strong"]',
            'a[href*="em"]',
            'a[href*="b"]',
            'a[href*="i"]',
            'a[href*="br"]',
            'a[href*="mark"]',
            'a[href*="del"]',
            'a[href*="ins"]',
            'a[href*="sub"]',
            'a[href*="sup"]',
            'a[href*="small"]',
            'a[href*="big"]',
            'a[href*="cite"]',
            'a[href*="q"]',
            'a[href*="abbr"]',
            'a[href*="acronym"]',
            'a[href*="dfn"]',
            'a[href*="kbd"]',
            'a[href*="samp"]',
            'a[href*="var"]',
            'a[href*="time"]',
            'a[href*="figure"]',
            'a[href*="figcaption"]',
            'a[href*="aside"]',
            'a[href*="header"]',
            'a[href*="footer"]',
            'a[href*="nav"]',
            'a[href*="main"]',
            'a[href*="article"]',
            'a[href*="section"]',
            'article a[href*="/a/"]',
            'article a[href*="dzen.ru/a/"]',
            'div a[href*="/a/"]',
            'div a[href*="dzen.ru/a/"]',
            'a[href*="aK_"]',
            'a[href*="a/"]',
            'a[href*="dzen.ru"]',
            'a[href*="zen.yandex.com"]',
            'a[href*="yandex.com"]',
            'a[href*="ya.ru"]',
            'a[href*="yandex.ru"]',
            'a[href*="feed"]',
            'a[href*="article"]',
            'a[href*="post"]',
            'a[href*="story"]',
            'a[href*="entry"]',
            'a[href*="content"]',
            'a[href*="text"]',
            'a[href*="body"]',
            'a[href*="main"]',
            'a[href*="section"]',
            'a[href*="div"]',
            'a[href*="span"]',
            'a[href*="p"]',
            'a[href*="h1"]',
            'a[href*="h2"]',
            'a[href*="h3"]',
            'a[href*="h4"]',
            'a[href*="h5"]',
            'a[href*="h6"]',
            'a[href*="ul"]',
            'a[href*="ol"]',
            'a[href*="li"]',
            'a[href*="blockquote"]',
            'a[href*="pre"]',
            'a[href*="code"]',
            'a[href*="strong"]',
            'a[href*="em"]',
            'a[href*="b"]',
            'a[href*="i"]',
            'a[href*="br"]',
            'a[href*="mark"]',
            'a[href*="del"]',
            'a[href*="ins"]',
            'a[href*="sub"]',
            'a[href*="sup"]',
            'a[href*="small"]',
            'a[href*="big"]',
            'a[href*="cite"]',
            'a[href*="q"]',
            'a[href*="abbr"]',
            'a[href*="acronym"]',
            'a[href*="dfn"]',
            'a[href*="kbd"]',
            'a[href*="samp"]',
            'a[href*="var"]',
            'a[href*="time"]',
            'a[href*="figure"]',
            'a[href*="figcaption"]',
            'a[href*="aside"]',
            'a[href*="header"]',
            'a[href*="footer"]',
            'a[href*="nav"]',
            'a[href*="main"]',
            'a[href*="article"]',
            'a[href*="section"]'
        ]

        found_selector = False
        for selector in alternative_selectors:
            try:
                page.wait_for_selector(selector, timeout=5000)
                log_success(f"Найден альтернативный селектор: {selector}")
                found_selector = True
                break
            except PlaywrightTimeoutError:
                continue

        if not found_selector:
            log_error("Не удалось найти ссылки на статьи")
            log_info("Проверяю содержимое страницы...")
            try:
                page_content = page.content()
                if "статей" in page_content.lower() or "результатов" in page_content.lower():
                    log_warning("Страница содержит результаты поиска, но ссылки не найдены")
                else:
                    log_error("Страница не содержит результатов поиска")
            except Exception as e:
                log_error(f"Ошибка при проверке содержимого: {e}")
            return []

    while True:
        try:
            try:
                current_url = page.url
                if "search" not in current_url:
                    log_warning("Покинул страницу поиска, возвращаюсь...")
                    page.go_back()
                    human_delay(2000, 3000)
                    continue

                load_more_selectors = [
                    'button:has-text("Показать ещё")',
                    'button:has-text("Показать еще")',
                    'button:has-text("Ещё")',
                    'button:has-text("Еще")',
                    '[data-qa*="load-more"] button',
                    'div[class*="load"] button'
                ]
                for lm in load_more_selectors:
                    btn = page.locator(lm).first
                    if btn.count() > 0:
                        log_info("Нажимаю кнопку 'Показать ещё'")
                        btn.click(timeout=3000)
                        human_delay(2000, 3000)
                        break
            except Exception:
                pass

            link_selectors = [
                'a[href*="/a/"]',
                'a[href*="aK_"]',
                'a[href*="/media/"]',
                'a[href*="/away?to="]',
                'a[href*="kursy-vse.ru"]',
                'div[class*="article"] a[href*="/a/"]',
                'div[class*="card"] a[href*="/a/"]',
                'div[class*="item"] a[href*="/a/"]',
                'div[class*="result"] a[href*="/a/"]',
                'article a[href*="/a/"]'
            ]

            links = []
            for selector in link_selectors:
                try:
                    found_links = page.query_selector_all(selector)
                    if found_links:
                        links.extend(found_links)
                        if len(links) > 100:
                            break
                except Exception:
                    continue

            new_links = []
            for a in links:
                try:
                    href = a.get_attribute("href")
                    if not href:
                        continue

                    url = normalize_url(href)

                    if is_channel_url(url):
                        continue

                    if is_article_url(url):
                        if url not in seen_urls and url not in processed_urls:
                            seen_urls.add(url)
                            new_links.append(url)
                            print(f"Добавлена статья: {url}")
                    elif "/away?to=" in url:
                        if url not in seen_urls and url not in processed_urls:
                            seen_urls.add(url)
                            new_links.append(url)
                            print(f"Добавлена внешняя ссылка: {url}")
                    elif "kursy-vse.ru" in url:
                        if url not in seen_urls and url not in processed_urls:
                            seen_urls.add(url)
                            new_links.append(url)
                            print(f"Добавлена внешняя ссылка: {url}")
                    else:
                        pass
                except Exception as e:
                    print(f"Ошибка при обработке ссылки: {e}")
                    continue

            if new_links:
                log_stats(f"Найдено {len(new_links)} новых ссылок, всего уникальных: {len(seen_urls)}")
                consecutive_no_new_articles = 0

                batch_to_parse = new_links[:batch_size]
                if batch_to_parse:
                    log_progress(
                        f"Парсинг пачки из {len(batch_to_parse)} статей (всего обработано: {len(parsed_articles)})...")

                    for i, url in enumerate(batch_to_parse, 1):
                        if max_articles_per_topic and max_articles_per_topic > 0 and len(
                                parsed_articles) >= max_articles_per_topic:
                            log_warning(f"Достигнут лимит статей ({max_articles_per_topic})")
                            return parsed_articles

                        normalized_url = normalize_url(url)
                        if normalized_url in processed_urls:
                            continue

                        try:
                            if no_content:
                                log_progress(
                                    f"[{len(parsed_articles) + 1}/{max_articles_per_topic if max_articles_per_topic else '∞'}] Ссылка: {url}")
                                title = ""
                                html = ""
                            else:
                                log_progress(
                                    f"[{len(parsed_articles) + 1}/{max_articles_per_topic if max_articles_per_topic else '∞'}] Парсинг: {url}")
                                if "/away?to=" in url or "kursy-vse.ru" in url:
                                    print("МАКСИМАЛЬНАЯ ОБРАБОТКА ВНЕШНЕЙ ССЫЛКИ")
                                    print("Будет использовано 4 уровня извлечения контента")
                                article_page = page.context.new_page()
                                try:
                                    title, html = parse_article(article_page, url, max_retries=max_retries,
                                                                per_article_delay_ms=per_article_delay_ms,
                                                                min_content_length=min_content_length)
                                finally:
                                    try:
                                        article_page.close()
                                    except Exception:
                                        pass
                                if not title or not html:
                                    continue

                                title_normalized = title.strip().lower()
                                if title_normalized in seen_titles:
                                    log_warning(f"Дубликат заголовка пропущен: {title[:50]}...")
                                    continue

                                content_hash = get_content_hash(html)
                                if content_hash and content_hash in seen_content_hashes:
                                    log_warning(f"Дубликат содержимого пропущен: {title[:50]}...")
                                    continue

                                if len(html) < 100:
                                    print(f"ПРЕДУПРЕЖДЕНИЕ: Контент слишком короткий ({len(html)} символов) для {url}")

                                seen_titles.add(title_normalized)
                                if content_hash:
                                    seen_content_hashes.add(content_hash)

                            row = {
                                "url": url,
                                "title": title,
                                "html": html,
                                "topic": topic,
                                "fetched_at": now_iso()
                            }
                            parsed_articles.append(row)
                            processed_urls.add(normalized_url)

                            if not no_content and ("/away?to=" in url or "kursy-vse.ru" in url):
                                print("ВНЕШНЯЯ ССЫЛКА ОБРАБОТАНА")
                                print(f"Заголовок: {title}")
                                print(f"Длина контента: {len(html)} символов")
                                if len(html) > 0:
                                    preview = html.replace('<', '').replace('>', '').replace('\n', ' ')[:200]
                                    print(f"Превью: {preview}...")
                                else:
                                    print("Контент пустой!")

                            log_success(f"Статья обработана: {title[:50]}..." if not no_content else f"Ссылка добавлена: {url}")

                            if per_topic_sheet:
                                try:
                                    df_temp = pd.DataFrame([row],
                                                           columns=["url", "title", "html", "topic", "fetched_at"])
                                    write_excel_per_topic(output_path, [(topic, df_temp)])
                                    log_info(f"Сохранено в Excel: {title[:30]}..." if not no_content else f"Сохранено в Excel: {url[:40]}...")
                                except Exception as e:
                                    log_error(f"Ошибка при сохранении в Excel: {e}")
                            else:
                                try:
                                    df_temp = pd.DataFrame([row],
                                                           columns=["url", "title", "html", "topic", "fetched_at"])
                                    write_excel_single_sheet(output_path, df_temp)
                                    log_info(f"Сохранено в Excel: {title[:30]}..." if not no_content else f"Сохранено в Excel: {url[:40]}...")
                                except Exception as e:
                                    log_error(f"Ошибка при сохранении в Excel: {e}")

                            if not no_content:
                                human_delay(500, 800)

                        except KeyboardInterrupt:
                            log_warning("Парсинг прерван пользователем")
                            return parsed_articles
                        except Exception as e:
                            if "/away?to=" in url or "kursy-vse.ru" in url:
                                print(f"ОШИБКА ПРИ ОБРАБОТКЕ ВНЕШНЕЙ ССЫЛКИ {url}: {e}")
                            log_error(f"Ошибка при парсинге {url}: {e}")
                            continue

                empty_runs = 0
            else:
                empty_runs += 1
                consecutive_no_new_articles += 1
                log_warning(
                    f"Пустая итерация {empty_runs}/{empty_limit}, подряд без новых статей: {consecutive_no_new_articles}")

                if empty_runs == 1:
                    print("Диагностика: проверяю содержимое страницы...")
                    try:
                        page_content = page.content()
                        if "статей" in page_content.lower() or "результатов" in page_content.lower():
                            print("Страница содержит результаты поиска")
                        else:
                            print("Страница не содержит результатов поиска")

                        all_links = page.query_selector_all('a')
                        print(f"Всего ссылок на странице: {len(all_links)}")

                        for i, link in enumerate(all_links[:10]):
                            try:
                                href = link.get_attribute("href")
                                text = link.inner_text()[:50] if link.inner_text() else "Нет текста"
                                print(f"Ссылка {i + 1}: {href} - {text}")
                                if href and ("/a/" in href or "aK_" in href or "/media/" in href):
                                    print(f"  ПОТЕНЦИАЛЬНАЯ СТАТЬЯ: {href}")
                            except Exception:
                                continue
                    except Exception as e:
                        print(f"Ошибка при диагностике: {e}")

            if empty_runs >= empty_limit:
                log_info(f"Достигнут лимит пустых итераций ({empty_limit})")
                break

            if consecutive_no_new_articles >= max_consecutive_no_new:
                log_info(f"Подряд {max_consecutive_no_new} итераций без новых статей, завершаю")
                break

            if max_articles_per_topic and max_articles_per_topic > 0 and len(parsed_articles) >= max_articles_per_topic:
                log_success(f"Достигнут лимит статей ({max_articles_per_topic})")
                break

            if not new_links:
                consecutive_no_new_articles += 1
            else:
                consecutive_no_new_articles = 0
                last_article_count = len(parsed_articles)

            log_progress(f"Прокручиваю страницу... (скролл {total_scrolls + 1}/{max_scrolls if max_scrolls else '∞'})")

            scroll_success = False
            for scroll_attempt in range(5):
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                    human_delay(1000, 1500)
                    scroll_success = True
                    break
                except Exception as e:
                    log_warning(f"Попытка прокрутки {scroll_attempt + 1}/5 не удалась: {e}")
                    if scroll_attempt < 4:
                        human_delay(500, 1000)
                        try:
                            page.keyboard.press("End")
                            human_delay(1000, 1500)
                            scroll_success = True
                            break
                        except Exception:
                            try:
                                page.evaluate(f"window.scrollBy(0, {scroll_step_px});")
                                human_delay(800, 1200)
                                scroll_success = True
                                break
                            except Exception:
                                continue

            if not scroll_success:
                log_error("Все 5 попыток прокрутки не удались")

            try:
                page.wait_for_load_state("domcontentloaded", timeout=8000)
            except PlaywrightTimeoutError:
                pass

            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except PlaywrightTimeoutError:
                pass

            try:
                page.wait_for_selector('a[href*="/a/"], a[href*="aK_"], a[href*="/media/"]', timeout=5000)
            except PlaywrightTimeoutError:
                pass

            total_scrolls += 1
            if max_scrolls and total_scrolls >= max_scrolls:
                log_warning(f"Достигнут лимит скроллов ({max_scrolls})")
                break

        except KeyboardInterrupt:
            log_warning("Сбор ссылок прерван пользователем")
            break
        except Exception as e:
            log_error(f"Ошибка при сборе ссылок: {e}")
            break

    log_stats(f"Всего обработано уникальных статей: {len(parsed_articles)}")
    log_stats(f"Всего найдено уникальных ссылок: {len(seen_urls)}")
    log_stats(f"Всего уникальных заголовков: {len(seen_titles)}")
    log_stats(f"Всего уникальных хешей контента: {len(seen_content_hashes)}")
    log_stats(f"Всего выполнено скроллов: {total_scrolls}")
    log_stats(f"Всего пустых итераций: {empty_runs}")
    log_success(f"Завершен сбор статей для темы: {topic}")
    return parsed_articles


def select_first_nonempty_html(page, selectors, timeout=15000):
    deadline = time.time() + timeout / 1000.0
    while time.time() < deadline:
        for sel in selectors:
            try:
                locator = page.locator(sel).first
                if locator.count() > 0:
                    html = locator.evaluate("el => el.outerHTML")
                    if html and len(html.strip()) > 50:
                        return html
            except Exception:
                continue
        human_delay(300, 600)
    return None


def extract_title(page):
    title_selectors = [
        "h1",
        'h1[class*="title"]',
        'h1[data-qa*="title"]',
        'h1[data-testid*="title"]',
        'div[class*="title"] h1',
        'div[data-qa*="title"] h1',
        'div[data-testid*="title"] h1',
        'div[class*="article-title"] h1',
        'div[class*="post-title"] h1',
        'div[class*="entry-title"] h1',
        'div[class*="story-title"] h1',
        'div[class*="title"]',
        'div[data-qa*="title"]',
        'div[data-testid*="title"]',
        'div[class*="article-title"]',
        'div[class*="post-title"]',
        'div[class*="entry-title"]',
        'div[class*="story-title"]',
        'div[class*="headline"]',
        'div[class*="heading"]',
        'div[class*="header"]',
        'h2[class*="title"]',
        'h3[class*="title"]',
        'h2',
        'h3',
        'h4',
        'h5',
        'h6',
        'div[class*="name"]',
        'div[class*="label"]',
        'div[class*="text"]',
        'span[class*="title"]',
        'span[class*="name"]',
        'span[class*="label"]',
        'span[class*="text"]',
        'meta[property="og:title"]',
        'meta[name="twitter:title"]',
        'meta[property="article:title"]',
        'meta[name="title"]',
        'meta[property="title"]'
    ]

    for selector in title_selectors:
        try:
            if selector.startswith('meta'):
                element = page.locator(selector).first
                if element.count() > 0:
                    content = element.get_attribute("content")
                    if content and len(content.strip()) > 0:
                        return content.strip()
            else:
                element = page.locator(selector).first
                if element.count() > 0:
                    txt = element.inner_text(timeout=5000).strip()
                    if txt and len(txt) > 0:
                        return txt
        except Exception:
            continue

    try:
        t = page.title()
        if t and len(t.strip()) > 0:
            return t.strip()
    except Exception:
        pass

    try:
        page_content = page.content()
        soup = BeautifulSoup(page_content, "lxml")

        for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span']):
            text = tag.get_text(separator=' ', strip=True)
            if len(text) > 5 and len(text) < 300:
                return text
    except Exception:
        pass

    try:
        js_title = page.evaluate("""
            (() => {
                const titleSelectors = ['h1', 'h2', 'h3', '.title', '[class*="title"]', '[class*="headline"]', '[class*="heading"]'];
                for (const selector of titleSelectors) {
                    const element = document.querySelector(selector);
                    if (element && element.textContent && element.textContent.trim().length > 3) {
                        return element.textContent.trim();
                    }
                }
                return null;
            })()
        """)
        if js_title:
            return js_title
    except Exception:
        pass

    try:
        meta_title = page.evaluate("""
            (() => {
                const metaTags = document.querySelectorAll('meta[property="og:title"], meta[name="twitter:title"], meta[property="article:title"]');
                for (const meta of metaTags) {
                    const content = meta.getAttribute('content');
                    if (content && content.trim().length > 3) {
                        return content.trim();
                    }
                }
                return null;
            })()
        """)
        if meta_title:
            return meta_title
    except Exception:
        pass

    return "Без заголовка"


def sanitize_article_html(html):
    try:
        allowed = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "span", "div", "ul", "li", "ol", "strong", "em", "b", "i",
                   "br", "blockquote", "pre", "code", "a", "mark", "del", "ins", "sub", "sup", "small", "big", "cite",
                   "q", "abbr", "acronym", "dfn", "kbd", "samp", "var", "time", "figure", "figcaption", "section",
                   "aside", "header", "footer", "nav", "main", "article"}
        soup = BeautifulSoup(html, "lxml")

        for bad in soup.select(
                '[data-testid*="ad"], [class*="ad-"], [class*="advert"], [id*="ad-"], [class*="social"], [class*="share"], [class*="comment"], [class*="related"], [class*="recommend"], [class*="sidebar"], [class*="widget"], [class*="banner"], [class*="popup"], [class*="modal"], [class*="overlay"], [class*="cookie"], [class*="privacy"], [class*="consent"], [class*="notification"], [class*="alert"], [class*="message"], [class*="tooltip"], [class*="toolbar"], [class*="menu"], [class*="nav"], [class*="header"], [class*="footer"], [class*="aside"], [class*="sidebar"], [class*="widget"], [class*="banner"], [class*="popup"], [class*="modal"], [class*="overlay"], [class*="cookie"], [class*="privacy"], [class*="consent"], [class*="notification"], [class*="alert"], [class*="message"], [class*="tooltip"], [class*="toolbar"], [class*="menu"], [class*="nav"], [class*="header"], [class*="footer"], [class*="aside"]'):
            bad.decompose()

        for tag in soup.find_all(True):
            if tag.name in allowed:
                if tag.name == "a":
                    href = tag.get("href")
                    if href:
                        tag.attrs = {"href": href}
                    else:
                        tag.attrs = {}
                else:
                    tag.attrs = {}
            else:
                tag.unwrap()

        removed = True
        while removed:
            removed = False
            for t in soup.find_all(
                    ["div", "span", "p", "li", "ul", "ol", "blockquote", "pre", "code", "section", "aside", "header",
                     "footer", "nav", "main", "article"]):
                if not t.get_text(strip=True) and not t.find("br"):
                    t.decompose()
                    removed = True

        text = str(soup)
        for _ in range(10):
            text = text.replace('\n\n\n', '\n\n')
            text = text.replace('\r\n\r\n\r\n', '\r\n\r\n')
            text = text.replace('\r\r\r', '\r\r')
            text = text.replace('  ', ' ')
            text = text.replace('\t\t', '\t')
            text = text.replace('  ', ' ')

        text = (text
                .replace('&nbsp;', ' ')
                .replace('&amp;', '&')
                .replace('&lt;', '<')
                .replace('&gt;', '>')
                .replace('&quot;', '"')
                .replace('&#39;', "'")
                .replace('&ldquo;', '"')
                .replace('&rdquo;', '"')
                .replace('&lsquo;', "'")
                .replace('&rsquo;', "'")
                .replace('&mdash;', '—')
                .replace('&ndash;', '–')
                .replace('&hellip;', '…')
                .replace('&copy;', '©')
                .replace('&reg;', '®')
                .replace('&trade;', '™')
                .replace('&euro;', '€')
                .replace('&pound;', '£')
                .replace('&cent;', '¢')
                .replace('&yen;', '¥')
                .replace('&sect;', '§')
                .replace('&para;', '¶')
                .replace('&deg;', '°')
                .replace('&plusmn;', '±')
                .replace('&times;', '×')
                .replace('&divide;', '÷')
                .replace('&frac12;', '½')
                .replace('&frac14;', '¼')
                .replace('&frac34;', '¾')
                .replace('&sup1;', '¹')
                .replace('&sup2;', '²')
                .replace('&sup3;', '³')
                .replace('&micro;', 'µ')
                .replace('&alpha;', 'α')
                .replace('&beta;', 'β')
                .replace('&gamma;', 'γ')
                .replace('&delta;', 'δ')
                .replace('&epsilon;', 'ε')
                .replace('&zeta;', 'ζ')
                .replace('&eta;', 'η')
                .replace('&theta;', 'θ')
                .replace('&iota;', 'ι')
                .replace('&kappa;', 'κ')
                .replace('&lambda;', 'λ')
                .replace('&mu;', 'μ')
                .replace('&nu;', 'ν')
                .replace('&xi;', 'ξ')
                .replace('&omicron;', 'ο')
                .replace('&pi;', 'π')
                .replace('&rho;', 'ρ')
                .replace('&sigma;', 'σ')
                .replace('&tau;', 'τ')
                .replace('&upsilon;', 'υ')
                .replace('&phi;', 'φ')
                .replace('&chi;', 'χ')
                .replace('&psi;', 'ψ')
                .replace('&omega;', 'ω')
                .replace('&Alpha;', 'Α')
                .replace('&Beta;', 'Β')
                .replace('&Gamma;', 'Γ')
                .replace('&Delta;', 'Δ')
                .replace('&Epsilon;', 'Ε')
                .replace('&Zeta;', 'Ζ')
                .replace('&Eta;', 'Η')
                .replace('&Theta;', 'Θ')
                .replace('&Iota;', 'Ι')
                .replace('&Kappa;', 'Κ')
                .replace('&Lambda;', 'Λ')
                .replace('&Mu;', 'Μ')
                .replace('&Nu;', 'Ν')
                .replace('&Xi;', 'Ξ')
                .replace('&Omicron;', 'Ο')
                .replace('&Pi;', 'Π')
                .replace('&Rho;', 'Ρ')
                .replace('&Sigma;', 'Σ')
                .replace('&Tau;', 'Τ')
                .replace('&Upsilon;', 'Υ')
                .replace('&Phi;', 'Φ')
                .replace('&Chi;', 'Χ')
                .replace('&Psi;', 'Ψ')
                .replace('&Omega;', 'Ω'))

        return text.strip()
    except Exception as e:
        print(f"Ошибка при очистке HTML: {e}")
        return html


def parse_article(page, url, max_retries, per_article_delay_ms, min_content_length=100):
    normalized_url = normalize_url(url)
    print(f"Нормализованный URL: {normalized_url}")

    if is_channel_url(normalized_url):
        print(f"Пропускаю канал: {normalized_url}")
        return "Канал Дзен", "<div>Это канал, а не статья</div>"

    if not is_article_url(normalized_url) and "/away?to=" not in url and "kursy-vse.ru" not in url:
        print(f"Пропускаю не-статью: {normalized_url}")
        return "Не статья", "<div>Это не статья</div>"

    attempt = 0
    while attempt < max_retries:
        attempt += 1
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector("body", timeout=15000)
            human_delay(500, 1000)

            if "/away?to=" in url:
                print("МАКСИМАЛЬНАЯ ОБРАБОТКА ВНЕШНЕЙ ССЫЛКИ...")
                human_delay(1000, 2000)

                original_url = url
                target_url = None

                try:
                    encoded_target = url.split("/away?to=")[1]
                    if encoded_target:
                        target_url = encoded_target.replace("%3A", ":").replace("%2F", "/").replace("%3F", "?").replace(
                            "%26", "&").replace("%3D", "=")
                        print(f"Целевой URL: {target_url}")
                except Exception as e:
                    print(f"Не удалось декодировать URL: {e}")

                try:
                    print("Прямой переход на целевой сайт...")
                    if target_url:
                        page.goto(target_url, wait_until="domcontentloaded", timeout=25000)
                    else:
                        page.goto(url, wait_until="domcontentloaded", timeout=25000)

                    human_delay(3000, 5000)

                    try:
                        page.wait_for_load_state("networkidle", timeout=20000)
                    except Exception:
                        pass

                    try:
                        page.wait_for_selector("body", timeout=15000)
                    except Exception:
                        pass

                except Exception as e:
                    print(f"Прямой переход не удался: {e}")
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=20000)
                        human_delay(4000, 6000)
                    except Exception:
                        pass

                current_url = page.url
                print(f"Текущий URL после обработки: {current_url}")

                if current_url and current_url != original_url:
                    print("УСПЕШНО ПЕРЕШЛИ НА ВНЕШНИЙ САЙТ!")

                    try:
                        page.evaluate("window.scrollTo(0, 0);")
                        human_delay(500, 1000)

                        for i in range(5):
                            page.evaluate(f"window.scrollTo(0, {i * 500});")
                            human_delay(300, 600)

                        page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                        human_delay(1000, 2000)

                        for i in range(3):
                            page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                            human_delay(500, 1000)

                    except Exception as e:
                        print(f"Ошибка при скролле: {e}")

                    try:
                        page.evaluate("""
                            const allButtons = document.querySelectorAll('button, a, div[role="button"], span[role="button"]');
                            const clickCandidates = [];

                            allButtons.forEach(btn => {
                                const text = btn.textContent?.toLowerCase().trim() || '';
                                if (text.includes('показать') || text.includes('загрузить') || text.includes('ещё') || text.includes('еще') ||
                                    text.includes('читать') || text.includes('развернуть') || text.includes('открыть') ||
                                    text.includes('подробнее') || text.includes('больше') || text.includes('load') ||
                                    text.includes('more') || text.includes('show') || text.includes('read')) {
                                    clickCandidates.push(btn);
                                }
                            });

                            console.log(`Найдено ${clickCandidates.length} кандидатов для клика`);
                            clickCandidates.forEach((btn, index) => {
                                try {
                                    if (btn.offsetParent !== null) {
                                        btn.click();
                                        console.log(`Клик ${index + 1} выполнен`);
                                    }
                                } catch(e) {
                                    console.log(`Клик ${index + 1} не удался: ${e.message}`);
                                }
                            });
                        """)
                        human_delay(3000, 5000)
                    except Exception as e:
                        print(f"Ошибка при кликах: {e}")

                    try:
                        page.evaluate("""
                            const expandableElements = document.querySelectorAll('[aria-expanded="false"], [data-expanded="false"], .collapsed, .hidden-content');
                            expandableElements.forEach(el => {
                                try {
                                    el.setAttribute('aria-expanded', 'true');
                                    el.setAttribute('data-expanded', 'true');
                                    el.classList.remove('collapsed');
                                    el.classList.add('expanded');
                                    el.style.display = 'block';
                                    el.style.visibility = 'visible';
                                } catch(e) {}
                            });
                        """)
                        human_delay(1000, 2000)
                    except Exception as e:
                        print(f"Ошибка при раскрытии: {e}")

                else:
                    print("ПЕРЕХОД НА ВНЕШНИЙ САЙТ НЕ УДАЛСЯ")

            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            try:
                page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass

            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2);")
                human_delay(1000, 1500)
                page.evaluate("window.scrollTo(0, 0);")
                human_delay(500, 800)
            except Exception:
                pass

            try:
                page.evaluate("""
                    const observer = new MutationObserver(() => {});
                    observer.observe(document.body, {
                        childList: true,
                        subtree: true
                    });
                    setTimeout(() => observer.disconnect(), 3000);
                """)
                human_delay(2000, 3000)
            except Exception:
                pass

            try:
                page.evaluate("""
                    const loadMoreButtons = document.querySelectorAll('button[class*="load"], button[class*="more"], button[class*="show"], button:contains("Показать"), button:contains("Загрузить"), button:contains("Ещё"), button:contains("Еще")');
                    loadMoreButtons.forEach(btn => {
                        if (btn.offsetParent !== null) {
                            btn.click();
                        }
                    });
                """)
                human_delay(2000, 3000)
            except Exception:
                pass

            try:
                page.evaluate("""
                    const expandButtons = document.querySelectorAll('button[class*="expand"], button[class*="open"], button[class*="read"], button:contains("Читать"), button:contains("Развернуть"), button:contains("Открыть"), button:contains("Показать полностью")');
                    expandButtons.forEach(btn => {
                        if (btn.offsetParent !== null) {
                            btn.click();
                        }
                    });
                """)
                human_delay(2000, 3000)
            except Exception:
                pass

            try:
                page.evaluate("""
                    const lazyElements = document.querySelectorAll('[data-src], [data-lazy], [class*="lazy"], [class*="loading"]');
                    lazyElements.forEach(el => {
                        if (el.offsetParent !== null) {
                            el.scrollIntoView();
                        }
                    });
                """)
                human_delay(1000, 1500)
            except Exception:
                pass

            try:
                page.evaluate("""
                    const articleContent = document.querySelector('article, [class*="article"], [class*="post"], [class*="entry"], [class*="story"]');
                    if (articleContent) {
                        articleContent.scrollIntoView();
                    }
                """)
                human_delay(1000, 1500)
            except Exception:
                pass

            try:
                page.evaluate("""
                    const readMoreButtons = document.querySelectorAll('button[class*="read"], button[class*="more"], button:contains("Читать"), button:contains("Показать"), button:contains("Развернуть"), button:contains("Полностью")');
                    readMoreButtons.forEach(btn => {
                        if (btn.offsetParent !== null && btn.textContent.length > 0) {
                            btn.click();
                        }
                    });
                """)
                human_delay(2000, 3000)
            except Exception:
                pass

            try:
                page.evaluate("""
                    const iframes = document.querySelectorAll('iframe[src*="dzen"], iframe[src*="article"], iframe[src*="post"]');
                    iframes.forEach(iframe => {
                        if (iframe.offsetParent !== null) {
                            iframe.scrollIntoView();
                        }
                    });
                """)
                human_delay(1000, 1500)
            except Exception:
                pass

            try:
                page.evaluate("""
                    const articleElements = document.querySelectorAll('article, [class*="article"], [class*="post"], [class*="entry"], [class*="story"]');
                    articleElements.forEach(article => {
                        if (article.offsetParent !== null) {
                            const textElements = article.querySelectorAll('p, div, span, h1, h2, h3, h4, h5, h6');
                            textElements.forEach(el => {
                                if (el.textContent && el.textContent.length > 100) {
                                    el.style.display = 'block';
                                    el.style.visibility = 'visible';
                                }
                            });
                        }
                    });
                """)
                human_delay(1000, 1500)
            except Exception:
                pass

            title = extract_title(page)
            if not title:
                print(f"Не удалось извлечь заголовок для {url}")
                title = "Статья без заголовка"

            if is_article_url(url) or "dzen.ru" in url:
                print("СПЕЦИАЛЬНАЯ ОБРАБОТКА ЯНДЕКС.ДЗЕН")
                try:
                    page.evaluate("""
                        (() => {
                            const allButtons = document.querySelectorAll('button, a, div[role="button"], span[role="button"]');
                            allButtons.forEach(btn => {
                                const text = btn.textContent?.toLowerCase().trim() || '';
                                if ((text.includes('читать') || text.includes('показать') || text.includes('развернуть') || 
                                     text.includes('полностью') || text.includes('ещё') || text.includes('еще') ||
                                     text.includes('expand') || text.includes('read') || text.includes('more') || 
                                     text.includes('show')) && btn.offsetParent !== null) {
                                    try {
                                        btn.click();
                                    } catch(e) {}
                                }
                            });

                            const lazyElements = document.querySelectorAll('[data-src], [data-lazy], [class*="lazy"], [class*="loading"]');
                            lazyElements.forEach(el => {
                                if (el.offsetParent !== null) {
                                    el.scrollIntoView();
                                }
                            });

                            const articleElements = document.querySelectorAll('article, [class*="article"], [class*="post"], [class*="entry"], [class*="story"]');
                            articleElements.forEach(article => {
                                if (article.offsetParent !== null) {
                                    const textElements = article.querySelectorAll('p, div, span, h1, h2, h3, h4, h5, h6, li, blockquote, pre, code, strong, em, b, i');
                                    textElements.forEach(el => {
                                        if (el.textContent && el.textContent.length > 50) {
                                            el.style.display = 'block';
                                            el.style.visibility = 'visible';
                                            el.style.opacity = '1';
                                        }
                                    });
                                }
                            });
                        })()
                    """)
                    human_delay(2000, 3000)
                except Exception as e:
                    print(f"Ошибка при специальной обработке Дзен: {e}")

            html = extract_article_content_before_comments(page)
            print(f"РЕЗУЛЬТАТ ИЗВЛЕЧЕНИЯ: {len(html) if html else 0} символов")

            if html and len(html.strip()) >= 10:
                print(f"КОНТЕНТ УСПЕШНО ИЗВЛЕЧЕН: {len(html)} символов")
                cleaned = html

                if "/away?to=" in url or "kursy-vse.ru" in url:
                    if len(cleaned.strip()) < 3:
                        print(f"КРИТИЧЕСКИ КОРОТКИЙ КОНТЕНТ ВНЕШНЕЙ ССЫЛКИ: {len(cleaned.strip())} символов")
                        continue
                    else:
                        print(f"КОНТЕНТ ВНЕШНЕЙ ССЫЛКИ ПРИНЯТ: {len(cleaned.strip())} символов")
                elif is_channel_url(url):
                    print(f"Пропускаю канал: {url}")
                    continue

                human_delay(per_article_delay_ms, per_article_delay_ms + 400)
                return title, cleaned
            else:
                print(f"Контент слишком короткий или пустой для {url}, пробую экстренные меры...")

                try:
                    emergency_content = page.evaluate("""
                        (() => {
                            const body = document.body;
                            if (body) {
                                const commentsHeader = body.querySelector('span.comments2--comments-default-header-block__commentsTitle-Y4[data-testid="comments-header-title-text"]:contains("Комментарии")');
                                let content = '';
                                if (commentsHeader) {
                                    let currentNode = body.firstChild;
                                    while (currentNode) {
                                        if (currentNode === commentsHeader || currentNode.contains(commentsHeader)) {
                                            break;
                                        }
                                        if (currentNode.nodeType === 1) {
                                            content += currentNode.outerHTML || '';
                                        }
                                        currentNode = currentNode.nextSibling;
                                    }
                                }
                                if (content.trim().length < 50) {
                                    return body.innerHTML || body.outerHTML || '<div>Emergency content</div>';
                                }
                                return content;
                            }
                            return '<div>No content available</div>';
                        })()
                    """)
                    if emergency_content and len(emergency_content.strip()) > 10:
                        print(f"ЭКСТРЕННЫЙ HTML ПОЛУЧЕН: {len(emergency_content)} символов")
                        human_delay(per_article_delay_ms, per_article_delay_ms + 400)
                        return title, emergency_content
                except Exception as e:
                    print(f"ЭКСТРЕННЫЙ HTML НЕ ПОЛУЧЕН: {e}")

                print("ЭКСТРЕННЫЕ МЕРЫ НЕ ПОМОГЛИ")
                continue

        except PlaywrightTimeoutError as e:
            print(f"Таймаут при парсинге {url}: {e}")
        except Exception as e:
            print(f"Ошибка при парсинге {url}: {e}")

        if attempt < max_retries - 1:
            backoff = 1.0 + attempt * 0.7 + random.uniform(0, 0.6)
            time.sleep(backoff)
        else:
            print(f"ПОСЛЕДНЯЯ ПОПЫТКА ПАРСИНГА {url}...")

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=10000)

                try:
                    title = extract_title(page)
                except Exception:
                    title = f"Статья {url.split('/')[-1] if '/' in url else 'Без названия'}"

                try:
                    emergency_html = page.evaluate("""
                        (() => {
                            const body = document.body;
                            if (body) {
                                const commentsHeader = body.querySelector('span.comments2--comments-default-header-block__commentsTitle-Y4[data-testid="comments-header-title-text"]:contains("Комментарии")');
                                let content = '';
                                if (commentsHeader) {
                                    let currentNode = body.firstChild;
                                    while (currentNode) {
                                        if (currentNode === commentsHeader || currentNode.contains(commentsHeader)) {
                                            break;
                                        }
                                        if (currentNode.nodeType === 1) {
                                            content += currentNode.outerHTML || '';
                                        }
                                        currentNode = currentNode.nextSibling;
                                    }
                                }
                                if (content.trim().length < 50) {
                                    return body.innerHTML || body.outerHTML || '<div>Emergency content</div>';
                                }
                                return content;
                            }
                            return '<div>No content available</div>';
                        })()
                    """)
                    if emergency_html and len(emergency_html.strip()) > 10:
                        print(f"ЭКСТРЕННЫЙ HTML ПОЛУЧЕН: {len(emergency_html)} символов")
                        return title, emergency_html
                except Exception as e2:
                    print(f"ЭКСТРЕННЫЙ HTML НЕ ПОЛУЧЕН: {e2}")

                try:
                    fallback_text = page.evaluate("""
                        (() => {
                            const body = document.body;
                            if (body) {
                                const text = body.textContent || body.innerText || '';
                                return text ? `<div>${text.substring(0, 10000)}</div>` : '<div>No text found</div>';
                            }
                            return '<div>No content available</div>';
                        })()
                    """)
                    if fallback_text and len(fallback_text.strip()) > 5:
                        print(f"ЭКСТРЕННЫЙ ТЕКСТ ПОЛУЧЕН: {len(fallback_text)} символов")
                        return title, fallback_text
                except Exception as e3:
                    print(f"ЭКСТРЕННЫЙ ТЕКСТ НЕ ПОЛУЧЕН: {e3}")

                return title, "<div>Не удалось получить полный контент, но страница была загружена</div>"

            except Exception as final_e:
                print(f"ПОСЛЕДНЯЯ ПОПЫТКА ПРОВАЛИЛАСЬ: {final_e}")
                return f"Ошибка загрузки {url}", "<div>Критическая ошибка при загрузке страницы</div>"

    print(f"ВСЕ ПОПЫТКИ ИЗВЛЕЧЕНИЯ {url} ПРОВАЛИЛИСЯ")
    return "", ""


def write_excel_per_topic(output_path, topic_dfs):
    try:
        mode = "a" if Path(output_path).exists() else "w"
        with pd.ExcelWriter(output_path, engine="openpyxl", mode=mode, if_sheet_exists="overlay") as writer:
            for topic, df in topic_dfs:
                sheet = topic[:31] if topic else "Sheet1"
                try:
                    df.to_excel(writer, sheet_name=sheet, index=False,
                                startrow=writer.sheets[sheet].max_row if sheet in writer.sheets else 0)
                except Exception:
                    df.to_excel(writer, sheet_name=sheet, index=False)
    except Exception as e:
        print(f"Ошибка при записи в Excel: {e}")
        raise


def write_excel_single_sheet(output_path, df):
    try:
        df = df.reset_index(drop=True)
        if Path(output_path).exists():
            mode = "a"
            if_sheet_exists = "overlay"
        else:
            mode = "w"
            if_sheet_exists = None

        with pd.ExcelWriter(output_path, engine="openpyxl", mode=mode, if_sheet_exists=if_sheet_exists) as writer:
            if mode == "a" and "Sheet1" in writer.sheets:
                startrow = writer.sheets["Sheet1"].max_row
                df.to_excel(writer, sheet_name="Sheet1", index=False, startrow=startrow, header=False)
            else:
                df.to_excel(writer, sheet_name="Sheet1", index=False)
    except Exception as e:
        print(f"Ошибка при записи в Excel: {e}")
        raise


def get_content_hash(html_content):
    try:
        soup = BeautifulSoup(html_content, "lxml")
        text = soup.get_text(separator=' ', strip=True)
        words = text.split()
        if len(words) < 10:
            return None
        content_sample = ' '.join(words[:50] + words[-50:])
        return hash(content_sample.lower())
    except Exception:
        return None


def extract_dzen_specific_content(page):
    try:
        print("Пробую Дзен-специфичные селекторы...")

        dzen_selectors = [
            'div[data-qa="article"]',
            'div[data-qa*="article"]',
            'div[data-qa*="content"]',
            'div[data-qa*="text"]',
            'div[data-qa*="body"]',
            'div[data-qa*="post"]',
            'div[data-qa*="entry"]',
            'div[data-qa*="story"]',
            'div[class*="article-content"]',
            'div[class*="article-body"]',
            'div[class*="article-text"]',
            'div[class*="post-content"]',
            'div[class*="post-body"]',
            'div[class*="post-text"]',
            'div[class*="entry-content"]',
            'div[class*="entry-body"]',
            'div[class*="entry-text"]',
            'div[class*="story-content"]',
            'div[class*="story-body"]',
            'div[class*="story-text"]',
            'div[class*="content-body"]',
            'div[class*="text-content"]',
            'div[class*="main-content"]',
            'div[class*="primary-content"]',
            'article',
            'main',
            'div[itemprop="articleBody"]',
            'div[itemprop="text"]',
            'div[itemprop="content"]'
        ]

        for selector in dzen_selectors:
            try:
                element = page.locator(selector).first
                if element.count() > 0:
                    html = element.evaluate("el => el.outerHTML")
                    if html and len(html.strip()) > 100:
                        print(f"Найден контент через Дзен селектор: {selector}")
                        print("ВОЗВРАЩАЮ ПОЛНЫЙ HTML КОД БЕЗ САНИТИЗАЦИИ")
                        return html
            except Exception:
                continue

        print("Пробую JavaScript извлечение для Дзен...")
        js_content = page.evaluate("""
            (() => {
                const selectors = [
                    'div[data-qa="article"]',
                    'div[data-qa*="article"]',
                    'div[data-qa*="content"]',
                    'div[data-qa*="text"]',
                    'div[data-qa*="body"]',
                    'div[class*="article-content"]',
                    'div[class*="article-body"]',
                    'div[class*="article-text"]',
                    'div[class*="post-content"]',
                    'div[class*="post-body"]',
                    'div[class*="post-text"]',
                    'div[class*="entry-content"]',
                    'div[class*="entry-body"]',
                    'div[class*="entry-text"]',
                    'div[class*="story-content"]',
                    'div[class*="story-body"]',
                    'div[class*="story-text"]',
                    'div[class*="content-body"]',
                    'div[class*="text-content"]',
                    'div[class*="main-content"]',
                    'div[class*="primary-content"]',
                    'article',
                    'main',
                    'div[itemprop="articleBody"]',
                    'div[itemprop="text"]',
                    'div[itemprop="content"]'
                ];

                for (const selector of selectors) {
                    const element = document.querySelector(selector);
                    if (element) {
                        const text = element.textContent || element.innerText || '';
                        if (text.trim().length > 200) {
                            return element.outerHTML;
                        }
                    }
                }

                const allTextElements = document.querySelectorAll('p, div, span, h1, h2, h3, h4, h5, h6, li, blockquote, pre, code, strong, em, b, i');
                let content = '';
                for (const el of allTextElements) {
                    const text = el.textContent || el.innerText || '';
                    if (text.trim().length > 10) {
                        content += el.outerHTML + '\\n';
                    }
                }

                return content.length > 200 ? content : null;
            })()
        """)

        if js_content and len(js_content.strip()) > 100:
            print(f"Найден контент через JavaScript: {len(js_content)} символов")
            return js_content

        print("Пробую агрессивное извлечение для Дзен...")
        aggressive_content = page.evaluate("""
            (() => {
                let content = '';
                let textCount = 0;

                const textSelectors = [
                    'p', 'div', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote', 'pre', 'code', 
                    'strong', 'em', 'b', 'i', 'article', 'section', 'main', 'td', 'th', 'dd', 'dt'
                ];

                for (const selector of textSelectors) {
                    const elements = document.querySelectorAll(selector);
                    for (const el of elements) {
                        const text = el.textContent || el.innerText || '';
                        if (text.trim().length > 30) {
                            const hasScripts = el.querySelector('script, style, noscript, iframe, embed, object, applet, canvas, svg, img, video, audio');
                            if (!hasScripts) {
                                content += el.outerHTML + '\\n';
                                textCount += text.length;
                            }
                        }
                    }
                }

                if (textCount > 1000) {
                    return content;
                }

                const bodyText = document.body ? document.body.textContent || document.body.innerText : '';
                if (bodyText.length > 1000) {
                    return `<div>${bodyText}</div>`;
                }

                const allText = document.documentElement ? document.documentElement.textContent || document.documentElement.innerText : '';
                return allText.length > 1000 ? `<div>${allText}</div>` : null;
            })()
        """)

        if aggressive_content and len(aggressive_content.strip()) > 200:
            print(f"Найден контент через агрессивное извлечение: {len(aggressive_content)} символов")
            return aggressive_content

    except Exception as e:
        print(f"Ошибка при Дзен-специфичном извлечении: {e}")

    return None


def extract_article_content(page):
    """Извлекает контент даже из сайтов с пустыми div"""
    try:
        # 1. Ждём появления реального текста
        try:
            page.wait_for_function("""
                () => {
                    const text = document.body?.innerText || '';
                    return text.length > 300 || document.querySelector('article, [class*="content"], [class*="article"]');
                }
            """, timeout=8000)
        except:
            pass

        # 2. Скроллим для подгрузки ленивого контента
        for i in range(3):
            page.evaluate(f"window.scrollBy(0, {500})")
            human_delay(500, 800)

        # 3. Агрессивное извлечение текста через JavaScript
        content = page.evaluate("""
            (() => {
                // Функция для проверки, есть ли у элемента реальный текст
                function hasRealText(element) {
                    if (!element) return false;
                    const text = element.textContent || element.innerText || '';
                    const cleanText = text.replace(/\\s+/g, ' ').trim();
                    return cleanText.length > 30;
                }

                // Стратегия 1: Ищем основные контейнеры
                const mainSelectors = [
                    'article',
                    'main',
                    '[role="main"]',
                    '[class*="content"]',
                    '[class*="article"]',
                    '[class*="post"]',
                    '[class*="text"]',
                    '[class*="body"]',
                    '[itemprop="articleBody"]',
                    '.entry-content',
                    '.post-content',
                    '.article-content'
                ];

                for (const selector of mainSelectors) {
                    const element = document.querySelector(selector);
                    if (element && hasRealText(element)) {
                        console.log('Найден контейнер:', selector);
                        return element.innerHTML;
                    }
                }

                // Стратегия 2: Собираем все параграфы и заголовки
                const textElements = [];
                const tags = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span', 'section'];

                tags.forEach(tag => {
                    document.querySelectorAll(tag).forEach(el => {
                        if (hasRealText(el)) {
                            // Проверяем, что это не навигация/реклама
                            const className = el.className.toLowerCase();
                            const id = el.id.toLowerCase();
                            if (!className.includes('nav') && !className.includes('menu') && 
                                !className.includes('ad') && !className.includes('banner') &&
                                !id.includes('nav') && !id.includes('ad')) {
                                textElements.push(el.outerHTML);
                            }
                        }
                    });
                });

                if (textElements.length > 0) {
                    console.log('Найдено текстовых элементов:', textElements.length);
                    // Берём первые 30 элементов (чтобы не перегружать)
                    return textElements.slice(0, 30).join('\\n');
                }

                // Стратегия 3: Весь текст страницы, разбитый на абзацы
                const body = document.body;
                if (body) {
                    const allText = body.innerText || body.textContent || '';
                    if (allText.length > 500) {
                        // Разбиваем на предложения для создания абзацев
                        const sentences = allText.split(/[\\.!?]+\\s+/);
                        const paragraphs = [];
                        let currentPara = [];

                        for (const sentence of sentences) {
                            if (sentence.trim().length > 10) {
                                currentPara.push(sentence.trim());
                                if (currentPara.join(' ').length > 200) {
                                    paragraphs.push('<p>' + currentPara.join(' ') + '</p>');
                                    currentPara = [];
                                }
                            }
                        }

                        if (currentPara.length > 0) {
                            paragraphs.push('<p>' + currentPara.join(' ') + '</p>');
                        }

                        if (paragraphs.length > 0) {
                            console.log('Создано абзацев из текста:', paragraphs.length);
                            return paragraphs.slice(0, 20).join('\\n');
                        }
                    }
                }

                // Стратегия 4: Fallback - весь HTML body
                if (body) {
                    const html = body.innerHTML;
                    if (html && html.length > 1000) {
                        return html.substring(0, 15000); // Ограничиваем размер
                    }
                }

                return '<div>Контент не найден</div>';
            })()
        """)

        if content and len(content.strip()) > 100:
            print(f"Извлечено {len(content)} символов контента")
            return content
        else:
            print("Контент слишком короткий или пустой")
            return None

    except Exception as e:
        print(f"Ошибка при извлечении контента: {e}")
        return None


def extract_article_content_before_comments(page):
    """Извлекает контент статьи от h1 до комментариев только со стандартными тегами"""
    try:
        # Упрощенная версия с фильтрацией тегов
        content = page.evaluate("""
            (() => {
                // 1. Находим первый заголовок h1
                const h1 = document.querySelector('h1');
                if (!h1) {
                    return '<div>Не найден заголовок h1</div>';
                }

                // 2. Находим элемент комментариев
                const commentsElement = document.querySelector('span.comments2--comments-default-header-block__commentsTitle-Y4[data-testid="comments-header-title-text"]');

                // 3. Определяем область сбора контента
                let startElement = h1;
                let endElement = commentsElement;

                // 4. Собираем контент между h1 и комментариями
                let result = '';
                let currentElement = startElement;

                // Разрешенные теги
                const allowedTags = [
                    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                    'p', 'div', 'span', 'a',
                    'ul', 'ol', 'li',
                    'strong', 'em', 'b', 'i',
                    'blockquote', 'pre', 'code',
                    'table', 'tr', 'td', 'th'
                ];

                // Функция для фильтрации элемента
                function filterElement(element) {
                    if (!element || !element.tagName) return '';

                    const tagName = element.tagName.toLowerCase();

                    // Если тег не в списке разрешенных, пропускаем
                    if (!allowedTags.includes(tagName)) {
                        return '';
                    }

                    // Удаляем все атрибуты кроме href у ссылок
                    const cleanElement = element.cloneNode(false);

                    if (tagName === 'a' && element.hasAttribute('href')) {
                        cleanElement.setAttribute('href', element.getAttribute('href'));
                    }

                    // Копируем текстовое содержимое
                    if (element.childNodes.length === 0) {
                        cleanElement.textContent = element.textContent;
                    } else {
                        // Рекурсивно обрабатываем дочерние элементы
                        for (const child of element.childNodes) {
                            if (child.nodeType === 3) { // Текстовый узел
                                cleanElement.appendChild(document.createTextNode(child.textContent));
                            } else if (child.nodeType === 1) { // Элемент
                                const filteredChild = filterElement(child);
                                if (filteredChild) {
                                    cleanElement.appendChild(filteredChild);
                                }
                            }
                        }
                    }

                    return cleanElement;
                }

                // Идем от h1 до комментариев
                while (currentElement && currentElement !== endElement) {
                    // Проверяем, не достигли ли мы комментариев или их родителя
                    if (currentElement.contains(endElement) || currentElement === endElement) {
                        break;
                    }

                    // Фильтруем элемент
                    const filteredElement = filterElement(currentElement);
                    if (filteredElement && filteredElement.outerHTML) {
                        result += filteredElement.outerHTML + '\\n';
                    }

                    // Переходим к следующему элементу
                    let nextElement = currentElement.nextElementSibling;

                    if (!nextElement) {
                        // Если нет следующего элемента, переходим к следующему элементу родителя
                        let parent = currentElement.parentElement;
                        while (parent && parent !== document.body) {
                            if (parent.nextElementSibling) {
                                nextElement = parent.nextElementSibling;
                                break;
                            }
                            parent = parent.parentElement;
                        }

                        // Если дошли до тела документа, останавливаемся
                        if (!nextElement || parent === document.body) {
                            break;
                        }
                    }

                    currentElement = nextElement;

                    // Дополнительная проверка на комментарии
                    if (currentElement && (currentElement.contains(endElement) || currentElement === endElement)) {
                        break;
                    }
                }

                // 5. Если собрали слишком мало контента, пробуем альтернативный подход
                if (result.length < 500) {
                    // Альтернативный подход: находим общий контейнер и извлекаем разрешенные теги
                    let commonContainer = null;

                    // Ищем ближайший общий контейнер для h1 и комментариев
                    let h1Parent = h1.parentElement;
                    while (h1Parent && h1Parent !== document.body) {
                        if (commentsElement && h1Parent.contains(commentsElement)) {
                            commonContainer = h1Parent;
                            break;
                        }
                        h1Parent = h1Parent.parentElement;
                    }

                    if (!commonContainer) {
                        commonContainer = h1.closest('article, main, [class*="content"], [class*="article"], [class*="post"]') || h1.parentElement;
                    }

                    if (commonContainer) {
                        result = '';
                        const allElements = commonContainer.querySelectorAll('*');

                        for (const element of allElements) {
                            // Пропускаем элементы после комментариев
                            if (commentsElement && 
                                (element === commentsElement || element.contains(commentsElement))) {
                                break;
                            }

                            // Пропускаем элементы до h1
                            if (!element.contains(h1) && element !== h1 && !h1.contains(element)) {
                                continue;
                            }

                            // Фильтруем элемент
                            const filteredElement = filterElement(element);
                            if (filteredElement && filteredElement.outerHTML) {
                                result += filteredElement.outerHTML + '\\n';
                            }
                        }
                    }
                }

                // 6. Очищаем результат от пустых элементов
                if (result) {
                    const tempDiv = document.createElement('div');
                    tempDiv.innerHTML = result;

                    // Удаляем пустые элементы
                    const emptyElements = tempDiv.querySelectorAll('div:empty, span:empty, p:empty');
                    emptyElements.forEach(el => el.remove());

                    // Удаляем элементы без текста
                    const elementsWithoutText = tempDiv.querySelectorAll('div:not(:has(*)), span:not(:has(*)), p:not(:has(*))');
                    elementsWithoutText.forEach(el => {
                        if (!el.textContent.trim()) {
                            el.remove();
                        }
                    });

                    result = tempDiv.innerHTML;
                }

                return result || '<div>Не удалось извлечь контент</div>';
            })()
        """)

        if content and len(content.strip()) > 100:
            # Дополнительная очистка на стороне Python
            try:
                soup = BeautifulSoup(content, 'html.parser')

                # Удаляем скрипты, стили и т.д.
                for tag in soup.find_all(['script', 'style', 'iframe', 'embed', 'object', 'applet',
                                          'canvas', 'svg', 'img', 'video', 'audio', 'form', 'input',
                                          'button', 'select', 'textarea']):
                    tag.decompose()

                # Оставляем только разрешенные теги
                allowed_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                                'p', 'div', 'span', 'a',
                                'ul', 'ol', 'li',
                                'strong', 'em', 'b', 'i',
                                'blockquote', 'pre', 'code',
                                'table', 'tr', 'td', 'th']

                for tag in soup.find_all(True):
                    if tag.name not in allowed_tags:
                        tag.unwrap()  # Разворачиваем тег, оставляя содержимое
                    else:
                        # Очищаем атрибуты, оставляем только href у ссылок
                        attrs_to_keep = {}
                        if tag.name == 'a' and tag.get('href'):
                            attrs_to_keep['href'] = tag['href']
                        tag.attrs = attrs_to_keep

                # Удаляем пустые элементы
                for tag in soup.find_all(['div', 'span', 'p', 'li']):
                    if not tag.get_text(strip=True) and not tag.find_all(['img', 'br']):
                        tag.decompose()

                cleaned_content = str(soup)
                print(f"Извлечено {len(cleaned_content)} символов контента (только стандартные теги)")
                return cleaned_content

            except Exception as e:
                print(f"Ошибка при очистке HTML: {e}")
                return content
        else:
            print("Контент слишком короткий, пробую стандартное извлечение...")
            return extract_article_content(page)

    except Exception as e:
        print(f"Ошибка при извлечении контента: {e}")
        return extract_article_content(page)


def extract_text_fallback(page):
    try:
        page_content = page.content()
        soup = BeautifulSoup(page_content, "lxml")

        for bad in soup.select(
                'script, style, noscript, iframe, embed, object, applet, canvas, svg, img, video, audio, [class*="ad"], [class*="social"], [class*="share"], [class*="comment"], [class*="related"], [class*="recommend"], [class*="sidebar"], [class*="widget"], [class*="banner"], [class*="popup"], [class*="modal"], [class*="overlay"], [class*="cookie"], [class*="privacy"], [class*="consent"], [class*="notification"], [class*="alert"], [class*="message"], [class*="tooltip"], [class*="toolbar"], [class*="menu"], [class*="nav"], [class*="header"], [class*="footer"], [class*="aside"]'):
            bad.decompose()

        text_elements = []

        for tag in soup.find_all(
                ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span', 'li', 'blockquote', 'pre', 'code', 'article',
                 'main', 'section', 'td', 'th', 'strong', 'em', 'b', 'i']):
            text = tag.get_text(separator=' ', strip=True)
            if len(text) > 5:
                text_elements.append(f"<{tag.name}>{text}</{tag.name}>")

        if text_elements:
            return '\n'.join(text_elements)

        all_text = soup.get_text(separator='\n', strip=True)
        if len(all_text) > 10:
            return f"<div>{all_text}</div>"

        try:
            iframes = page.query_selector_all('iframe')
            for iframe in iframes:
                try:
                    frame = iframe.content_frame()
                    if frame:
                        frame_content = frame.content()
                        frame_soup = BeautifulSoup(frame_content, "lxml")

                        for bad in frame_soup.select(
                                'script, style, noscript, iframe, embed, object, applet, canvas, svg, img, video, audio, [class*="ad"], [class*="social"], [class*="share"], [class*="comment"], [class*="related"], [class*="recommend"], [class*="sidebar"], [class*="widget"], [class*="banner"], [class*="popup"], [class*="modal"], [class*="overlay"], [class*="cookie"], [class*="privacy"], [class*="consent"], [class*="notification"], [class*="alert"], [class*="message"], [class*="tooltip"], [class*="toolbar"], [class*="menu"], [class*="nav"], [class*="header"], [class*="footer"], [class*="aside"]'):
                            bad.decompose()

                        frame_text_elements = []
                        for tag in frame_soup.find_all(
                                ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span', 'li', 'blockquote', 'pre',
                                 'code', 'article', 'main', 'section', 'td', 'th', 'strong', 'em', 'b', 'i']):
                            text = tag.get_text(separator=' ', strip=True)
                            if len(text) > 5:
                                frame_text_elements.append(f"<{tag.name}>{text}</{tag.name}>")

                        if frame_text_elements:
                            return '\n'.join(frame_text_elements)

                        frame_all_text = frame_soup.get_text(separator='\n', strip=True)
                        if len(frame_all_text) > 10:
                            return f"<div>{frame_all_text}</div>"
                except Exception:
                    continue
        except Exception:
            pass

        return None
    except Exception as e:
        print(f"Ошибка при извлечении текста fallback: {e}")
        return None


def run_scrape(topics, output_path, per_topic_sheet, headless, proxy, user_agent, storage_state_path, max_scrolls,
               empty_limit, scroll_step_px, max_articles_per_topic, per_article_delay_ms, max_retries,
               min_content_length=100, timeout=30000, slow_mo=0, devtools=False, mobile=False, no_content=False):
    rows_all = []
    topic_tables = []

    try:
        with sync_playwright() as p:
            browser_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--disable-extensions",
                "--disable-plugins",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-field-trial-config",
                "--disable-ipc-flooding-protection",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-default-apps",
                "--disable-sync",
                "--disable-translate",
                "--hide-scrollbars",
                "--mute-audio",
                "--no-zygote",
                "--disable-background-networking",
                "--disable-client-side-phishing-detection",
                "--disable-component-extensions-with-background-pages",
                "--disable-hang-monitor",
                "--disable-prompt-on-repost",
                "--disable-domain-reliability",
                "--disable-features=TranslateUI",
                "--disable-ios-physical-web",
                "--disable-sync-preferences",
                "--disable-background-mode",
                "--metrics-recording-only",
                "--disable-features=TranslateUI,BlinkGenPropertyTrees",
                "--disable-ipc-flooding-protection",
                "--disable-blink-features",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--disable-features=TranslateUI",
                "--disable-features=TranslateUI,BlinkGenPropertyTrees",
                "--disable-features=TranslateUI,BlinkGenPropertyTrees,Translate",
                "--disable-features=TranslateUI,BlinkGenPropertyTrees,Translate,TranslateUI",
                "--disable-features=TranslateUI,BlinkGenPropertyTrees,Translate,TranslateUI,Translate",
                "--disable-features=TranslateUI,BlinkGenPropertyTrees,Translate,TranslateUI,Translate,TranslateUI",
                "--disable-features=TranslateUI,BlinkGenPropertyTrees,Translate,TranslateUI,Translate,TranslateUI,Translate",
                "--disable-features=TranslateUI,BlinkGenPropertyTrees,Translate,TranslateUI,Translate,TranslateUI,Translate,TranslateUI",
                "--disable-features=TranslateUI,BlinkGenPropertyTrees,Translate,TranslateUI,Translate,TranslateUI,Translate,TranslateUI,Translate",
                "--disable-features=TranslateUI,BlinkGenPropertyTrees,Translate,TranslateUI,Translate,TranslateUI,Translate,TranslateUI,Translate,TranslateUI"
            ]
            try:
                browser = p.chromium.launch(headless=headless, args=browser_args, slow_mo=slow_mo)
            except Exception as e:
                print(f"Ошибка при запуске браузера: {e}")
                print("Пробую запуск без дополнительных аргументов...")
                browser = p.chromium.launch(headless=headless, slow_mo=slow_mo)
            context_args = {}
            if proxy:
                context_args["proxy"] = {"server": proxy}
            if user_agent:
                context_args["user_agent"] = user_agent
            if storage_state_path:
                storage_path = Path(storage_state_path)
                if storage_path.exists():
                    try:
                        context_args["storage_state"] = storage_state_path
                    except Exception as e:
                        print(f"Ошибка при загрузке storage state: {e}")
                else:
                    print(f"Файл storage state не найден: {storage_state_path}")
            try:
                if mobile:

                    if "user_agent" in context_args:
                        del context_args["user_agent"]
                    context = browser.new_context(
                        viewport={"width": 390, "height": 844},
                        device_scale_factor=3,
                        is_mobile=True,
                        has_touch=True,
                        locale="ru-RU",
                        timezone_id="Europe/Moscow",
                        user_agent="Mozilla/5.0 (Linux; Android 12; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
                        ignore_https_errors=True,
                        **context_args
                    )
                else:
                    context = browser.new_context(
                        viewport={"width": 1400, "height": 900},
                        locale="ru-RU",
                        timezone_id="Europe/Moscow",
                        ignore_https_errors=True,
                        **context_args
                    )
            except Exception as e:
                print(f"Ошибка при создании контекста: {e}")
                print("Пробую создание контекста без дополнительных параметров...")
                context = browser.new_context()
            try:
                page = context.new_page()
                page.set_default_timeout(timeout)
                try:
                    page.set_extra_http_headers({
                        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                        "DNT": "1",
                        "Upgrade-Insecure-Requests": "1"
                    })
                except Exception:
                    pass
            except Exception as e:
                print(f"Ошибка при создании страницы: {e}")
                raise

            try:
                page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined,
                    });

                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5],
                    });

                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['ru-RU', 'ru', 'en-US', 'en'],
                    });

                    window.chrome = {
                        runtime: {},
                        loadTimes: function() {},
                        csi: function() {},
                        app: {}
                    };

                    Object.defineProperty(navigator, 'permissions', {
                        get: () => ({
                            query: async () => ({ state: 'granted' }),
                        }),
                    });

                    Object.defineProperty(navigator, 'connection', {
                        get: () => ({
                            effectiveType: '4g',
                            rtt: 50,
                            downlink: 10,
                            saveData: false
                        }),
                    });

                    Object.defineProperty(navigator, 'hardwareConcurrency', {
                        get: () => 8,
                    });

                    Object.defineProperty(navigator, 'deviceMemory', {
                        get: () => 8,
                    });

                    Object.defineProperty(navigator, 'maxTouchPoints', {
                        get: () => 10,
                    });

                    Object.defineProperty(navigator, 'platform', {
                        get: () => 'Win32',
                    });

                    Object.defineProperty(navigator, 'vendor', {
                        get: () => 'Google Inc.',
                    });

                    Object.defineProperty(navigator, 'userAgent', {
                        get: () => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                    });

                    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
                    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
                    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;

                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined,
                    });

                    window.navigator.chrome = {
                        runtime: {},
                    };

                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5],
                    });

                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['ru-RU', 'ru', 'en-US', 'en'],
                    });

                    // Avoid navigator.connection override if proxied by Bright Data (some unlockers inject it)
                    try { delete navigator.connection; } catch (e) {}
                """)
            except Exception as e:
                print(f"Ошибка при добавлении скриптов: {e}")

            page.set_default_timeout(30000)

            for idx, topic in enumerate(topics):
                topic = topic.strip()
                if not topic:
                    continue

                log_info(f"Обрабатываю тему {idx + 1}/{len(topics)}: {topic}")
                log_info(f"Прогресс: {idx}/{len(topics)} тем обработано")

                try:
                    topic_rows = collect_and_parse_articles(
                        page=page,
                        query=topic,
                        max_scrolls=max_scrolls,
                        empty_limit=empty_limit,
                        scroll_step_px=scroll_step_px,
                        max_articles_per_topic=max_articles_per_topic if max_articles_per_topic and max_articles_per_topic > 0 else None,
                        per_article_delay_ms=per_article_delay_ms,
                        max_retries=max_retries,
                        min_content_length=min_content_length,
                        topic=topic,
                        output_path=output_path,
                        per_topic_sheet=per_topic_sheet,
                        no_content=no_content
                    )
                except KeyboardInterrupt:
                    log_warning("Парсинг прерван пользователем")
                    raise
                except Exception as e:
                    log_error(f"Ошибка при обработке темы '{topic}': {e}")
                    continue

                log_success(f"Обработано {len(topic_rows)} статей для темы: {topic}")
                log_info(f"Прогресс: {idx + 1}/{len(topics)} тем обработано")

                if not per_topic_sheet:
                    try:
                        rows_all.extend(topic_rows)
                    except Exception as e:
                        print(f"Ошибка при добавлении строк для темы {topic}: {e}")
                human_delay(900, 1600)

            print(f"Парсинг завершен успешно!")
            print(f"Все данные сохранены в: {output_path}")
            print(f"Обработано тем: {len(topics)}")
            print(f"Всего статей: {len(rows_all) if not per_topic_sheet else 'см. отдельные листы'}")

            try:
                if storage_state_path:
                    context.storage_state(path=storage_state_path)
            except Exception as e:
                print(f"Ошибка при сохранении состояния браузера: {e}")
            finally:
                try:
                    context.close()
                except Exception as e:
                    print(f"Ошибка при закрытии контекста: {e}")
                try:
                    browser.close()
                except Exception as e:
                    print(f"Ошибка при закрытии браузера: {e}")
                try:
                    p.stop()
                except Exception as e:
                    print(f"Ошибка при остановке playwright: {e}")

    except Exception as e:
        print(f"Критическая ошибка: {e}")
    finally:
        try:
            if 'p' in locals():
                p.stop()
        except Exception:
            pass


def get_user_input():
    print("============================================================")
    print("    ПАРСЕР СТАТЕЙ ЯНДЕКС.ДЗЕН")
    print("============================================================")
    print()

    topics = []
    while True:
        print("Введите тему для поиска (или 'готово' для завершения):")
        topic = input("> ").strip()
        if not topic:
            continue
        if topic.lower() in ['готово', 'done', 'exit', 'quit']:
            break
        topics.append(topic)
        print(f"Добавлена тема: {topic}")
        print(f"Всего тем: {len(topics)}")
        print()

    if not topics:
        print("Не указано ни одной темы!")
        return None

    print("НАСТРОЙКИ:")

    output_path = input("Имя файла Excel (по умолчанию: dzen_export.xlsx): ").strip()
    if not output_path:
        output_path = "dzen_export.xlsx"

    per_topic_sheet = input("Отдельный лист для каждой темы? (y/N): ").strip().lower() in ['y', 'yes', 'да']

    if '--headless' in sys.argv:
        headless = True
        print("Скрытый режим браузера: Да (--headless)")
    else:
        headless = input("Скрытый режим браузера? (y/N): ").strip().lower() in ['y', 'yes', 'да']

    mobile = input("Мобильный режим (рекомендуется)? (Y/n): ").strip().lower()
    mobile = mobile not in ['n', 'no', 'нет']

    max_articles = input("Максимум статей на тему (0 = без лимита): ").strip()
    try:
        max_articles = int(max_articles) if max_articles else 0
    except ValueError:
        max_articles = 0

    no_content = '--no-content' in sys.argv
    if no_content:
        print("Режим без загрузки контента: Да (--no-content)")

    slow_mo = 250 if not headless else 0

    return {
        "topics": topics,
        "output_path": output_path,
        "per_topic_sheet": per_topic_sheet,
        "headless": headless,
        "slow_mo": slow_mo,
        "devtools": not headless,
        "mobile": mobile,
        "no_content": no_content,
        "proxy": None,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "storage_state_path": None,
        "max_scrolls": 0,
        "empty_limit": 8,
        "scroll_step_px": 1600,
        "max_articles_per_topic": max_articles,
        "per_article_delay_ms": 700,
        "max_retries": 3,
        "min_content_length": 100,
        "timeout": 30000
    }


def main():
    try:
        config = get_user_input()
        if not config:
            return

        print("НАЧИНАЮ ПАРСИНГ...")
        print(f"Темы: {', '.join(config['topics'])}")
        print(f"Файл: {config['output_path']}")
        print(
            f"Режим: {'Мобильный' if config['mobile'] else 'Десктоп'} | {'Скрытый' if config['headless'] else 'Видимый'}")
        print(
            f"Максимум статей на тему: {'Без лимита' if config['max_articles_per_topic'] == 0 else config['max_articles_per_topic']}")
        print(f"Отдельные листы: {'Да' if config['per_topic_sheet'] else 'Нет'}")

        run_scrape(
            topics=config['topics'],
            output_path=config['output_path'],
            per_topic_sheet=config['per_topic_sheet'],
            headless=config['headless'],
            proxy=config.get('proxy'),
            user_agent=config.get('user_agent'),
            storage_state_path=config.get('storage_state_path'),
            max_scrolls=config['max_scrolls'],
            empty_limit=config['empty_limit'],
            scroll_step_px=config['scroll_step_px'],
            max_articles_per_topic=config['max_articles_per_topic'],
            per_article_delay_ms=config['per_article_delay_ms'],
            max_retries=config['max_retries'],
            min_content_length=config['min_content_length'],
            timeout=config['timeout'],
            slow_mo=config['slow_mo'],
            devtools=config.get('devtools', False),
            mobile=config['mobile']
        )
    except KeyboardInterrupt:
        print("\nПарсинг прерван пользователем")
    except Exception as e:
        print(f"Критическая ошибка в main: {e}")
        if "Target page, context or browser has been closed" in str(e):
            print("КРИТИЧЕСКАЯ ОШИБКА: Браузер был закрыт неожиданно")
    finally:
        print("Программа завершена")


if __name__ == "__main__":
    main()