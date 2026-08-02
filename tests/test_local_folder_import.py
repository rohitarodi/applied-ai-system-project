from app import scan_local_folder


def test_scan_local_folder_finds_only_supported_extensions(tmp_path):
    (tmp_path / "song_one.wav").write_bytes(b"fake wav")
    (tmp_path / "notes.txt").write_text("not audio")
    (tmp_path / "song_two.flac").write_bytes(b"fake flac")

    found = scan_local_folder(str(tmp_path))

    titles = sorted(s["title"] for s in found)
    assert titles == ["Song One"]


def test_scan_local_folder_audio_fields(tmp_path):
    f = tmp_path / "my-track.wav"
    f.write_bytes(b"fake wav")

    found = scan_local_folder(str(tmp_path))

    assert len(found) == 1
    song = found[0]
    assert song["audio"]["source_type"] == "local"
    assert song["audio"]["path"] == str(f)
    assert song["artist"] == "local import"  # normalize_song lowercases artist
    assert song["tags"] == ["local-import"]
    assert song["energy"] == 5


def test_scan_local_folder_missing_folder_returns_empty_list():
    assert scan_local_folder("this/path/does/not/exist") == []


def test_scan_local_folder_recurses_into_subdirectories(tmp_path):
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "nested.mp3").write_bytes(b"fake mp3")

    found = scan_local_folder(str(tmp_path))

    assert len(found) == 1
    assert found[0]["title"] == "Nested"
