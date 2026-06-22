# Amagra — Launch Copy (debugger-led)

Issue #9 assets, reframed to lead with the **cross-model prompt debugger** — the
differentiated wedge. The memory/replay angle is kept as depth, not the headline.
Every claim below is fact-checked against the code.

> **GATE before posting:** the Run Across Models GUI button is endpoint-verified but
> not yet click-verified in a browser. Open the app, click **Run** in the Prompt
> Debugger, confirm result cards render, *then* post. Don't launch on an unverified click.

---

## ✅ Claims that are TRUE (safe to make)
- **Cross-model debugger is real:** `POST /debug/prompt` runs one prompt across N models
  concurrently and returns each output + latency + length, side by side. Verified live
  (ollama answered "Paris" in 2.4s; a second model ran in parallel, failures isolated).
- **Local works with zero key, offline:** default model **phi4-mini** via Ollama.
- **Cloud is BYO-key:** `anthropic` and `openai` ship in the image (`requirements.txt`);
  add your own Anthropic / OpenAI (or Groq / OpenRouter / Together / LM Studio) key to
  compare Claude/GPT against your local model. **Nothing is sent anywhere you didn't configure.**
- **Static prompt analysis** (heuristic, client-side): health score, missing-context
  detection, one-click auto-repair (role/format/constraints).
- **Persistent memory + replay** (depth, already shipped): SQLite → FAISS, and
  `/runs/{id}/replay` re-runs a past decision with routing + retrieved memory.
- MIT licensed, self-hosted. No phone-home, no third-party telemetry — local logs only.

## ⚠️ Claims to AVOID
- ❌ "Frontier-quality answers." Output quality = whatever model you point it at. Say so.
- ❌ Any bare accuracy % for routing. Not relevant to the debugger pitch — leave it out.
- ❌ "Diff / divergence view." Not built yet (scope #3). Outputs are shown stacked; *you*
  compare them. Don't claim automatic divergence highlighting.
- ❌ "No telemetry." There's a local `logs/telemetry.db`. Say "no phone-home, nothing
  leaves your machine."

---

## 1. Show HN post

**Title** (≤ 80 chars, HN style — plain, no hype):
```
Show HN: Amagra – Local prompt debugger that runs one prompt across Claude, GPT, and local models
```

**Body:**
```
I kept tweaking prompts blind — change a word, re-run, eyeball the output, repeat,
with no idea whether the problem was my prompt or the model. So I built Amagra: a
local prompt debugger.

You paste a prompt, hit Run, and it executes the SAME prompt across whatever models
you've configured — side by side, with latency and length for each. Local models
(via Ollama) work offline with no API key. Add your own Anthropic/OpenAI key and you
can put Claude or GPT next to your local model on the same prompt and see exactly
where they diverge.

Next to the run, a static analyzer scores the prompt, flags missing context for the
detected domain, and offers a one-click repair (adds role/output-format/constraints).

It also remembers your project across sessions and lets you replay any past decision —
that started as the whole app, but the debugger is the part I now use every day.

Honest about what it is:
- Output quality is whatever model you run — I don't fight on answer quality.
- The "diff" is your eyes for now; automatic divergence highlighting isn't built yet.
- Runs 100% locally. No phone-home, no third-party telemetry. MIT, self-hosted.

  docker pull d4shm1r/amagra        # or: git clone + docker compose up
  open http://localhost:8000

Solo-built. The prompt-debugging loop is the thing I'd love feedback on — does
cross-model side-by-side actually change how you write prompts, or is the static
analysis the more useful half?
```

**First comment to self-seed** (HN rewards the maintainer adding context):
```
Architecture notes for anyone curious: /debug/prompt fans out with asyncio +
worker threads so N models run concurrently (one slow/failing model never blocks
the others — it just shows its error in its own slot). Providers are pluggable:
Ollama, Anthropic, and any OpenAI-compatible endpoint share one interface. Happy
to go into the routing/memory layer if useful.
```

---

## 2. Docker Hub — publish steps (run these; nothing is pushed yet)

The Dockerfile already builds clean (`pip install -r requirements.txt`, serves
`uvicorn api:app` on 8000, `REQUIRE_AUTH=0`). To publish:

```bash
# 1. Log in (uses your Docker Hub account)
docker login

# 2. Build with version + latest tags (run from repo root)
docker build -t d4shm1r/amagra:1.2.0 -t d4shm1r/amagra:latest .

# 3. (Recommended) multi-arch so Apple Silicon + x86 both work:
#    docker buildx create --use --name amagra-builder   # once
#    docker buildx build --platform linux/amd64,linux/arm64 \
#      -t d4shm1r/amagra:1.2.0 -t d4shm1r/amagra:latest --push .

# 4. Or single-arch push:
docker push d4shm1r/amagra:1.2.0
docker push d4shm1r/amagra:latest

# 5. Smoke-test the published image from a clean dir:
docker run --rm -p 8000:8000 d4shm1r/amagra:latest
#    then: curl localhost:8000/health   → expect 200
```

After publishing, flip the README quick-start to `docker pull d4shm1r/amagra` and
update any "claims to avoid" line that currently says Docker Hub isn't live.

> Note: to actually reach a cloud model from inside the container you pass the key at
> run time, e.g. `-e BRAIN_PROVIDER=anthropic -e ANTHROPIC_API_KEY=...`. Local Ollama
> from a container needs `--add-host=host.docker.internal:host-gateway` and
> `OLLAMA_BASE_URL=http://host.docker.internal:11434`. Document both, or the first
> cross-model run will confuse people.

---

## 3. Homebrew — honest recommendation: defer it

Amagra is a FastAPI server + bundled UI, not a standalone CLI binary. Homebrew is built
for binaries/CLIs; shipping a Python web app + Ollama dependency through a formula is
awkward and high-maintenance, and Docker already covers the "one command to run" promise
better. **Recommendation: drop Homebrew from the v1 launch checklist** and keep the
Show HN + Docker Hub as the two real channels.

If you still want it later, the realistic shape is a formula that installs the package
and exposes a `amagra` launcher that runs uvicorn — sketch:

```ruby
class Amagra < Formula
  desc "Local cross-model prompt debugger with persistent memory"
  homepage "https://github.com/d4shm1r/amagra"
  url "https://github.com/d4shm1r/amagra/archive/refs/tags/v1.2.0.tar.gz"
  # sha256 "<fill after the release tarball exists>"
  license "MIT"
  depends_on "python@3.11"

  def install
    # virtualenv_install_with_resources or a venv + pip install -r requirements.txt,
    # then write a bin/amagra wrapper that execs: uvicorn api:app --port 8000
  end

  test do
    # assert_match "ok", shell_output("#{bin}/amagra --health")
  end
end
```

This needs a tagged GitHub **release** with a tarball + a real sha256 before it can work.
You already publish releases (latest v1.2.0), so a formula is feasible later — it's just
extra surface to maintain for a server app, which is why it's a "later," not a launch blocker.

---

## Updated issue #9 checklist
- [ ] **Show HN** — copy above; **gate on GUI click-verification first**
- [ ] **Docker Hub** — build/push steps above; smoke-test the pulled image; update README
- [ ] **Homebrew** — recommend deferring; not a v1 blocker
