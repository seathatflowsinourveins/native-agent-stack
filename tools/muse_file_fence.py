#!/usr/bin/env python3
"""Run the native Muse lane argv inside a named-bind bubblewrap filesystem.

Reference: co-op rankedfeeds_fence.sh (2026-10-14); upstream flag semantics:
https://github.com/containers/bubblewrap/blob/v0.11.1/bwrap.xml
See docs/decisions/2026-10-14-muse-file-fence.md for the threat boundary.
No credential contents are opened by this launcher. The sign-in file is only
mounted read-only. Network remains shared; this is a file-access fence.
"""
import argparse
import collections
import contextlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import tempfile


MODEL = "muse-wonder-full-1.0"
VERSION = "1.4.9-R6297.1"
RUNTIME_SHA256 = 'a228010021276e112aa8422eb56ae82c0375405701950f6529bed4c9fe8abe05'
DEFAULT_RUNTIME = (Path.home() / '.local/share/native-agent-stack/muse-fence/runtimes'
                   / VERSION / 'muse-bin')
DEFAULT_LANE = Path.home() / ".local/state/native-agent-stack/coordination/command-center/cc-tools/muse_lane.sh"
SYSTEM_FILES = ("/etc/resolv.conf", "/etc/hosts", "/etc/nsswitch.conf",
                "/etc/passwd", "/etc/group", "/etc/localtime")
# Trusting a workspace must not reintroduce project hooks, MCP, or plugins.
PROJECT_MASKS = (".muse", ".mcp.json")
HOST_ARTIFACT_NAMES = ('probe-echo.jsonl', 'probe-echo.stderr.log', 'fence-probe.json',
                       'muse-exec.jsonl', 'muse-exec.stderr.log', 'receipt.json')
# Trusted policy, not supplied by a model or an arbitrary per-run allowlist.
# CC ruling-f1-meta-fence-dirbind-20261015.md:9-15; bubblewrap v0.11.1 bwrap.xml.
TOOLCHAIN_DIRECTORY_ALLOWLIST = frozenset({
    Path.home() / '.local/share/mise/installs/go/1.25.12',
})
# These reserved store roots are an additional metadata-only refusal policy,
# not a claim to recognize arbitrary secrets. Only the reviewed root above is
# admitted; changing that inventory requires another reviewed policy change.
TOOLCHAIN_STORE_NAMES = frozenset({
    '.ssh', '.aws', '.azure', '.gnupg', '.kube', '.codex', '.claude', '.hcom',
    '.config', '.local', '.cache', '.git', '.muse', '.mcp.json',
    'sessions', 'state', 'auth.json', 'credentials', 'credentials.json',
    '.netrc', '.npmrc', '.git-credentials',
})


class ToolchainDirectoryRefused(ValueError):
    """A requested directory is outside the reviewed toolchain policy."""


def require_toolchain_directory(path, home, private_files):
    # CC ruling-f1-meta-fence-dirbind-20261015.md:9-15. Inspect components
    # without resolving them; Codex rust-v0.162.1 bwrap.rs:1445-1485.
    if path not in TOOLCHAIN_DIRECTORY_ALLOWLIST or '..' in path.parts:
        raise ToolchainDirectoryRefused('toolchain directory refused')
    for component in (*reversed(path.parents), path):
        if component.is_symlink():
            raise ToolchainDirectoryRefused('toolchain directory refused')
    if not path.is_dir():
        raise ToolchainDirectoryRefused('toolchain directory refused')
    protected = [home / name for name in TOOLCHAIN_STORE_NAMES
                 if name not in {'.local'}]
    protected.append(home / '.local/state')
    if (path.name.casefold() in TOOLCHAIN_STORE_NAMES
            or any(part.casefold() in TOOLCHAIN_STORE_NAMES - {'.local'} for part in path.parts)
            or any(not disjoint(path, store) for store in (*protected, *private_files))):
        raise ToolchainDirectoryRefused('toolchain directory refused')
    # Metadata only; do not follow links or open contents. Refuse the whole
    # root on any unsupported entry rather than constructing a filtered tree.
    pending = [path]
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                if entry.name.casefold() in TOOLCHAIN_STORE_NAMES:
                    raise ToolchainDirectoryRefused('toolchain directory refused')
                mode = entry.stat(follow_symlinks=False).st_mode
                if stat.S_ISDIR(mode):
                    pending.append(Path(entry.path))
                elif not stat.S_ISREG(mode):
                    raise ToolchainDirectoryRefused('toolchain directory refused')


class UnsupportedGitWorktree(ValueError):
    """The sealed CC loop stop requires a private clone for every role."""


def require_own_clone(worktree):
    # adjudication-pr1120-5cfb8346-20261015.addendum-01.md items 1-3.
    git = worktree / '.git'
    if git.is_file() or git.is_symlink() or (git / 'commondir').exists() or (git / 'commondir').is_symlink():
        raise UnsupportedGitWorktree('linked Git worktrees refused; every role requires its own clone')


def checked_path(value, *, directory=False):
    path = Path(value).absolute()
    if any(ord(c) < 32 or ord(c) == 127 for c in str(path)):
        raise ValueError("control characters in paths are unsupported")
    if path != path.resolve():
        raise ValueError("symlink or noncanonical path refused")
    if not (path.is_dir() if directory else path.is_file()):
        raise ValueError("required directory/file is absent")
    return path


def sanitized_settings(source):
    """Copy only inert preferences, discarding executable/remote extensions.

    Both mcpServers and legacy mcp_servers, hooks, managed_* and plugins are
    deliberately absent. Unknown future extension keys do not survive.
    """
    doc = json.loads(source.read_text()) if source else {"schema_version": 1}
    if not isinstance(doc, dict) or doc.get("schema_version") != 1:
        raise ValueError("unsupported Muse settings schema")
    result = {"schema_version": 1, "contributor_mode_enabled": False}
    key = "contributor_mode_disclosure_acknowledged"
    if key in doc:
        if not isinstance(doc[key], bool):
            raise ValueError("invalid disclosure preference")
        result[key] = doc[key]
    return result


def verify_runtime_identity(runtime):
    """Check the vendor artifact before any runtime startup or credential bind.

    Identity pin: versioned Meta x86_linux manifest, 1.4.9-R6297.1.
    CPython 3.13 hashlib.file_digest and os.open supply the native interfaces.
    Concurrent hostile host mutation remains outside the fence's threat scope.
    """
    fd = os.open(runtime, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(fd, 'rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != RUNTIME_SHA256:
        raise ValueError('runtime sha256 mismatch')
    return digest


def clean_env(home, logdir):
    # No inherited XDG paths, MUSE_AUTH_PATH, transport tracing, API keys,
    # loader variables, proxies, fail-open controls, or user PATH entries.
    return {"HOME": str(home), "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8",
            "TERM": "dumb", "NO_COLOR": "1", "MUSE_LOGIN": "0",
            "MUSE_NO_AUTO_UPDATE": "1", "TMPDIR": str(logdir / "tmp"),
            "XDG_DATA_HOME": str(logdir / "data"),
            "XDG_STATE_HOME": str(logdir / "state"),
            "XDG_CACHE_HOME": str(logdir / "cache")}


def native_argv(lane, runtime, worktree, brief, logdir, role, steps):
    """Use the unchanged CC builder; never eval its shell-escaped dry-run."""
    require_own_clone(worktree)
    env = clean_env(Path.home(), logdir)
    env.update(MUSE_BIN=str(runtime), MUSE_LANE_MODEL=MODEL,
               MUSE_LANE_MAX_MODEL_STEPS=str(steps))
    plan = subprocess.run(["/bin/bash", str(lane), "--dry-run", "--role", role,
                           str(worktree), str(brief), str(logdir)], env=env,
                          capture_output=True, text=True, check=True)
    lines = [line[10:] for line in plan.stdout.splitlines() if line.startswith("argv     :")]
    if len(lines) != 1 or "$'" in lines[0]:
        raise ValueError("unsupported native argv rendering")
    argv = shlex.split(lines[0])
    expected = [str(runtime), "exec", "--json", "--prompt-file", str(brief),
                "--model", MODEL, "--reasoning-effort", "max", "--trust-workspace",
                "--workspace", str(worktree)]
    roles = {"reader": ["--approval-mode", "never", "--disable-write", "--disable-shell"],
             "reviewer": ["--permission-profile", ":read-only"],
             "builder": ["--approval-mode", "never"]}
    expected += roles[role] + ["--contributor-mode", "off", "--disable-web-tools",
                               "--max-model-steps", str(steps)]
    if argv != expected:
        raise ValueError("native argv changed; review the pinned contract before running")
    return argv


def disjoint(a, b):
    return a != b and a not in b.parents and b not in a.parents


@contextlib.contextmanager
def host_artifacts(logdir):
    """Establish host-owned descriptor custody before any fenced execution.

    CPython os.open(dir_fd=...) and fdopen retain the original file objects.
    Every artifact is exclusive, no-follow, close-on-exec, and additionally
    mounted read-only by Fence.command. Only intentional stdout/stderr handles
    are passed to the child. No artifact is reopened by pathname after a run.
    """
    with contextlib.ExitStack() as stack:
        directory = os.open(logdir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        stack.callback(os.close, directory)
        artifacts = {}
        for name in HOST_ARTIFACT_NAMES:
            fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o600, dir_fd=directory)
            artifacts[name] = stack.enter_context(os.fdopen(fd, 'w+', encoding='utf-8'))
        yield artifacts, directory


def write_json(stream, document):
    stream.seek(0)
    json.dump(document, stream, indent=2)
    stream.write('\n')
    stream.truncate()
    stream.flush()


def run_bounded_fence(argv, *, stdout, stderr, timeout):
    """Keep bwrap a direct child; its upstream parent-death handling applies.

    Python supplies the deadline without an intermediate watchdog process.
    See bubblewrap v0.11.1 bubblewrap.c:380-388 and CPython subprocess.Popen.
    """
    process = subprocess.Popen(argv, env={}, stdin=subprocess.DEVNULL,
                               stdout=stdout, stderr=stderr)
    try:
        try:
            rc = process.wait(timeout=timeout)
            return rc if rc >= 0 else 128 - rc
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            return 124
    except BaseException:
        process.kill()
        process.wait()
        raise


class Fence:
    def __init__(self, worktree, brief, logdir, runtime, auth, settings=None, inputs=(),
                 toolchain_dirs=()):
        self.home = Path.home().resolve()
        self.worktree = checked_path(worktree, directory=True)
        require_own_clone(self.worktree)
        self.brief = checked_path(brief)
        self.runtime = checked_path(runtime)
        # Metadata only: do not read/hash/copy auth, including in receipts.
        self.auth = checked_path(auth)
        self.settings = checked_path(settings) if settings else None
        self.inputs = [checked_path(p) for p in inputs]
        self.toolchain_dirs = list(dict.fromkeys(Path(p).absolute() for p in toolchain_dirs))
        self.logdir = Path(logdir).absolute()
        if self.logdir != self.logdir.resolve() or any(ord(c) < 32 for c in str(self.logdir)):
            raise ValueError("noncanonical log path")
        # Writable host trees must be dedicated /var/tmp children, never home,
        # the co-op, /etc, or an ancestor of read-only runtime/sign-in inputs.
        for p in (self.worktree, self.logdir):
            if Path('/var/tmp') not in p.parents or p == Path('/var/tmp'):
                raise ValueError("worktree and logs must be dedicated /var/tmp directories")
        if not disjoint(self.worktree, self.logdir):
            raise ValueError("worktree and log directory must be disjoint")
        for p in (self.runtime, self.auth):
            if not all(disjoint(p, rw) for rw in (self.worktree, self.logdir)):
                raise ValueError("read-only dependency overlaps writable tree")
        for p in (self.brief, *self.inputs):
            if not disjoint(p, self.logdir):
                raise ValueError("brief/inputs must be outside the log directory")
            if p == self.auth or p == self.settings:
                raise ValueError("credential/config cannot be a brief input")
            protected = ('.ssh', '.codex', '.claude', '.config', '.hcom', '.aws',
                         '.azure', '.gnupg', '.kube', '.local/state', '.local/share',
                         '.netrc', '.npmrc', '.git-credentials')
            if p == self.home or any(p == self.home / n or (self.home / n) in p.parents
                                     for n in protected):
                raise ValueError("protected home input refused")
            if any(x in p.parts for x in PROJECT_MASKS):
                raise ValueError("input would reopen project tool discovery")
        self.require_toolchain_policy()

    def require_toolchain_policy(self):
        for path in self.toolchain_dirs:
            require_toolchain_directory(path, self.home,
                                        [p for p in (self.auth, self.settings) if p])
            # Bidirectional source/target separation; bubblewrap v0.11.1
            # bwrap.xml:251-259; Codex rust-v0.162.1 bwrap.rs:411-425.
            if any(not disjoint(path, writable) for writable in
                   (self.worktree, self.logdir, Path('/tmp'), Path('/proc'), Path('/dev'))):
                raise ToolchainDirectoryRefused('toolchain directory refused')

    @contextlib.contextmanager
    def prepared(self):
        require_own_clone(self.worktree)
        self.require_toolchain_policy()
        # Host-only staging is outside every visible bind. No auth copy.
        with host_artifacts(self.logdir) as (self.artifacts, self.artifact_dirfd), \
                tempfile.TemporaryDirectory(prefix="muse-fence-control-", dir="/var/tmp") as tmp:
            stage = Path(tmp)
            home = stage / 'home'
            (home / '.config/muse').mkdir(parents=True)
            config = home / '.config/muse/settings.json'
            config.write_text(json.dumps(sanitized_settings(self.settings)) + '\n')
            config.chmod(0o400)
            (home / '.config/muse/auth.json').touch(mode=0o400)
            for path in self.toolchain_dirs:
                if self.home in path.parents:
                    (home / path.relative_to(self.home)).mkdir(parents=True, exist_ok=True)
            for path in (self.runtime, self.brief, *self.inputs):
                if self.home in path.parents:
                    target = home / path.relative_to(self.home)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.touch(mode=0o400)
            empty = stage / 'empty'
            empty.mkdir()
            blank = stage / 'blank'
            blank.write_text('{}\n')
            yield self.command(stage, home, empty, blank)

    def command(self, stage, home, empty, blank):
        self.require_toolchain_policy()
        # Empty root, rather than exposing host / and subtracting known secrets.
        args = ["bwrap", "--unshare-pid", "--unshare-ipc", "--unshare-uts",
                "--die-with-parent", "--new-session", "--cap-drop", "ALL",
                "--clearenv", "--ro-bind", "/usr", "/usr"]
        for name in ('bin', 'sbin', 'lib', 'lib64'):
            target = Path('/') / name
            if target.exists():
                if target.is_symlink():
                    args += ['--symlink', os.readlink(target), str(target)]
                else:
                    args += ['--ro-bind', str(target), str(target)]
        for name in SYSTEM_FILES:
            if Path(name).exists():
                args += ['--ro-bind', name, name]
        args += ['--ro-bind', '/etc/ssl/certs', '/etc/ssl/certs',
                 '--proc', '/proc', '--dev', '/dev',
                 '--ro-bind', str(home), str(self.home),
                 '--ro-bind', str(self.runtime), str(self.runtime),
                 '--ro-bind', str(self.auth), str(self.home / '.config/muse/auth.json'),
                 '--bind', str(self.worktree), str(self.worktree),
                 '--bind', str(self.logdir), str(self.logdir),
                 # A real mount accepts nested read-only /tmp input overlays.
                 # Bind it before those overlays; a later symlink collides.
                 '--bind', str(self.logdir / 'tmp'), '/tmp']
        for path in dict.fromkeys([self.brief, *self.inputs]):
            args += ['--ro-bind', str(path), str(path)]
        for path in self.toolchain_dirs:
            args += ['--ro-bind', str(path), str(path)]
        for name in PROJECT_MASKS:
            path = self.worktree / name
            # Mountpoints cannot follow a workspace symlink outside its tree.
            if path.is_symlink():
                raise ValueError("symlink project configuration refused")
            args += ['--ro-bind', str(empty if name == '.muse' else blank), str(path)]
        # openai/codex rust-v0.162.1 permissions.rs:2347-2367 protects Git
        # administrative paths under writable roots. Missing metadata is also
        # sealed so this fence cannot introduce a new administrative tree.
        git = self.worktree / '.git'
        if git.is_symlink():
            raise ValueError('symlink Git metadata refused')
        args += ['--ro-bind', str(git if git.exists() else empty), str(git)]
        for name in HOST_ARTIFACT_NAMES:
            artifact = self.logdir / name
            args += ['--ro-bind', str(artifact), str(artifact)]
        for key, value in clean_env(self.home, self.logdir).items():
            args += ['--setenv', key, value]
        # bwrap's initial tmpfs root is writable unless explicitly sealed.
        # Per bwrap.xml, this leaves nested work/log bind mounts writable.
        return args + ['--remount-ro', '/', '--chdir', str(self.worktree), '--']


def event_receipt(stream, rc):
    counts = collections.Counter()
    models = set()
    terminals = collections.Counter()
    invalid = 0
    stream.seek(0)
    for line in stream:
        try:
            event = json.loads(line)
        except ValueError:
            invalid += 1
            continue
        kind = event.get('payload_type', '<unknown>')
        counts[kind] += 1
        payload = event.get('payload') or {}
        if kind == 'run.model.configured':
            models.add(payload.get('model_id', '<unknown>'))
        if kind.startswith('run.terminal.'):
            terminals[kind] += 1
    return {'exit_code': rc, 'event_count': sum(counts.values()),
            'event_counts': dict(counts), 'invalid_lines': invalid,
            'models': sorted(models), 'terminal_counts': dict(terminals)}


def probe(fence, command, argv):
    """Model-free positive control, named OS masks and native echo startup.

    The caller must run this successfully before the first live invocation.
    Neither the payload nor receipt reads auth contents.
    """
    with tempfile.TemporaryDirectory(prefix='muse-outside-canary-', dir='/var/tmp') as tmp:
        canary = Path(tmp) / 'planted-public-file'
        canary.write_text('public fence positive control\n')
        read = 'from pathlib import Path; Path(' + repr(str(canary)) + ').read_bytes()'
        before = subprocess.run(['/usr/bin/python3', '-I', '-c', read],
                                capture_output=True, timeout=20)
        after = subprocess.run(command + ['/usr/bin/python3', '-I', '-c', read],
                               env={}, capture_output=True, timeout=20)
        facts = {'unfenced-canary-readable': before.returncode == 0,
                 'fenced-canary-denied': after.returncode != 0 and b'FileNotFoundError' in after.stderr}
    masks = {name: str(fence.home / name) for name in (
        '.ssh', '.codex', '.claude', '.hcom', '.local/state',
        '.local/state/native-agent-stack/coordination/ns2604-coop',
        '.local/state/native-agent-stack/coordination/command-center')}
    masks.update({'host-runtime': '/run/user', 'host-mounts': '/mnt'})
    script = f'''
import json, os, tempfile
from pathlib import Path
facts = {{name + '-masked': not Path(p).exists() for name, p in {masks!r}.items()}}
for name in ['code', 'projects']:
    root = Path({str(fence.home)!r}) / name
    expected = {{Path(p) for p in {[str(p) for p in (fence.brief, *fence.inputs)]!r} if root in Path(p).parents}}
    found = {{p for p in root.rglob('*') if not p.is_dir()}} if root.exists() else set()
    facts[name + '-other-files-masked'] = found == expected
for name, p in {{'worktree': {str(fence.worktree)!r}, 'logdir': {str(fence.logdir)!r}}}.items():
    # CPython NamedTemporaryFile uses exclusive creation with a random name;
    # the context removes only this probe's file, preserving existing entries.
    with tempfile.NamedTemporaryFile(mode='w+', dir=p, prefix='.muse-fence-probe-') as marker:
        marker.write('public'); marker.flush(); marker.seek(0)
        facts[name + '-rw'] = marker.read() == 'public'
for name, p in {{'brief': {str(fence.brief)!r}, 'runtime': {str(fence.runtime)!r},
                 'settings': {str(fence.home/'.config/muse/settings.json')!r},
                 'sign-in': {str(fence.home/'.config/muse/auth.json')!r}}}.items():
    facts[name + '-ro'] = Path(p).is_file() and not os.access(p, os.W_OK)
for p in {[str(p) for p in fence.toolchain_dirs]!r}:
    try:
        with tempfile.NamedTemporaryFile(dir=p, prefix='.muse-toolchain-ro-probe-'):
            facts['toolchain-ro:' + p] = False
    except OSError as exc:
        import errno
        facts['toolchain-ro:' + p] = Path(p).is_dir() and exc.errno in (errno.EROFS, errno.EACCES)
facts['project-hooks-masked'] = not list(Path({str(fence.worktree/'.muse')!r}).iterdir())
facts['project-config-ro'] = not os.access({str(fence.worktree/'.muse')!r}, os.W_OK)
facts['git-metadata-ro'] = not os.access({str(fence.worktree/'.git')!r}, os.W_OK)
for name in {HOST_ARTIFACT_NAMES!r}:
    facts['host-artifact-ro-' + name] = not os.access(Path({str(fence.logdir)!r}) / name, os.W_OK)
cfg = json.loads(Path({str(fence.home/'.config/muse/settings.json')!r}).read_text())
facts['mcp-hooks-plugins-removed'] = set(cfg) <= {{'schema_version', 'contributor_mode_enabled', 'contributor_mode_disclosure_acknowledged'}}
for p in ['/', '/etc', {str(fence.home)!r}]:
    try:
        with tempfile.NamedTemporaryFile(dir=p, prefix='.muse-fence-probe-'):
            facts[p + '-readonly'] = False
    except OSError:
        facts[p + '-readonly'] = True
print(json.dumps(facts))
'''
    check = subprocess.run(command + ['/usr/bin/python3', '-I', '-c', script],
                           env={}, capture_output=True, text=True, timeout=30, check=True)
    facts.update(json.loads(check.stdout))
    if not all(facts.values()):
        raise ValueError('model-free filesystem probe failed')
    # Echo provider is the installed upstream's offline execution path. It
    # exercises startup/config/hooks/MCP discovery with no Meta model request.
    echo_argv = list(argv)
    # The upstream echo provider refuses a Meta model selection. This change
    # applies to the offline startup probe only; live argv stays byte-for-byte.
    for flag in ('--model', '--reasoning-effort'):
        index = echo_argv.index(flag)
        del echo_argv[index:index + 2]
    echo = subprocess.run(command + echo_argv + ['--provider', 'echo', '--disable-reminders'],
                          env={}, stdin=subprocess.DEVNULL, stdout=fence.artifacts['probe-echo.jsonl'],
                          stderr=fence.artifacts['probe-echo.stderr.log'], timeout=45)
    echo_receipt = event_receipt(fence.artifacts['probe-echo.jsonl'], echo.returncode)
    facts['native-echo-exit-zero'] = echo.returncode == 0
    facts['native-echo-terminal'] = echo_receipt['terminal_counts'].get('run.terminal.completed', 0) == 1
    for name in ('mcp-fired', 'user-hook-fired', 'project-hook-fired', 'managed-hook-fired'):
        try:
            os.stat(name, dir_fd=fence.artifact_dirfd, follow_symlinks=False)
        except FileNotFoundError:
            facts[name + '-absent'] = True
        else:
            facts[name + '-absent'] = False
    result = {'schema': 'muse-file-fence-probe/1', 'checks': facts,
              'pass': all(facts.values()), 'echo': echo_receipt}
    write_json(fence.artifacts['fence-probe.json'], result)
    if not result['pass']:
        raise ValueError('native model-free probe failed')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lane', type=Path, default=DEFAULT_LANE)
    parser.add_argument('--runtime', type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument('--auth', type=Path, default=Path.home() / '.config/muse/auth.json')
    parser.add_argument('--settings', type=Path,
                        help='explicit settings file (must exist); absent default uses inert defaults')
    parser.add_argument('--input', action='append', default=[], type=Path)
    parser.add_argument('--toolchain-dir', action='append', default=[], type=Path,
                        help='named read-only directory from the reviewed toolchain allowlist')
    parser.add_argument('--role', choices=['reader', 'reviewer', 'builder'], default='reader')
    parser.add_argument('--max-model-steps', type=int, default=2)
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--probe-only', action='store_true', help='OS and native echo only; no model call')
    parser.add_argument('worktree', type=Path)
    parser.add_argument('brief', type=Path)
    parser.add_argument('logdir', type=Path)
    options = parser.parse_args()
    if options.max_model_steps < 1 or options.timeout < 1:
        parser.error('positive bounds required')
    settings = options.settings
    if settings is None:
        default_settings = Path.home() / '.config/muse/settings.json'
        # Muse supports no user settings file. Explicit paths, existing
        # non-files and symlinks still pass through strict checked_path().
        if default_settings.exists() or default_settings.is_symlink():
            settings = default_settings
    fence = Fence(options.worktree, options.brief, options.logdir, options.runtime,
                  options.auth, settings, options.input, options.toolchain_dir)
    runtime_sha256 = verify_runtime_identity(fence.runtime)
    lane = checked_path(options.lane)
    lane_sha256 = hashlib.sha256(lane.read_bytes()).hexdigest()
    argv = native_argv(lane, fence.runtime, fence.worktree, fence.brief,
                       fence.logdir, options.role, options.max_model_steps)
    fence.logdir.mkdir(mode=0o700)  # exclusive fresh log dir; never overwrite a run
    for name in ('tmp', 'data', 'state', 'cache'):
        (fence.logdir / name).mkdir(mode=0o700)
    start = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with fence.prepared() as command:
        version = subprocess.run(command + [str(fence.runtime), '--version'],
                                 env={}, capture_output=True, text=True, timeout=20, check=True)
        if f'({VERSION})' not in version.stdout:
            raise ValueError('runtime pin mismatch')
        probe(fence, command, argv)
        if options.probe_only:
            print('muse-file-fence: model-free probe PASS')
            return 0
        rc = run_bounded_fence(command + argv, stdout=fence.artifacts['muse-exec.jsonl'],
                               stderr=fence.artifacts['muse-exec.stderr.log'], timeout=options.timeout)
        receipt = event_receipt(fence.artifacts['muse-exec.jsonl'], rc)
        receipt.update(schema='muse-file-fence/1', role=options.role, requested_model=MODEL,
                       runtime_version=version.stdout.strip(), started_utc=start,
                       finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                       network='shared host network; no egress allowlist',
                       argv=argv, lane_sha256=lane_sha256, runtime_sha256=runtime_sha256)
        receipt['toolchain_directories'] = [str(p) for p in fence.toolchain_dirs]
        write_json(fence.artifacts['receipt.json'], receipt)
    print(json.dumps({k: receipt[k] for k in ('exit_code', 'event_count', 'models', 'terminal_counts')}))
    return rc


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except UnsupportedGitWorktree:
        print('muse-file-fence: linked Git worktrees refused; every role requires its own clone',
              file=__import__('sys').stderr)
        raise SystemExit(1)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        # Do not serialize environment/config/payloads from exceptions.
        print('muse-file-fence: refused (' + type(exc).__name__ + ')', file=__import__('sys').stderr)
        raise SystemExit(1)
