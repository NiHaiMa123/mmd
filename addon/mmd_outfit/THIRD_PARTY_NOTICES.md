# PPF-derived candidate-cache adapter

`contact_broadphase.py` adapts candidate-cache logic from
`core/shell_untangle.py` in the ST-Tech / ZOZO PPF Contact Solver Blender add-on,
pinned distribution `addon-2026-10-19-0917`.

Upstream source: https://github.com/st-tech/ppf-contact-solver

Copyright 2025 Ryoichi Ando (ZOZO, Inc.). Licensed under Apache-2.0;
the full license is included as `PPF_APACHE_LICENSE.txt`.
Upstream file credits: Code: Claude Code; Review: Ryoichi Ando.

Modifications: bounded-memory NumPy AABB batches and prescribed-static-collider
scope, installed only in the project's portable untangling worker. No vendor
file is overwritten. Collider/collider pairs are excluded by this scope;
that does not establish the absence of collisions within prescribed objects.

The PPF runtime, original add-on, models, music and motions are not bundled.
