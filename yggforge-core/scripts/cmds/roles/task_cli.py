"""联合角色任务入口，分别保留执行状态和模型输出。"""

from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from knowledge.graph_models import GraphError
from roles.loader import load_task
from roles.registry import RoleError
from roles.scheduler import run_task


def main():
    parser = argparse.ArgumentParser(description="YggForge 联合角色任务")
    parser.add_argument("action", choices=["run"])
    parser.add_argument("--task-file", type=Path, required=True)
    parser.add_argument("--backend", choices=["prepare", "codex"])
    parser.add_argument("--isolation", choices=["logical", "enforced"])
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    try:
        if not 15 <= args.timeout <= 3600:
            raise RoleError("timeout 需在 15 至 3600 秒内。")
        result = run_task(load_task(args.task_file), args.backend, args.isolation, args.timeout)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result["status"] == "failed" else 0
    except (RoleError, GraphError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
