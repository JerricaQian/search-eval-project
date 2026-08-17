#!/usr/bin/env python3
"""SKILL.md frontmatter 校验（非阻断，PostToolUse 钩子调用）。
读 stdin 中的 Claude Code 工具 JSON，取 tool_input.file_path；若为 SKILL.md 则校验：
- eval 评测项（路径含 /eval-skills/eval-）：必须含 name/title/weight/aggregate 四键，
  且 name 的值必须与所在目录名完全一致（见 .claude/rules/skill-frontmatter.md）。
- 非评测 skill（phase1/phase2/phase4 等渲染/标注/截图 skill）：只需 name 存在（值不要求与目录名一致）。
结果打印到 stderr，始终 exit 0（仅提示，不阻断编辑）。"""
import sys, json, re, os


def main() -> int:
    try:
        d = json.load(sys.stdin)
    except Exception:
        return 0
    p = ((d.get("tool_input") or {}).get("file_path")) or ""
    if not p or os.path.basename(p) != "SKILL.md":
        return 0
    norm = p.replace("\\", "/")
    is_eval = "/eval-skills/eval-" in norm
    try:
        txt = open(p, encoding="utf-8").read()
    except Exception as e:  # noqa: BLE001
        print(f"[skill-frontmatter] WARN: 无法读取 {p}: {e}", file=sys.stderr)
        return 0
    m = re.match(r"^---\n(.*?\n)---\n", txt, re.S)
    if not m:
        print(f"[skill-frontmatter] FAIL: {p} 缺少 frontmatter 块 (--- ... ---)", file=sys.stderr)
        return 0
    fm = m.group(1)
    required = ["name:", "title:", "weight:", "aggregate:"] if is_eval else ["name:"]
    miss = [k for k in required if k not in fm]
    kind = "eval 评测项" if is_eval else "非评测 skill"
    problems = []
    if miss:
        problems.append(f"frontmatter 缺少: {', '.join(miss)}")
    if is_eval and "name:" not in miss:
        name_match = re.search(r"^name:\s*(\S+)\s*$", fm, re.M)
        name_value = name_match.group(1).strip() if name_match else ""
        dir_name = os.path.basename(os.path.dirname(p))
        if name_value != dir_name:
            problems.append(f"name 值 '{name_value}' 与目录名 '{dir_name}' 不一致")
    if problems:
        print(f"[skill-frontmatter] FAIL: {p}（{kind}）{'; '.join(problems)}", file=sys.stderr)
    else:
        print(f"[skill-frontmatter] OK: {p}（{kind}）frontmatter 完整", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
