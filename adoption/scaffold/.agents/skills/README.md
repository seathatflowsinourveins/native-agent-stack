# Repository skills

Skills that only this repository needs go here, one folder per skill holding a `SKILL.md` whose frontmatter has `name`
and `description` (the [Agent Skills](https://agentskills.io) format). Codex scans `.agents/skills` in every directory
from its working directory up to the repository root ([Codex skills](https://developers.openai.com/codex/skills), "Where
Codex loads local skills"), while Claude Code reads project skills from `.claude/skills/`. The `skills` CLI installs one
canonical copy with a link for each agent it targets, so `skills add <source> --skill <name> -a claude-code codex`
serves both ([vercel-labs/skills v1.7.0](https://github.com/vercel-labs/skills/tree/v1.7.0), "Supported Agents" and
"Installation Methods").

Skills every repository uses are global and are not copied here: each host installs them once from
[native-agent-stack](https://github.com/seathatflowsinourveins/native-agent-stack)'s `adoption/skills/manifest.json`,
through its `tools/adoption/install_skills.py` or `adoption/bootstrap-linux.sh --configure-full-profile`.
