"""Thin offline commands for bounded deterministic context utilities."""
from pathlib import Path
import json
from .contracts import ContractDenied
from .efficiency_tools import repo_outline,context_pack,tool_result_reduce,evidence_extract

HANDLED_COMMANDS=frozenset({'tools'})
def register(commands):
    tools=commands.add_parser('tools',help='Bounded deterministic local transforms')
    sub=tools.add_subparsers(dest='tool_command',required=True)
    outline=sub.add_parser('outline');outline.add_argument('--path',type=Path,required=True)
    reduce=sub.add_parser('reduce');reduce.add_argument('--input',type=Path,required=True);reduce.add_argument('--artifact-dir',type=Path,required=True);reduce.add_argument('--max-chars',type=int,default=12000)
    for parser in (outline,reduce):
        parser.add_argument('--namespace',choices=('dc','rf'),required=True);parser.add_argument('--role',required=True);parser.add_argument('--workspace',type=Path,required=True);parser.add_argument('--grant-file',type=Path,required=True)
    context=sub.add_parser('context-pack');context.add_argument('--input',type=Path,required=True);context.add_argument('--evidence-tokens',type=int,default=4000);context.add_argument('--context-tokens',type=int,default=32000)
    extract=sub.add_parser('extract');extract.add_argument('--html',type=Path,required=True);extract.add_argument('--provenance',type=Path,required=True)
    return HANDLED_COMMANDS

def _read(path,max_bytes=8*1024*1024):
    if any(p.is_symlink() for p in (path,*path.parents)):raise ContractDenied('input symlink denied')
    with path.open('rb') as f:raw=f.read(max_bytes+1)
    if len(raw)>max_bytes:raise ValueError('input exceeds local transform bound')
    return raw.decode('utf-8')

def execute(args,repository):
    operation=args.tool_command
    if operation in {'outline','reduce'}:
        from .runtime_authority import RuntimeAuthority
        from .registry_snapshot import compile_repository
        payload=json.loads(_read(args.grant_file))
        if set(payload)!={'role','layers'} or payload['role']!=args.namespace+':'+args.role:raise ContractDenied('invalid explicit tool grant')
        authority=RuntimeAuthority(args.namespace,args.workspace,snapshot=compile_repository(repository),task_layers=payload['layers'])
        if operation=='outline':return repo_outline(args.path,authority.effective(args.role))
        authority.tool(args.role,'filesystem.read',target=args.input)
        authority.tool(args.role,'filesystem.write',target=args.artifact_dir,write=True)
        return tool_result_reduce(json.loads(_read(args.input)),args.artifact_dir,max_chars=args.max_chars)
    if operation=='context-pack':
        payload=json.loads(_read(args.input));return context_pack(payload['protected'],payload['evidence'],evidence_tokens=args.evidence_tokens,max_context_tokens=args.context_tokens)
    if operation=='extract':return evidence_extract(_read(args.html,4*1024*1024),json.loads(_read(args.provenance)))
    raise ValueError('unknown utility')
