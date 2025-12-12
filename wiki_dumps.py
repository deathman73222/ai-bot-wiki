#!/usr/bin/env python3
"""Wikipedia dumps downloader and extractor.

This script downloads the latest pages-articles XML dump for a given
language from dumps.wikimedia.org, extracts article plaintext and writes
each article to an individual .txt file under the output directory.

Usage examples:
    python wiki_dumps.py --lang en --outdir "C:\\AI Bot\\data\\wiki_dumps"
    python wiki_dumps.py --lang en --outdir ./data/wiki_dumps --max 1000

Notes:
- This script is a pragmatic extractor: it writes the raw wiki markup
  text found in the dump. If `mwparserfromhell` is installed it will
  be used to render a cleaner plain-text output.
- For very large dumps it may take many hours and require tens of GB.
  Use `--max` to limit articles during testing.
"""
from __future__ import annotations

import argparse
import bz2
import html
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterator, Optional
from xml.etree import ElementTree as ET

try:
    import mwparserfromhell  # type: ignore
except Exception:
    mwparserfromhell = None  # type: ignore


def safe_filename(title: str, max_length: int = 200) -> str:
    """Create a filesystem-safe filename from an article title."""
    # Replace path separators and control characters
    s = title.replace("/", "_").replace("\\", "_")
    s = re.sub(r'[<>:"\\|?*]', "_", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = html.unescape(s)
    if len(s) > max_length:
        s = s[:max_length]
    if not s:
        s = "untitled"
    return s


def iter_pages_from_bz2(bz2_path: Path) -> Iterator[tuple[str, str]]:
    """Yield (title, text) tuples by streaming parsing the XML dump.

    This uses a low-memory incremental parser (iterparse) over the
    decompressed bz2 stream so it can handle large dumps.
    """
    # ET.iterparse requires a file-like object that yields bytes; bz2.open
    # provides that. We search for <page> elements.
    with bz2.open(str(bz2_path), "rb") as fh:
        # Use a namespace-agnostic tag search: we check element tag endswith 'page'
        context = ET.iterparse(fh, events=("end",))
        for event, elem in context:
            tag = elem.tag
            if tag.endswith('page'):
                title_el = elem.find('title')
                revision = elem.find('revision')
                text_el = None
                if revision is not None:
                    text_el = revision.find('text')

                title = title_el.text if title_el is not None else ""
                text = text_el.text if text_el is not None and text_el.text else ""

                yield (title or "", text or "")

                # Clear the element to save memory
                elem.clear()


def render_plaintext(wiki_text: str) -> str:
    """Convert wiki markup to plain text when possible.

    If mwparserfromhell is installed we use it to strip templates and
    convert links; otherwise return the raw wiki_text.
    """
    if not wiki_text:
        return ""
    if mwparserfromhell:
        try:
            parsed = mwparserfromhell.parse(wiki_text)
            return parsed.strip_code()
        except Exception:
            return wiki_text
    # Basic fallback: remove common wiki markup patterns
    text = wiki_text
    # Remove templates {{...}}
    text = re.sub(r"\{\{[^\}]*\}\}", "", text)
    # Remove file links [[File:...]] and [[Image:...]]
    text = re.sub(r"\[\[(?:File|Image):[^\]]*\]\]",
                  "", text, flags=re.IGNORECASE)
    # Replace internal links [[A|B]] or [[A]] -> B or A
    text = re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]", lambda m: m.group(2), text)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    return text


def download_dump(url: str, dest: Path) -> None:
    """Download the given URL to dest (streaming).

    Uses urllib to avoid adding requests as a hard dependency.
    """
    import urllib.request

    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading: {url}")
    with urllib.request.urlopen(url) as resp:
        total = resp.getheader('Content-Length')
        total = int(total) if total else None
        with open(dest, 'wb') as out:
            downloaded = 0
            chunk_size = 65536
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    # Emit parseable progress so external processes can read it
                    print(f"PROGRESS_DOWNLOAD:{pct}:{downloaded}", flush=True)
    print("\nDownload complete.")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Download and extract Wikipedia dumps into text files")
    parser.add_argument("--lang", default="en",
                        help="Language code (e.g. en, es, fr)")
    parser.add_argument("--outdir", default="data/wiki_dumps",
                        help="Output directory for extracted files")
    parser.add_argument("--max", type=int, default=0,
                        help="Maximum number of articles to extract (0 = all)")
    parser.add_argument("--skip-download", action="store_true",
                        help="Skip download step and use existing .bz2 file in outdir")
    parser.add_argument("--use-wikiextractor", action="store_true",
                        help="If WikiExtractor.py is available in PATH use it for faster extraction")
    args = parser.parse_args(argv)

    lang = args.lang
    outdir = Path(args.outdir) / lang
    outdir.mkdir(parents=True, exist_ok=True)

    dump_filename = f"{lang}wiki-latest-pages-articles.xml.bz2"
    dump_path = outdir / dump_filename
    dump_url = f"https://dumps.wikimedia.org/{lang}wiki/latest/{dump_filename}"

    if not args.skip_download:
        try:
            download_dump(dump_url, dump_path)
        except Exception as exc:
            print(f"Failed to download dump: {exc}")
            return 2

    # Extraction
    articles_dir = outdir / "articles"
    articles_dir.mkdir(exist_ok=True)

    index = []
    max_articles = args.max or 0
    count = 0

    print("Starting extraction (this can take a long time for full dumps)...")

    # If requested and WikiExtractor.py is installed, try to use it
    if args.use_wikiextractor:
        try:
            # WikiExtractor writes output directories; call it with -b to set chunk size
            subprocess = __import__('subprocess')
            out_chunks = outdir / 'wikiextractor_output'
            cmd = [
                'WikiExtractor.py',
                str(dump_path),
                '-o', str(out_chunks),
                '--no-templates',
                '-b', '1M'
            ]
            print('Running WikiExtractor.py (external tool)...')
            subprocess.check_call(cmd)
            print('WikiExtractor.py completed. Converting to per-article files...')
            # Walk chunks and split into individual article files
            for chunk in out_chunks.rglob('*.txt'):
                with chunk.open('r', encoding='utf-8', errors='ignore') as fh:
                    text = fh.read()
                # WikiExtractor output already has title lines like <doc id="..." title="...">
                parts = re.split(r'<doc[^>]*>', text)
                for part in parts[1:]:
                    m = re.search(r'title="([^"]+)"', part)
                    title = m.group(1) if m else 'untitled'
                    content = re.sub(r'</doc>\s*$', '', part)
                    fname = safe_filename(title)
                    target = articles_dir / f"{fname}.txt"
                    with target.open('w', encoding='utf-8') as outfh:
                        outfh.write(render_plaintext(content))
                    index.append({'title': title, 'file': str(target)})
                    count += 1
                    if max_articles and count >= max_articles:
                        break
                if max_articles and count >= max_articles:
                    break
        except FileNotFoundError:
            print(
                'WikiExtractor.py not found in PATH; falling back to built-in extractor.')
        except Exception as exc:
            print(
                f'WikiExtractor failed: {exc}; falling back to built-in extractor.')

    if count == 0:
        # Built-in streaming extractor
        try:
            for title, text in iter_pages_from_bz2(dump_path):
                if not title and not text:
                    continue
                fname = safe_filename(title) or f"article_{count}"
                target = articles_dir / f"{fname}.txt"
                try:
                    with target.open('w', encoding='utf-8') as fh:
                        fh.write(render_plaintext(text))
                except Exception as exc:
                    print(f"Failed to write {target}: {exc}")
                    continue

                index.append({'title': title, 'file': str(target)})
                count += 1
                if count % 100 == 0:
                    # Print parseable extraction progress
                    print(f"EXTRACTED:{count}", flush=True)
                if max_articles and count >= max_articles:
                    break
        except Exception as exc:
            print(f"Extraction failed: {exc}")
            return 3

    # Save index
    index_file = outdir / 'index.json'
    try:
        with index_file.open('w', encoding='utf-8') as fh:
            json.dump(index, fh, ensure_ascii=False, indent=2)
        print(f"Saved index with {len(index)} articles to {index_file}")
    except Exception as exc:
        print(f"Failed to save index: {exc}")

    print(f"Done. Extracted {count} articles to {articles_dir}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
