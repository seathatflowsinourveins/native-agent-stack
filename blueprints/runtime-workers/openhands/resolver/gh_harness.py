"""gh harness for the OpenHands resolver: resolver plan section 3.

Every GitHub read and write the driver makes goes through GhHarness.run, which
checks the argv against a denylist and then against fixed templates before any
subprocess starts. Children get an environment built from an allowlist, run from
an empty 0700 directory, and never see a token: the driver never calls `gh auth
token`, and a push takes its credential only through git's helper pipe. A push names
an exact commit, and runs only after the trusted pre-push gate (resolver/push_gate.py)
passed that commit in this harness.

Upstream behaviour this follows, read at cli/cli@0cf10924 (gh v2.101.0):
- pkg/cmd/root/help_topic.go:45-58: GH_TOKEN, GITHUB_TOKEN and the enterprise
  pair override stored credentials, and GH_REPO names the repository for commands
  that otherwise read a local one; :105-109 GH_CONFIG_DIR moves the store; :71,
  :94, :111 and :124-125 GH_PAGER, GH_NO_UPDATE_NOTIFIER, GH_PROMPT_DISABLED and
  GH_TELEMETRY.
- pkg/cmd/auth/status/status.go:147-149 (--json always exits 0, so gate on the
  parsed state), :284-295 (without --show-token the JSON drops the token),
  :376-381 (a stored-config token reports the hosts file path), :426-428 (a
  source ending in _TOKEN is an environment variable); internal/config/config.go
  :257-280 ("keyring" source).
- pkg/cmd/auth/gitcredential/helper.go:58-144: get only, https only, answering
  with the active token for the requested host.
- internal/gitcredentials/helper_config.go:36-56: gh's own setup writes an empty
  helper value to sever the chain, then `!<gh> auth git-credential` for the host.
- pkg/cmd/api/api.go:329-331: fields or --input without --method make a POST.
- pkg/cmd/pr/create/create.go:283-287, 833-866 and 1085-1096: with --head and
  GH_REPO, pr create neither pushes nor needs a local repository.
- pkg/cmd/version/version.go:27-36: the `gh --version` first line.
git: gitcredentials(7) (an empty helper value resets the list; with prompting off
and no askpass, git fails when no helper answers), git(1) GIT_CEILING_DIRECTORIES,
git-remote(1) get-url --push --all, and parse-options' unique-prefix long options.
The templates, denylist and preflight are local compositions of those mechanisms.
"""
from __future__ import annotations

import json
import os
import posixpath
import pwd
import re
import stat
import subprocess
import sys
import tempfile

REPO = "seathatflowsinourveins/native-agent-stack"
OWNER, REPO_NAME = REPO.split("/", 1)
HOST = "github.com"
ORIGIN_URL = f"https://{HOST}/{REPO}.git"
API = f"repos/{REPO}"
GH_VERSION = "2.101.0"
LANE_LABELS = ("lane:foundation", "lane:trading", "lane:shared")  # docs/lanes.md:145-151
PR_VIEW_FIELDS = ("number,url,isDraft,state,baseRefName,headRefName,headRefOid,labels,body,"
                  "autoMergeRequest,mergedAt")
CHECK_FIELDS = "name,state,bucket,link,workflow"
HELPER_KEY = f"credential.https://{HOST}.helper"
MAX_TITLE = 250  # EXT main.py:1093-1100 cuts the title at 250 characters

NUMBER = r"[1-9][0-9]{0,8}"
BRANCH = rf"openhands/issue-(?P<branch_number>{NUMBER})(?:-(?:[2-9]|1[01]))?"  # EXT main.py:449-463
SHA = r"[0-9a-f]{40}"
ABSOLUTE = r"/[^\x00-\x1f\x7f]*"
SAFE_EXECUTABLE = re.compile(r"/[A-Za-z0-9._+/-]+")
CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class HarnessRefused(Exception):
    """A refused operation or failed precondition. `reason` is a stable code.

    The message is the code alone: never argv values, output or environment values.
    """

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _absolute(value):
    return isinstance(value, str) and value.startswith("/") and not CONTROL.search(value)


def _executable(path, reason):
    """An absolute executable path without shell metacharacters.

    The path goes into `!<path> auth git-credential`, which git runs through the
    shell; gh's own shellQuote (helper_config.go:119-124) would be needed for spaces,
    `$` or backslashes, so such paths are refused rather than quoted.
    """
    if not (isinstance(path, str) and SAFE_EXECUTABLE.fullmatch(path)
            and os.path.isfile(path) and os.access(path, os.X_OK)):
        raise HarnessRefused(reason)
    return path


def child_env(base, *, gh_path, workdir):
    """Plan section 3's child environment, built from an allowlist (never inherited).

    Only HOME and XDG_CONFIG_HOME are taken from `base`; the caller injects the
    mapping, so this module reads no environment itself. HOME falls back to the
    password database. GIT_CEILING_DIRECTORIES (git(1)) stops repository discovery
    above the empty working directory, so gh and git find no local repository.
    """
    home = base.get("HOME") or pwd.getpwuid(os.getuid()).pw_dir
    xdg = base.get("XDG_CONFIG_HOME")
    for value in (home, xdg, workdir):
        if value is not None and not _absolute(value):
            raise HarnessRefused("unsafe_environment_path")
    if not (isinstance(gh_path, str) and SAFE_EXECUTABLE.fullmatch(gh_path)):
        raise HarnessRefused("unsafe_gh_path")
    env = {
        "PATH": f"{posixpath.dirname(gh_path)}:/usr/bin:/bin",
        "HOME": home,
        "LANG": "C.UTF-8",
        "GH_HOST": HOST,
        "GH_REPO": REPO,
        "GH_PROMPT_DISABLED": "1",
        "GH_NO_UPDATE_NOTIFIER": "1",
        "GH_TELEMETRY": "false",
        "GH_PAGER": "cat",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CEILING_DIRECTORIES": posixpath.dirname(workdir),
    }
    if xdg:
        env["XDG_CONFIG_HOME"] = xdg
    return env


def check_workdir(path):
    """Plan section 3: gh runs from an empty 0700 directory owned by this user.

    The path must also be canonical, so no symlink component can redirect it.
    """
    if not _absolute(path) or os.path.realpath(path) != path:
        raise HarnessRefused("unsafe_workdir")
    try:
        info = os.lstat(path)
        entries = os.listdir(path)
    except OSError:
        raise HarnessRefused("unsafe_workdir") from None
    if (not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700
            or info.st_uid != os.geteuid() or entries):
        raise HarnessRefused("unsafe_workdir")
    return path


def private_workdir(parent):
    """A new empty working directory; tempfile.mkdtemp creates it with mode 0700."""
    return check_workdir(os.path.realpath(tempfile.mkdtemp(prefix="gh-cwd-", dir=parent)))


# -- Operation builders: the fixed argv templates of plan section 3 ("gh" and "git"
# stand for the pinned absolute executables that GhHarness.run substitutes).

def op_version():
    return ["gh", "--version"]


def op_auth_status():
    return ["gh", "auth", "status", "--active", "--hostname", HOST, "--json", "hosts"]


def op_issue(number):
    return ["gh", "api", f"{API}/issues/{number}"]


def op_issue_comments(number):
    return ["gh", "api", "--paginate", f"{API}/issues/{number}/comments"]


# The one GraphQL operation: a read-only query for the edit provenance of the issue and its
# comments, with the content read in the same snapshot as its history (review item D2).
# REST issues and comments carry no editor, and neither do gh's issue JSON fields
# (api/query_builder.go:42-60 and 314-351 at 0cf10924). Fields, from the public schema (docs.github.com/public/fpt/schema.docs.graphql, fetched
# 2026-09-28): Issue fullDatabaseId, author, editor, lastEditedAt, userContentEdits,
# timelineItems(itemTypes:) and comments; IssueComment the same content fields;
# UserContentEdit editor, deletedAt and deletedBy; RenamedTitleEvent actor. gh sends -f
# `query` top-level and every other field as a variable (pkg/cmd/api/http.go:95-112), and -F
# types an integer (api.go:112-122); api.go:178 is the upstream example of this shape.
PROVENANCE_ACTOR = "{ __typename login }"
PROVENANCE_EDITS = ("userContentEdits(first: 100) { totalCount pageInfo { hasNextPage } nodes { editor "
                    f"{PROVENANCE_ACTOR} deletedAt deletedBy {PROVENANCE_ACTOR} }} }}")
PROVENANCE_CONTENT = (f"fullDatabaseId body authorAssociation author {PROVENANCE_ACTOR} editor {PROVENANCE_ACTOR} "
                      f"lastEditedAt {PROVENANCE_EDITS}")
ISSUE_PROVENANCE_QUERY = (
    "query($owner: String!, $name: String!, $number: Int!) { repository(owner: $owner, name: $name) { "
    f"issue(number: $number) {{ number state title {PROVENANCE_CONTENT} "
    "titleRenames: timelineItems(itemTypes: [RENAMED_TITLE_EVENT], first: 100) { pageInfo { hasNextPage } "
    f"nodes {{ ... on RenamedTitleEvent {{ actor {PROVENANCE_ACTOR} }} }} }} "
    f"comments(first: 100) {{ totalCount pageInfo {{ hasNextPage }} nodes {{ {PROVENANCE_CONTENT} }} }} }} }} }}")


def op_issue_provenance(number):
    return ["gh", "api", "graphql", "-f", f"query={ISSUE_PROVENANCE_QUERY}", "-F", f"owner={OWNER}",
            "-F", f"name={REPO_NAME}", "-F", f"number={number}"]


def op_repository():
    """GET the repository, for the preflight's identity check (plan section 3, stage 2)."""
    return ["gh", "api", API]


def op_base():
    """One anonymous `git ls-remote <origin> refs/heads/main`: the pinned base (plan section 2 step 2).

    git-ls-remote(1): the output is "<oid> TAB <ref>" for every ref that matches the
    pattern; parse_base accepts exactly the one line for main.
    """
    return ["git", "ls-remote", ORIGIN_URL, "refs/heads/main"]


def op_branch_rules(branch):
    return ["gh", "api", f"{API}/rules/branches/{branch}"]


def op_base_rules():
    """GET every page of main's active rules, for its required status checks (review item D3).

    GitHub's "Get rules for a branch" (docs.github.com/en/rest/repos/rules, read
    2026-09-28) returns every active rule, 30 to a page by default, so --paginate reads
    them all. main has no classic branch protection (GET .../branches/main/protection
    answered 404 "Branch not protected" on 2026-09-28), so no protection read is allowed.
    """
    return ["gh", "api", "--paginate", f"{API}/rules/branches/main"]


def op_compare(base, head):
    """GET compare, whose status must read "ahead" for a fast-forward repair (plan A5)."""
    return ["gh", "api", f"{API}/compare/{base}...{head}"]


def op_ls_remote(number):
    return ["git", "ls-remote", "--heads", ORIGIN_URL, f"openhands/issue-{number}*"]


def op_push_urls(clone):
    """git-remote(1) get-url --push --all: the URLs a push to origin would use, after
    pushurl and insteadOf rewriting, so the check covers what the push does."""
    return ["git", "-C", clone, "remote", "get-url", "--push", "--all", "origin"]


def op_push(clone, branch, commit, *, gh):
    """Plan section 3's push: one refspec, the token only on git's helper pipe.

    The empty values reset every inherited helper (gitcredentials(7)); the last value
    is the helper gh itself installs (helper_config.go:36-56), scoped to github.com.
    The source is the exact commit the trusted pre-push gate passed (git-push(1): a
    <src> may be any commit name when <dst> is a full ref), never HEAD.
    """
    return ["git", "-C", clone,
            "-c", "credential.helper=",
            "-c", f"{HELPER_KEY}=",
            "-c", f"{HELPER_KEY}=!{gh} auth git-credential",
            "-c", "core.hooksPath=/dev/null",
            "-c", "push.followTags=false",
            "-c", "remote.origin.mirror=false",
            "push", "--no-verify", "origin", f"{commit}:refs/heads/{branch}"]


def op_pr_create(branch, title, body_file, label):
    return ["gh", "pr", "create", "--draft", "--base", "main", "--head", branch, "--title", title,
            "--body-file", body_file, "--label", label]


def op_pr_view(number):
    return ["gh", "pr", "view", str(number), "--json", PR_VIEW_FIELDS]


def op_pr_checks(number):
    return ["gh", "pr", "checks", str(number), "--required", "--json", CHECK_FIELDS]


def op_run_log(run_id):
    return ["gh", "run", "view", str(run_id), "--log-failed"]


# No `gh pr diff` template: it fetches the PR's current diff by number (diff.go:127-137 and
# 212-236 at 0cf10924), so the loop reads the reviewed diff from the host clone (review item D4).

def op_review(number, commit_id, body_file):
    """One COMMENT review; a COMMENT review requires a body (plan A11)."""
    return ["gh", "api", "--method", "POST", f"{API}/pulls/{number}/reviews", "-f", "event=COMMENT",
            "-f", f"commit_id={commit_id}", "-F", f"body=@{body_file}"]


def op_pr_comment(number, body_file):
    return ["gh", "pr", "comment", str(number), "--body-file", body_file]


# -- Denylist: named refusals checked first, so each has its own reason code.

GH_PR_CHANGES = {"close", "reopen", "edit", "lock", "unlock", "revert", "update-branch"}
GH_AUTH_CHANGES = {"refresh", "login", "logout", "setup-git", "git-credential", "switch"}
GH_DENIED_GROUPS = {"release": "release_denied", "workflow": "workflow_denied", "secret": "secret_denied",
                    "variable": "secret_denied", "ruleset": "ruleset_denied"}
API_VALUE_FLAGS = {"-X", "--method", "-f", "--raw-field", "-F", "--field", "-H", "--header", "--input",
                   "-q", "--jq", "-t", "--template", "--hostname", "--cache", "-p", "--preview"}
API_BODY_FLAGS = {"-f", "--raw-field", "-F", "--field", "--input"}
MERGE_PATH = re.compile(r"(?:^|/)merge(?:s|-upstream)?(?:/|$)")
REF_PATH = re.compile(r"(?:^|/)git/refs(?:/|$)")
REVIEWS_PATH = re.compile(rf"{re.escape(API)}/pulls/{NUMBER}/reviews")
PUSH_DENIED = {"--force": "force_push_denied", "--force-with-lease": "force_push_denied",
               "--force-if-includes": "force_push_denied", "--delete": "delete_push_denied",
               "--tags": "tag_push_denied", "--follow-tags": "tag_push_denied",
               "--mirror": "mirror_push_denied", "--all": "all_push_denied", "--branches": "all_push_denied",
               "--prune": "prune_push_denied"}
FALSE_VALUES = {"false", "no", "off", "0", ""}


def _api_request(words):
    """The method and endpoints a `gh api` argv would use (api.go:329-331 default)."""
    method, endpoints, has_body, index = None, [], False, 0
    while index < len(words):
        word = words[index]
        name, attached = word, None
        if word.startswith("--") and "=" in word:
            name, attached = word.split("=", 1)
        elif word.startswith("-") and not word.startswith("--") and len(word) > 2:
            name, attached = word[:2], word[2:].removeprefix("=")  # pflag's -XDELETE and -X=DELETE
        if name in API_VALUE_FLAGS:
            if attached is None:
                index += 1
                attached = words[index] if index < len(words) else ""
            if name in ("-X", "--method"):
                method = attached.upper()
            has_body = has_body or name in API_BODY_FLAGS
        elif not word.startswith("-"):
            endpoints.append(word.split("?", 1)[0].strip("/"))
        index += 1
    return method or ("POST" if has_body else "GET"), endpoints


def _provenance_query(words):
    """True only for op_issue_provenance's exact argv, so no other query, variable or flag passes."""
    expected = op_issue_provenance(1)[1:]
    return (len(words) == len(expected) and words[:-1] == expected[:-1]
            and re.fullmatch(f"number={NUMBER}", words[-1]) is not None)


def _gh_denied(words):
    head = tuple(words[:2])
    if "--show-token" in words or (head == ("auth", "status") and "-t" in words):
        return "show_token_denied"
    if head == ("pr", "ready"):
        return "pr_ready_denied"
    if head == ("pr", "merge"):
        return "merge_denied"
    if "--auto" in words:
        return "auto_merge_denied"
    if head[:1] == ("pr",) and len(head) == 2 and head[1] in GH_PR_CHANGES:
        return "pr_change_denied"
    if head == ("auth", "token"):
        return "auth_token_denied"
    if head[:1] == ("auth",) and len(head) == 2 and head[1] in GH_AUTH_CHANGES:
        return "auth_change_denied"
    if head[:1] == ("repo",) and len(head) == 2 and head[1] != "view":
        return "repo_change_denied"
    if words and words[0] in GH_DENIED_GROUPS:
        return GH_DENIED_GROUPS[words[0]]
    if words[:1] == ["api"]:
        if _provenance_query(words):
            return None  # the read-only query above; its template below matches it again
        method, endpoints = _api_request(words[1:])
        for endpoint in endpoints:
            if endpoint == "graphql":
                return "graphql_denied"
            if MERGE_PATH.search(endpoint):
                return "merge_endpoint_denied"
            if method == "DELETE" and REF_PATH.search(endpoint):
                return "ref_delete_denied"
        if method not in ("GET", "POST") or (method == "POST" and not all(
                REVIEWS_PATH.fullmatch(endpoint) for endpoint in endpoints)):
            return "method_denied"
    return None


def _git_denied(words):
    index, settings = 0, []
    while index + 1 < len(words) and words[index] in ("-C", "-c"):
        if words[index] == "-c":
            settings.append(words[index + 1])
        index += 2
    for setting in settings:
        key, has_value, value = setting.partition("=")
        key = key.lower()
        truthy = not has_value or value.strip().lower() not in FALSE_VALUES  # `-c key` alone means true
        if key == "push.followtags" and truthy:
            return "tag_push_denied"
        if key.startswith("remote.") and key.endswith(".mirror") and truthy:
            return "mirror_push_denied"
    rest = words[index:]
    if rest[:1] and rest[0].startswith("credential"):
        return "credential_denied"
    if rest[:1] != ["push"]:
        return None
    for word in rest[1:]:
        if word.startswith("--"):
            name = word.split("=", 1)[0]
            for option, reason in PUSH_DENIED.items():
                # parse-options also accepts a unique prefix of a long option.
                if name == option or (len(name) > 4 and option.startswith(name)):
                    return reason
        elif word.startswith("-") and len(word) > 1:
            if "f" in word[1:]:
                return "force_push_denied"
            if "d" in word[1:]:
                return "delete_push_denied"
        elif word.startswith("+"):
            return "force_refspec_denied"
        elif word.startswith(":"):
            return "delete_refspec_denied"
        elif word == "tag" or "refs/tags/" in word:
            return "tag_push_denied"
    return None


def denied_reason(argv):
    """The named refusal for an argv, or None (plan section 3's denied list and the brief's)."""
    if argv[0] == "gh":
        return _gh_denied(list(argv[1:]))
    if argv[0] == "git":
        return _git_denied(list(argv[1:]))
    return None


# -- Allowlist: exact templates. A pattern word is a literal or a compiled regex whose
# named groups are captured; `post` checks relations between captured values.

def _templates(gh):
    clone = re.compile(f"(?P<clone>{ABSOLUTE})")
    body = re.compile(f"(?P<body>{ABSOLUTE})")
    number = re.compile(NUMBER)
    return {
        "version": (["gh", "--version"], None),
        "auth_status": (op_auth_status(), None),
        "issue": (["gh", "api", re.compile(rf"{re.escape(API)}/issues/{NUMBER}")], None),
        "issue_comments": (["gh", "api", "--paginate", re.compile(rf"{re.escape(API)}/issues/{NUMBER}/comments")],
                           None),
        "issue_provenance": (op_issue_provenance(1)[:-1] + [re.compile(f"number={NUMBER}")], None),
        "repository": (op_repository(), None),
        "base": (op_base(), None),
        "branch_rules": (["gh", "api", re.compile(rf"{re.escape(API)}/rules/branches/{BRANCH}")], None),
        "base_rules": (op_base_rules(), None),
        "compare": (["gh", "api", re.compile(rf"{re.escape(API)}/compare/{SHA}\.\.\.{SHA}")], None),
        "ls_remote": (["git", "ls-remote", "--heads", ORIGIN_URL, re.compile(rf"openhands/issue-{NUMBER}\*")], None),
        "push_urls": (["git", "-C", clone, "remote", "get-url", "--push", "--all", "origin"], None),
        "push": (["git", "-C", clone, "-c", "credential.helper=", "-c", f"{HELPER_KEY}=",
                  "-c", f"{HELPER_KEY}=!{gh} auth git-credential", "-c", "core.hooksPath=/dev/null",
                  "-c", "push.followTags=false", "-c", "remote.origin.mirror=false",
                  "push", "--no-verify", "origin", re.compile(f"(?P<commit>{SHA}):refs/heads/{BRANCH}")], None),
        "pr_create": (["gh", "pr", "create", "--draft", "--base", "main", "--head", re.compile(BRANCH),
                       "--title", re.compile(rf"(?P<title>\[#(?P<title_number>{NUMBER})\] [^\x00-\x1f\x7f]+)"),
                       "--body-file", body, "--label", re.compile("|".join(map(re.escape, LANE_LABELS)))],
                      lambda values: (values["title_number"] == values["branch_number"]
                                      and len(values["title"]) <= MAX_TITLE)),
        "pr_view": (["gh", "pr", "view", number, "--json", PR_VIEW_FIELDS], None),
        "pr_checks": (["gh", "pr", "checks", number, "--required", "--json", CHECK_FIELDS], None),
        "run_log": (["gh", "run", "view", re.compile(r"[1-9][0-9]{0,19}"), "--log-failed"], None),
        "review": (["gh", "api", "--method", "POST", re.compile(rf"{re.escape(API)}/pulls/{NUMBER}/reviews"),
                    "-f", "event=COMMENT", "-f", re.compile(f"commit_id={SHA}"), "-F",
                    re.compile(f"body=@(?P<body>{ABSOLUTE})")], None),
        "pr_comment": (["gh", "pr", "comment", number, "--body-file", body], None),
    }


WRITE_OPS = {"pr_create", "review", "pr_comment"}
# Every operation that changes GitHub; GhHarness.writes journals each one (stage 2 receipt).
GITHUB_WRITES = WRITE_OPS | {"push"}


def _match(argv, gh):
    for op, (pattern, post) in _templates(gh).items():
        if len(pattern) != len(argv):
            continue
        values = {}
        for expected, word in zip(pattern, argv):
            if isinstance(expected, str):
                if word != expected:
                    break
            else:
                found = expected.fullmatch(word)
                if not found:
                    break
                values.update({key: value for key, value in found.groupdict().items() if value is not None})
        else:
            if post is None or post(values):
                return op, values
    return None, None


def check_argv(argv, *, gh, guard=None):
    """Refuse or name the operation, before any subprocess starts.

    The denylist runs first so that each named refusal keeps its own code; the
    exact templates then refuse everything else. Write operations need the
    outgoing-text guard's approval of the body file (and of the PR title).
    """
    if not isinstance(argv, (list, tuple)) or not argv or not all(isinstance(word, str) for word in argv):
        raise HarnessRefused("not_allowlisted")
    reason = denied_reason(argv)
    if reason:
        raise HarnessRefused(reason)
    op, values = _match(list(argv), gh)
    if op is None:
        raise HarnessRefused("not_allowlisted")
    if op in WRITE_OPS:
        if guard is None:
            raise HarnessRefused("no_outgoing_guard")
        if not guard.approved_file(values["body"]):
            raise HarnessRefused("body_not_approved")
        if op == "pr_create" and not guard.approved_text(values["title"]):
            raise HarnessRefused("title_not_approved")
    return op


# -- Preflight parsers (plan section 3 "Preflight on every run").

VERSION_LINE = re.compile(r"gh version (?P<version>[0-9]+\.[0-9]+\.[0-9]+)(?: \([^)]*\))?")


def parse_gh_version(text):
    """version.go:27-36 at 0cf10924: "gh version X.Y.Z (date)" then the changelog URL."""
    first = text.splitlines()[0] if text else ""
    found = VERSION_LINE.fullmatch(first)
    if not found:
        raise HarnessRefused("gh_version_unparseable")
    return found["version"]


def token_source_class(source):
    """Classify gh's tokenSource without keeping it (it can be a host path).

    status.go:426-428 and helper.go:121: a source ending in _TOKEN is an environment
    variable; config.go:275-277: "keyring"; status.go:376-381: the hosts file path.
    """
    if not isinstance(source, str) or not source:
        return "unknown"
    if source.endswith("_TOKEN"):
        return "environment"
    if source == "keyring":
        return "keyring"
    if posixpath.basename(source) == "hosts.yml":
        return "config_file"
    return "unknown"


def check_auth_status(text):
    """Gate on `gh auth status --active --hostname github.com --json hosts`.

    status.go:147-149: with --json the command exits 0 whatever the state, so the
    parsed entry decides. Fields: status.go:30-43. The record keeps the scope names
    (displayScopes splits on commas, :349-357) and only the token source's class.
    """
    try:
        data = json.loads(text)
    except ValueError:
        raise HarnessRefused("auth_status_unparseable") from None
    hosts = data.get("hosts") if isinstance(data, dict) else None
    if not isinstance(hosts, dict):
        raise HarnessRefused("auth_status_unparseable")
    entries = hosts.get(HOST)
    if not entries:
        raise HarnessRefused("auth_host_missing")
    if set(hosts) != {HOST} or not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], dict):
        raise HarnessRefused("auth_entries_unexpected")
    entry = entries[0]
    if entry.get("token"):
        raise HarnessRefused("token_in_status_output")
    if entry.get("state") != "success":
        raise HarnessRefused("auth_not_success")
    if entry.get("active") is not True:
        raise HarnessRefused("auth_not_active")
    if entry.get("host") != HOST:
        raise HarnessRefused("auth_host_mismatch")
    if entry.get("login") != OWNER:
        raise HarnessRefused("auth_login_mismatch")
    if entry.get("gitProtocol") != "https":
        raise HarnessRefused("git_protocol_not_https")
    source = token_source_class(entry.get("tokenSource"))
    if source == "environment":
        raise HarnessRefused("token_from_environment")
    if source not in ("config_file", "keyring"):
        raise HarnessRefused("token_source_unknown")
    scopes = entry.get("scopes") if isinstance(entry.get("scopes"), str) else ""
    names = sorted({scope.strip() for scope in scopes.split(",") if scope.strip()})
    if "repo" not in names:
        raise HarnessRefused("repo_scope_missing")
    return {"host": HOST, "login": OWNER, "git_protocol": "https", "token_source_class": source, "scopes": names}


def check_branch_rules(text):
    """Plan section 3 preflight: the branch's rules include non_fast_forward (section 4)."""
    try:
        rules = json.loads(text)
    except ValueError:
        raise HarnessRefused("branch_rules_unparseable") from None
    if not isinstance(rules, list):
        raise HarnessRefused("branch_rules_unparseable")
    types = sorted({rule["type"] for rule in rules if isinstance(rule, dict) and isinstance(rule.get("type"), str)})
    if "non_fast_forward" not in types:
        raise HarnessRefused("branch_rules_missing_non_fast_forward")
    return types


BASE_LINE = re.compile(rf"(?P<oid>{SHA})\trefs/heads/main")


def parse_base(text):
    """op_base's output: exactly one "<oid> TAB refs/heads/main" line (git-ls-remote(1))."""
    lines = text.splitlines() if isinstance(text, str) else []
    found = BASE_LINE.fullmatch(lines[0]) if len(lines) == 1 else None
    if not found:
        raise HarnessRefused("base_unparseable")
    return found["oid"]


def check_repository(text):
    """op_repository's answer names this repository, with main as its default branch.

    Fields of GitHub's "Get a repository" (docs.github.com/en/rest/repos/repos):
    full_name, default_branch, archived and disabled. An archived or disabled
    repository takes no push, so it refuses here, before any container starts.
    """
    try:
        data = json.loads(text)
    except ValueError:
        raise HarnessRefused("repository_unparseable") from None
    if not isinstance(data, dict):
        raise HarnessRefused("repository_unparseable")
    if data.get("full_name") != REPO:
        raise HarnessRefused("repository_mismatch")
    if data.get("default_branch") != "main":
        raise HarnessRefused("default_branch_not_main")
    if data.get("archived") is not False or data.get("disabled") is True:
        raise HarnessRefused("repository_not_writable")
    return {"full_name": REPO, "default_branch": "main"}


def _inside(path, trees):
    """True when `path` resolves into one of `trees` (os.path.realpath, then commonpath)."""
    resolved = os.path.realpath(path)
    for tree in trees:
        root = os.path.realpath(tree)
        if os.path.commonpath([resolved, root]) == root:
            return True
    return False


class GhHarness:
    """Runs allowlisted gh and git operations with the pinned executables.

    `runner` defaults to subprocess.run and is injectable for tests. `guard` is the
    outgoing-text guard (resolver/outgoing_guard.py); without one every write is refused.
    `writes` journals each GitHub write (GITHUB_WRITES) as its operation name and the
    exit status of gh or git, which is non-zero when GitHub answers with an error. An
    entry is added before the write runs, so one that raised keeps exit_code None.

    `push_gate` is the trusted pre-push gate (resolver/push_gate.py); without one every
    push is refused. `gates` journals one gate record per commit checked, and a push
    runs only for a commit in this harness's passed set (decision record amendment of
    2026-10-04: enforcement before execution, in trusted harness code).
    """

    def __init__(self, gh, *, base_env, workdir, git="/usr/bin/git", runner=subprocess.run, guard=None,
                 timeout=600, push_gate=None):
        self.gh = _executable(gh, "unsafe_gh_path")
        self.git = _executable(git, "unsafe_git_path")
        self.workdir = check_workdir(workdir)
        self.env = child_env(base_env, gh_path=self.gh, workdir=self.workdir)
        self.runner, self.guard, self.timeout = runner, guard, timeout
        self.push_gate = push_gate
        self.writes, self.gates = [], []
        self._gated = set()

    def run(self, argv):
        op = check_argv(argv, gh=self.gh, guard=self.guard)
        if op == "push":
            # Only the exact commit the trusted gate passed in this harness is ever pushed.
            if self.push_gate is None:
                raise HarnessRefused("push_gate_missing")
            _, values = _match(list(argv), self.gh)
            if values.get("commit") not in self._gated:
                raise HarnessRefused("push_not_gated")
        check_workdir(self.workdir)
        executable = self.gh if argv[0] == "gh" else self.git
        record = None
        if op in GITHUB_WRITES:
            record = {"op": op, "exit_code": None}
            self.writes.append(record)
        result = self.runner([executable, *argv[1:]], cwd=self.workdir, env=dict(self.env),
                             stdin=subprocess.DEVNULL, capture_output=True, encoding="utf-8", errors="replace",
                             timeout=self.timeout, check=False)
        if record is not None:
            record["exit_code"] = result.returncode
        return result

    def base_sha(self):
        """The origin/main commit the attempt pins, read anonymously (op_base)."""
        listed = self.run(op_base())
        if listed.returncode != 0:
            raise HarnessRefused("base_read_failed")
        return parse_base(listed.stdout)

    def repository(self):
        """The preflight's repository check (op_repository, check_repository)."""
        viewed = self.run(op_repository())
        if viewed.returncode != 0:
            raise HarnessRefused("repository_read_failed")
        return check_repository(viewed.stdout)

    def branch_rules(self, branch):
        """The agent branch's active rules, which must include non_fast_forward (check_branch_rules)."""
        listed = self.run(op_branch_rules(branch))
        if listed.returncode != 0:
            raise HarnessRefused("branch_rules_failed")
        return check_branch_rules(listed.stdout)

    def preflight(self):
        """gh 2.101.0 at the pinned path, then the stored owner login with repo scope."""
        version = self.run(op_version())
        if version.returncode != 0:
            raise HarnessRefused("gh_version_failed")
        found = parse_gh_version(version.stdout)
        if found != GH_VERSION:
            raise HarnessRefused("gh_version_mismatch")
        status = self.run(op_auth_status())
        if status.returncode != 0:
            raise HarnessRefused("auth_status_failed")
        return {"gh_version": found, **check_auth_status(status.stdout)}

    def push(self, clone, branch, *, base, head, agent_trees=()):
        """Check that origin pushes only to this repository, gate the exact commit, then push it.

        The gate runs before the push, from trusted code: a push starts `push` workflows
        from the pushed commit, and its pull request runs without a fork boundary, so a
        check inside CI would come too late (resolver/push_gate.py). The gate's module must
        lie outside `clone` and every agent tree (the attempt's result directory holds the
        agent's workspace and this clone). Its record is journaled before any refusal.
        """
        if self.push_gate is None:
            raise HarnessRefused("push_gate_missing")
        urls = self.run(op_push_urls(clone))
        if urls.returncode != 0 or urls.stdout.splitlines() != [ORIGIN_URL]:
            raise HarnessRefused("origin_url_mismatch")
        trees = (clone, *agent_trees)
        module = sys.modules.get(type(self.push_gate).__module__)
        gate_file = getattr(module, "__file__", None)
        if not isinstance(gate_file, str) or _inside(gate_file, trees):
            record = {"commit": head, "base": base, "status": "fail", "reasons": ["gate_inside_agent_tree"],
                      "paths": [], "trusted_commit": None, "protected": None,
                      "zizmor": {"version": None, "findings": None, "failing": []}}
        else:
            record = self.push_gate.check(clone, base=base, head=head, agent_trees=tuple(agent_trees))
        self.gates.append(dict(record) if isinstance(record, dict) else {"commit": head, "status": "fail",
                                                                         "reasons": ["gate_record_invalid"]})
        if not (isinstance(record, dict) and record.get("status") == "pass" and record.get("commit") == head
                and not record.get("reasons")):
            raise HarnessRefused("push_gate_refused")
        self._gated.add(head)
        return self.run(op_push(clone, branch, head, gh=self.gh))
