# Manipulator Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move claude-pods' manipulator calibration into nbs-bl, driven by the holder's geometry so 2-sided bars get 2 side frames.

**Architecture:** Pure geometry in `geometry/calibration.py`; holders in `geometry/bars.py` describe faces and cross-section; plans in `plans/edges.py` and `plans/alignment.py` read the holder.

**Tech Stack:** numpy, bluesky, ophyd. Tests run with
`PYTHONPATH=src ../claude-pods/.pixi/envs/qs/bin/python -m pytest -q -p no:cacheprovider src/nbs_bl/tests --ignore=src/nbs_bl/tests/test_panels.py`
(baseline: 77 pass, `test_frames.py::test_frame_to_global` already fails).

**Spec:** `docs/superpowers/specs/2026-10-29-manipulator-calibration-design.md`

## Global Constraints

- Plate: 15 mm wide, 3 mm thick, 150 mm long; side 1 edge-on at r = 0, side 2 at r = 180.
- Square bar default stays `Standard4SidedBar(24.5, 215)`.
- Redis key stays `MANIPULATOR_CONFIG`; old saved data (`origin`, `calibration`) still loads onto a 4-sided bar.
- Commit locally only.

## Review Focus

- A saved 4-sided calibration with a 2-sided holder: not applied (test in Task 4).
- Fit with a plate (a != b): faces and corners use the right half-extent (Task 1).
- Negative frame rotation: side 1 r small negative, side 4 still near 270 (Task 2).
- `calibrate_sides` on a 2-sided bar: raises, naming `calibrate_bar` (Task 4).
- Holders without faces (`AbsoluteBar`, `Bar1d`): plans raise a clear error (Task 4).

---

### Task 1: Rectangle cross-section geometry

**Files:** Create `src/nbs_bl/geometry/calibration.py`, test `src/nbs_bl/tests/test_calibration.py`.

**Produces:** `side_points(x1, y1, x3, y3, z1, z3, r1, center) -> (p1, p2, p3)`;
`corner_y(x1, r1, x2, r2, nsides) -> float`;
`fit_rigid_bar(rows, half_extents=None, square=True, kmax=10, k=None, tilt=None) -> dict` with keys `k, a, b, cx, cy, tx, ty, zref, rms, residuals, at_limit`;
`edge_distance(fit, r, z, trailing=False)`; `face_distance(fit, face, z)`; `face_corner_heights(fit, z_end, faces, r0=0, beam_x=0) -> list | None`.

Model: support `a|cos(r-k)| + b|sin(r-k)|`; `square=True` ties a = b. Face f is edge-on at k + 90 f; its origin corner in local (x across side 1, y across face 1) is `[(-a, b), (a, b), (a, -b), (-a, -b)][f]`.

- [ ] Tests: synthetic edges from a known square (k = 1.3, h = 12.25, tilt) and a known plate (a = 1.5, b = 7.5, k = -2) are fitted back to 1e-6; `face_distance` gives a for even and b for odd faces; `side_points` of the fitted plate matches `Standard2SidedBar` side frames (Task 2).
- [ ] Implement, run, commit.

### Task 2: Holders and the r wrap fix

**Files:** Modify `geometry/bars.py`, `geometry/affine.py:213`, `sim/manipulator.py`; tests in `tests/test_calibration.py`.

**Produces:** `RectangularBar(across, along, length, faces)` base with `side_frames`, `update_side`, `make_sample_frame`, `shift_position`, `read_sample_csv`, `get_geometry`, plus `faces` (tuple of face indices) and `half_extents` (a, b). `Standard4SidedBar(width, length)` = faces (0, 1, 2, 3); `Standard2SidedBar(width, thickness, length)` = faces (0, 2), a = thickness / 2, b = width / 2. `ManipulatorBuilder(..., holder="Standard4SidedBar", width=24.5, thickness=None, length=215)`.

`find_rotation` wraps to [-45, 315) degrees.

- [ ] Tests: 4-sided frames identical to today's; plate has 2 sides; side 2 grazing 180; after rotating all frames by -2 deg side 1's manip r is -2 and side 4's is 268.
- [ ] Implement, run, commit.

### Task 3: Edge finding

**Files:** Create `plans/edges.py` (from claude-pods 10-find_edges.py and `_edge_near`/`_edge_direction` from 26).

**Produces:** `alignment_detector() -> str`, `alignment_is_direct() -> bool`, `find_edge(...)`, `find_x(invert=False, precision=0.1, fly=True)`, `find_z(...)`, `edge_near(x_pred, trailing=False, precision=0.1)`, `scan_x_*/scan_z_*/scan_r_*`. Uses `bl.primary_sampleholder` axes when `manipx` etc. aren't named.

- [ ] Import test only (motion is tested on the pods); commit.

### Task 4: Calibration plans and storage

**Files:** Create `plans/alignment.py`; modify `startup.py`; test `tests/test_calibration.py`.

**Produces:** plans `calibrate_beam_offset`, `calibrate_bar`, `calibrate_bar_angle`, `calibrate_sides`, `load_saved_manipulator_calibration`; functions `set_manipulator_origin`, `restore_manipulator_calibration(manipulator=None) -> bool`, `save_side(manipulator, side, points)`.

Saved: `rotation_center` [x, y], `holder` {type, sides}, `calibration` {side: points}, `rigid_fit`. Restore applies points only if holder type and sides match; legacy data without `holder` only onto a 4-sided bar.

- [ ] Tests: restore round trip with a `use_redis=False` dict; mismatch skipped; `calibrate_sides` raises on 2 sides; plans raise on `Bar1d`.
- [ ] Implement, run, commit.

### Task 5: claude-pods switch-over and pods test

- [ ] Take the pods lock; delete startup 10/20/25/26, keep the sc threshold in config; run `calibrate_beam_offset`, `calibrate_bar`, check `move_sample` to each side; release lock; commit locally.
