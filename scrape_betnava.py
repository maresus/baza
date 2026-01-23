#!/usr/bin/env python3
"""
Scrape MC Betnava website and create knowledge.jsonl for chatbot
"""

import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urlparse
import time

# List of URLs to scrape
URLS = [
    "https://www.mc-betnava.si/dermatolog-maribor",
    "https://www.mc-betnava.si/o-nas/narocanje",
    "https://www.mc-betnava.si/dermatolog-maribor/dermatolo%C5%A1ke-bolezni",
    "https://www.mc-betnava.si/dermatolog-maribor/spolno-prenosljive-oku%C5%BEbe",
    "https://www.mc-betnava.si/dermatolog-maribor/dermatolo%C5%A1ki-pregled-maribor",
    "https://www.mc-betnava.si/dermatolog-maribor/laserski-posegi-maribor",
    "https://www.mc-betnava.si/dermatolog-maribor/estetski-posegi-maribor",
    "https://www.mc-betnava.si/dermatolog-maribor/dermatolo%C5%A1ke-bolezni/ko%C5%BEna-znamenja",
    "https://www.mc-betnava.si/dermatolog-maribor/dermatolo%C5%A1ke-bolezni/akne",
    "https://www.mc-betnava.si/dermatolog-maribor/dermatolo%C5%A1ke-bolezni/aktini%C4%8Dne-keratoze",
    "https://www.mc-betnava.si/dermatolog-maribor/dermatolo%C5%A1ke-bolezni/atopijski-dermatitis",
    "https://www.mc-betnava.si/dermatolog-maribor/dermatolo%C5%A1ke-bolezni/luskavica",
    "https://www.mc-betnava.si/dermatolog-maribor/dermatolo%C5%A1ke-bolezni/prekomerno-znojenje-hiperhidroza",
    "https://www.mc-betnava.si/dermatolog-maribor/dermatolo%C5%A1ke-bolezni/rosacea",
    "https://www.mc-betnava.si/dermatolog-maribor/spolno-prenosljive-oku%C5%BEbe/sifilis",
    "https://www.mc-betnava.si/dermatolog-maribor/spolno-prenosljive-oku%C5%BEbe/gonoreja",
    "https://www.mc-betnava.si/dermatolog-maribor/spolno-prenosljive-oku%C5%BEbe/genitalni-herpes",
    "https://www.mc-betnava.si/dermatolog-maribor/spolno-prenosljive-oku%C5%BEbe/oku%C5%BEba-s-klamidijo",
    "https://www.mc-betnava.si/dermatolog-maribor/spolno-prenosljive-oku%C5%BEbe/genitalne-bradavice-kondilomi",
    "https://www.mc-betnava.si/o-nas/zdravniki/asist-simona-senega%C4%8Dnik,-dr-med-,-specialistka-dermatovenerologije",
    "https://www.mc-betnava.si/dermatolog-maribor/dermatolo%C5%A1ka-ambulanta",
    "https://www.mc-betnava.si/dermatolog-maribor/dermatolo%C5%A1ki-pregled-maribor",
    "https://www.mc-betnava.si/dermatolog-maribor/estetski-posegi-maribor/101-pomlajevanje-z-radiofrekvenco-pelleve",
    "https://www.mc-betnava.si/dermatolog-maribor/estetski-posegi-maribor/42-glajenje-gub-polnila-s-hialuronsko-kislino-filerji",
    "https://www.mc-betnava.si/dermatolog-maribor/estetski-posegi-maribor/41-glajenje-gub-botulinum-toksin-botox",
    "https://www.mc-betnava.si/dermatolog-maribor/laserski-posegi-maribor/lasersko-odstranjevanje-%C5%BEilic-kapilar",
    "https://www.mc-betnava.si/dermatolog-maribor/laserski-posegi-maribor/lasersko-zdravljenje-glivic-na-nohtih",
    "https://www.mc-betnava.si/dermatolog-maribor/laserski-posegi-maribor/lasersko-odstranjevanje-bradavic",
    "https://www.mc-betnava.si/dermatolog-maribor/laserski-posegi-maribor",
    "https://www.mc-betnava.si/dermatolog-maribor/laserski-posegi-maribor/lasersko-odstranjevanje-%C5%BEilic-kapilar",
    "https://www.mc-betnava.si/dermatolog-maribor/laserski-posegi-maribor/lasersko-zdravljenje-mozoljev-maribor",
    "https://www.mc-betnava.si/dermatolog-maribor/laserski-posegi-maribor/lasersko-odstranjevanje-bradavic",
    "https://www.mc-betnava.si/dermatolog-maribor/laserski-posegi-maribor/lasersko-zdravljenje-glivic-na-nohtih",
    "https://www.mc-betnava.si/dermatolog-maribor/estetski-posegi-maribor/medicinski-microneedling",
    "https://www.mc-betnava.si/dermatolog-maribor/estetski-posegi-maribor/biorevitalizacija-koze-prx-t33",
    "https://www.mc-betnava.si/dermatolog-maribor/estetski-posegi-maribor/glajenje-gub-s-polnili-s-hialuronsko-kislino-filerji",
    "https://www.mc-betnava.si/dermatolog-maribor/estetski-posegi-maribor/pomlajevanje-z-radiofrekvenco-pelleve",
    "https://www.mc-betnava.si/dermatolog-maribor/estetski-posegi-maribor/glajenje-gub-z-botulinum-toksinom-botox",
    "https://www.mc-betnava.si/dermatolog-maribor/nasveti/267-ali-ste-vedeli-o-kozi",
    "https://www.mc-betnava.si/dermatolog-maribor/nasveti/spolno-prenosljive-bolezni",
    "https://www.mc-betnava.si/dermatolog-maribor/nasveti/nega-ko%C5%BEe-pri-rosaceji",
    "https://www.mc-betnava.si/dermatolog-maribor/nasveti/ko%C5%BEa-poleti",
    "https://www.mc-betnava.si/dermatolog-maribor/nasveti/kako-lahko-sami-odpravimo-akne",
    "https://www.mc-betnava.si/dermatolog-maribor/nasveti/odpravite-prekomerno-znojenje-z-botoxom",
    "https://www.mc-betnava.si/dermatolog-maribor/nasveti/pomlajevanje-obraza",
    "https://www.mc-betnava.si/dermatolog-maribor/nasveti/ipl-ni-laser",
    "https://www.mc-betnava.si/dermatolog-maribor/nasveti/androgena-ple%C5%A1avost",
    "https://www.mc-betnava.si/o-nas/zdravniki/zmago-krajnc-specialist-ortoped",
    "https://www.mc-betnava.si/ortoped-maribor/ortopedska-ambulanta-maribor",
    "https://www.mc-betnava.si/ortoped-maribor/ortopedski-nasveti/350-artroskopija",
    "https://www.mc-betnava.si/ortoped-maribor/ortopedski-nasveti/341-osteoartroza-degenerativna-obraba-sklepov",
    "https://www.mc-betnava.si/ortoped-maribor/ortopedski-nasveti/342-operativno-zdravljenje-artroze-kolenskega-sklepa",
    "https://www.mc-betnava.si/ortoped-maribor/ortopedski-nasveti/344-skakal%C4%8Devo-koleno",
    "https://www.mc-betnava.si/ortoped-maribor/ortopedski-nasveti/345-konzervativno-zdravljenje-artroze",
    "https://www.mc-betnava.si/ortoped-maribor/ortopedski-nasveti/346-zivljenje-z-umetnim-sklepom",
    "https://www.mc-betnava.si/ortoped-maribor/ortopedski-nasveti/349-bolecina-v-krizu",
    "https://www.mc-betnava.si/o-nas/zdravniki/tina-kobale",
    "https://www.mc-betnava.si/okulist-maribor",
    "https://www.mc-betnava.si/okulist-maribor",
    "https://www.mc-betnava.si/okulist-maribor/o%C4%8Desni-pregled-maribor",
    "https://www.mc-betnava.si/o-nas/zdravniki/simon-trpin-dr-med-specialist-oftalmolog",
    "https://www.mc-betnava.si/o-nas/zdravniki/levin-vrhovec-dr-med-specialist-oftalmolog",
    "https://www.mc-betnava.si/kozmetik-maribor/nega-obraza",
    "https://www.mc-betnava.si/cenik/dermatoloske-storitve-cenik",
    "https://www.mc-betnava.si/cenik/oftalmoloske-storitve-cenik",
    "https://www.mc-betnava.si/cenik/ortopedski-pregledi-cenik",
    "https://www.mc-betnava.si/kozmetik-maribor/cenik-kozmeti%C4%8Dnih-storitev",
]

def clean_text(text):
    """Clean and normalize text"""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove leading/trailing whitespace
    text = text.strip()
    return text

def replace_center_name(text):
    """Replace MC Betnava or Zdravstveni center Betnava with just BETNAVA"""
    patterns = [
        r'Zdravstveni center Betnava',
        r'Zdravstvenega centra Betnava',
        r'Zdravstvenemu centru Betnava',
        r'MC Betnava',
        r'mc-betnava',
        r'MC BETNAVA',
    ]

    for pattern in patterns:
        text = re.sub(pattern, 'BETNAVA', text, flags=re.IGNORECASE)

    return text

def extract_main_content(soup):
    """Extract main content from page, removing navigation, footer, etc."""

    # Remove unwanted elements
    for element in soup.find_all(['nav', 'header', 'footer', 'script', 'style', 'iframe', 'noscript']):
        element.decompose()

    # Remove common navigation/menu classes
    for class_name in ['navigation', 'menu', 'sidebar', 'footer', 'header', 'navbar', 'breadcrumb']:
        for element in soup.find_all(class_=re.compile(class_name, re.I)):
            element.decompose()

    # Try to find main content area
    main_content = None

    # Look for common content containers
    for selector in ['main', 'article', '[role="main"]', '.content', '.main-content', '#content', '#main']:
        main_content = soup.select_one(selector)
        if main_content:
            break

    # If no main content found, use body
    if not main_content:
        main_content = soup.find('body')

    if not main_content:
        return ""

    # Extract text
    text = main_content.get_text(separator=' ', strip=True)

    return clean_text(text)

def get_page_title(soup):
    """Extract page title"""
    title_tag = soup.find('title')
    if title_tag:
        title = title_tag.get_text().strip()
        # Remove site name suffix if present
        title = re.sub(r'\s*[-|]\s*(MC\s*)?Betnava.*$', '', title, flags=re.IGNORECASE)
        return title.strip()

    # Try h1 as fallback
    h1 = soup.find('h1')
    if h1:
        return h1.get_text().strip()

    return "Untitled"

def scrape_url(url):
    """Scrape a single URL and return content"""
    print(f"Scraping: {url}")

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8'

        soup = BeautifulSoup(response.text, 'html.parser')

        title = get_page_title(soup)
        content = extract_main_content(soup)

        if not content or len(content) < 50:
            print(f"  Warning: Little or no content extracted from {url}")
            return None

        # Replace center name
        title = replace_center_name(title)
        content = replace_center_name(content)

        return {
            "text": content,
            "metadata": {
                "source": url,
                "title": title
            }
        }

    except Exception as e:
        print(f"  Error scraping {url}: {str(e)}")
        return None

def main():
    """Main function to scrape all URLs and create knowledge.jsonl"""

    print(f"Starting to scrape {len(URLS)} URLs...")
    print("-" * 80)

    entries = []
    unique_urls = list(set(URLS))  # Remove duplicates

    for i, url in enumerate(unique_urls, 1):
        print(f"\n[{i}/{len(unique_urls)}]")

        entry = scrape_url(url)
        if entry:
            entries.append(entry)
            print(f"  ✓ Successfully scraped: {entry['metadata']['title']}")

        # Be polite - wait between requests
        time.sleep(1)

    print("\n" + "=" * 80)
    print(f"Successfully scraped {len(entries)} pages out of {len(unique_urls)} URLs")

    # Write to JSONL file
    output_file = "/Volumes/SSD KLJUC/KOVACNIK AI/ZDRAVSTVENI CENTER/knowledge.jsonl"

    with open(output_file, 'w', encoding='utf-8') as f:
        for entry in entries:
            json_line = json.dumps(entry, ensure_ascii=False)
            f.write(json_line + '\n')

    print(f"\nKnowledge base saved to: {output_file}")
    print(f"Total entries: {len(entries)}")

    # Print some statistics
    total_chars = sum(len(entry['text']) for entry in entries)
    print(f"Total characters: {total_chars:,}")
    print(f"Average entry size: {total_chars // len(entries):,} characters")

if __name__ == "__main__":
    main()
