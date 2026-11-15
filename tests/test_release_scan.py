"""Check release exclusions and token boundaries without real credentials."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "release_scan", Path(__file__).resolve().parent.parent / "scripts/check_public_tree.py"
)
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)


def test_standalone_api_key_shapes_are_rejected():
    fake = b"sk-" + b"a" * 40
    assert scanner.inspect("config.txt", b'key="' + fake + b'"')
    assert scanner.inspect("HouseTalk.dll", b"\x00" + fake + b"\x00")


def test_key_substring_inside_binary_identifier_is_not_a_credential():
    # The .NET runtime contains concatenated locale identifiers with this substring.
    assert not scanner.inspect("System.Private.CoreLib.dll", b"ksk-" + b"a" * 746 + b"\x00")


def test_runtime_files_and_unsafe_archive_paths_are_rejected():
    for name in ["Data/config.json", "connection.dpapi", "../secret.txt", "secrets.yaml"]:
        assert scanner.inspect(name, b"{}")
