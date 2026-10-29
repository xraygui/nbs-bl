# Manipulator calibration in nbs-bl: design

Status: approved by Jamie, 2026-10-29.

## Why

The manipulator calibration that works today lives in four claude-pods startup
scripts (`10-find_edges.py`, `20-alignment.py`, `25-alignment-nbs-bl.py`,
`26-fast-calibration.py`). They are copies of `ucal/plans/alignment.py` and
`find_edges.py`, patched in place for nbs-bl's manipulator, plus the newer
fast and rigid-bar calibrations. Only claude-pods can use them, they rely on
IPython's shared startup namespace, and they assume a 4-sided square bar
(`nsides=4`, sides 90 degrees apart). Some beamlines use two-sided bars, which
must not be calibrated as if they had four faces.

## Goals

- Any nbs-bl beamline with a 4-axis manipulator gets the calibration plans
  without copying code into its profile.
- The calibration follows the holder: a 2-sided bar is calibrated as two faces
  180 degrees apart, a 4-sided bar as four faces 90 degrees apart.
- A saved calibration is restored at startup.
- The pure geometry (fits, corner maths) is unit-tested without motors.

## Non-goals

- Changing ucal in this pass (its tree is dirty and it has its own sign
  convention); see "ucal" below.
- New edge-finding algorithms. The two-way fly `find_edge` is moved as is.
- Holders with no faces to calibrate (`AbsoluteBar`, `Bar1d`): the plans
  refuse them with a clear error.

## Anti-goals

- A 2-sided bar silently getting 4-sided frames (the bug this is about).
- Beamline-specific numbers (detector names, thresholds, bar sizes) hard-coded
  in nbs-bl.

## Module layout (nbs-bl)

| Module | Contents | From |
|---|---|---|
| `nbs_bl/geometry/calibration.py` | Pure numpy, no motion: `side_points` (nbs-bl convention, today's `find_side_points` from 25), `corner_y` for regular polygons, the rigid cross-section fit (`fit_rigid_bar`, `edge_distance`, `face_distance`, `bar_end_heights`) | 20, 25, 26 |
| `nbs_bl/plans/edges.py` | `alignment_detector()` / `alignment_is_direct()` from the `direct_alignment` / `indirect_alignment` roles, `find_edge` (two-way fly), `find_x`, `find_z`, `edge_near`, the adaptive and stepped `scan_*` helpers | 10, 26 |
| `nbs_bl/plans/alignment.py` | The plans (below), `MANIPULATOR_CONFIG`, `set_manipulator_origin`, `load_saved_manipulator_calibration` | 20, 25, 26 |
| `nbs_bl/geometry/bars.py` | Holders say how they are calibrated (below); new `Standard2SidedBar` | new |
| `nbs_bl/tests/test_calibration.py` | Fits and side points against a known bar, both holder types | new |

## How a calibration picks its routine from the holder

Each holder that can be calibrated describes its cross-section and its
sample faces, so the plans never assume `nsides`:

```python
class Standard4SidedBar:
    sides = 4
    def calibration_faces(self):
        # (face index on the cross-section, manipr offset at which it is edge-on)
        return [(0, 0), (1, 90), (2, 180), (3, 270)]
    cross_section = (width, width)          # full extents across, along side 1

class Standard2SidedBar:                    # new
    sides = 2
    def calibration_faces(self):
        return [(0, 0), (2, 180)]           # the two broad faces
    cross_section = (width, thickness)
```

The key observation is that the rigid fit in `26-fast-calibration.py` already
models the bar as a convex cross-section whose support in direction `u` is
`h (|cos| + |sin|)`. Generalising `h` to two half-extents `(a, b)` gives
`a |cos(r - k)| + b |sin(r - k)|`, which covers a square bar (`a = b`), a
rectangular bar, and a flat 2-sided plate (`b` the plate's half-thickness). So:

- **`calibrate_bar`** (today's `rigid_calibrate_bar`, the recommended plan)
  works for both holder types. It measures the V around face 1, an edge 90
  degrees on (side 2 on a square bar, the plate's edge on a 2-sided bar), the
  same at a second height for tilt, and the trailing edge for thickness. It
  then writes a frame only for the holder's faces from `calibration_faces()`:
  four on a square bar, two on a plate.
- **`calibrate_sides`** (today's `fast_calibrate_sides`, reversed second pass)
  stays as the face-by-face fallback. Its corner maths (`corner_y`) only holds
  for regular polygons, so it runs only on holders with `sides >= 3` and
  raises on a 2-sided bar, pointing to `calibrate_bar`.
- **`calibrate_bar_angle`** and **`calibrate_beam_offset`** don't depend on
  the number of sides and work on both.

The slow `find_side_basis` / old `calibrate_sides` / `new_calibrate_sides`
are dropped: `calibrate_sides` (fast) supersedes them. *(My call.)*

## What stays beamline-specific (in the profile)

- Holder type and dimensions, as `devices.toml` kwargs to the manipulator
  builder (`holder = "Standard2SidedBar"`, `width`, `thickness`, `length`).
  `nbs_bl.sim.manipulator.ManipulatorBuilder` grows these kwargs, defaulting
  to today's `Standard4SidedBar(24.5, 215)`.
- Which detector aligns: the existing `direct_alignment` / `indirect_alignment`
  roles.
- Its threshold: `beamline.toml [devices] sc = { threshold = ... }`, which
  nbs-bl currently ignores; I'll make the loader pass it to
  `DetectorGroup.add(threshold=...)`.
- Optional tuning defaults in `beamline.toml [settings.alignment]` (lever arm,
  V angles, max fit rms, bump above the bar end). Plan kwargs override them.

## Calibration storage and startup

- The rotation axis offset replaces the claude-pods `manipulator.origin`
  monkeypatch: `calibrate_beam_offset` sets `manipulator.set_rotation_center`,
  and the z attachment comes from `attachment_point`.
- `MANIPULATOR_CONFIG` (Redis) keeps `rotation_center`, per-side points, the
  holder type, and the rigid fit. Saved points are applied only when the saved
  holder type and side count match the current holder, so a 4-sided
  calibration is never loaded onto a 2-sided bar.
- `nbs_bl.startup` loads the saved calibration after the devices are built
  (plain function, not a plan).

## Related fix

The known bug where `move_sample` sends side 1 to r = 357.9 after a negative
frame rotation: `geometry/affine.angle_between_vectors_2d` says it returns
-pi..pi but returns `angle % 2pi`. Fixed as described under "r wrap fix" below, with a test.

## ucal

ucal keeps its own `alignment.py` unchanged for now (its tree has uncommitted
edits, and its manipulator uses the older origin and sign convention). Once
ucal's manipulator uses `rotation_center`, `ucal/plans/alignment.py` can become
a re-export of `nbs_bl.plans.alignment`. That is a follow-up.

## claude-pods

The four startup scripts are deleted and `00-startup.py` imports the plans
from `nbs_bl.plans.alignment`. Done after the nbs-bl side passes its tests,
under the pods lock, and coordinated with the other thread editing
claude-pods. Commits stay local.

## Two-sided bars (answered by Jamie)

A two-sided bar is a flat plate, typically 15 mm wide, 3 mm thick and 150 mm
long, with samples on both broad faces. Side 1 is edge-on at r = 0 and side 2
at r = 180. In the rectangle model the half-extent normal to side 1 is
thickness / 2 and the half-extent normal to the narrow edge is width / 2.
Each side's origin is the corner shared with the next face round the
cross-section (the narrow edge for a plate), as on the 4-sided bar.

## r wrap fix (detail)

Changing `angle_between_vectors_2d` to -pi..pi would move side 4 from
r = 315 to r = -45 for every beamline. Instead `find_rotation` wraps the
grazing angle into [-45, 315) degrees, so unrotated sides keep their current
angles (0, 90, 180, 270) and a small negative frame rotation gives side 1 a
small negative r. *(My call.)*

## Left to the builder

Exact function names inside modules, status messages, scan window sizes for
the plate edge, test fixtures.
