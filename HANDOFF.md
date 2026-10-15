# Handoff: point tracker interface (draft)

Branch: `point-tracker-api-draft`. Temporary file, delete before merging.

## Goal

Run point trackers (starting with CoTracker3) through a common interface,
each tracker in its own isolated uv env, as a first step towards the
train/infer/compare workflow for PoseMark.

## Current state

Everything is a skeleton: signatures, types and docstrings only. Bodies
raise `NotImplementedError` and the tests are empty.

```
poseinterface/trackers.py          # PointTracker ABC + PoseMark <-> array helpers (no torch)
tests/test_unit/test_trackers.py   # base-class tests, main env, StaticTracker dummy
envs/cotracker3/
  pyproject.toml                   # standalone uv project (NOT a workspace member)
  infer.py                         # CoTracker3(PointTracker) + CLI
  tests/test_infer.py              # tool tests, run inside this env
```

### Design decisions

- **No uv workspace.** A workspace shares a single lockfile across all
  members, which defeats per-tool isolation. Each env depends on
  `poseinterface` via `{ path = "../..", editable = true }` and gets its
  own `.venv` and `uv.lock`.
- **The base class lives in the main package** and must never import
  torch or any other tool dependency. Concrete trackers live only in
  their env, and the main env never imports them: it calls them with
  `uv run --project envs/<tool> python envs/<tool>/infer.py ...`.
- **Contract:** subclasses implement only
  `track(video (T,H,W,3), queries (N,3) as t,x,y) -> tracks (T,N,2), visibility (T,N)`.
  The inherited `run()` handles PoseMark I/O: it reads `startlabels.json`
  and the clip, then writes predictions as **clip labels**, so they can
  be compared directly with the ground-truth clip labels.
- **Evaluation is not a tracker method.** It is tool-agnostic and will
  live in the main package (step 4 of the workflow).

### Tests

- Main env: `pytest`. The root config now has `testpaths = ["tests"]`, so
  `envs/` is not collected.
- Per env: `uv run --project envs/cotracker3 pytest envs/cotracker3/tests`.
  pytest comes from the env's `dev` dependency group, and
  `pythonpath = ["."]` makes `infer` importable.

## Next steps

1. Implement `startlabels_to_queries`, `tracks_to_cliplabels` and
   `PointTracker.run` (reuse the existing helpers in `clips.py`/`io.py`),
   and test them with `StaticTracker` against `tests/data`.
2. Implement `CoTracker3.__init__`/`track` (torch.hub
   `cotracker3_offline`, query mode, not grid mode) and `parse_args`.
3. Add a CI job per env.
4. Write a second tracker. Only then extract shared CLI arguments
   (`--startlabels --video --out`) into `poseinterface.trackers`.

## Maintainability notes

- **Envs inherit all core dependencies.** Each tracker env installs
  everything `poseinterface` depends on (boto3, jupyter, movement,
  sleap-io): currently 208 packages. This adds weight, and more
  importantly, more chances to clash with an old tool's pins (e.g. DLC
  and numpy). Consider moving `jupyter` to an extra/dev group and keeping
  the core small. If a tool really can't coexist with `poseinterface`,
  the fallback is to have the env not depend on it at all and exchange
  only files.
- **The editable path dependency couples the envs to the main package
  source.** A change to `PointTracker` or its helpers can silently break
  every env. Per-env CI is what catches this, so it isn't optional once
  there are real implementations.
- **Lockfiles are gitignored** (`uv.lock` in `.gitignore`), so the env
  locks aren't committed and env reproducibility isn't guaranteed yet.
  Decide whether to un-ignore `envs/*/uv.lock`.
- **Unpinned upstream code:** the `cotracker` git dependency has no
  `rev`, and `torch.hub.load("facebookresearch/co-tracker", ...)` pulls
  the default branch at runtime. Pin both to a tag or commit.
- **Heavy CI:** torch envs and model weight downloads are slow. Keep the
  tool tests to a shape check plus a CLI smoke test on a tiny clip, and
  cache `~/.cache/torch/hub` and the uv cache.
- **Python version drift:** the env says `requires-python >=3.12` while
  `.python-version` is 3.13. Align them with the root project.
- **Keep the ABC small.** One abstract method is easy to follow for new
  tools. Resist adding hooks until a second tracker needs them.
