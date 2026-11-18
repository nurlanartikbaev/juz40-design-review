#!/usr/bin/env python3
"""Обновляет скилл из репозитория и сообщает, какую версию использовать.

Печатает JSON:
  status   updated, current, offline или skipped
  version  версия, которую нужно использовать
  path     папка этой версии
  reread   true, если нужно заново прочитать SKILL.md из path

Сбой обновления не мешает ревью: скрипт всегда завершается с кодом 0.
"""
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

REPOSITORY = "https://raw.githubusercontent.com/nurlanartikbaev/juz40-design-review/main"
VERSION_URL = f"{REPOSITORY}/skills/juz40-design-review/VERSION"
PACKAGE_URL = f"{REPOSITORY}/dist/juz40-design-review.skill"

HOME = Path(os.environ.get("JUZ40_REVIEW_HOME", Path.home() / ".juz40-design-review"))
CURRENT = HOME / "current"
SKILL_NAME = "juz40-design-review"
REQUIRED_FILES = (
    "SKILL.md",
    "VERSION",
    "assets/report_template.md",
    "references/compare.md",
    "scripts/devshot.py",
    "scripts/update.py",
)
ALLOWED_SUFFIXES = {".md", ".py"}
MAX_BYTES = 5 * 1024 * 1024
MAX_FILES = 40


class Offline(Exception):
    """GitHub недоступен."""


class BadPackage(Exception):
    """Пакет обновления нельзя установить."""


def fetch(url, target):
    command = [
        "curl", "-fsSL", "--proto", "=https", "--proto-redir", "=https", "--tlsv1.2",
        "--connect-timeout", "4", "--max-time", "20", "--max-filesize", str(MAX_BYTES),
        "-o", str(target), url,
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as error:
        raise Offline(str(error)) from error


def parse_version(text):
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", text.strip())
    return tuple(int(part) for part in match.groups()) if match else None


def read_version(folder):
    try:
        return parse_version((folder / "VERSION").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None


def is_complete(folder):
    return read_version(folder) is not None and all((folder / name).is_file() for name in REQUIRED_FILES)


def format_version(version):
    return ".".join(str(part) for part in version)


def extract(package, target):
    """Распаковывает только ожидаемые файлы скилла."""
    try:
        with zipfile.ZipFile(package) as archive:
            files = [item for item in archive.infolist() if not item.is_dir()]
            if len(files) > MAX_FILES or sum(item.file_size for item in files) > MAX_BYTES:
                raise BadPackage("пакет слишком большой")
            for item in files:
                path = PurePosixPath(item.filename)
                parts = path.parts
                if path.is_absolute() or "\\" in item.filename or ".." in parts:
                    raise BadPackage(f"недопустимый путь: {item.filename}")
                if len(parts) < 2 or parts[0] != SKILL_NAME:
                    raise BadPackage(f"файл вне скилла: {item.filename}")
                if path.name != "VERSION" and path.suffix not in ALLOWED_SUFFIXES:
                    raise BadPackage(f"недопустимый тип файла: {item.filename}")
                if stat.S_ISLNK(item.external_attr >> 16):
                    raise BadPackage(f"символическая ссылка: {item.filename}")
                destination = target.joinpath(*parts[1:])
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(item))
    except zipfile.BadZipFile as error:
        raise BadPackage("пакет повреждён") from error


def install(version):
    """Скачивает и проверяет пакет, затем заменяет установленную версию."""
    staging = Path(tempfile.mkdtemp(prefix="staging-", dir=HOME))
    try:
        package = staging / "package.skill"
        fetch(PACKAGE_URL, package)
        unpacked = staging / "skill"
        unpacked.mkdir()
        extract(package, unpacked)
        if not is_complete(unpacked):
            raise BadPackage("в пакете не хватает файлов")
        if read_version(unpacked) != version:
            raise BadPackage("версия пакета не совпадает с опубликованной")

        previous = None
        if CURRENT.exists():
            previous = staging / "previous"
            CURRENT.rename(previous)
        try:
            unpacked.rename(CURRENT)
        except OSError:
            if previous:
                previous.rename(CURRENT)
            raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def active_folder(own):
    own_version = read_version(own) or (0, 0, 0)
    if own.resolve() != CURRENT.resolve() and is_complete(CURRENT) and read_version(CURRENT) > own_version:
        return CURRENT
    return own


def latest_version():
    with tempfile.TemporaryDirectory(dir=HOME) as folder:
        target = Path(folder) / "VERSION"
        fetch(VERSION_URL, target)
        version = parse_version(target.read_text(encoding="utf-8", errors="replace"))
    if version is None:
        raise BadPackage("неверный формат версии")
    return version


def run(own):
    HOME.mkdir(parents=True, exist_ok=True)
    folder = active_folder(own)
    result = {"status": "current"}
    try:
        latest = latest_version()
        if latest > (read_version(folder) or (0, 0, 0)):
            install(latest)
            folder = CURRENT
            result["status"] = "updated"
    except Offline:
        result["status"] = "offline"
    except (BadPackage, OSError) as error:
        result["status"] = "skipped"
        result["reason"] = str(error)
    result.update(
        {
            "version": format_version(read_version(folder) or (0, 0, 0)),
            "path": str(folder),
            "reread": result["status"] == "updated" or folder.resolve() != own.resolve(),
        }
    )
    return result


if __name__ == "__main__":
    print(json.dumps(run(Path(__file__).resolve().parent.parent), ensure_ascii=False, indent=2))
