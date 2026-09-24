"""Test package setup.

Tests never read the developer's global or system git configuration. CI runners have
none, so local runs must match: a host that installs a global ``core.hooksPath`` (for
example a gitleaks pre-commit hook), aliases or identity must not change what scratch
repositories created by the tests do. ``GIT_CONFIG_GLOBAL`` replaces both
``~/.gitconfig`` and ``$XDG_CONFIG_HOME/git/config``; ``GIT_CONFIG_NOSYSTEM`` skips the
system file (including Apple Git's bundled one). See native-agent-stack issue #179.
"""

import atexit
import os
import shutil
import tempfile

_HERMETIC_GIT_DIR = tempfile.mkdtemp(prefix="nas-tests-git-")
atexit.register(shutil.rmtree, _HERMETIC_GIT_DIR, True)
HERMETIC_GIT_CONFIG = os.path.join(_HERMETIC_GIT_DIR, "gitconfig")
with open(HERMETIC_GIT_CONFIG, "w", encoding="utf-8"):
    pass
os.environ["GIT_CONFIG_GLOBAL"] = HERMETIC_GIT_CONFIG
os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
