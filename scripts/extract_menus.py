"""Extract the ten development menus into auditable dish/price candidates.

Profiles describe the layouts in batch 001. The five test restaurants remain
reserved for evaluating a later frozen parser.
"""

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import numpy as np
import pdfplumber
import pypdfium2
from bs4 import BeautifulSoup
from PIL import Image

from download_menus import atomic_write

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data' / 'processed' / 'batch_001' / 'development'
OCR_CACHE = ROOT / 'data' / 'processed' / 'ocr_cache'
VERSION = '0.1.0'
PRICE = re.compile(r'(?<![\w.,])\d{1,3}[,.]\d{2}(?![\w\d])')
DUFKE_PRICE = re.compile(r'(?<![\w.,])\d{1,3},\d{2}(?=\s*€)')
DUFKE_DRINK_SIZE = re.compile(r'\s*(?:(Flasche)\s+)?(\d+(?:,\d+)?)[ ]*l$', re.I)
ALLERGEN_CODES = re.compile(r'\(\s*\d+(?:\s*,\s*\d+)*\s*\)')
UNIT = re.compile(r'^\s*(?:ml|cl|dl|l|kg|g|%|am|pm)\b', re.I)
PROFILES = {
    'dufke': {'currency': 'EUR', 'mode': 'inline', 'columns': [0, 1]},
    'berg': {'currency': 'EUR', 'mode': 'inline', 'columns': [0, 1]},
    'dishoom': {'currency': 'GBP', 'mode': 'heading', 'columns': [0.04, 0.285, 0.53, 0.775, 0.98]},
    'salut': {'currency': 'EUR'},
    'vonbis': {'currency': 'EUR'},
    'hollberg': {'currency': 'EUR'},
    'mediterran': {'currency': 'EUR', 'mode': 'inline', 'columns': [0, 1]},
    'ramenya': {'currency': 'EUR', 'mode': 'heading', 'columns': [0.065, 0.345, 0.60, 0.82]},
    'retro': {'currency': 'EUR', 'mode': 'numbered', 'columns': [0, 1]},
    'goldberg': {'currency': 'EUR', 'mode': 'numbered', 'columns': [0, 0.34, 0.67, 1]},
}
COLUMNS = [
    'record_id', 'menu_id', 'restaurant', 'split', 'category', 'dish_name',
    'variant', 'price', 'currency', 'item_kind', 'source_file', 'source_sha256',
    'page', 'column', 'source_text', 'method', 'ocr_confidence', 'review_status',
    'review_flags',
]


def clean(text):
    return re.sub(r'\s+', ' ', text).strip()


def prices(text):
    """Decimal amounts only; volumes, weights, percentages and times are excluded."""
    return [match for match in PRICE.finditer(text) if not UNIT.match(text[match.end():])]


def amount(text):
    return format(Decimal(text.replace(',', '.')), '.2f')


def record(source, asset, name, price, evidence, *, page=1, column=1,
           variant='', category='', method='html', confidence=None, flags=()):
    name = clean(name)
    if source['id'] != 'dufke':
        name = re.sub(r'^\d{1,3}[.)]?\s+', '', name)
    name = re.sub(r'\.{2,}', ' ', name).strip(' .:*-')
    issue_flags = set(flags)
    if method == 'ocr':
        issue_flags.add('ocr_text')
        if confidence is None or confidence < 0.9:
            issue_flags.add('low_ocr_confidence')
    if not name or not any(character.isalpha() for character in name):
        issue_flags.add('missing_dish_name')
    if not price:
        issue_flags.add('missing_price')
    if len(name) > 100:
        issue_flags.add('long_name_or_description')
    kind = 'menu_item'
    if name.startswith('+') or re.search(r'\b(?:extra|zusatz|upgrade|zuschlag)\b', name, re.I):
        kind = 'supplement'
    identity = json.dumps([source['id'], asset['sha256'], page, column, name, variant, price, evidence], ensure_ascii=False)
    return dict(zip(COLUMNS, [
        hashlib.sha256(identity.encode()).hexdigest()[:20], source['id'], source['restaurant'],
        source['split'], category, name, variant, price, PROFILES[source['id']]['currency'], kind,
        asset['path'], asset['sha256'], page, column, clean(evidence), method,
        '' if confidence is None else round(confidence, 4), 'needs_review', ';'.join(sorted(issue_flags)),
    ]))


def html_records(source, asset):
    soup = BeautifulSoup((ROOT / asset['path']).read_bytes(), 'html.parser')
    results = []
    if source['id'] == 'hollberg':
        for item in soup.select('.eltdf-pricing-item'):
            name = item.select_one('.eltdf-pricing-title')
            price = item.select_one('.eltdf-pricing-price')
            if name and price and prices(price.get_text(' ', strip=True)):
                match = prices(price.get_text(' ', strip=True))[0]
                results.append(record(source, asset, name.get_text(' ', strip=True), amount(match.group()), item.get_text(' ', strip=True)))
    elif source['id'] == 'salut':
        for row in soup.select('.fusion-builder-row'):
            headings = row.select('h4, h5')
            if len(headings) != 2:
                continue
            name, price_text = [node.get_text(' ', strip=True) for node in headings]
            match = re.fullmatch(r'(?:(klein|groß)\s+)?(\d{1,3}(?:[,.]\d{1,2})?)', price_text)
            if match and re.search(r'[A-Za-zÄÖÜäöü]', name):
                results.append(record(source, asset, name, amount(match.group(2)), row.get_text(' ', strip=True), variant=match.group(1) or ''))
    else:
        for heading in soup.select('h4'):
            row = heading.parent.parent
            price_nodes = row.find_all('p', recursive=False)
            price_text = ' '.join(node.get_text(' ', strip=True) for node in price_nodes)
            matches = prices(price_text)
            if matches:
                for match in matches:
                    results.append(record(source, asset, heading.get_text(' ', strip=True), amount(match.group()), row.parent.get_text(' ', strip=True)))
            elif heading.get_text(' ', strip=True).startswith('Schnitzel'):
                # These three dishes share accompaniment prices elsewhere on the page.
                results.append(record(source, asset, heading.get_text(' ', strip=True), '', row.get_text(' ', strip=True), flags=['shared_price_options']))
    return results, soup.get_text('\n', strip=True)


def pdf_lines(path, boundaries):
    pages = []
    with pdfplumber.open(path) as document:
        for page_number, page in enumerate(document.pages, start=1):
            for column, (left, right) in enumerate(zip(boundaries, boundaries[1:]), start=1):
                cropped = page.crop((page.width * left, 0, page.width * right, page.height))
                lines = []
                for line in cropped.extract_text_lines(x_tolerance=2, y_tolerance=3):
                    lines.append({'text': clean(line['text']), 'x': line['x0'], 'y': line['top'], 'confidence': None})
                pages.append({'page': page_number, 'column': column, 'lines': lines})
    return pages


def ocr_lines(path, asset, engine, boundaries):
    cache_key = hashlib.sha256((asset['sha256'] + json.dumps(boundaries) + VERSION).encode()).hexdigest()
    cache_path = OCR_CACHE / f'{cache_key}.json'
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding='utf-8'))
    images = []
    if path.suffix == '.pdf':
        with pypdfium2.PdfDocument(path) as document:
            for page in document:
                images.append(page.render(scale=2.5).to_pil().convert('RGB'))
    else:
        with Image.open(path) as picture:
            images.append(picture.convert('RGB'))
    pages = []
    for page_number, picture in enumerate(images, start=1):
        for column, (left, right) in enumerate(zip(boundaries, boundaries[1:]), start=1):
            cropped = picture.crop((int(picture.width * left), 0, int(picture.width * right), picture.height))
            # Upscale small restaurant images to aid recognition of small type.
            scale = max(1, 1600 / cropped.height)
            cropped = cropped.resize((int(cropped.width * scale), int(cropped.height * scale)))
            output = engine(np.array(cropped))
            boxes = []
            if output.txts:
                for box, text, score in zip(output.boxes, output.txts, output.scores):
                    boxes.append({'text': text, 'x': float(min(box[:, 0])), 'y': float(min(box[:, 1])),
                                  'bottom': float(max(box[:, 1])), 'confidence': float(score)})
            # Join dish and right-aligned price boxes on the same visual row.
            grouped = []
            for box in sorted(boxes, key=lambda item: (item['y'], item['x'])):
                if grouped and abs(box['y'] - grouped[-1][0]['y']) <= max(5, (box['bottom'] - box['y']) * 0.45):
                    grouped[-1].append(box)
                else:
                    grouped.append([box])
            lines = []
            for group in grouped:
                group.sort(key=lambda item: item['x'])
                lines.append({'text': clean(' '.join(item['text'] for item in group)),
                              'x': group[0]['x'], 'y': min(item['y'] for item in group),
                              'confidence': min(item['confidence'] for item in group)})
            pages.append({'page': page_number, 'column': column, 'lines': lines})
    OCR_CACHE.mkdir(parents=True, exist_ok=True)
    atomic_write(cache_path, json.dumps(pages, ensure_ascii=False, indent=2).encode())
    return pages


def layout_records(source, asset, pages):
    mode = PROFILES[source['id']]['mode']
    method = 'ocr' if source['format'] == 'ocr' else 'pdf_text'
    results = []
    for page in pages:
        heading = ''
        context = []
        previous_name = ''
        for line in page['lines']:
            text = line['text']
            matches = list(DUFKE_PRICE.finditer(text)) if source['id'] == 'dufke' else prices(text)
            letter_text = re.sub(r'[^A-Za-zÄÖÜäöüß]', '', text)
            is_heading = len(letter_text) >= 3 and letter_text.isupper() and not matches
            is_numbered = bool(re.match(r'^\d{1,3}[.)]?\s+[A-Za-zÄÖÜäöü]', text))
            if is_heading or (mode == 'numbered' and is_numbered):
                heading = text
                context = [text]
            else:
                context.append(text)
            if not matches:
                continue
            before = text[:matches[0].start()].strip(' .:€')
            name = before
            flags = []
            variant = ''
            if mode == 'heading':
                name = heading
                flags.append('heading_price_association')
            elif mode == 'numbered' and not is_numbered:
                name = heading or before
                variant = before
                flags.append('continuation_or_variant')
            if source['id'] == 'dufke':
                if before.endswith('*'):
                    name = previous_name
                    variant = 'small portion'
                else:
                    name = ALLERGEN_CODES.sub('', before).replace('(*)', '').strip()
                    size = DUFKE_DRINK_SIZE.search(name)
                    if size:
                        name = name[:size.start()].strip()
                        variant = f'{size.group(2).replace(",", ".")} L'
                        if size.group(1):
                            variant += ' bottle'
                        if not name or re.fullmatch(r'\([^()]+\)', name):
                            name = previous_name
            if len(matches) > 1:
                flags.append('multiple_prices')
            for match in matches:
                results.append(record(source, asset, name, amount(match.group()), ' | '.join(context[-8:]),
                                      page=page['page'], column=page['column'], variant=variant,
                                      method=method, confidence=line['confidence'], flags=flags))
            previous_name = name
            context = []
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--menu', choices=sorted(PROFILES), help='Extract one development menu')
    args = parser.parse_args()
    sources = json.loads((ROOT / 'data' / 'sources.json').read_text(encoding='utf-8'))
    sources = [source for source in sources if source['split'] == 'development'
               and (args.menu is None or source['id'] == args.menu)]
    output = OUTPUT if args.menu is None else OUTPUT / args.menu
    output.mkdir(parents=True, exist_ok=True)
    lock = output / '.extract.lock'
    try:
        lock_stream = lock.open('x')
    except FileExistsError:
        raise SystemExit(f'Extraction is already running, or a prior run was interrupted. Inspect {lock}')
    try:
        run(sources, output)
    finally:
        lock_stream.close()
        lock.unlink()


def run(sources, output=OUTPUT):
    engine = None
    records = []
    evidence = []
    statuses = []
    for source in sources:
        receipt = json.loads((ROOT / 'data' / 'raw' / 'batch_001' / source['id'] / 'receipt.json').read_text(encoding='utf-8'))
        menu_records = []
        for asset in receipt['assets']:
            path = ROOT / asset['path']
            if hashlib.sha256(path.read_bytes()).hexdigest() != asset['sha256']:
                raise ValueError(f'Raw file changed: {path}')
            print(f"Extracting {source['id']}/{path.name}", flush=True)
            if source['format'] == 'html':
                extracted, text = html_records(source, asset)
                evidence.append({'menu_id': source['id'], 'source_file': asset['path'], 'text': text})
            else:
                boundaries = PROFILES[source['id']]['columns']
                if source['format'] == 'text_pdf':
                    pages = pdf_lines(path, boundaries)
                else:
                    if engine is None:
                        from rapidocr import RapidOCR, LangRec, OCRVersion, ModelType
                        engine = RapidOCR(params={
                            'Global.model_root_dir': str(ROOT / '.models'),
                            'Rec.lang_type': LangRec.LATIN,
                            'Rec.ocr_version': OCRVersion.PPOCRV5,
                            'Rec.model_type': ModelType.MOBILE,
                            'EngineConfig.onnxruntime.intra_op_num_threads': 2,
                            'EngineConfig.onnxruntime.inter_op_num_threads': 2,
                        })
                    pages = ocr_lines(path, asset, engine, boundaries)
                extracted = layout_records(source, asset, pages)
                evidence.append({'menu_id': source['id'], 'source_file': asset['path'], 'pages': pages})
            menu_records.extend(extracted)
        # Exact duplicates may appear in repeated website markup.
        unique = {row['record_id']: row for row in menu_records}
        records.extend(unique.values())
        statuses.append({'menu_id': source['id'], 'candidate_rows': len(unique), 'duplicates_removed': len(menu_records) - len(unique)})
        print(f"  {len(unique)} candidate rows", flush=True)
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerows(records)
    csv_bytes = buffer.getvalue().encode('utf-8-sig')
    evidence_bytes = ('\n'.join(json.dumps(row, ensure_ascii=False) for row in evidence) + '\n').encode()
    report = {
        'extractor_version': VERSION, 'completed_at_utc': datetime.now(timezone.utc).isoformat(),
        'split': 'development', 'menus': statuses, 'candidate_rows': len(records),
        'review_status_counts': dict(Counter(row['review_status'] for row in records)),
        'dishes_csv_sha256': hashlib.sha256(csv_bytes).hexdigest(),
        'evidence_jsonl_sha256': hashlib.sha256(evidence_bytes).hexdigest(),
        'limitations': ['Candidates require manual verification.', 'Test menus have not been extracted.',
                        'OCR can miss or misread dishes and prices, especially handwriting.',
                        'Currency is assigned by the curated restaurant profile.'],
    }
    atomic_write(output / 'dishes.csv', csv_bytes)
    atomic_write(output / 'evidence.jsonl', evidence_bytes)
    # Written last; consumers can verify the data files against these hashes.
    atomic_write(output / 'report.json', (json.dumps(report, indent=2) + '\n').encode())
    print(f'Saved {len(records)} candidate rows to {output / "dishes.csv"}')


if __name__ == '__main__':
    main()
