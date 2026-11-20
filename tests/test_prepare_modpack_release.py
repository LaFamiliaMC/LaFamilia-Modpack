"""Tests for schema-2 preparation of the user's three ZIP archives."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from scripts.prepare_modpack_release import process_archive, safe_name, main
from unittest.mock import patch


class PreparationTests(unittest.TestCase):
    def make_zip(self, root, name, files):
        archive = root / name
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for path, contents in files.items():
                z.writestr(path, contents)
        return archive

    def test_safe_names(self):
        self.assertEqual(safe_name("mods/example.jar", "mods"), "example.jar")
        self.assertEqual(safe_name("sub/settings.toml", "config"), "sub/settings.toml")
        for name in ("../evil.jar", "mods/../evil.jar", "mods/evil.exe",
                     "mods/sub/evil.jar", "mods/CON.jar", "mods/a?.jar"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    safe_name(name, "mods")

    def test_manifest_format_and_jar_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            incoming, out = root / "input", root / "out"
            incoming.mkdir()
            self.make_zip(incoming, "mods.zip", {"mods/fabric-api.jar": b"jar-data"})
            self.make_zip(incoming, "resourcepacks.zip", {"resourcepacks/MyPack.zip": b"rp-data"})
            self.make_zip(incoming, "config.zip", {"config/sub/settings.toml": b"cfg-data"})
            with patch("sys.argv", ["prepare", "--input", str(incoming), "--output", str(out), "--version", "1.0.1"]):
                main()
            manifest = json.loads((out / "manifest.json").read_text("utf-8"))
            self.assertEqual(manifest["schemaVersion"], 2)
            self.assertEqual(manifest["minecraftVersion"], "1.21.1")
            self.assertEqual(manifest["mods"][0]["path"], "mods/fabric-api.jar")
            self.assertEqual(manifest["mods"][0]["file"], "fabric-api.jar")
            self.assertRegex(manifest["mods"][0]["url"], r"/mod-[a-f0-9]{64}\\.jar$")
            self.assertEqual(manifest["resourcepacks"]["files"][0]["path"], "resourcepacks/MyPack.zip")
            self.assertEqual(manifest["config"]["files"][0]["path"], "config/sub/settings.toml")
            self.assertEqual(len(list((out / "assets").glob("mod-*.jar"))), 1)
            self.assertEqual(next((out / "assets").glob("mod-*.jar")).read_bytes(), b"jar-data")

    def test_bracket_filename_keeps_original_mod_name_but_safe_github_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self.make_zip(root, "mods.zip", {
                "mods/CameraOverhaul-v2.1.2-fabric+mc[1.21-1.21.2].jar": b"jar-test"
            })
            output = root / "out"
            (output / "assets").mkdir(parents=True)
            entries = process_archive("mods", archive, output, "1.0.1")
            self.assertEqual(entries[0]["file"],
                "CameraOverhaul-v2.1.2-fabric+mc[1.21-1.21.2].jar")
            self.assertRegex(entries[0]["url"], r"/mod-[a-f0-9]{64}\\.jar$")
            self.assertEqual(len(list((output / "assets").glob("mod-*.jar"))), 1)

    def test_27158_config_entries_are_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "config.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as z:
                for i in range(27158):
                    z.writestr(f"config/generated/entry_{i:05d}.json", b"{}")
            output = root / "out"
            output.mkdir()
            result = process_archive("config", archive, output, "1.0.1")
            self.assertEqual(len(result), 27158)
            self.assertEqual(result[0]["path"], "config/generated/entry_00000.json")
            self.assertEqual(result[-1]["path"], "config/generated/entry_27157.json")

    def test_duplicate_and_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "out"
            (out / "assets").mkdir(parents=True)
            bad = self.make_zip(root, "bad.zip", {"mods/../attack.jar": b"bad"})
            with self.assertRaises(ValueError):
                process_archive("mods", bad, out, "1.0.1")
            duplicate = root / "duplicate.zip"
            with zipfile.ZipFile(duplicate, "w") as z:
                z.writestr("mods/Test.jar", b"one")
                z.writestr("mods/test.jar", b"two")
            with self.assertRaises(ValueError):
                process_archive("mods", duplicate, out, "1.0.1")


if __name__ == "__main__":
    unittest.main()
