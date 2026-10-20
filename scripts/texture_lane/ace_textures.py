"""Wave-2 texture beds for 285 Hz (Drift "心身の回復"): three unpitched ACE-Step soundscapes, 90 s each.
Positive-only prompts (no negations), lyrics="[inst]" (whole-field instrumental flag), no bpm/key.
Takes the GPU lock (optional), downloads the 48 kHz float wavs, releases the lock.

    python scripts/texture_lane/ace_textures.py --out <work>/bed-src [--api URL] [--lock PATH [--lock-ssh USER@HOST]]

ACE-Step 1.5 API base URL: --api or $ACESTEP_API_URL (required, no default).
GPU lock file (shared GPU etiquette): --lock or $ACESTEP_GPU_LOCK; unset = no locking.
  The lock is written/removed locally, or on the GPU host via ssh (Windows cmd there) when
  --lock-ssh / $ACESTEP_GPU_LOCK_SSH is set. Use the Windows ssh.exe (PowerShell), not Git-Bash ssh.
Writes <out>/<tag>-90s-48kf32.wav and <out>/ace-textures-manifest.json.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

TEXTURES = [
    ("ace-T1-rain-leaves",
     "ambient field recording soundscape, soft steady rain falling on broad tropical leaves at night, fine droplets, "
     "gentle continuous hiss, distant and enveloping, very even, calm, pure nature sound design, wide stereo, long unchanging take"),
    ("ace-T2-tape-wind",
     "sound design texture, warm analog tape hiss, slow breathing wind moving through a wooden corridor, faint vinyl crackle, "
     "soft air pressure swells every twenty seconds, enveloping, calm, continuous, wide stereo, long unchanging take"),
    ("ace-T3-ocean-air",
     "ambient field recording soundscape, distant ocean surf at night heard through a window, soft foam washing over sand, "
     "faint high shimmer of humid air, slow tidal swells, calm, continuous, wide stereo, long unchanging take"),
]
SEED_BASE = 285000
LOCK_NOTE = "owner=music-stack task=wave2-ace-textures-x3 eta_min=20"
SSH_OPTS = ["-o", "IdentitiesOnly=yes", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15"]


class Api:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def post(self, path, payload, timeout=300):
        req = urllib.request.Request(self.base + path, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())

    def submit(self, prompt, seed, with_meta=False):
        body = {"prompt": prompt, "lyrics": "[inst]", "audio_duration": 90,
                "vocal_language": "english", "audio_format": "wav",
                "thinking": False, "use_cot_caption": False, "use_cot_language": False,
                "use_random_seed": False, "seed": seed, "inference_steps": 8, "batch_size": 1,
                "infer_method": "ode", "shift": 2.4, "model": "acestep-v15-turbo"}
        if with_meta:
            body.update({"bpm": 60, "key_scale": "Am"})
        return self.post("/release_task", body)["data"]["task_id"]


class GpuLock:
    """Lock file on the GPU host: local path, or remote (ssh + Windows cmd) when ssh_target is set."""

    def __init__(self, path: str | None, ssh_target: str | None, ssh_key: str):
        self.path, self.ssh_target = path, ssh_target
        self.ssh_key = os.path.expanduser(ssh_key)

    def _ssh(self, args, timeout=120):
        r = subprocess.run(["ssh", "-i", self.ssh_key] + SSH_OPTS + [self.ssh_target] + args,
                           capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            print(f"WARNING lock ssh exit {r.returncode}: {r.stderr.strip()[-200:]}", flush=True)

    def acquire(self):
        if not self.path:
            print("NO LOCK (no --lock / ACESTEP_GPU_LOCK)", flush=True)
            return
        if self.ssh_target:
            self._ssh(["cmd", "/c", f"echo {LOCK_NOTE} >", self.path])
        else:
            Path(self.path).write_text(LOCK_NOTE + "\n", encoding="utf-8")
        print("LOCK SET", flush=True)

    def release(self):
        if not self.path:
            return
        if self.ssh_target:
            self._ssh(["cmd", "/c", "del", self.path])
        else:
            Path(self.path).unlink(missing_ok=True)
        print("LOCK RELEASED", flush=True)


def generate(api: Api, out: Path) -> list[dict]:
    try:
        print("INIT:", api.post("/v1/init", {"init_llm": False}).get("data", {}).get("loaded_model"), flush=True)
    except Exception as e:
        print("INIT ERR:", e, flush=True)
    manifest = []
    for i, (tag, prompt) in enumerate(TEXTURES):
        seed = SEED_BASE + i
        try:
            tid = api.submit(prompt, seed)
            meta = "none"
        except Exception as e:
            print(f"[{tag}] submit without bpm/key failed ({str(e)[:80]}); retrying with bpm/key", flush=True)
            tid = api.submit(prompt, seed, with_meta=True)
            meta = "bpm60/Am"
        print(f"[{tag}] seed={seed} meta={meta} -> {tid}", flush=True)
        t0 = time.time()
        while time.time() - t0 < 1800:
            time.sleep(30)
            try:
                it = api.post("/query_result", {"task_id_list": [tid]}, timeout=30)["data"][0]
            except Exception as e:
                print(f"[{tag}] query err: {e}", flush=True)
                continue
            if it["status"] == 0:
                print(f"[{tag}] {int(time.time()-t0)}s running", flush=True)
                continue
            if it["status"] == 2:
                print(f"[{tag}] FAILED {(it.get('progress_text') or '')[-200:]}", flush=True)
                break
            url = json.loads(it["result"])[0]["file"]
            dest = out / (tag + "-90s-48kf32.wav")
            urllib.request.urlretrieve(api.base + url, dest)
            win = urllib.parse.unquote(urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["path"][0])
            manifest.append({"tag": tag, "seed": seed, "task_id": tid, "prompt": prompt, "meta": meta,
                             "worker_path": win, "local": str(dest), "bytes": os.path.getsize(dest)})
            print(f"[{tag}] DONE {int(time.time()-t0)}s -> {dest} ({os.path.getsize(dest)//1024} KB)", flush=True)
            break
        else:
            print(f"[{tag}] TIMEOUT", flush=True)
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="generate the three 90 s ACE-Step texture beds (GPU, via the ACE-Step API)")
    ap.add_argument("--out", required=True, help="bed folder (outside the repo), e.g. <work>/bed-src")
    ap.add_argument("--api", default=os.environ.get("ACESTEP_API_URL"),
                    help="ACE-Step API base URL (default: $ACESTEP_API_URL; required)")
    ap.add_argument("--lock", default=os.environ.get("ACESTEP_GPU_LOCK"),
                    help="GPU lock file path (default: $ACESTEP_GPU_LOCK; unset = no locking)")
    ap.add_argument("--lock-ssh", default=os.environ.get("ACESTEP_GPU_LOCK_SSH"), metavar="USER@HOST",
                    help="write/remove the lock on this ssh host (default: $ACESTEP_GPU_LOCK_SSH; unset = local file)")
    ap.add_argument("--ssh-key", default="~/.ssh/id_ed25519", help="ssh identity for --lock-ssh")
    a = ap.parse_args(argv)
    if not a.api:
        ap.error("ACE-Step API URL required: --api URL or set ACESTEP_API_URL")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    lock = GpuLock(a.lock, a.lock_ssh, a.ssh_key)
    lock.acquire()
    try:
        manifest = generate(Api(a.api), out)
    finally:
        lock.release()
    (out / "ace-textures-manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print("ALL DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
