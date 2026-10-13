"""Prepare an explicit user-task contract; never infer authority from model output."""
import argparse
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
from agent_core.task_contract import validate_contract

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--workspace",type=Path,required=True)
    parser.add_argument("--request-file",type=Path,required=True)
    parser.add_argument("--allowed-path",action="append",required=True)
    parser.add_argument("--operation",action="append",choices=("create","modify"),required=True)
    parser.add_argument("--criterion",action="append",required=True)
    parser.add_argument("--verification-argv",action="append",required=True,help="Exact JSON argument-vector array")
    parser.add_argument("--output",type=Path,required=True,help="New explicit authority record; existing records are never overwritten")
    parser.add_argument("--tokens",type=int,default=80000)
    parser.add_argument("--calls",type=int,default=16)
    parser.add_argument("--repair-cycles",type=int,default=1)
    parser.add_argument("--tool-rounds",type=int,default=4)
    parser.add_argument("--deadline-seconds",type=int,default=900)
    args=parser.parse_args(argv)
    request=args.request_file.read_bytes().decode("utf-8")
    contract={"schema_version":1,"request_sha256":hashlib.sha256(request.encode()).hexdigest(),
      "workspace":str(args.workspace.resolve()),"acceptance_criteria":args.criterion,
      "allowed_paths":args.allowed_path,"operations":args.operation,
      "verification_commands":[json.loads(value) for value in args.verification_argv],
      "limits":{"tokens":args.tokens,"calls":args.calls,"repair_cycles":args.repair_cycles,
                "tool_rounds":args.tool_rounds,"verification_timeout":120,"deadline_seconds":args.deadline_seconds},
      "authorization_source":"user-task","authorized_at":datetime.now(timezone.utc).isoformat()}
    contract=validate_contract(contract,request,args.workspace,parent_tokens=args.tokens)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf-8") as handle:
        json.dump(contract,handle,indent=2,allow_nan=False)
        handle.write("\n")
    print(json.dumps({"task_contract":str(args.output.resolve()),"request_sha256":contract["request_sha256"]}))
    return 0

if __name__=="__main__":raise SystemExit(main())
