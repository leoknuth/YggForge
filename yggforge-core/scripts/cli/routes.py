# -*- coding: utf-8 -*-
"""Ygg 显式 action 路由表（``route_explicit``）。

将 ``ygg <action> [args]`` 适配为叶子 CLI argv，并编排 deploy→git、sync 前 import 等链式逻辑。
"""

from __future__ import annotations

import json
import sys
from typing import List, Optional

from cli.errors import YggError
from cli.runtime import (
    SCRIPT_DIR,
    behavior_gate,
    git_sync_args,
    load_sync_policy,
    maybe_import_targets,
    parse_target_list,
    run_python,
    _pop_force_flags,
)
from lib.repo_paths import CORE_ROOT, RUNTIME_ROOT


def route_explicit(action: str, rest: List[str]) -> int:
    if action == "status":
        scope = "user"
        project_root = None
        targets: List[str] = []
        idx = 0
        while idx < len(rest):
            token = rest[idx]
            if token == "--scope":
                idx += 1
                if idx >= len(rest) or rest[idx].startswith("--"):
                    raise YggError("ygg {0} --scope requires a value.".format(action))
                scope = rest[idx]
            elif token == "--project-root":
                idx += 1
                if idx >= len(rest) or rest[idx].startswith("--"):
                    raise YggError("ygg {0} --project-root requires a value.".format(action))
                project_root = rest[idx]
            else:
                targets.append(token)
            idx += 1
        if not targets:
            targets = ["cursor"]
        status_args = ["--action", "status", "--scope", scope, "--targets"] + targets
        if project_root:
            status_args += ["--project-root", project_root]
        return run_python("deploy.py", status_args)

    if action == "deploy":
        rest, force = _pop_force_flags(rest)
        if force == "deny":
            print("deploy_status  : skipped (--no)")
            return 0
        mode = "link"
        scope = "user"
        project_root = None
        targets: List[str] = []
        backup = False
        install_deps = False
        idx = 0
        while idx < len(rest):
            token = rest[idx]
            if token in ("link", "copy", "render"):
                mode = token
            elif token == "--backup":
                backup = True
            elif token == "--install-deps":
                install_deps = True
            elif token == "--scope":
                idx += 1
                if idx >= len(rest) or rest[idx].startswith("--"):
                    raise YggError("ygg {0} --scope requires a value.".format(action))
                scope = rest[idx]
            elif token == "--project-root":
                idx += 1
                if idx >= len(rest) or rest[idx].startswith("--"):
                    raise YggError("ygg {0} --project-root requires a value.".format(action))
                project_root = rest[idx]
            else:
                targets.append(token)
            idx += 1
        if not targets:
            targets = ["cursor"]
        deploy_args = ["--action", "deploy", "--mode", mode, "--scope", scope, "--targets"] + targets
        if project_root:
            deploy_args += ["--project-root", project_root]
        if backup:
            deploy_args.append("--backup")
        if install_deps:
            deploy_args.append("--install-deps")
        if force == "dry_run":
            deploy_args.append("--dry-run")
        code = run_python("deploy.py", deploy_args)
        if code != 0:
            return code
        if force == "dry_run":
            return 0
        # 项目级部署是本机投影，不触发远端 git update
        if scope == "project":
            return 0
        # 部署后可选 git update（默认 deny = 本机记忆即可，不拉远程）
        outcome, decision = behavior_gate(
            "deploy.git_sync_after",
            "部署完成后对本仓库执行 git update（pull --rebase）",
            force=force,
            deny_means="skip",
        )
        if outcome == "skip":
            print("deploy_git     : skipped (local-only; memory 写 runtime 即可)", flush=True)
            return 0
        if outcome == "abort":
            return 2
        print("deploy_git     : start -> git update ({0})".format(decision.get("mode")), flush=True)
        sync_policy = load_sync_policy()
        return run_python("git_sync.py", git_sync_args("sync", sync_policy))

    if action == "import":
        rest, force = _pop_force_flags(rest)
        if force == "deny":
            print("import_status  : skipped (--no)")
            return 0
        scope = "user"
        project_root = None
        preview_only = force == "dry_run"
        targets: List[str] = []
        idx = 0
        while idx < len(rest):
            token = rest[idx]
            if token == "--scope":
                idx += 1
                if idx >= len(rest) or rest[idx].startswith("--"):
                    raise YggError("ygg {0} --scope requires a value.".format(action))
                scope = rest[idx]
            elif token == "--project-root":
                idx += 1
                if idx >= len(rest) or rest[idx].startswith("--"):
                    raise YggError("ygg {0} --project-root requires a value.".format(action))
                project_root = rest[idx]
            elif token == "--preview-only":
                preview_only = True
            else:
                targets.append(token)
            idx += 1
        if not targets:
            targets = ["cursor"]
        import_args = ["--action", "import", "--scope", scope, "--targets"] + targets
        if project_root:
            import_args += ["--project-root", project_root]
        if preview_only:
            import_args.append("--preview-only")
        return run_python("deploy.py", import_args)

    if action == "sync":
        rest, force = _pop_force_flags(rest)
        outcome, _decision = behavior_gate(
            "git.update",
            "对本仓库执行 git update（pull --rebase）",
            force=force,
            deny_means="skip",
        )
        if outcome == "skip":
            return 0
        if outcome == "abort":
            return 2
        policy = load_sync_policy()
        targets = parse_target_list(action, rest)
        maybe_import_targets(action, targets, policy)
        return run_python("git_sync.py", git_sync_args(action, policy))

    if action == "push":
        rest, force = _pop_force_flags(rest)
        outcome, _decision = behavior_gate(
            "git.push",
            "对本仓库执行 git update + push",
            force=force,
            deny_means="skip",
        )
        if outcome == "skip":
            return 0
        if outcome == "abort":
            return 2
        policy = load_sync_policy()
        targets = parse_target_list(action, rest)
        maybe_import_targets(action, targets, policy)
        return run_python("git_sync.py", git_sync_args(action, policy))

    if action == "ingest":
        if not rest:
            raise YggError("`ygg ingest` requires a URL or supported source path.")
        first = rest[0]
        if first.startswith("http://") or first.startswith("https://"):
            args = ["--url", first]
            idx = 1
            while idx < len(rest):
                token = rest[idx]
                if token == "--save-raw-html":
                    args.append(token)
                elif token == "--slug":
                    idx += 1
                    if idx >= len(rest):
                        raise YggError("`ygg ingest --slug` requires a value.")
                    args.extend(["--slug", rest[idx]])
                elif idx == 1 and not token.startswith("--"):
                    args.extend(["--slug", token])
                else:
                    raise YggError("Unrecognized `ygg ingest` token: {0}".format(token))
                idx += 1
            return run_python("ingest.py", args)
        raise YggError("Current `ygg ingest` only supports URL input.")

    if action == "distill":
        if not rest:
            return run_python("distill.py", ["--latest"])
        args = []
        idx = 0
        while idx < len(rest):
            token = rest[idx]
            if token == "--latest":
                args.append(token)
            elif token in ("--input", "--slug"):
                idx += 1
                if idx >= len(rest):
                    raise YggError("`ygg distill {0}` requires a value.".format(token))
                args.extend([token, rest[idx]])
            elif idx == 0 and not token.startswith("--"):
                args.extend(["--input", token])
            else:
                raise YggError("Unrecognized `ygg distill` token: {0}".format(token))
            idx += 1
        return run_python("distill.py", args)

    if action == "dream":
        args: List[str] = []
        idx = 0
        while idx < len(rest):
            token = rest[idx]
            if token == "--limit":
                idx += 1
                if idx >= len(rest):
                    raise YggError("`ygg dream --limit` requires a value.")
                args.extend(["--limit", rest[idx]])
            elif token == "--scan":
                args.append("--scan")
            elif token in ("--json", "--yes", "--no"):
                args.append(token)
            else:
                raise YggError("Unrecognized `ygg dream` token: {0}".format(token))
            idx += 1
        return run_python("dream.py", args)

    if action == "recall":
        query_tokens: List[str] = []
        limit: Optional[str] = None
        kinds: List[str] = []
        tags: List[str] = []
        scope: Optional[str] = None
        agents: List[str] = []
        channels: List[str] = []
        as_json = False
        include_inactive = False
        idx = 0
        while idx < len(rest):
            token = rest[idx]
            if token == "--limit":
                idx += 1
                if idx >= len(rest):
                    raise YggError("`ygg recall --limit` requires a value.")
                limit = rest[idx]
            elif token == "--type":
                idx += 1
                if idx >= len(rest):
                    raise YggError("`ygg recall --type` requires a value.")
                kinds.append(rest[idx])
            elif token == "--tag":
                idx += 1
                if idx >= len(rest):
                    raise YggError("`ygg recall --tag` requires a value.")
                tags.append(rest[idx])
            elif token == "--scope":
                idx += 1
                if idx >= len(rest):
                    raise YggError("`ygg recall --scope` requires a value.")
                scope = rest[idx]
            elif token == "--agent":
                idx += 1
                if idx >= len(rest):
                    raise YggError("`ygg recall --agent` requires a value.")
                agents.append(rest[idx])
            elif token == "--channel":
                idx += 1
                if idx >= len(rest):
                    raise YggError("`ygg recall --channel` requires a value.")
                channels.append(rest[idx])
            elif token == "--json":
                as_json = True
            elif token == "--include-inactive":
                include_inactive = True
            elif token.startswith("--"):
                raise YggError("Unrecognized `ygg recall` token: {0}".format(token))
            else:
                query_tokens.append(token)
            idx += 1

        if not query_tokens and not (kinds or tags or scope or agents or channels):
            raise YggError("`ygg recall` requires query text and/or --type/--tag/--scope/--agent/--channel.")

        args = []
        if query_tokens:
            args.extend(["--query", " ".join(query_tokens)])
        if limit:
            args.extend(["--limit", limit])
        for kind in kinds:
            args.extend(["--type", kind])
        for tag in tags:
            args.extend(["--tag", tag])
        if scope:
            args.extend(["--scope", scope])
        for agent in agents:
            args.extend(["--agent", agent])
        for channel in channels:
            args.extend(["--channel", channel])
        if as_json:
            args.append("--json")
        if include_inactive:
            args.append("--include-inactive")
        return run_python("recall.py", args)

    if action == "remember":
        title: Optional[str] = None
        title_refined: Optional[str] = None
        source = "user"
        scope = "cross-project"
        note_tokens: List[str] = []
        tags: List[str] = []
        allow_duplicate = False
        as_json = False
        force_yes = False
        force_no = False
        standing = False
        as_kind = "inbox"
        channel: Optional[str] = None
        idx = 0
        while idx < len(rest):
            token = rest[idx]
            if token == "--title":
                idx += 1
                if idx >= len(rest):
                    raise YggError("`ygg remember --title` requires a value.")
                title = rest[idx]
            elif token == "--title-refined":
                idx += 1
                if idx >= len(rest):
                    raise YggError("`ygg remember --title-refined` requires a value.")
                title_refined = rest[idx]
            elif token == "--source":
                idx += 1
                if idx >= len(rest):
                    raise YggError("`ygg remember --source` requires a value.")
                source = rest[idx]
            elif token == "--scope":
                idx += 1
                if idx >= len(rest):
                    raise YggError("`ygg remember --scope` requires a value.")
                scope = rest[idx]
            elif token == "--channel":
                idx += 1
                if idx >= len(rest):
                    raise YggError("`ygg remember --channel` requires a value.")
                channel = rest[idx]
            elif token == "--tags":
                idx += 1
                while idx < len(rest) and not rest[idx].startswith("--"):
                    tags.append(rest[idx])
                    idx += 1
                continue
            elif token == "--allow-duplicate":
                allow_duplicate = True
            elif token == "--standing":
                standing = True
            elif token == "--as":
                idx += 1
                if idx >= len(rest):
                    raise YggError("`ygg remember --as` requires inbox|lesson|rule.")
                as_kind = rest[idx].lower()
                if as_kind not in ("inbox", "lesson", "rule"):
                    raise YggError("`ygg remember --as` must be inbox, lesson, or rule.")
            elif token == "--yes":
                force_yes = True
            elif token == "--no":
                force_no = True
            elif token == "--json":
                as_json = True
            else:
                note_tokens.append(token)
            idx += 1

        if not note_tokens:
            raise YggError("`ygg remember` requires note text.")
        if force_yes and force_no:
            raise YggError("`ygg remember` --yes 与 --no 不能同时使用")

        note_joined = " ".join(note_tokens)
        # 文字中的长期意图由记忆模块统一判定，避免路由层把否定或引用升级。

        args = ["--note", note_joined, "--source", source, "--scope", scope]
        if title:
            args.extend(["--title", title])
        if title_refined:
            args.extend(["--title-refined", title_refined])
        if channel:
            args.extend(["--channel", channel])
        if tags:
            args.append("--tags")
            args.extend(tags)
        if allow_duplicate:
            args.append("--allow-duplicate")
        if as_kind != "inbox":
            args.extend(["--as", as_kind])
        if standing:
            args.append("--standing")
        if force_yes:
            args.append("--yes")
        if force_no:
            args.append("--no")
        if as_json:
            args.append("--json")
        return run_python("remember.py", args)

    if action == "promote":
        destination: Optional[str] = None
        entries: List[str] = []
        name: Optional[str] = None
        dry_run = False
        allow_duplicate = False
        promote_all = False
        as_json = False
        force_yes = False
        force_no = False
        auto_promote = False
        standing = False
        objective = False
        idx = 0
        while idx < len(rest):
            token = rest[idx]
            lowered = token.lower()
            if lowered in ("lesson", "reference", "rule", "template", "decision") and destination is None:
                destination = lowered
            elif token == "--entry":
                idx += 1
                if idx >= len(rest):
                    raise YggError("`ygg promote --entry` requires a value.")
                entries.append(rest[idx])
            elif token == "--name":
                idx += 1
                if idx >= len(rest):
                    raise YggError("`ygg promote --name` requires a value.")
                name = rest[idx]
            elif token == "--dry-run":
                dry_run = True
            elif token == "--allow-duplicate":
                allow_duplicate = True
            elif token == "--all":
                promote_all = True
            elif token == "--auto":
                auto_promote = True
            elif token == "--standing":
                standing = True
            elif token == "--objective":
                objective = True
            elif token == "--yes":
                force_yes = True
            elif token == "--no":
                force_no = True
            elif token == "--json":
                as_json = True
            elif token.startswith("--"):
                raise YggError("Unrecognized `ygg promote` token: {0}".format(token))
            else:
                entries.append(token)
            idx += 1

        if not destination:
            raise YggError("`ygg promote` requires a destination type: lesson, reference, rule, template, or decision.")
        if not promote_all and not entries:
            raise YggError("`ygg promote` requires an inbox entry or --all.")
        if force_yes and force_no:
            raise YggError("`ygg promote` --yes 与 --no 不能同时使用")

        args = ["--to", destination]
        for entry in entries:
            args.extend(["--entry", entry])
        if name:
            args.extend(["--name", name])
        if dry_run:
            args.append("--dry-run")
        if allow_duplicate:
            args.append("--allow-duplicate")
        if promote_all:
            args.append("--all")
        if auto_promote:
            args.append("--auto")
        if standing:
            args.append("--standing")
        if objective:
            args.append("--objective")
        if force_yes:
            args.append("--yes")
        if force_no:
            args.append("--no")
        if as_json:
            args.append("--json")
        return run_python("promote.py", args)

    if action == "behavior":
        # ygg behavior [--json]  列出当前生效的 mode / dream / features
        as_json = "--json" in rest
        if str(SCRIPT_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPT_DIR))
        from policies.behavior import dream_settings, list_operation_modes, load_behavior_config

        cfg = load_behavior_config()
        rows = list_operation_modes(cfg)
        dream = dream_settings(cfg)
        features = cfg.get("features") or {}
        payload = {
            "default_mode": cfg.get("default_mode", "ask"),
            "operations": rows,
            "dream": dream,
            "features": features,
            "channel": cfg.get("channel") or {},
            "defaults_path": str(CORE_ROOT / "config" / "behavior.defaults.yaml"),
            "local_path": str(RUNTIME_ROOT / "config" / "behavior.local.yaml"),
            "channels_path": str(CORE_ROOT / "config" / "channels.yaml"),
        }
        if as_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print("behavior_default : {0}".format(payload["default_mode"]))
            print("behavior_defaults: {0}".format(payload["defaults_path"]))
            print("behavior_local   : {0}".format(payload["local_path"]))
            for row in rows:
                print("op {0} : {1}".format(row["operation"], row["mode"]))
            ch = payload["channel"]
            print("channel_unknown  : {0}".format(ch.get("unknown_policy")))
            print("channel_default  : {0}".format(ch.get("default")))
            print("channels_path    : {0}".format(payload["channels_path"]))
            print("dream_enabled    : {0}".format(dream.get("enabled")))
            print("dream_auto_run   : {0}".format(cfg.get("dream", {}).get("auto_run")))
            print("dream_intensity  : {0}".format(dream.get("intensity")))
            print("dream_depth      : {0}".format(dream.get("depth")))
            print("dream_period     : {0}".format(dream.get("period")))
            for key, val in sorted(features.items()):
                print("feature_{0} : {1}".format(key, val))
        return 0

    if action == "doctor":
        # 透传 --fix-deps / --yes / --no：检测并自动补装缺失依赖
        doc_args = [a for a in rest if a in ("--fix-deps", "--yes", "--no")]
        return run_python("doctor.py", doc_args)

    if action == "index":
        args = []
        idx = 0
        while idx < len(rest):
            token = rest[idx]
            if token in ("--check", "--dry-run", "--json"):
                args.append(token)
            else:
                raise YggError("Unrecognized `ygg index` token: {0}".format(token))
            idx += 1
        return run_python("index_knowledge.py", args)

    if action == "graph":
        # ygg graph build|check [--with-by-tag] [--skip-by-tag] [--dry-run] [--json]
        if not rest:
            raise YggError("`ygg graph` requires subcommand: build or check")
        sub = rest[0].lower()
        args = []
        if sub == "build":
            args.append("--build")
        elif sub == "check":
            args.append("--check")
        else:
            raise YggError("Unrecognized `ygg graph` subcommand: {0}".format(rest[0]))
        for token in rest[1:]:
            if token in ("--with-by-tag", "--skip-by-tag", "--dry-run", "--json"):
                args.append(token)
            else:
                raise YggError("Unrecognized `ygg graph` token: {0}".format(token))
        return run_python("graph_index.py", args)

    if action == "project":
        # ygg project mdc [--check|--write]
        if not rest:
            raise YggError("`ygg project` requires subcommand: mdc")
        sub = rest[0].lower()
        if sub != "mdc":
            raise YggError("Unrecognized `ygg project` subcommand: {0}".format(rest[0]))
        args: List[str] = []
        for token in rest[1:]:
            if token in ("--check", "--write"):
                args.append(token)
            else:
                raise YggError("Unrecognized `ygg project mdc` token: {0}".format(token))
        if not args:
            args.append("--write")
        return run_python("project_mdc.py", args)

    if action == "associate":
        # ygg associate --tag X [--tag Y] [--hop N] [--limit N] [--type T] [--no-entry-related] [--json]
        args = []
        idx = 0
        while idx < len(rest):
            token = rest[idx]
            if token == "--tag":
                idx += 1
                if idx >= len(rest):
                    raise YggError("`ygg associate --tag` requires a value.")
                args.extend(["--tag", rest[idx]])
            elif token == "--hop":
                idx += 1
                if idx >= len(rest):
                    raise YggError("`ygg associate --hop` requires a value.")
                args.extend(["--hop", rest[idx]])
            elif token == "--limit":
                idx += 1
                if idx >= len(rest):
                    raise YggError("`ygg associate --limit` requires a value.")
                args.extend(["--limit", rest[idx]])
            elif token == "--type":
                idx += 1
                if idx >= len(rest):
                    raise YggError("`ygg associate --type` requires a value.")
                args.extend(["--type", rest[idx]])
            elif token in ("--no-entry-related", "--json", "--include-inactive"):
                args.append(token)
            else:
                raise YggError("Unrecognized `ygg associate` token: {0}".format(token))
            idx += 1
        if "--tag" not in args:
            raise YggError("`ygg associate` requires at least one --tag.")
        return run_python("associate.py", args)

    if action == "tag":
        args = []
        idx = 0
        while idx < len(rest):
            token = rest[idx]
            if token == "--list":
                args.append("--list")
            elif token == "--add":
                args.append("--add")
                idx += 1
                while idx < len(rest) and not rest[idx].startswith("--"):
                    args.append(rest[idx])
                    idx += 1
                continue
            elif token == "--relate":
                idx += 1
                if idx + 1 >= len(rest):
                    raise YggError("`ygg tag --relate` requires two tags.")
                args.extend(["--relate", rest[idx], rest[idx + 1]])
                idx += 2
                continue
            elif token == "--set-weight":
                idx += 1
                if idx + 1 >= len(rest):
                    raise YggError("`ygg tag --set-weight` requires two tags.")
                args.extend(["--set-weight", rest[idx], rest[idx + 1]])
                idx += 2
                continue
            elif token == "--authority-writeback":
                idx += 1
                if idx + 1 >= len(rest):
                    raise YggError("`ygg tag --authority-writeback` requires two tags.")
                args.extend(["--authority-writeback", rest[idx], rest[idx + 1]])
                idx += 2
                continue
            elif token == "--weight":
                idx += 1
                if idx >= len(rest):
                    raise YggError("`ygg tag --weight` requires a number in [0,1].")
                args.extend(["--weight", rest[idx]])
            elif token == "--propagate":
                idx += 1
                if idx >= len(rest):
                    raise YggError("`ygg tag --propagate` requires a tag.")
                args.extend(["--propagate", rest[idx]])
            elif token == "--suggest":
                args.append("--suggest")
            elif token == "--apply":
                args.append("--apply")
            elif token == "--language":
                args.append("--language")
            elif token in ("--json", "--yes", "--no", "--dry-run"):
                args.append(token)
            else:
                raise YggError("Unrecognized `ygg tag` token: {0}".format(token))
            idx += 1
        if not args:
            raise YggError(
                "`ygg tag` requires --list, --add, --relate, --set-weight, "
                "--authority-writeback, --propagate, --suggest, or --language."
            )
        if "--language" in args:
            return run_python("tag_language.py", ["--json"] if "--json" in args else [])
        return run_python("tag_cli.py", args)

    raise YggError("Unknown explicit action: {0}".format(action))
