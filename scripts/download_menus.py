"""Download the curated first batch and preserve the original response bytes."""

import hashlib
import io
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw' / 'batch_001'
MAX_BYTES = 30 * 1024 * 1024


def inspect_content(body, content_type, expected_format):
    """Check actual content rather than trusting a URL's file extension."""
    if body.startswith(b'%PDF-'):
        if expected_format not in ('text_pdf', 'ocr'):
            raise ValueError('Expected an HTML menu, received a PDF')
        reader = PdfReader(io.BytesIO(body))
        characters = [len((page.extract_text() or '').strip()) for page in reader.pages]
        if expected_format == 'text_pdf' and sum(characters) < 100:
            raise ValueError('PDF lacks sufficient extractable text')
        if expected_format == 'ocr' and sum(characters) >= 100:
            raise ValueError('Expected an image PDF, but found substantial text')
        return '.pdf', {'pages': len(reader.pages), 'text_characters_by_page': characters}
    if content_type.startswith('image/') and expected_format == 'ocr':
        with Image.open(io.BytesIO(body)) as picture:
            details = {'width': picture.width, 'height': picture.height, 'image_format': picture.format}
            suffix = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp', 'AVIF': '.avif'}[picture.format]
            picture.verify()
        return suffix, details
    if content_type == 'text/html' and expected_format == 'html':
        if b'<html' not in body.lower() or len(body) < 1000:
            raise ValueError('Incomplete HTML document')
        return '.html', {'html_review': 'Manual menu-content check required'}
    raise ValueError(f'Unexpected content type {content_type} for {expected_format}')


def atomic_write(path, body):
    """Keep partial downloads out of the accepted batch."""
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary.write(body)
        temporary_path = Path(temporary.name)
    try:
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def download_menu(source):
    folder = RAW / source['id']
    folder.mkdir(parents=True, exist_ok=True)
    receipt_path = folder / 'receipt.json'
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        if receipt['source'] != source:
            raise ValueError('Source changed; use a new batch to preserve this snapshot')
        for asset in receipt['assets']:
            digest = hashlib.sha256((ROOT / asset['path']).read_bytes()).hexdigest()
            if digest != asset['sha256']:
                raise ValueError(f"Checksum mismatch for {asset['path']}")
        print(f"Verified existing {source['id']}", flush=True)
        return

    assets = []
    for number, url in enumerate(source['urls'], start=1):
        request = Request(url, headers={'User-Agent': 'MenuPortfolio/0.1 (educational menu collection)'})
        with urlopen(request, timeout=40) as response:
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ValueError('File exceeds 30 MiB limit')
            content_type = response.headers.get_content_type()
            suffix, details = inspect_content(body, content_type, source['format'])
            destination = folder / f'menu_{number:02d}{suffix}'
            asset = {
                'url': url,
                'final_url': response.url,
                'downloaded_at_utc': datetime.now(timezone.utc).isoformat(),
                'http_status': response.status,
                'content_type': content_type,
                'last_modified': response.headers.get('Last-Modified'),
                'etag': response.headers.get('ETag'),
                'path': destination.relative_to(ROOT).as_posix(),
                'bytes': len(body),
                'sha256': hashlib.sha256(body).hexdigest(),
                **details,
            }
        atomic_write(destination, body)
        assets.append(asset)
    receipt = {'source': source, 'assets': assets}
    atomic_write(receipt_path, (json.dumps(receipt, indent=2, ensure_ascii=False) + '\n').encode('utf-8'))
    print(f"Downloaded {source['id']}: {len(assets)} file(s)", flush=True)


def main():
    sources = json.loads((ROOT / 'data' / 'sources.json').read_text(encoding='utf-8'))
    failures = []
    for source in sources:
        try:
            download_menu(source)
        except Exception as error:
            failures.append(source['id'])
            print(f"FAILED {source['id']}: {error}", file=sys.stderr, flush=True)
    if failures:
        raise SystemExit(f'Incomplete batch. Rerun to retry: {", ".join(failures)}')
    print(f'Complete: {len(sources)} menu sets in {RAW}')


if __name__ == '__main__':
    main()
