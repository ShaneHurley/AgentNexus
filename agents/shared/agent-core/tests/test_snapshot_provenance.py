import hashlib
from agent_core.isolation import DockerRunner

def test_snapshot_returns_only_materialized_file_hashes(tmp_path):
    repo=tmp_path/"repo";repo.mkdir()
    destination=tmp_path/"snapshot";destination.mkdir()
    (repo/"code.py").write_text("print(1)\n")
    (repo/".env").write_text("PRIVATE=value")
    (repo/"credentials.json").write_text("PRIVATE")
    outside=tmp_path/"outside";outside.write_text("private")
    (repo/"link").symlink_to(outside)
    runner=DockerRunner("python@sha256:"+"a"*64,repo)
    manifest=runner._snapshot(destination)
    assert manifest=={"code.py":hashlib.sha256(b"print(1)\n").hexdigest()}
    assert set(p.name for p in destination.iterdir())=={"code.py"}
