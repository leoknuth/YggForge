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
    listing = commands.add_parser("list")
    listing.add_argument("--brief", action="store_true", help="只显示角色说明、标签和技能/业务记录数量")
    listing.add_argument("--tag", action="append", default=[], help="仅显示包含所有指定标签的角色")
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
            child.add_argument("--workflow", default="", help="选择本角色注册的完整技能工作流")
            child.add_argument("--record-id", default="", help="命例正式记录ID，独立于知识project_id")
            child.add_argument("--track", default="", help="盲阶段的独立轨道")
            child.add_argument("--stage", choices=["blind", "synthesis", "review"])
        if action == "run":
            child.add_argument("--backend", choices=["prepare", "codex"])
            child.add_argument("--isolation", choices=["logical", "enforced"])
            child.add_argument("--timeout", type=int, default=180)
    for action in ("case-init", "case-add-track", "case-freeze", "case-check"):
        child = commands.add_parser(action)
        child.add_argument("role_id")
        child.add_argument("case_id")
        if action == "case-init":
            child.add_argument("--track", action="append", default=[], help="额外启用模板可选独立专项；默认必选轨道保留")
        if action in {"case-freeze", "case-add-track"}:
            child.add_argument("--track", required=True)
        if action == "case-check":
            child.add_argument("--require-frozen", action="store_true")
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
            roles = [item for item in list_roles() if all(tag in item.get("tags", []) for tag in args.tag)]
            if args.brief:
                roles = [{key: item[key] for key in ("id", "name", "revision", "description", "tags")} | {"skill_count": len(item["skills"]), "record_count": len(item["records"])} for item in roles]
            result = {"roles": roles}
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
        elif args.action in {"case-init", "case-add-track", "case-freeze", "case-check"}:
            from roles.cases import initialize_case, add_track, freeze_track, check_case, resolve_record
            role = load_role(args.role_id)
            if args.action == "case-init":
                result = initialize_case(role, args.case_id, tracks=args.track)
            elif args.action == "case-add-track":
                result = add_track(role, args.case_id, args.track)
            else:
                _record_id, record = resolve_record(role, args.case_id)
                result = freeze_track(record["root"], args.track) if args.action == "case-freeze" else check_case(record["root"], args.require_frozen)
        else:
            from roles.loader import load_task, prepare_context
            task = load_task(args.task_file, args.task, args.project_id, args.tag, args.workflow)
            for field in ("record_id", "track", "stage"):
                if getattr(args, field):
                    task[field] = getattr(args, field)
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
