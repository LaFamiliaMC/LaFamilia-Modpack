#!/usr/bin/env python3
"""Convert three GitHub Release ZIP archives into Launcher schema-2 assets.

Run only on a trusted, unpublished LaFamilia-Modpack draft release.
No Minecraft files or existing GitHub release are changed by this script.
"""
import argparse
import hashlib
import json
import re
import shutil
import stat
import unicodedata
import urllib.parse
import zipfile
from pathlib import Path

PACK_REPO = "LaFamiliaMC/LaFamilia-Modpack"
CATEGORIES = ("mods", "resourcepacks", "config")
SHA_CHUNK = 1024 * 1024
INVALID = re.compile(r'[<>:"|?*\\\\\\x00-\\x1f]')
RESERVED = re.compile(r'^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\\.|$)', re.I)


def digest_file(path):
    hash_ = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(SHA_CHUNK), b""):
            hash_.update(chunk)
    return hash_.hexdigest()


def safe_name(raw, category):
    if not isinstance(raw, str) or not raw or "\\" in raw or raw.startswith("/"):
        raise ValueError(f"Unsicherer ZIP-Pfad ({category}): {raw!r}")
    if raw.startswith(category + "/"):
        raw = raw[len(category) + 1:]
    parts = raw.split("/")
    if not raw or len(category + "/" + raw) > 235 or unicodedata.normalize("NFC", raw) != raw:
        raise ValueError(f"Ungueltiger ZIP-Pfad ({category}): {raw!r}")
    for part in parts:
        if not part or part in (".", "..") or part[-1] in (" ", ".") or INVALID.search(part) or RESERVED.search(part):
            raise ValueError(f"Unsicherer ZIP-Pfad ({category}): {raw!r}")
    if category == "mods" and (len(parts) != 1 or not parts[0].lower().endswith(".jar")):
        raise ValueError(f"Mods-ZIP enthaelt keine Mod-JAR: {raw!r}")
    return raw


def asset_url(version, name):
    return (f"https://github.com/{PACK_REPO}/releases/download/"
            f"modpack-v{version}/{urllib.parse.quote(name, safe='')}")


def process_archive(category, archive, output, version):
    entries = []
    found = set()
    max_count = 950 if category == "mods" else 20000
    total_size = 0
    with zipfile.ZipFile(archive, "r") as source:
        for info in source.infolist():
            if info.filename in (category + "/",):
                continue
            if info.is_dir():
                safe_name(info.filename.rstrip("/"), category)
                continue
            if info.flag_bits & 1:
                raise ValueError(f"Verschluesselte ZIP-Datei: {info.filename!r}")
            if stat.S_ISLNK((info.external_attr >> 16) & 0xffff):
                raise ValueError(f"ZIP-Symlink nicht erlaubt: {info.filename!r}")
            if info.filename.startswith("__MACOSX/") or info.filename == ".DS_Store":
                continue
            relative = safe_name(info.filename, category)
            key = relative.casefold()
            if key in found:
                raise ValueError(f"Doppelter Dateiname im {category}-ZIP: {relative}")
            found.add(key)
            total_size += info.file_size
            if info.file_size > 2 * 1024**3 or total_size > 12 * 1024**3 or len(found) > max_count:
                raise ValueError(f"ZIP-Grenze ueberschritten: {category}")
            hash_ = hashlib.sha256()
            output_file = None
            if category == "mods":
                output_file = output / "assets" / ("mod-" + "0" * 16 + "-" + relative)
                # The final hashed asset name is chosen after streaming the JAR.
                output_file.parent.mkdir(parents=True, exist_ok=True)
            written = 0
            with source.open(info) as input_stream:
                if output_file:
                    with output_file.open("wb") as dest:
                        for chunk in iter(lambda: input_stream.read(SHA_CHUNK), b""):
                            written += len(chunk)
                            hash_.update(chunk)
                            dest.write(chunk)
                else:
                    for chunk in iter(lambda: input_stream.read(SHA_CHUNK), b""):
                        written += len(chunk)
                        hash_.update(chunk)
            if written != info.file_size:
                raise ValueError(f"Dateigroesse stimmt nicht: {relative}")
            item = {
                "path": category + "/" + relative,
                "size": written,
                "sha256": hash_.hexdigest(),
            }
            if category == "mods":
                if written == 0:
                    raise ValueError(f"Leere Mod-JAR: {relative}")
                asset = "mod-" + item["sha256"][:16] + "-" + relative
                if len(asset.encode("utf-8")) > 255:
                    raise ValueError(f"GitHub-Assetname zu lang: {asset}")
                output_file.rename(output / "assets" / asset)
                item.update({"file": relative, "url": asset_url(version, asset)})
            entries.append(item)
    if not entries:
        raise ValueError(f"Das ZIP enthaelt keine Dateien: {category}")
    entries.sort(key=lambda item: item["path"].casefold())
    return entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"\\d+\\.\\d+\\.\\d+", args.version):
        parser.error("Version muss x.y.z sein")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "assets").mkdir(exist_ok=True)
    records = {}
    totals = 0
    for category in CATEGORIES:
        archive = args.input / (category + ".zip")
        if not archive.is_file():
            raise SystemExit(f"ZIP fehlt: {archive}")
        files = process_archive(category, archive, args.output, args.version)
        totals += sum(item["size"] for item in files)
        archive_record = {
            "file": archive.name,
            "size": archive.stat().st_size,
            "sha256": digest_file(archive),
            "url": asset_url(args.version, archive.name),
        }
        records[category] = {"files": files, "archive": archive_record}
        print(f"{category}: {len(files)} Dateien verarbeitet", flush=True)
    if totals > 12 * 1024**3:
        raise SystemExit("Gesamtpaket ueber 12 GiB")
    manifest = {
        "schemaVersion": 2,
        "packId": "la-familia",
        "minecraftVersion": "1.21.1",
        "modLoader": "fabric",
        "version": args.version,
        "mods": records["mods"]["files"],
        "resourcepacks": records["resourcepacks"],
        "config": records["config"],
    }
    output_file = args.output / "manifest.json"
    output_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    print(f"FERTIG: {len(manifest['mods'])} Mods, "
          f"{len(manifest['resourcepacks']['files'])} Resourcepacks, "
          f"{len(manifest['config']['files'])} Config-Dateien")


if __name__ == "__main__":
    main()
