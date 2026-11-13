"""Собирает браузерную версию LegalBot в папку docs для GitHub Pages."""

import json
import shutil
from dataclasses import asdict
from pathlib import Path

from knowledge import CARDS, TOPICS


ROOT = Path(__file__).resolve().parent


def main():
    output = ROOT / "docs"
    output.mkdir(exist_ok=True)
    for filename in ("style.css", "chat.js", "config.js"):
        shutil.copyfile(ROOT / "site" / filename, output / filename)
    shutil.copyfile(ROOT / "pages" / "local.js", output / "local.js")
    index = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    script = '  <script src="./chat.js" defer></script>'
    if index.count(script) != 1:
        raise RuntimeError("В шаблоне сайта не найдено подключение chat.js.")
    index = index.replace(script, '  <script src="./local.js" defer></script>\n' + script)
    (output / "index.html").write_text(index, encoding="utf-8")
    data = {"topics": TOPICS, "cards": [asdict(card) for card in CARDS]}
    (output / "knowledge.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / ".nojekyll").touch()


if __name__ == "__main__":
    main()
