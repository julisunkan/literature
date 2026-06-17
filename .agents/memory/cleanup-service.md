---
name: Cleanup Service
description: Where file cleanup logic lives and why — avoids circular import between app.py and admin blueprint
---

File cleanup is in `services/cleanup_service.py` (`run_cleanup`, `cleanup_old_files`).

**Why:** Originally in `app.py` as `_run_cleanup`. When the admin blueprint needed to call it via a manual-trigger route, it imported `from app import _run_cleanup` — a circular import (blueprints are registered by app.py). Moving it to a services module breaks the cycle.

**How to apply:** Any new code that needs to trigger cleanup or reference the cleanup functions should import from `services.cleanup_service`, never from `app`.
