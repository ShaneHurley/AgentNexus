"""Offline model administration commands, independent of supervisor startup.

register() attaches parsers; execute() returns JSON-serializable results and raises
validation errors for the hosting CLI to render. No command constructs a provider.
"""
from __future__ import annotations
import json
from pathlib import Path
from .model_catalog import CatalogStore, digest
from .model_resolver import ModelResolver
from .evaluation import evaluate

HANDLED_COMMANDS = frozenset({"models", "eval", "usage-report"})


def register(parser_subcommands):
    models = parser_subcommands.add_parser("models", help="Inspect and explicitly activate reviewed model settings")
    commands = models.add_subparsers(dest="model_command", required=True)
    inspect = commands.add_parser("inspect", help="Inspect reviewed settings or an immutable catalog pin")
    inspect.add_argument("--catalog-hash")
    explain = commands.add_parser("explain", help="Explain eligibility without provider calls")
    explain.add_argument("--role", required=True)
    explain.add_argument("--requirements", required=True, help="Requirements JSON object")
    explain.add_argument("--environment", help="Availability JSON object; defaults to mock with no credentials")
    explain.add_argument("--override")
    publish = commands.add_parser("publish", help="Publish a validated candidate catalog without activation")
    publish.add_argument("--catalog", type=Path, required=True)
    diff = commands.add_parser("diff", help="Compare two published catalog pins")
    diff.add_argument("old_hash")
    diff.add_argument("new_hash")
    activate = commands.add_parser("activate", help="Confirm a matching catalog and reviewed policy pair")
    activate.add_argument("--catalog-hash", required=True)
    activate.add_argument("--policy", type=Path, required=True)
    activate.add_argument("--policy-hash", required=True, help="Expected full canonical policy snapshot hash")
    activate.add_argument("--confirm", action="store_true")
    for command in (inspect, explain, publish, diff, activate):
        command.add_argument("--directory", type=Path, help="Model snapshot directory")
    evaluation = parser_subcommands.add_parser("eval", help="Evaluate pinned offline task records")
    evaluation.add_argument("--records", type=Path, required=True)
    for flag in ("role", "evaluation-class", "candidate", "baseline", "corpus-hash", "catalog-hash", "routing-policy-hash"):
        evaluation.add_argument("--" + flag, required=True)
    evaluation.add_argument("--evidence-kind", choices=("mock", "measured"), default="mock")
    usage = parser_subcommands.add_parser("usage-report", help="Aggregate offline usage JSON; preserve unknown costs")
    usage.add_argument("--records", type=Path, required=True)
    return HANDLED_COMMANDS


def _reject_constant(value):
    raise ValueError("nonfinite JSON number")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _json(text):
    return json.loads(text, parse_constant=_reject_constant, object_pairs_hook=_unique_object)


def _object(text):
    value = _json(text)
    if not isinstance(value, dict): raise ValueError("JSON object required")
    return value


def _records(path):
    value = _json(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError("JSON record array required")
    return value


def _configuration(path):
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        import yaml
        value = yaml.safe_load(text)
    else:
        value = _json(text)
    if not isinstance(value, dict): raise ValueError("configuration object required")
    return value


def _existing_store(directory):
    # CatalogStore creates its directory; read-only commands must check first.
    if not directory.is_dir(): raise ValueError("model snapshot directory does not exist")
    return CatalogStore(directory)


def execute(args, repository):
    """Dispatch only offline commands; all live execution stays with the host CLI.

    Evaluation --routing-policy-hash is routing_policy_digest(policy), excluding
    embedded qualifications. Activation --policy-hash pins the full policy instead.
    Publishing a candidate never activates it; --confirm authorizes one exact pair.
    """
    if args.command == "eval":
        return evaluate(_records(args.records), role=args.role, evaluation_class=args.evaluation_class,
                        candidate=args.candidate, baseline=args.baseline, corpus_hash=args.corpus_hash,
                        catalog_hash=args.catalog_hash, policy_hash=args.routing_policy_hash,
                        evidence_kind=args.evidence_kind)
    if args.command == "usage-report":
        from .efficiency_tools import usage_report
        return usage_report(_records(args.records))
    if args.command != "models": raise ValueError("unsupported offline command")
    directory = Path(args.directory) if args.directory is not None else Path(repository) / ".agentnexus/models"
    if args.model_command == "publish":
        # Validation occurs before constructing a store, avoiding writes on bad input.
        from .model_catalog import CatalogSnapshot
        candidate = CatalogSnapshot.from_dict(_configuration(args.catalog))
        snapshot = CatalogStore(directory).publish(candidate.data)
        return {"catalog_hash": snapshot.hash, "activated": False}
    if args.model_command == "diff":
        return _existing_store(directory).diff(args.old_hash, args.new_hash)
    if args.model_command == "activate":
        if args.confirm is not True: raise ValueError("model activation requires --confirm")
        policy = _configuration(args.policy)
        if digest(policy) != args.policy_hash: raise ValueError("confirmed policy hash mismatch")
        snapshot = _existing_store(directory).load(args.catalog_hash)
        ModelResolver(snapshot, policy)
        from .routing_runtime import activate_model_settings
        return activate_model_settings(directory, args.catalog_hash, policy, confirmed=True)
    if args.model_command == "inspect" and args.catalog_hash is not None:
        snapshot = _existing_store(directory).load(args.catalog_hash)
        return {"catalog_hash": snapshot.hash, "model_catalog": snapshot.data}
    if args.model_command in {"inspect", "explain"}:
        from .routing_runtime import load_model_settings
        settings = load_model_settings(repository, directory=directory)
        if args.model_command == "inspect": return settings
        requirements = _object(args.requirements)
        environment = (_object(args.environment) if args.environment is not None
                       else {"available_providers": ["mock"], "available_credentials": []})
        return ModelResolver(settings["model_catalog"], settings["model_policy"]).explain(
            args.role, requirements, environment, args.override)
    raise ValueError("unsupported model command")
