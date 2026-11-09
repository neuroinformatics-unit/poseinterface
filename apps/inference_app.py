import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full", app_title="Pose inference")


@app.cell
def _():
    import json
    from pathlib import Path

    import cv2
    import marimo as mo
    import numpy as np
    import pandas as pd
    import matplotlib.patheffects as pe
    from matplotlib import colormaps
    from matplotlib.figure import Figure

    DLC, LP = "DeepLabCut", "Lightning Pose"
    THRESHOLD = 0.6  # likelihood cut-off for the COCO file (also the viewer slider's starting value)

    def card(title, *body, note=None):
        """A titled, bordered block (works in light and dark themes)."""
        head = [mo.md(f"### {title}")]
        if note:
            head.append(mo.md(f"<span style='opacity:.65'>{note}</span>"))
        return mo.vstack([*head, *body], gap=0.75).style(
            {"border": "1px solid rgba(128,128,128,.35)", "border-radius": "10px", "padding": "1rem 1.25rem"}
        )

    def video_info(path):
        """(width, height, fps, n_frames) or None if the video cannot be opened."""
        cap = cv2.VideoCapture(str(path))
        try:
            if not cap.isOpened():
                return None
            return (
                int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                cap.get(cv2.CAP_PROP_FPS) or 30.0,
                int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            )
        finally:
            cap.release()

    def arrays(df):
        """Keypoint names and (frames x keypoints) arrays of x, y and likelihood."""
        names = list(dict.fromkeys(df.columns.get_level_values(0)))
        get = lambda c: df.xs(c, axis=1, level=1)[names].to_numpy(dtype=float)
        return names, get("x"), get("y"), get("likelihood")

    def to_coco(df, video, width, height, fps, thr):
        """COCO keypoints: one image + one annotation per frame.

        keypoints = [x, y, v, ...] with v=2 if likelihood >= thr, 1 if below, 0 if missing.
        Raw likelihoods are kept in `keypoint_scores`. Frames are not saved as images.
        """
        names, x, y, p = arrays(df)
        p = np.nan_to_num(p, nan=0.0)
        present = np.isfinite(x) & np.isfinite(y)
        vis = np.where(present, np.where(p >= thr, 2, 1), 0)
        xs, ys = np.where(present, x, 0).round(3), np.where(present, y, 0).round(3)
        good = vis == 2
        x0, x1 = np.where(good, x, np.inf).min(1), np.where(good, x, -np.inf).max(1)
        y0, y1 = np.where(good, y, np.inf).min(1), np.where(good, y, -np.inf).max(1)
        has = good.any(1)

        images, anns = [], []
        for i in range(len(df)):
            images.append(
                {"id": i + 1, "file_name": f"{video.stem}_frame{i:06d}.png", "width": width,
                 "height": height, "frame_index": i, "time_s": round(i / fps, 6)}
            )
            bbox = [round(x0[i], 3), round(y0[i], 3), round(x1[i] - x0[i], 3), round(y1[i] - y0[i], 3)] if has[i] else [0, 0, 0, 0]
            anns.append(
                {"id": i + 1, "image_id": i + 1, "category_id": 1,
                 "keypoints": [c for t in zip(xs[i].tolist(), ys[i].tolist(), vis[i].tolist()) for c in t],
                 "num_keypoints": int((vis[i] > 0).sum()), "bbox": bbox, "area": round(bbox[2] * bbox[3], 3),
                 "iscrowd": 0,
                 "score": round(float(p[i][present[i]].mean()), 5) if present[i].any() else 0.0,
                 "keypoint_scores": [round(v, 5) for v in p[i].tolist()]}
            )
        return {
            "info": {"description": "Pose predictions from the inference app", "video": video.name,
                     "fps": fps, "visibility_threshold": thr},
            "licenses": [],
            "images": images,
            "annotations": anns,
            "categories": [{"id": 1, "name": "animal", "supercategory": "animal", "keypoints": names, "skeleton": []}],
        }

    def annotate_video(df, video, dst, thr, progress):
        """Draw every keypoint with likelihood >= thr on the video and write it to dst."""
        names, x, y, p = arrays(df)
        cmap = colormaps["tab20"]
        bgr = [tuple(int(255 * c) for c in cmap(i % 20)[:3][::-1]) for i in range(len(names))]
        width, height, fps, _ = video_info(video)
        part = dst.with_name(dst.stem + ".part.mp4")  # renamed when complete, so a stop never leaves a half file
        writer = cv2.VideoWriter(str(part), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        cap = cv2.VideoCapture(str(video))
        for i in progress(range(len(df)), title="Saving annotated video"):
            ok, frame = cap.read()
            if not ok:
                break
            for j in range(len(names)):
                if p[i, j] >= thr and np.isfinite(x[i, j]) and np.isfinite(y[i, j]):
                    cv2.circle(frame, (int(x[i, j]), int(y[i, j])), 4, bgr[j], -1)
            writer.write(frame)
        writer.release()
        cap.release()
        part.replace(dst)

    return (
        DLC, LP, Figure, Path, THRESHOLD, annotate_video, card, colormaps, cv2,
        json, mo, np, pd, pe, to_coco, video_info,
    )


@app.cell
def _(DLC, LP, Path, mo):
    method = mo.ui.radio([DLC, LP], value=DLC, inline=True)
    video_path = mo.ui.text(full_width=True, placeholder="/path/to/video.mp4", label="Video file")
    model_path = mo.ui.text(full_width=True, placeholder="/path/to/model", label="Model")
    out_dir = mo.ui.text(value=str(Path.home() / "pose_inference_out"), full_width=True, label="Output folder")
    run = mo.ui.run_button(label="Run inference", kind="success")
    return method, model_path, out_dir, run, video_path


@app.cell
def _(DLC, Path, method, model_path, out_dir, video_path):
    # Turn the typed paths into Paths and check each one.
    def _as_path(box):
        text = box.value.strip()
        return Path(text).expanduser() if text else None

    def _check(label, path, valid, hint):
        if path is None:
            return False, f"○ {label}: not set"
        if not path.exists():
            return False, f"✗ {label}: not found at `{path}`"
        if not valid(path):
            return False, f"✗ {label}: {hint}"
        return True, f"✓ {label}: `{path.name}`"

    video, model = _as_path(video_path), _as_path(model_path)
    out_root = Path(out_dir.value.strip() or ".").expanduser()

    video_ok, _v = _check("Video", video, lambda p: p.is_file(), "not a file")
    if method.value == DLC:
        model_ok, _m = _check(
            "Model", model, lambda p: p.is_file() and p.suffix.lower() in {".yaml", ".yml"},
            "expected the project's `config.yaml`",
        )
    else:
        model_ok, _m = _check("Model", model, lambda p: p.is_dir(), "expected a trained model folder")

    status = "\n\n".join([_v, _m, f"○ Output: `{out_root}`"])
    ready = video_ok and model_ok
    return model, model_ok, out_root, ready, status, video, video_ok


@app.cell
def _(DLC, LP, card, method, mo, model_path, out_dir, ready, run, status, video_path):
    _hint = {
        DLC: "Path to the DeepLabCut project's `config.yaml`.",
        LP: "Path to a trained model folder (the one with the config and checkpoint).",
    }
    mo.vstack(
        [
            mo.md(
                "# Pose inference\n"
                "Run DeepLabCut or Lightning Pose on a video. The predictions and a COCO JSON are saved "
                "to the output folder automatically. The annotated video is saved on request."
            ),
            mo.hstack(
                [
                    mo.vstack(
                        [
                            card("1. Method", method),
                            card("2. Video", video_path),
                            card("3. Model", model_path, note=_hint[method.value]),
                            card("4. Output folder", out_dir),
                            run,
                        ],
                        gap=1,
                    ),
                    card(
                        "Checklist",
                        mo.md(status),
                        mo.callout(
                            mo.md("Ready." if ready else "Waiting on a valid video and model."),
                            kind="success" if ready else "neutral",
                        ),
                    ),
                ],
                widths=[2.4, 1],
                align="start",
                gap=1.5,
            ),
        ],
        gap=1.25,
    )
    return


@app.cell
def _(DLC, method, mo, model, model_ok, out_root, run, video, video_ok):
    mo.stop(
        not (video_ok and model_ok),
        mo.callout(mo.md("Add a valid video and model above to see predictions here."), kind="neutral"),
    )

    _out = out_root / ("dlc" if method.value == DLC else "lp")

    def _find_csv():
        found = list(_out.glob(f"{video.stem}*.csv")) if _out.exists() else []
        return min(found, key=lambda p: len(p.name)) if found else None

    pred_csv = _find_csv()  # reuse predictions from an earlier run
    if pred_csv is None:
        mo.stop(
            not run.value,
            mo.callout(mo.md(f"No predictions for `{video.name}` yet. Press **Run inference**."), kind="info"),
        )
        _out.mkdir(parents=True, exist_ok=True)
        _err = None
        with mo.status.spinner(title=f"Running {method.value} on {video.name} ..."):
            try:
                if method.value == DLC:
                    import deeplabcut

                    deeplabcut.analyze_videos(
                        str(model), [str(video)], videotype=video.suffix, save_as_csv=True, destfolder=str(_out)
                    )
                else:
                    from lightning_pose.api.model import Model

                    Model.from_dir(str(model)).predict_on_video_file(
                        video_file=str(video), output_dir=str(_out), compute_metrics=False
                    )
            except Exception as e:
                _err = e
        mo.stop(
            _err is not None,
            mo.callout(mo.md(f"**{method.value} failed.** `{type(_err).__name__}: {_err}`"), kind="danger"),
        )
        pred_csv = _find_csv()

    mo.stop(
        pred_csv is None,
        mo.callout(mo.md("Inference finished but no predictions CSV was found in the output folder."), kind="danger"),
    )
    return (pred_csv,)


@app.cell
def _(mo, pd, pred_csv):
    # DLC and LP both write a 3-row header: scorer / bodyparts / coords
    df, bodyparts, _err = None, [], None
    try:
        df = pd.read_csv(pred_csv, header=[0, 1, 2], index_col=0).droplevel(0, axis=1)
        bodyparts = list(dict.fromkeys(df.columns.get_level_values(0)))
        df[(bodyparts[0], "likelihood")]  # fails early if the columns are not x / y / likelihood
    except Exception as e:
        _err = e
    mo.stop(
        _err is not None,
        mo.callout(
            mo.md(
                f"Could not read `{pred_csv.name}` as pose predictions (expected a 3-row header with "
                f"x, y, likelihood columns). `{type(_err).__name__}: {_err}`"
            ),
            kind="danger",
        ),
    )
    return bodyparts, df


@app.cell
def _(THRESHOLD, bodyparts, colormaps, cv2, df, mo, video, video_info):
    _info = video_info(video)
    mo.stop(_info is None, mo.callout(mo.md(f"Could not open `{video.name}` for reading."), kind="danger"))
    _, _, fps, _n = _info
    n_frames = min(_n, len(df))
    mo.stop(n_frames < 1, mo.callout(mo.md("The video has no readable frames."), kind="danger"))

    cap = cv2.VideoCapture(str(video))
    frame_idx = mo.ui.slider(0, max(n_frames - 1, 1), value=0, label="Frame", full_width=True, debounce=True)
    thresh = mo.ui.slider(0.0, 1.0, step=0.05, value=THRESHOLD, label="Likelihood threshold")
    point_size = mo.ui.slider(10, 120, step=5, value=35, label="Point size")
    show_labels = mo.ui.checkbox(value=True, label="Show names")
    trace_parts = mo.ui.multiselect(bodyparts, value=bodyparts[:3], label="Keypoints")
    trace_axis = mo.ui.dropdown(["y", "x"], value="y", label="Coordinate")
    colors = {bp: colormaps["tab20"](i % 20)[:3] for i, bp in enumerate(bodyparts)}
    return (cap, colors, fps, frame_idx, n_frames, point_size, show_labels, thresh, trace_axis, trace_parts)


@app.cell
def _(bodyparts, df, fps, mo, n_frames, np, pred_csv, video):
    _lik = np.concatenate([df[(bp, "likelihood")].to_numpy() for bp in bodyparts])
    mo.vstack(
        [
            mo.md(f"## {video.name}\n<span style='opacity:.65'>Predictions: `{pred_csv}`</span>"),
            mo.hstack(
                [
                    mo.stat(f"{n_frames:,}", label="Frames", bordered=True),
                    mo.stat(f"{n_frames / fps:,.1f} s", label="Duration", bordered=True),
                    mo.stat(f"{len(bodyparts)}", label="Keypoints", bordered=True),
                    mo.stat(f"{np.nanmean(_lik):.2f}", label="Mean likelihood", bordered=True),
                ],
                justify="start",
                gap=1,
            ),
        ],
        gap=0.75,
    )
    return


@app.cell
def _(THRESHOLD, df, json, mo, pred_csv, to_coco, video, video_info):
    # The predictions CSV is written by the model. Save the COCO JSON next to it.
    # A COCO file that is already newer than the predictions is kept.
    _info = video_info(video)
    mo.stop(_info is None)
    _width, _height, _fps, _ = _info
    _coco = pred_csv.parent / f"{video.stem}_coco.json"
    if not _coco.exists() or _coco.stat().st_mtime < pred_csv.stat().st_mtime:
        _coco.write_text(json.dumps(to_coco(df, video, _width, _height, _fps, THRESHOLD), separators=(",", ":")))
    mo.callout(
        mo.md(
            f"**Saved to** `{pred_csv.parent}`\n\n"
            f"- `{pred_csv.name}` (predictions)\n"
            f"- `{_coco.name}` (COCO keypoints, visible = likelihood >= {THRESHOLD})"
        ),
        kind="success",
    )
    return


@app.cell
def _(Figure, bodyparts, cap, card, colors, cv2, df, fps, frame_idx, mo, pe, point_size, show_labels, thresh):
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx.value)
    _ok, _frame = cap.read()
    _fig = Figure(figsize=(9, 5.6))
    _ax = _fig.subplots()
    if _ok:
        _ax.imshow(cv2.cvtColor(_frame, cv2.COLOR_BGR2RGB))
    _row = df.iloc[frame_idx.value]
    for _bp in bodyparts:
        _x, _y, _p = _row[(_bp, "x")], _row[(_bp, "y")], _row[(_bp, "likelihood")]
        _good = _p >= thresh.value
        _ax.scatter(
            _x, _y, s=point_size.value, color=colors[_bp],
            edgecolors="white" if _good else "red", linewidths=1.5, alpha=1.0 if _good else 0.35,
        )
        if show_labels.value:
            _ax.annotate(
                f"{_bp} {_p:.2f}", (_x, _y), color="white", fontsize=7,
                xytext=(4, 4), textcoords="offset points",
                path_effects=[pe.withStroke(linewidth=2, foreground="black")],
            )
    _ax.set_title(
        f"Frame {frame_idx.value} at {frame_idx.value / fps:.2f} s "
        f"(white edge: likelihood >= {thresh.value}, red edge: below)",
        fontsize=9,
    )
    _ax.axis("off")
    _fig.tight_layout()
    card(
        "Frame viewer",
        frame_idx,
        mo.hstack([thresh, point_size, show_labels], justify="start", align="end", gap=2),
        _fig,
    )
    return


@app.cell
def _(Figure, card, colors, df, frame_idx, mo, thresh, trace_axis, trace_parts):
    _fig = Figure(figsize=(10, 5))
    _axes = _fig.subplots(2, 1, sharex=True)
    for _bp in trace_parts.value:
        _axes[0].plot(df[(_bp, trace_axis.value)].values, label=_bp, lw=0.8, color=colors[_bp])
        _axes[1].plot(df[(_bp, "likelihood")].values, lw=0.8, color=colors[_bp])
    _axes[1].axhline(thresh.value, color="red", ls="--", lw=0.8)
    for _a in _axes:
        _a.axvline(frame_idx.value, color="black", lw=0.8)
    _axes[0].set_ylabel(f"{trace_axis.value} (px)")
    _axes[1].set_ylabel("likelihood")
    _axes[1].set_xlabel("frame")
    if trace_parts.value:
        _axes[0].legend(fontsize=7, ncol=4)
    _fig.tight_layout()
    card(
        "Traces",
        mo.hstack([trace_parts, trace_axis], justify="start", align="end", gap=2),
        _fig,
        note="The black line marks the frame shown above. The dashed red line is the likelihood threshold.",
    )
    return


@app.cell
def _(bodyparts, card, df, mo, pd, thresh):
    _stats = pd.DataFrame(
        {
            "mean likelihood": [df[(bp, "likelihood")].mean() for bp in bodyparts],
            f"% frames >= {thresh.value}": [100 * (df[(bp, "likelihood")] >= thresh.value).mean() for bp in bodyparts],
        },
        index=bodyparts,
    ).round(3)
    card("Per-keypoint confidence", mo.ui.table(_stats.rename_axis("keypoint").reset_index(), selection=None))
    return


@app.cell
def _(card, mo):
    export_btn = mo.ui.run_button(label="Save annotated video")
    card(
        "Annotated video",
        export_btn,
        note="Draws every keypoint above the likelihood threshold set in the frame viewer. "
        "Saved next to the predictions. It can take a while on a long video.",
    )
    return (export_btn,)


@app.cell
def _(annotate_video, df, export_btn, mo, pred_csv, thresh, video):
    mo.stop(not export_btn.value)
    _dst = pred_csv.parent / f"{video.stem}_annotated.mp4"
    annotate_video(df, video, _dst, thresh.value, mo.status.progress_bar)
    mo.callout(mo.md(f"Saved `{_dst}` (points with likelihood >= {thresh.value})"), kind="success")
    return


if __name__ == "__main__":
    app.run()
