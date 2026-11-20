"""加载角色摘要与双路联想，按命中路径窄读正文。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
import uuid

from knowledge.graph_query import KnowledgeGraphIndex
from knowledge.spaces import role_space, shared_space
from lib.front_matter import parse_front_matter
from lib.repo_paths import CORE_ROOT
from roles.context import ContextBundle, RoleContext
from roles.registry import RoleError, inside, load_role


def load_task(task_file: Optional[Path] = None, prompt: str = "", project_id: str = "", tags: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    task = json.loads(Path(task_file).read_text(encoding="utf-8-sig")) if task_file else {}
    if not isinstance(task, dict):
        raise RoleError("任务必须是 JSON 对象。")
    allowed = {"task_id", "prompt", "project_id", "tags", "project_root", "files", "roles", "dependencies"}
    if set(task) - allowed:
        raise RoleError("任务包含未支持字段: " + ", ".join(sorted(set(task) - allowed)))
    task["prompt"] = prompt or str(task.get("prompt", ""))
    if not task["prompt"].strip():
        raise RoleError("任务 prompt 不能为空。")
    task["task_id"] = str(task.get("task_id") or "task-" + uuid.uuid4().hex)
    task["project_id"] = project_id or str(task.get("project_id", ""))
    raw_tags = tags or task.get("tags", [])
    if not isinstance(raw_tags, (list, tuple)):
        raise RoleError("任务 tags 必须是列表。")
    selected = list(raw_tags)
    if not selected or any(not isinstance(tag, str) or not tag.strip() for tag in selected):
        raise RoleError("任务必须提供由任务提炼的 tags 列表。")
    task["tags"] = list(dict.fromkeys(tag.strip() for tag in selected))
    if len(task["prompt"]) > 100000:
        raise RoleError("任务过长，请使用分阶段任务或资料文件。")
    return task


def _read_hits(index: KnowledgeGraphIndex, tags: Sequence[str], limit: int, max_chars: int, project_id: str) -> List[Dict[str, Any]]:
    from knowledge.space_lock import graph_lock
    with graph_lock(index.repo_root, index.config):
        return _read_hits_locked(index, tags, limit, max_chars, project_id)


def _read_hits_locked(index: KnowledgeGraphIndex, tags: Sequence[str], limit: int, max_chars: int, project_id: str) -> List[Dict[str, Any]]:
    hits, _meta = index.associate(tags, limit=max(50, limit))
    results = []
    remaining = max_chars
    for hit in hits:
        path = inside(index.repo_root / hit.entry.path, index.repo_root)
        metadata, body = parse_front_matter(path.read_text(encoding="utf-8-sig"))
        entry_project = str(metadata.get("project_id", ""))
        if entry_project and entry_project != project_id:
            continue
        if remaining <= 0 or len(results) >= limit:
            break
        size = min(len(body), remaining)
        results.append({"space_id": index.config.get("space_id", "shared"), "entry_id": hit.entry.id, "path": hit.entry.path, "title": hit.entry.title, "type": hit.entry.kind, "status": hit.entry.status, "confidence": hit.entry.confidence, "project_id": entry_project, "last_reviewed": hit.entry.last_reviewed, "source_fingerprint": hit.entry.source_fingerprint, "via_tags": hit.via_tags, "body": body[:size], "truncated": size < len(body)})
        remaining -= size
    return results


def prepare_context(role_id: str, task: Dict[str, Any], core_root: Optional[Path] = None) -> ContextBundle:
    core = Path(core_root or CORE_ROOT).resolve()
    role = load_role(role_id, core)
    own = role_space(role_id, core)
    from backends.role_memory import refresh_role_memory, role_summary_status
    def own_context():
        from knowledge.space_lock import graph_lock
        with graph_lock(own.root, own.config):
            summary_status = role_summary_status(own)
            if not summary_status.get("matched"):
                refresh_role_memory(own)
                summary_status = role_summary_status(own)
            if not summary_status.get("matched"):
                raise RoleError("角色摘要与记忆版本不一致。")
            summary_path = inside(role.root / "memories/summary.md", own.root)
            _metadata, summary_body = parse_front_matter(summary_path.read_text(encoding="utf-8-sig"))
            summary = {"space_id": own.space_id, "owner_role": role.id, "path": "memories/summary.md", "source_digest": summary_status.get("source_digest"), "body": summary_body[:4096], "truncated": len(summary_body) > 4096}
            return summary, _read_hits(KnowledgeGraphIndex(space=own), task["tags"], role.retrieval["role_limit"], role.retrieval["max_chars"], task.get("project_id", ""))
    shared = shared_space(core, allowed_paths=role.shared_paths)
    with ThreadPoolExecutor(max_workers=2) as pool:
        shared_job = pool.submit(_read_hits, KnowledgeGraphIndex(space=shared), task["tags"], role.retrieval["shared_limit"], role.retrieval["max_chars"], task.get("project_id", ""))
        own_job = pool.submit(own_context)
        shared_hits = shared_job.result()
        summary, own_hits = own_job.result()
    files = []
    project_root = Path(task["project_root"]).resolve() if task.get("project_root") else None
    if project_root and (core / "roles").resolve() in (project_root, *project_root.parents):
        raise RoleError("任务项目根不能是角色私有目录。")
    for value in task.get("files", []):
        if project_root is None:
            raise RoleError("读取任务文件必须显式提供 project_root。")
        path = inside(project_root / str(value), project_root)
        if (core / "roles").resolve() in path.parents:
            raise RoleError("任务资料不能直接引用角色私有目录。")
        if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
            raise RoleError("任务资料缺失或过大。")
        files.append({"name": path.name, "text": path.read_text(encoding="utf-8-sig")})
    clean_task = {key: value for key, value in task.items() if key not in {"project_root", "files", "roles", "dependencies"}}
    clean_task["assigned_role"] = role.id
    clean_task["files"] = files
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:12]
    context = RoleContext(role.id, run_id, task["task_id"], task.get("project_id", ""), role.revision)
    common = []
    behavior = core / "profiles/common/behavior-packs/karpathy-guidelines.md"
    for path in [behavior] + ([project_root / "AGENTS.md"] if project_root else []):
        if path.is_file():
            data = path.read_text(encoding="utf-8-sig")
            common.append({"path": path.name if project_root and path.parent == project_root else "profiles/common/behavior-packs/karpathy-guidelines.md", "body": data[:16000], "source_fingerprint": hashlib.sha256(data.encode("utf-8")).hexdigest()})
    metadata = role.metadata()
    return ContextBundle(context, metadata, clean_task, role.entry.read_text(encoding="utf-8-sig"), role.identity.read_text(encoding="utf-8-sig"), [{"path": reference, "body": path.read_text(encoding="utf-8-sig")[:8192]} for reference, path in zip(metadata["skills"], role.skills)], summary, shared_hits, own_hits, common)
