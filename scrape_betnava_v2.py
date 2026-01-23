#!/usr/bin/env python3
"""
Scrape MC Betnava website and create knowledge.jsonl for chatbot
Version 2 - Less aggressive filtering
"""

import urllib.request
import urllib.parse
from html.parser import HTMLParser
import json
import re
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
    "https://www.mc-betnava.si/dermatolog-maribor/estetski-posegi-maribor/101-pomlajevanje-z-radiofrekvenco-pelleve",
    "https://www.mc-betnava.si/dermatolog-maribor/estetski-posegi-maribor/42-glajenje-gub-polnila-s-hialuronsko-kislino-filerji",
    "https://www.mc-betnava.si/dermatolog-maribor/estetski-posegi-maribor/41-glajenje-gub-botulinum-toksin-botox",
    "https://www.mc-betnava.si/dermatolog-maribor/laserski-posegi-maribor/lasersko-odstranjevanje-%C5%BEilic-kapilar",
    "https://www.mc-betnava.si/dermatolog-maribor/laserski-posegi-maribor/lasersko-zdravljenje-glivic-na-nohtih",
    "https://www.mc-betnava.si/dermatolog-maribor/laserski-posegi-maribor/lasersko-odstranjevanje-bradavic",
    "https://www.mc-betnava.si/dermatolog-maribor/laserski-posegi-maribor/lasersko-zdravljenje-mozoljev-maribor",
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
    "https://www.mc-betnava.si/okulist-maribor/o%C4%8Desni-pregled-maribor",
    "https://www.mc-betnava.si/o-nas/zdravniki/simon-trpin-dr-med-specialist-oftalmolog",
    "https://www.mc-betnava.si/o-nas/zdravniki/levin-vrhovec-dr-med-specialist-oftalmolog",
    "https://www.mc-betnava.si/kozmetik-maribor/nega-obraza",
    "https://www.mc-betnava.si/cenik/dermatoloske-storitve-cenik",
    "https://www.mc-betnava.si/cenik/oftalmoloske-storitve-cenik",
    "https://www.mc-betnava.si/cenik/ortopedski-pregledi-cenik",
    "https://www.mc-betnava.si/kozmetik-maribor/cenik-kozmeti%C4%8Dnih-storitev",
]

class SimpleHTMLParser(HTMLParser):
    """Very simple HTML parser - extract text only from body, skip script/style"""

    def __init__(self):
        super().__init__()
        self.title = ""
        self.content_parts = []
        self.in_title = False
        self.in_script = False
        self.in_style = False
        self.in_body = False

    def handle_starttag(self, tag, attrs):
        if tag == 'title':
            self.in_title = True
        elif tag == 'script':
            self.in_script = True
        elif tag == 'style':
            self.in_style = True
        elif tag == 'body':
            self.in_body = True

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
        elif tag == 'script':
            self.in_script = False
        elif tag == 'style':
            self.in_style = False
        elif tag == 'body':
            self.in_body = False

    def handle_data(self, data):
        if self.in_script or self.in_style:
            return

        cleaned = data.strip()
        if not cleaned:
            return

        if self.in_title:
            self.title = cleaned
        elif self.in_body:
            self.content_parts.append(cleaned + ' ')

    def get_text(self):
        text = ''.join(self.content_parts)
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def get_title(self):
        # Clean title
        title = self.title
        title = re.sub(r'\s*[-|]\s*(MC\s*)?Betnava.*$', '', title, flags=re.IGNORECASE)
        return title.strip() if title else "Untitled"

def replace_center_name(text):
    """Replace MC Betnava or Zdravstveni center Betnava with just BETNAVA"""
    patterns = [
        (r'Zdravstveni\s+center\s+Betnava', 'BETNAVA'),
        (r'Zdravstvenega\s+centra\s+Betnava', 'BETNAVA'),
        (r'Zdravstvenemu\s+centru\s+Betnava', 'BETNAVA'),
        (r'MC\s+Betnava', 'BETNAVA'),
        (r'mc-betnava', 'BETNAVA'),
        (r'MC\s+BETNAVA', 'BETNAVA'),
    ]

    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text

def scrape_url(url):
    """Scrape a single URL and return content"""
    print(f"Scraping: {url}")

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            html = response.read().decode('utf-8', errors='ignore')

        # Parse HTML
        parser = SimpleHTMLParser()
        parser.feed(html)

        title = parser.get_title()
        content = parser.get_text()

        if not content or len(content) < 50:
            print(f"  Warning: Little or no content extracted ({len(content)} chars)")
            # Save HTML for debugging
            debug_file = f"/Volumes/SSD KLJUC/KOVACNIK AI/ZDRAVSTVENI CENTER/debug_{hash(url)}.html"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(html[:5000])  # Save first 5000 chars
            print(f"  Saved HTML to: {debug_file}")
            return None

        # Replace center name
        title = replace_center_name(title)
        content = replace_center_name(content)

        print(f"  ✓ Extracted {len(content)} characters")

        return {
            "text": content,
            "metadata": {
                "source": url,
                "title": title
            }
        }

    except Exception as e:
        print(f"  Error scraping {url}: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main function to scrape all URLs and create knowledge.jsonl"""

    print(f"Starting to scrape {len(URLS)} URLs...")
    print("-" * 80)

    entries = []
    unique_urls = list(set(URLS))  # Remove duplicates

    # Try just one URL first
    print("\n=== Testing first URL ===\n")
    test_entry = scrape_url(unique_urls[0])
    if test_entry:
        print(f"\nSample content (first 500 chars):\n{test_entry['text'][:500]}...\n")
        print("=== Test successful, continuing with all URLs ===\n")
    else:
        print("\n=== Test failed, check debug HTML file ===\n")
        return

    for i, url in enumerate(unique_urls, 1):
        print(f"\n[{i}/{len(unique_urls)}]")

        entry = scrape_url(url)
        if entry:
            entries.append(entry)

        # Be polite - wait between requests
        time.sleep(0.5)

    print("\n" + "=" * 80)
    print(f"Successfully scraped {len(entries)} pages out of {len(unique_urls)} URLs")

    if not entries:
        print("\nNo content extracted. Check debug files.")
        return

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
