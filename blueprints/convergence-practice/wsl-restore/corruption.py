"""Deliberately corrupt one pack in a newly created copy, preserving its source."""
from pathlib import Path
import shutil
import stat


def corrupt_repository_copy(source: Path, target: Path) -> dict:
    source=source.absolute(); target=target.absolute()
    if (source.resolve()!=source or target.resolve()!=target or target.exists()
            or source==target or source in target.parents or target in source.parents):
        raise ValueError('corruption requires a new disjoint canonical copy target')
    if any(p.is_symlink() for p in source.rglob('*')):
        raise ValueError('synthetic repository copy cannot contain symlinks')
    shutil.copytree(source,target,copy_function=shutil.copy2)
    packs=sorted(p for p in (target/'data').rglob('*') if p.is_file())
    if not packs: raise ValueError('synthetic repository has no pack')
    selected=packs[0]
    raw=bytearray(selected.read_bytes())
    if not raw:raise ValueError('synthetic pack is empty')
    selected.chmod(stat.S_IMODE(selected.stat().st_mode)|stat.S_IWUSR)
    raw[len(raw)//2]^=1
    selected.write_bytes(raw)
    return {'copied_pack_relative_path':selected.relative_to(target).as_posix(),
            'bytes':len(raw),'change':'One byte XOR 1 at floor(size/2), on isolated copied repository only; copied pack owner-write bit enabled.'}
