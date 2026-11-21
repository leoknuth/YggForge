"""角色注册、校验、上下文准备、执行与协调者提交入口。"""

from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from knowledge.graph_models import GraphError
from knowledge.spaces import role_space
from roles.registry import RoleError, create_role, list_roles, load_role


def parser():
    root = argparse.ArgumentParser(description="YggForge 角色与长期记忆")
    commands = root.add_subparsers(dest="action", required=True)
    commands.add_parser("list")
    for action in ("show", "check", "create", "prepare", "run"):
        child = commands.add_parser(action)
        child.add_argument("role_id")
        if action == "create":
            child.add_argument("--name", required=True)
            child.add_argument("--description", required=True)
        if action in {"prepare", "run"}:
            child.add_argument("--task-file", type=Path)
            child.add_argument("--task", default="")
            child.add_argument("--project-id", default="")
            child.add_argument("--tag", action="append", default=[])
            child.add_argument("--skill", action="append", default=[])
        if action == "run":
            child.add_argument("--backend", choices=["prepare", "codex"])
            child.add_argument("--isolation", choices=["logical", "enforced"])
            child.add_argument("--timeout", type=int, default=180)
    commit = commands.add_parser("commit")
    commit.add_argument("role_ids", nargs="+")
    commit.add_argument("--push", action="store_true")
    tool = commands.add_parser("tool")
    tool.add_argument("role_id")
    tool.add_argument("name")
    tool.add_argument("arguments", nargs=argparse.REMAINDER)
    return root


def main():
    args = parser().parse_args()
    try:
        if args.action == "list":
            result = {"roles": list_roles()}
        elif args.action == "tool":
            from roles.tools import run_tool
            values = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
            result = run_tool(args.role_id, args.name, values)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return result["exit_code"]
        elif args.action == "create":
            role = create_role(args.role_id, args.name, args.description)
            from backends.role_memory import refresh_role_memory
            result = {"role": role.metadata(), "memory": refresh_role_memory(role_space(role.id))}
        elif args.action == "show":
            result = load_role(args.role_id).metadata()
        elif args.action == "check":
            from backends.role_memory import role_summary_status
            role = load_role(args.role_id)
            result = {"role": role.metadata(), "memory": role_summary_status(role_space(role.id))}
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["memory"]["matched"] else 1
        elif args.action == "commit":
            from roles.git_store import commit_roles
            result = commit_roles(args.role_ids, args.push)
        else:
            from roles.loader import load_task, prepare_context
            task = load_task(args.task_file, args.task, args.project_id, args.tag)
            if args.skill:
                task["skills"] = args.skill
            if args.action == "prepare":
                result = prepare_context(args.role_id, task).as_dict()
            else:
                if not 15 <= args.timeout <= 3600:
                    raise RoleError("timeout 需在 15 至 3600 秒内。")
                from roles.scheduler import run_role
                result = run_role(args.role_id, task, args.backend, args.isolation, args.timeout)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("status") == "failed" else 0
    except (RoleError, GraphError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
