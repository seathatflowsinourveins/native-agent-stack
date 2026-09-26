#!/usr/bin/env python3
"""Independent verifier: integrity of the installed ai-memory 2.4.0 prefix (read-only).

1. Re-fetch the upstream release metadata (GitHub API asset digest/size/url, release
   body, .sha256 sidecar) and compare with the pinned value.
2. Hash the retained tarball in the implementer's dl/ directory.
3. Compare every tarball member with the installed prefix (type, bytes, mode bits of
   concern) and list anything in the prefix that is not in the tarball.
4. Report ctime of the newest prefix entry (a modification after install shows up here).
5. Hash the 2.3.2 binary (the baseline arm) and the cached pinned 2.3.2 tarball.
No writes except the JSON result in this verify/ directory.
"""
import hashlib, json, os, subprocess, tarfile, time, stat
from pathlib import Path

HOME = Path.home()
ECO = HOME / ".local/share/codex-ecosystem"
NEWP = ECO / "tools/ai-memory-2.4.0"
OLD = ECO / "tools/ai-memory-2.3.2/ai-memory"
IMPL = Path(__file__).resolve().parent.parent
TARBALL = IMPL / "dl/ai-memory-2.4.0-linux-x86_64.tar.gz"
PIN = "590f75ddaf0f8f1a07b70ba20900de717b89c3f6c46e6e5e0540ade302795076"
REPO, TAG, ASSET = "akitaonrails/ai-memory", "v2.4.0", "ai-memory-linux-x86_64.tar.gz"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


res = {"at": iso(time.time())}
rel = json.loads(subprocess.run(["gh", "api", f"repos/{REPO}/releases/tags/{TAG}"],
                                capture_output=True, text=True, check=True).stdout)
asset = next(a for a in rel["assets"] if a["name"] == ASSET)
side = subprocess.run(["gh", "release", "download", TAG, "--repo", REPO, "--pattern",
                       f"{ASSET}.sha256", "-O", "-"], capture_output=True, text=True, check=True).stdout.split()
latest = json.loads(subprocess.run(["gh", "api", f"repos/{REPO}/releases/latest"],
                                   capture_output=True, text=True, check=True).stdout)
res["upstream"] = {
    "tag_commit_via_api": None,
    "release_published_at": rel.get("published_at"), "immutable": rel.get("immutable"),
    "latest_release_tag": latest.get("tag_name"),
    "api_digest_matches_pin": asset.get("digest") == f"sha256:{PIN}",
    "api_size": asset.get("size"),
    "api_url_is_official": asset.get("browser_download_url")
    == f"https://github.com/{REPO}/releases/download/{TAG}/{ASSET}",
    "api_asset_updated_at": asset.get("updated_at"),
    "sidecar_matches_pin": bool(side) and side[0] == PIN,
    "release_body_lists_pin": PIN in (rel.get("body") or ""),
}
ref = json.loads(subprocess.run(["gh", "api", f"repos/{REPO}/git/ref/tags/{TAG}"],
                                capture_output=True, text=True, check=True).stdout)
res["upstream"]["tag_commit_via_api"] = ref["object"]["sha"][:12] + " (" + ref["object"]["type"] + ")"

tb_sha = sha(TARBALL)
res["tarball"] = {"sha256_matches_pin": tb_sha == PIN, "bytes": TARBALL.stat().st_size,
                  "bytes_match_api": TARBALL.stat().st_size == asset.get("size"),
                  "mtime": iso(TARBALL.stat().st_mtime)}

mismatch, missing, checked_files, checked_dirs, bad_modes = [], [], 0, 0, []
members = set()
with tarfile.open(TARBALL, "r:gz") as tar:
    for m in tar.getmembers():
        rel_name = os.path.normpath(m.name)
        members.add(rel_name)
        dest = NEWP / rel_name if rel_name != "." else NEWP
        if m.isdir():
            if not dest.is_dir():
                missing.append(rel_name)
            checked_dirs += 1
            continue
        if not m.isfile():
            mismatch.append(f"{rel_name}: non-regular member type")
            continue
        if not dest.is_file() or dest.is_symlink():
            missing.append(rel_name)
            continue
        data = tar.extractfile(m).read()
        if hashlib.sha256(data).hexdigest() != sha(dest):
            mismatch.append(rel_name)
        checked_files += 1
extra, newest_ctime, newest_path = [], 0, None
for root, dirs, files in os.walk(NEWP):
    for name in dirs + files:
        p = Path(root) / name
        r = os.path.normpath(os.path.relpath(p, NEWP))
        st = os.lstat(p)
        if r not in members:
            extra.append(r)
        if st.st_ctime > newest_ctime:
            newest_ctime, newest_path = st.st_ctime, r
        if st.st_mode & (stat.S_IWGRP | stat.S_IWOTH | stat.S_ISUID | stat.S_ISGID) or st.st_uid != os.getuid():
            bad_modes.append(r)
st = os.stat(NEWP)
res["prefix"] = {"files_checked": checked_files, "dirs_checked": checked_dirs,
                 "content_mismatches": mismatch, "missing_from_prefix": missing,
                 "extra_in_prefix": extra, "group_or_world_writable_setid_or_foreign_owner": bad_modes,
                 "newest_ctime": iso(newest_ctime), "newest_ctime_entry": newest_path,
                 "prefix_dir_ctime": iso(st.st_ctime), "prefix_dir_mode": oct(st.st_mode & 0o7777),
                 "binary_sha256": sha(NEWP / "ai-memory"),
                 "binary_mode": oct(os.stat(NEWP / "ai-memory").st_mode & 0o7777)}
vhome = Path(__file__).resolve().parent / "home-empty"
vhome.mkdir(mode=0o700, exist_ok=True)
env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": str(vhome), "TMPDIR": str(vhome),
       "AI_MEMORY_SERVER_URL": "http://127.0.0.1:9"}
v = subprocess.run([str(NEWP / "ai-memory"), "--version"], env=env, cwd=str(vhome), capture_output=True, text=True, timeout=30)
res["prefix"]["version_scratch_home_entries_after"] = len(list(vhome.iterdir()))
res["prefix"]["version_stdout"] = v.stdout.strip()
res["prefix"]["version_rc"] = v.returncode
res["baseline_2.3.2"] = {"binary_sha256": sha(OLD)}
cached = ECO / "downloads/ai-memory-linux-x86_64.tar.gz"
if cached.exists():
    res["baseline_2.3.2"]["cached_tarball_sha256"] = sha(cached)
    with tarfile.open(cached, "r:gz") as tar:
        for m in tar.getmembers():
            if os.path.normpath(m.name) == "ai-memory":
                res["baseline_2.3.2"]["cached_tarball_binary_sha256"] = hashlib.sha256(
                    tar.extractfile(m).read()).hexdigest()
out = json.dumps(res, indent=1)
(Path(__file__).resolve().parent / "integrity.json").write_text(out + "\n")
print(out)
