"""机器工具注册：只公开连接状态，不把凭据和安装路径注入角色。"""

import json
from pathlib import Path
import subprocess
from typing import Any, Dict

from lib.repo_paths import HOST_RUNTIME_ROOT
from roles.registry import RoleError, load_role


def configuration():
    path = HOST_RUNTIME_ROOT / "config/roles.local.json"
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else {}


def catalog(role_id):
    return [{"name": name, "installed": value.get("installed", False), "version": value.get("version", ""), "authenticated": value.get("authenticated", False), "status": value.get("status", "not-configured")} for name, value in configuration().get("tools", {}).items() if role_id in value.get("roles", [])]


def run_tool(role_id: str, name: str, arguments):
    """由协调者调用已登记工具；不自动登录或把旧接口凭据移到新服务。"""
    load_role(role_id)
    selected = configuration().get("tools", {}).get(name)
    if not selected or role_id not in selected.get("roles", []) or not selected.get("installed"):
        raise RoleError("角色工具未安装或未登记。")
    if not arguments:
        raise RoleError("必须给出工具命令。")
    metadata_only = arguments[0] in {"version", "capabilities", "schema"} or arguments[:2] == ["auth", "status"]
    if arguments[0] in {"update", "uninstall", "config", "worker", "data", "db"} or arguments[0] == "auth" and arguments[:2] != ["auth", "status"]:
        raise RoleError("登录、修改配置或维护数据操作不由角色自动执行。")
    if not metadata_only and not selected.get("authenticated", False):
        raise RoleError("客户端已安装但尚未授权；先由用户完成登录，再验证真实查询。")
    command = selected.get("command")
    if not isinstance(command, list) or not command:
        raise RoleError("本机工具命令未配置。")
    result = subprocess.run(command + list(arguments), capture_output=True, text=True, encoding="utf-8", timeout=60)
    try:
        payload = json.loads(result.stdout)
    except ValueError:
        payload = {"ok": False, "error": "工具未返回有效 JSON。"}
    return {"tool": name, "exit_code": result.returncode, "result": payload}
