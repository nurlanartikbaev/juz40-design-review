#!/usr/bin/env python3
"""Готовит новую версию скилла: python3 tools/release.py 2.2.0

Записывает версию в VERSION и манифесты плагина и собирает dist/juz40-design-review.skill.
После запуска сделайте коммит и отправьте его в main: сотрудники получат версию при следующем ревью.
"""
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "juz40-design-review"
VERSION_FILE = SKILL / "VERSION"
PACKAGE = ROOT / "dist" / "juz40-design-review.skill"
PLUGIN = ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"


def parse(text):
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", text.strip())
    if not match:
        sys.exit(f"Неверная версия: {text.strip()}. Формат: 2.2.0")
    return tuple(int(part) for part in match.groups())


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_package():
    PACKAGE.parent.mkdir(exist_ok=True)
    files = sorted(
        path for path in SKILL.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.name != ".DS_Store"
    )
    with zipfile.ZipFile(PACKAGE, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, Path(SKILL.name) / path.relative_to(SKILL))
    return [str(path.relative_to(SKILL)) for path in files]


def main():
    if len(sys.argv) != 2:
        sys.exit("Укажите версию: python3 tools/release.py 2.2.0")
    version = sys.argv[1].strip()
    if VERSION_FILE.exists() and parse(version) <= parse(VERSION_FILE.read_text(encoding="utf-8")):
        sys.exit("Новая версия должна быть больше текущей")
    parse(version)
    VERSION_FILE.write_text(version + "\n", encoding="utf-8")

    plugin = json.loads(PLUGIN.read_text(encoding="utf-8"))
    plugin["version"] = version
    write_json(PLUGIN, plugin)

    marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    marketplace["plugins"][0]["version"] = version
    write_json(MARKETPLACE, marketplace)

    print(json.dumps({"version": version, "package": str(PACKAGE), "files": build_package()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
