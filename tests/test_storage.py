import json
import logging

import storage


def test_load_json_missing_file_returns_default(tmp_path, caplog):
    path = tmp_path / "does_not_exist.json"
    default = {"songs": []}

    with caplog.at_level(logging.WARNING):
        result = storage.load_json(str(path), default=default)

    assert result == default
    # must be a deep copy, not the same object, so callers can't mutate the default
    assert result is not default
    assert any("does_not_exist.json" in record.message for record in caplog.records)


def test_load_json_missing_file_default_is_deep_copied(tmp_path):
    default = {"songs": [{"title": "a"}]}
    path = tmp_path / "missing.json"

    result = storage.load_json(str(path), default=default)
    result["songs"].append({"title": "b"})

    # mutating the result must not mutate the original default argument
    assert len(default["songs"]) == 1


def test_load_json_malformed_file_returns_default(tmp_path, caplog):
    path = tmp_path / "bad.json"
    path.write_text("{not valid json", encoding="utf-8")
    default = []

    with caplog.at_level(logging.WARNING):
        result = storage.load_json(str(path), default=default)

    assert result == default
    assert any("bad.json" in record.message for record in caplog.records)


def test_save_then_load_round_trip(tmp_path):
    path = tmp_path / "nested" / "dir" / "library.json"
    data = [{"title": "Thunderstruck", "artist": "AC/DC", "energy": 9}]

    storage.save_json(str(path), data)
    assert path.exists()

    loaded = storage.load_json(str(path), default=[])
    assert loaded == data


def test_save_json_creates_parent_dirs(tmp_path):
    path = tmp_path / "a" / "b" / "c" / "file.json"
    storage.save_json(str(path), {"x": 1})
    assert path.exists()
    with open(path, encoding="utf-8") as f:
        assert json.load(f) == {"x": 1}


def test_load_json_never_raises_on_permission_style_errors(tmp_path):
    # a directory path passed as if it were a file should not crash load_json
    dir_path = tmp_path / "a_directory"
    dir_path.mkdir()

    result = storage.load_json(str(dir_path), default={"fallback": True})
    assert result == {"fallback": True}
