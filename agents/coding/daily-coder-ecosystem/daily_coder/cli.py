from __future__ import annotations

import argparse, json
from pathlib import Path
from .budget import BudgetManager, DailyCapExceeded
from .evolution import EvolutionManager
from .jobs import JobManager
from .orchestrator import Orchestrator
from .providers.registry import PROVIDERS, build_provider, is_live
from .secrets import SecretStore
from .skills import SkillLibrary
from .state_store import StateStore
from .util import load_json
from .validation import validate_tree

def root(): return Path(__file__).resolve().parent.parent
def runtime():
    p=root()/'.daily-coder'; p.mkdir(exist_ok=True); return p

def _orchestrator(args, store):
    config=load_json(root()/'config/default.json')
    secrets=SecretStore(runtime()/'secrets.json')
    name=getattr(args,'provider','mock')
    live=is_live(name)
    if live and config.get("require_live_flag",True) and not getattr(args,'live',False):
        raise SystemExit(f"provider '{name}' spends real credits; re-run with --live to confirm")
    provider=build_provider(name,config=config,secrets=secrets,
                            command=getattr(args,'provider_command',None),
                            endpoint=getattr(args,'provider_endpoint',None))
    return Orchestrator(root(),store,provider,live=live,secrets=secrets)

def _provider_args(parser):
    parser.add_argument('--provider',choices=list(PROVIDERS),default='mock')
    parser.add_argument('--provider-command')
    parser.add_argument('--provider-endpoint')
    parser.add_argument('--live',action='store_true',help='confirm a credit-spending provider')

def main(argv=None):
    ap=argparse.ArgumentParser(prog='daily-coder'); sub=ap.add_subparsers(dest='cmd',required=True)

    run=sub.add_parser('run'); run.add_argument('--request',required=True); run.add_argument('--repo',default='.'); _provider_args(run)
    resume=sub.add_parser('resume'); resume.add_argument('run_id'); _provider_args(resume)
    status=sub.add_parser('status'); status.add_argument('run_id')
    runs=sub.add_parser('runs'); runs.add_argument('--limit',type=int,default=20)
    sub.add_parser('validate'); sub.add_parser('doctor')

    approve=sub.add_parser('approve'); approve.add_argument('run_id')
    approve.add_argument('--kind',default='plan'); approve.add_argument('--actor',default='cli-user')
    approve.add_argument('--reject',action='store_true'); approve.add_argument('--note')

    pending=sub.add_parser('pending')

    jobs=sub.add_parser('jobs'); jobs.add_argument('--run-id'); jobs.add_argument('--active',action='store_true')
    job=sub.add_parser('job'); job.add_argument('job_id'); job.add_argument('--cancel',action='store_true')

    secrets_cmd=sub.add_parser('secrets'); secrets_sub=secrets_cmd.add_subparsers(dest='secret_cmd',required=True)
    secrets_sub.add_parser('list')
    s_set=secrets_sub.add_parser('set'); s_set.add_argument('name'); s_set.add_argument('value')
    s_del=secrets_sub.add_parser('delete'); s_del.add_argument('name')

    spend=sub.add_parser('spend'); spend.add_argument('--run-id')
    benchmark=sub.add_parser('benchmark'); benchmark.add_argument('--output')
    benchmark.add_argument('--baseline')
    benchmark.add_argument('--repeats',type=int,default=1)
    benchmark.add_argument('--gate',action='store_true',
                           help='exit 1 when baseline compare fails routing or >10%% cost regression')
    sub.add_parser('skills')

    cands=sub.add_parser('candidates'); cands.add_argument('--state')
    evaluate=sub.add_parser('evaluate'); evaluate.add_argument('candidate_id')
    evaluate.add_argument('--frozen-command',required=True); evaluate.add_argument('--holdout-command',required=True)
    evaluate.add_argument('--timeout',type=int,default=1800)
    promote=sub.add_parser('promote'); promote.add_argument('candidate_id'); promote.add_argument('--actor',default='cli-user')
    rollback=sub.add_parser('rollback'); rollback.add_argument('candidate_id'); rollback.add_argument('--actor',default='cli-user')

    serve=sub.add_parser('serve'); serve.add_argument('--host'); serve.add_argument('--port',type=int)
    serve.add_argument('--token'); _provider_args(serve)

    gh=sub.add_parser('github'); gh_sub=gh.add_subparsers(dest='github_cmd',required=True)
    gh_clone=gh_sub.add_parser('clone'); gh_clone.add_argument('url'); gh_clone.add_argument('--dest')
    gh_meta=gh_sub.add_parser('repo'); gh_meta.add_argument('url')
    gh_pulls=gh_sub.add_parser('pulls'); gh_pulls.add_argument('url'); gh_pulls.add_argument('--state',default='open')

    a=ap.parse_args(argv); store=StateStore(runtime()/'state.sqlite')
    config=load_json(root()/'config/default.json')

    if a.cmd=='github':
        from .github_remote import (
            GitHubRemoteError,
            clone_github_repo,
            list_pulls,
            parse_github_https_url,
            repo_metadata,
            resolve_github_token,
        )
        secrets=SecretStore(runtime()/'secrets.json')
        token=resolve_github_token(secrets)
        roots=[Path(p).resolve() if Path(p).is_absolute() else (root()/p).resolve()
               for p in config.get('server',{}).get('allowed_repo_roots',['.'])]
        try:
            if a.github_cmd=='clone':
                out=clone_github_repo(a.url, allowed_roots=roots, dest=Path(a.dest) if a.dest else None, token=token)
            elif a.github_cmd=='repo':
                owner,repo,_=parse_github_https_url(a.url)
                out=repo_metadata(owner,repo,token=token)
            else:
                owner,repo,_=parse_github_https_url(a.url)
                out=list_pulls(owner,repo,state=a.state,token=token)
        except GitHubRemoteError as exc:
            raise SystemExit(str(exc))
        print(json.dumps(out,indent=2)); return

    if a.cmd=='validate':
        errors=validate_tree(root()); print(json.dumps({'ok':not errors,'errors':errors},indent=2)); raise SystemExit(bool(errors))
    if a.cmd=='doctor':
        print(json.dumps({'python':'ok','tree_errors':validate_tree(root()),'runtime':str(runtime()),
                          'providers':list(PROVIDERS),'secrets':SecretStore(runtime()/'secrets.json').list()},indent=2)); return
    if a.cmd=='status':
        row=store.get(a.run_id)
        row['pending_approvals']=[x for x in store.pending_approvals() if x['run_id']==a.run_id]
        row['jobs']=store.jobs(a.run_id)
        print(json.dumps(row,indent=2,default=str)); return
    if a.cmd=='runs':
        print(json.dumps(store.list_runs(a.limit),indent=2,default=str)); return
    if a.cmd=='pending':
        print(json.dumps(store.pending_approvals(),indent=2,default=str)); return
    if a.cmd=='approve':
        row=store.get(a.run_id)
        ok=store.decide_approval(a.run_id,a.kind,row.get('plan_hash'),'rejected' if a.reject else 'approved',a.actor,a.note)
        print(json.dumps({'run_id':a.run_id,'kind':a.kind,'decided':ok,
                          'state':store.approval_state(a.run_id,a.kind,row.get('plan_hash'))},indent=2)); return
    if a.cmd=='jobs':
        print(json.dumps(store.jobs(a.run_id,a.active),indent=2,default=str)); return
    if a.cmd=='job':
        manager=JobManager(store,runtime()/'jobs')
        result=manager.cancel(a.job_id) if a.cancel else manager.poll(a.job_id)
        print(json.dumps(result,indent=2,default=str)); return
    if a.cmd=='secrets':
        store_s=SecretStore(runtime()/'secrets.json')
        if a.secret_cmd=='list': print(json.dumps(store_s.list(),indent=2))
        elif a.secret_cmd=='set': print(json.dumps(store_s.set(a.name,a.value),indent=2))
        else: print(json.dumps({'deleted':store_s.delete(a.name)},indent=2))
        return
    if a.cmd=='spend':
        import datetime
        budget=BudgetManager(load_json(root()/'config/budgets.json'),store,
                             pricing=load_json(root()/'config/pricing.json'),limits=config.get('limits',{}))
        report=budget.report(a.run_id) if a.run_id else {'today':store.spend(datetime.date.today().isoformat()),
                                                         'limits':config.get('limits',{})}
        print(json.dumps(report,indent=2,default=str)); return
    if a.cmd=='benchmark':
        from .benchmark import run_benchmark, baseline_gate_failures, exit_code_for_gate
        report=run_benchmark(root(),a.output,a.baseline,a.repeats)
        print(json.dumps(report,indent=2,default=str))
        if a.gate:
            if not a.baseline:
                raise SystemExit("--gate requires --baseline")
            failures=baseline_gate_failures(report)
            if failures:
                for line in failures:
                    print(f"benchmark gate: {line}", flush=True)
                raise SystemExit(exit_code_for_gate(report))
        return
    if a.cmd=='skills':
        print(json.dumps(SkillLibrary(root()/'skills').index(),indent=2)); return
    if a.cmd=='candidates':
        print(json.dumps(store.candidates(a.state),indent=2,default=str)); return
    if a.cmd=='evaluate':
        verdict=EvolutionManager(root(),store).evaluate_commands(a.candidate_id,a.frozen_command,a.holdout_command,a.timeout)
        print(json.dumps({'candidate_id':a.candidate_id,'verdict':verdict},indent=2)); return
    if a.cmd in ('promote','rollback'):
        manager=EvolutionManager(root(),store)
        action=manager.promote if a.cmd=='promote' else manager.rollback
        print(json.dumps(action(a.candidate_id,a.actor),indent=2)); return
    if a.cmd=='serve':
        from .server import serve as run_server
        orch=_orchestrator(a,store)
        server_cfg=config.get('server',{})
        run_server(store,orch,root(),host=a.host or server_cfg.get('host','127.0.0.1'),
                   port=a.port or server_cfg.get('port',8765),token=a.token,
                   auth_required=server_cfg.get('auth_required',True)); return

    orch=_orchestrator(a,store)
    try:
        result=orch.start(a.request,a.repo) if a.cmd=='run' else orch.run(a.run_id)
    except DailyCapExceeded as exc:
        raise SystemExit(f"daily spend cap reached: {exc}")
    result['cost']=orch.budget.report(result['run_id'])
    print(json.dumps(result,indent=2,default=str))
