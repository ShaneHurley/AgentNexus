"""A fail-closed Docker worker. Repository writes remain gateway-owned."""
from __future__ import annotations
import fnmatch, os, re, shutil, stat, subprocess, tempfile, time, selectors, signal
from .lifecycle import ReconciliationRequired
from pathlib import Path
from .skills.secret_scanner import SECRET_PATTERNS

class IsolationUnavailable(PermissionError): pass

class DockerRunner:
    def __init__(self, image: str, workspace: str | Path, *, deny_paths=()):
        if not re.fullmatch(r"[a-zA-Z0-9./_:-]+@sha256:[a-f0-9]{64}", image):
            raise ValueError("isolated image must be pinned by sha256 digest")
        self.image=image; self.workspace=Path(workspace).resolve(); self.deny_paths=tuple(deny_paths)
        if not self.workspace.is_dir(): raise ValueError("workspace must exist")

    def _snapshot(self, destination):
        count=total=0
        def private(name):
            return name.startswith('.') or any(x in name.lower() for x in ('secret','credential','id_rsa'))
        root_fd=os.open(self.workspace,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            # Directory descriptors bind reads to inspected directories even if
            # another process renames a parent or replaces it with a symlink.
            for directory, directories, files, directory_fd in os.fwalk(".",follow_symlinks=False,dir_fd=root_fd):
                directories[:]=[name for name in directories if not private(name)]
                for name in files:
                    rel=Path(directory)/name
                    if private(name): continue
                    if any(fnmatch.fnmatch(rel.as_posix(),g) for g in self.deny_paths): continue
                    if rel.suffix.lower() in {'.pem','.key'}: continue
                    metadata=os.stat(name,dir_fd=directory_fd,follow_symlinks=False)
                    if not stat.S_ISREG(metadata.st_mode): continue
                    descriptor=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory_fd)
                    with os.fdopen(descriptor,'rb') as stream:
                        metadata=os.fstat(stream.fileno())
                        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 64*1024*1024:
                            raise IsolationUnavailable("workspace file exceeds snapshot boundary")
                        sample=stream.read(64*1024*1024+1)
                    total+=len(sample); count+=1
                    if total > 256*1024*1024 or count > 20000 or len(sample) > 64*1024*1024:
                        raise IsolationUnavailable("workspace snapshot exceeds resource ceiling")
                    if any(pattern.search(sample.decode('utf-8',errors='ignore')) for _,pattern in SECRET_PATTERNS): continue
                    target=destination/rel; target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(sample)
                    target.chmod(0o555 if metadata.st_mode & 0o111 else 0o444)
        finally:
            os.close(root_fd)

    def _attach(self, command, env, timeout, cancel_check):
        """Drain bounded output while supervising an owned client process group."""
        process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,start_new_session=True)
        selector=selectors.DefaultSelector(); buffers={}
        deadline=time.monotonic()+timeout
        cancelled=timed_out=False
        try:
            for stream in (process.stdout,process.stderr):
                os.set_blocking(stream.fileno(),False)
                selector.register(stream,selectors.EVENT_READ); buffers[stream]=bytearray()
            while selector.get_map():
                cancelled=bool(cancel_check())
                timed_out=time.monotonic() >= deadline
                if cancelled or timed_out: break
                for key,_ in selector.select(.1):
                    chunk=os.read(key.fileobj.fileno(),8192)
                    if not chunk: selector.unregister(key.fileobj)
                    else: buffers[key.fileobj].extend(chunk[:max(0,20000-len(buffers[key.fileobj]))])
            if cancelled or timed_out:
                if process.poll() is None:
                    os.killpg(process.pid,signal.SIGTERM)
                    try: process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid,signal.SIGKILL)
                        process.wait(timeout=2)
            else: process.wait(timeout=max(.1,deadline-time.monotonic()))
            return {"returncode":process.returncode,"timeout":timed_out,"cancelled":cancelled,
                    "cancellation_confirmed":cancelled,"stdout":buffers[process.stdout].decode(errors='replace'),
                    "stderr":buffers[process.stderr].decode(errors='replace')}
        except (OSError,subprocess.TimeoutExpired) as exc:
            raise ReconciliationRequired("worker client termination unconfirmed") from exc
        finally:
            selector.close()
            if process.poll() is None:
                try:
                    os.killpg(process.pid,signal.SIGKILL); process.wait(timeout=2)
                except (OSError,subprocess.TimeoutExpired) as exc:
                    raise ReconciliationRequired("worker client termination unconfirmed") from exc
            process.stdout.close(); process.stderr.close()

    def run(self, argv, *, timeout=900, cancel_check=None):
        if not isinstance(argv,list) or not argv or any(not isinstance(x,str) or '\x00' in x for x in argv):
            raise ValueError("argv must be a nonempty string list")
        timeout=int(timeout)
        if timeout < 1 or timeout > 900: raise ValueError("timeout outside worker ceiling")
        if cancel_check is not None and cancel_check():
            return {'argv':argv,'returncode':None,'timeout':False,'cancelled':True,'cancellation_confirmed':True,'stdout':'','stderr':'','duration_s':0.0}
        executable=shutil.which('docker')
        if not executable: raise IsolationUnavailable("Docker CLI is unavailable")
        env={'PATH':os.environ.get('PATH','/usr/bin:/bin')}
        # The host socket is used by the supervisor only, never mounted into workers.
        sock=Path.home()/'.docker/run/docker.sock'
        if sock.exists(): env['DOCKER_HOST']='unix://'+str(sock)
        started=time.monotonic(); container=None
        with tempfile.TemporaryDirectory(prefix='agentnexus-worker-') as temp:
            scratch=Path(temp); workspace=scratch/'workspace'; workspace.mkdir()
            self._snapshot(workspace)
            env['DOCKER_CONFIG']=str(scratch/'docker-config'); Path(env['DOCKER_CONFIG']).mkdir()
            command=[executable,'create','--pull=never','--network=none','--read-only','--cap-drop=ALL',
                     '--security-opt=no-new-privileges','--user=65534:65534','--pids-limit=128','--memory=512m',
                     '--cpus=1','--ulimit=nofile=128:128','--workdir=/workspace',
                     '--mount',f'type=bind,src={workspace},dst=/workspace,readonly',
                     '--tmpfs=/tmp:rw,noexec,nosuid,size=67108864,mode=1777',
                     '--tmpfs=/outputs:rw,noexec,nosuid,size=67108864,mode=1777',
                     '--env=HOME=/tmp','--env=PYTHONDONTWRITEBYTECODE=1',self.image,*argv]
            try:
                cp=subprocess.run(command,capture_output=True,text=True,timeout=30,env=env)
                if cp.returncode: raise IsolationUnavailable("Docker worker creation failed; check daemon and reviewed image")
                container=cp.stdout.strip()
                if not re.fullmatch(r'[a-zA-Z0-9]+',container): raise IsolationUnavailable("invalid Docker container identity")
                try:
                    if cancel_check is not None:
                        if cancel_check():
                            result={'argv':argv,'returncode':None,'timeout':False,'cancelled':True,'cancellation_confirmed':True,'stdout':'','stderr':''}
                        else:
                            result={'argv':argv,**self._attach([executable,'start','--attach',container],env,timeout,cancel_check)}
                    else:
                        result={'argv':argv,**self._attach([executable,'start','--attach',container],env,timeout,lambda:False)}
                except subprocess.TimeoutExpired:
                    result={'argv':argv,'returncode':None,'timeout':True,'stdout':'','stderr':'isolated worker timed out'}
                result['duration_s']=round(time.monotonic()-started,3)
                return result
            except (OSError,subprocess.TimeoutExpired) as exc:
                raise IsolationUnavailable("isolated worker transport failed") from exc
            finally:
                if container:
                    try: removed=subprocess.run([executable,'rm','--force',container],capture_output=True,text=True,timeout=30,env=env)
                    except (OSError,subprocess.TimeoutExpired) as exc:
                        failure=ReconciliationRequired if cancel_check is not None else IsolationUnavailable
                        raise failure("worker termination unconfirmed") from exc
                    if removed.returncode:
                        failure=ReconciliationRequired if cancel_check is not None else IsolationUnavailable
                        raise failure("worker termination unconfirmed")
