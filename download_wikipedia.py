#!/usr/bin/env python
"""Interactive Wikipedia dump downloader by language."""
import subprocess
from ai_bot.modules.wikipedia_offline import WikipediaOffline
from ai_bot.modules.web_search import WebSearcher
import sys
import os

repo_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, repo_root)


def list_supported_languages():
    """List common Wikipedia languages available for download."""
    languages = {
        'en': 'English',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'it': 'Italian',
        'pt': 'Portuguese',
        'ru': 'Russian',
        'ja': 'Japanese',
        'zh': 'Chinese',
        'ko': 'Korean',
        'ar': 'Arabic',
        'hi': 'Hindi',
        'nl': 'Dutch',
        'pl': 'Polish',
        'tr': 'Turkish',
    }
    return languages


def download_wikipedia_dump(language_code: str, output_dir: str = 'data/wiki_dumps', max_articles: int = None):
    """Download and extract Wikipedia dump for a given language.

    Args:
        language_code: Language code (e.g., 'en', 'es', 'fr').
        output_dir: Directory to store downloaded dumps.
        max_articles: Maximum articles to extract (None for unlimited).

    Returns:
        True if successful, False otherwise.
    """
    print(f"\n📥 Downloading Wikipedia dump for language: {language_code}")

    try:
        script_path = os.path.join(repo_root, 'wiki_dumps.py')
        cmd = [sys.executable, script_path, '--lang',
               language_code, '--outdir', output_dir]

        if max_articles:
            cmd.extend(['--max', str(max_articles)])

        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True)

        if result.returncode == 0:
            print(
                f"✅ Successfully downloaded {language_code} Wikipedia dump to {output_dir}")
            return True
        else:
            print(
                f"❌ Failed to download dump (exit code: {result.returncode})")
            return False
    except FileNotFoundError:
        print(f"❌ wiki_dumps.py not found at {script_path}")
        return False
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during download: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def main():
    """Main interactive menu."""
    print("\n" + "="*60)
    print("🌍 Wikipedia Offline Downloader")
    print("="*60)

    langs = list_supported_languages()

    print("\nAvailable languages:")
    for code, name in sorted(langs.items()):
        print(f"  {code:5} - {name}")

    print("\nOptions:")
    print("  'list'   - Show all available languages")
    print("  'full'   - Download full dump (many GB, hours)")
    print("  'sample' - Download sample (fast, ~100 articles)")
    print("  'quit'   - Exit")

    while True:
        user_input = input(
            "\nEnter language code or option (e.g., 'en', 'sample', 'quit'): ").strip().lower()

        if user_input == 'quit':
            print("Goodbye!")
            sys.exit(0)

        if user_input == 'list':
            print("\nFull language list:")
            for code, name in sorted(langs.items()):
                print(f"  {code:5} - {name}")
            continue

        if user_input in ('full', 'sample'):
            lang = input("Enter language code (e.g., 'en'): ").strip().lower()
            if lang not in langs:
                print(f"❌ Unknown language code: {lang}")
                continue

            max_articles = None if user_input == 'full' else 100
            mode_str = "FULL" if user_input == 'full' else "SAMPLE"

            confirm = input(
                f"\n⚠️  Download {mode_str} Wikipedia dump for {langs[lang]} ({lang})? (yes/no): ").strip().lower()
            if confirm not in ('yes', 'y'):
                print("Cancelled.")
                continue

            download_wikipedia_dump(lang, max_articles=max_articles)
            continue

        if user_input in langs:
            confirm = input(
                f"\n⚠️  Download Wikipedia dump for {langs[user_input]} ({user_input})? (yes/no): ").strip().lower()
            if confirm not in ('yes', 'y'):
                print("Cancelled.")
                continue

            download_wikipedia_dump(user_input)
        else:
            print(f"❌ Unknown option or language code: {user_input}")


if __name__ == '__main__':
    main()
