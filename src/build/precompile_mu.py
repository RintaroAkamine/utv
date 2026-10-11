#!/usr/bin/env python3
# Copyright (c) 2026 OpenUTV Contributors.
# SPDX-License-Identifier: Apache-2.0

"""Build and validate startup Mu archives without creating a viewer session."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

STARTUP_MODULES = ("rvui", "timeline", "hover_preview_mode", "openrv_help_menu_mode", "sync_mode", "window_title")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_manifest(path):
    try:
        manifest = json.loads(path.read_text())
        archives = manifest["archives"]
        if not isinstance(archives, dict) or any(
            Path(name).name != name or not name.endswith(".muc") for name in archives
        ):
            raise ValueError("Invalid Mu archive filenames")
        return manifest
    except (OSError, KeyError, ValueError, TypeError):
        return {}


def update_timestamp(path, newest_source):
    stamp = max(time.time_ns(), newest_source)
    os.utime(path, ns=(stamp, stamp))


def discard(directory):
    manifest = directory / "startup-mu-cache.json"
    archives = read_manifest(manifest).get("archives", {})
    for name in archives:
        (directory / name).unlink(missing_ok=True)
    manifest.unlink(missing_ok=True)
    print(f"Removed {len(archives)} generated startup Mu archives")


def precompile(executable, directory):
    executable = executable.resolve(strict=True)
    directory = directory.resolve(strict=True)
    inputs = sorted(p for p in directory.iterdir() if p.suffix in (".mu", ".so"))
    producers = [executable]
    wrapped_binary = executable.with_name(executable.name + ".bin")
    if wrapped_binary.is_file():
        producers.append(wrapped_binary)
    identity = {
        "schema": 1,
        "producer": {path.name: digest(path) for path in producers},
        "modules": list(STARTUP_MODULES),
        "inputs": {p.name: digest(p) for p in inputs},
    }
    manifest = directory / "startup-mu-cache.json"
    newest_source = max(p.stat().st_mtime_ns for p in inputs if p.suffix == ".mu")
    previous = read_manifest(manifest)
    try:
        current = (
            previous.get("identity") == identity
            and previous.get("archives")
            and all(digest(directory / name) == checksum for name, checksum in previous["archives"].items())
        )
    except OSError:
        current = False
    if current:
        # Package staging can change timestamps without changing source content.
        for name in previous["archives"]:
            update_timestamp(directory / name, newest_source)
        print("Startup Mu archives are current")
        return

    with tempfile.TemporaryDirectory(prefix="utv-mu-") as temporary:
        sources = Path(temporary)
        for path in inputs:
            if path.suffix == ".mu":
                shutil.copy2(path, sources / path.name)
        command = [
            str(executable),
            "-noPrefs",
            "-flags",
            f"PrecompileMuSources={sources}",
            f"PrecompileMuNative={directory}",
            "PrecompileMuModules=" + ",".join(STARTUP_MODULES),
        ]
        environment = dict(os.environ, QT_QPA_PLATFORM="offscreen", RV_NO_CONSOLE_REDIRECT="1")
        # A second fresh process reads the generated archives. Nothing is
        # published into the app unless both compilation and readback succeed.
        for phase in ("compile", "validate"):
            completed = subprocess.run(
                command, env=environment, capture_output=True, text=True, timeout=120, check=False
            )
            if completed.returncode:
                raise RuntimeError(
                    f"Mu {phase} failed ({completed.returncode}):\n{completed.stdout}\n{completed.stderr}"
                )
            if phase == "compile":
                for archive in sources.glob("*.muc"):
                    update_timestamp(archive, newest_source)
            elif "INFO: compiled " in completed.stdout:
                raise RuntimeError("Mu validation recompiled a module instead of reading its archive")
        archives = sorted(sources.glob("*.muc"))
        if not archives or not (sources / "rvui.muc").is_file():
            raise RuntimeError("Startup Mu compilation produced no rvui archive")
        checksums = {path.name: digest(path) for path in archives}
        for path in archives:
            staged = directory / (path.name + ".tmp")
            shutil.copyfile(path, staged)
            update_timestamp(staged, newest_source)
            staged.replace(directory / path.name)
        for name in previous.get("archives", {}):
            if name not in checksums:
                (directory / name).unlink(missing_ok=True)
        staged_manifest = manifest.with_suffix(".json.tmp")
        staged_manifest.write_text(json.dumps({"identity": identity, "archives": checksums}, indent=2) + "\n")
        staged_manifest.replace(manifest)
        print(f"Compiled and validated {len(archives)} startup Mu archives")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--mu-dir", type=Path, required=True)
    parser.add_argument("--clean", action="store_true", help="Remove archives owned by the build manifest")
    arguments = parser.parse_args()
    if arguments.clean:
        discard(arguments.mu_dir)
    else:
        precompile(arguments.executable, arguments.mu_dir)


if __name__ == "__main__":
    main()
