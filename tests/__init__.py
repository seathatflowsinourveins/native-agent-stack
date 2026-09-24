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
"""

import atexit
import os
import shutil
import tempfile

_HERMETIC_GIT_DIR = tempfile.mkdtemp(prefix="nas-tests-git-")
atexit.register(shutil.rmtree, _HERMETIC_GIT_DIR, True)
HERMETIC_GIT_CONFIG = os.path.join(_HERMETIC_GIT_DIR, "gitconfig")
HERMETIC_GIT_SETTINGS = "[core]\n\texcludesFile = /dev/null\n\tattributesFile = /dev/null\n"
with open(HERMETIC_GIT_CONFIG, "w", encoding="utf-8") as config:
    config.write(HERMETIC_GIT_SETTINGS)
HERMETIC_GIT_ENVIRONMENT = {"GIT_CONFIG_GLOBAL": HERMETIC_GIT_CONFIG, "GIT_CONFIG_NOSYSTEM": "1"}
os.environ.update(HERMETIC_GIT_ENVIRONMENT)


def hermetic_git_environment():
    """``os.environ`` without inherited ``GIT_*`` variables, keeping the hermetic configuration."""
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    return {**environment, **HERMETIC_GIT_ENVIRONMENT}
