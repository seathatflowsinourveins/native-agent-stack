"""Test package setup.

Tests never read the developer's global or system git configuration. CI runners have
none, so local runs must match: a host that installs a global ``core.hooksPath`` (for
example a gitleaks pre-commit hook), ignore rules, aliases or identity must not change
what scratch repositories created by the tests do. ``GIT_CONFIG_GLOBAL`` replaces both
``~/.gitconfig`` and ``$XDG_CONFIG_HOME/git/config``; ``GIT_CONFIG_NOSYSTEM`` skips the
system file (including Apple Git's bundled one). See native-agent-stack issue #179.

Git still reads ``$XDG_CONFIG_HOME/git/ignore`` and ``git/attributes`` (under
``~/.config`` when unset) as the defaults of ``core.excludesFile`` and
``core.attributesFile``, so the replacement file sets both to ``/dev/null``. A helper
that drops inherited ``GIT_*`` variables, so that a hook's ``GIT_DIR`` or
``GIT_INDEX_FILE`` cannot select another repository, builds its environment with
``hermetic_git_environment()``, which keeps this isolation.

The file also sets ``maintenance.auto = false``. Otherwise ``git commit`` and other
writing commands start ``git maintenance run --auto`` after their work, and since Git
2.47 that process detaches by default (``maintenance.autoDetach``). In a scratch
repository it can still be taking ``.git/objects/maintenance.lock`` while the test's
``TemporaryDirectory`` cleanup runs, which then fails with ``OSError: [Errno 39]
Directory not empty: 'objects'``. CI's git 2.55.0 hit this in ``test_host_receipts``.

Importing the package also removes every inherited ``GIT_*`` variable before it sets its
own. When the suite runs from a git hook, or from any shell that exports ``GIT_DIR``,
``GIT_WORK_TREE`` or ``GIT_INDEX_FILE``, a scratch repository's ``git init``, ``git
config`` or ``git commit`` would otherwise act on the repository those variables name.
``test_pre_commit_gate``, for example, would write its absolute ``core.hooksPath`` into
that repository's shared config.
"""

import atexit
import os
import shutil
import tempfile

_HERMETIC_GIT_DIR = tempfile.mkdtemp(prefix="nas-tests-git-")
atexit.register(shutil.rmtree, _HERMETIC_GIT_DIR, True)
HERMETIC_GIT_CONFIG = os.path.join(_HERMETIC_GIT_DIR, "gitconfig")
HERMETIC_GIT_SETTINGS = ("[core]\n\texcludesFile = /dev/null\n\tattributesFile = /dev/null\n"
                         "[maintenance]\n\tauto = false\n")
with open(HERMETIC_GIT_CONFIG, "w", encoding="utf-8") as config:
    config.write(HERMETIC_GIT_SETTINGS)
HERMETIC_GIT_ENVIRONMENT = {"GIT_CONFIG_GLOBAL": HERMETIC_GIT_CONFIG, "GIT_CONFIG_NOSYSTEM": "1"}
for _inherited in [key for key in os.environ if key.startswith("GIT_")]:
    del os.environ[_inherited]
os.environ.update(HERMETIC_GIT_ENVIRONMENT)


def hermetic_git_environment():
    """``os.environ`` without inherited ``GIT_*`` variables, keeping the hermetic configuration."""
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    return {**environment, **HERMETIC_GIT_ENVIRONMENT}
