#!/usr/bin/env python3
"""
icevault.collision_check -- run this BEFORE adding a new getter to
secrets_registry.py.

Compares a proposed function name against every existing getter,
normalized (lowercased, underscores/case stripped), so `get_oddsapi_key`
and `get_odds_api_key` are correctly flagged as the same logical name
even though they're different strings. Catches the exact failure mode
that started this whole project: 43 slightly-self-derivative spellings
of the same secret.

Usage:
    python3 collision_check.py get_oddsapi_key
"""
import re
import sys

import secrets_registry


def _normalize(name: str) -> str:
    return re.sub(r"[\W_]+", "", name).lower()


def existing_getters() -> list[str]:
    return [n for n in dir(secrets_registry) if n.startswith("get_") and callable(getattr(secrets_registry, n))]


def check_collision(proposed_name: str) -> str | None:
    """Returns the name of a colliding existing getter, or None if the
    proposed name is genuinely new."""
    target = _normalize(proposed_name)
    for name in existing_getters():
        if _normalize(name) == target:
            return name
    return None


def main():
    if len(sys.argv) != 2:
        print("usage: python3 collision_check.py <proposed_getter_name>", file=sys.stderr)
        print("example: python3 collision_check.py get_oddsapi_key", file=sys.stderr)
        sys.exit(2)

    proposed = sys.argv[1]
    collision = check_collision(proposed)
    if collision:
        print(f"COLLISION: '{proposed}' normalizes the same as existing '{collision}'.")
        print(f"Do not add a new getter -- reuse {collision}() instead.")
        sys.exit(1)
    else:
        print(f"Clear: '{proposed}' does not collide with any of {len(existing_getters())} existing getter(s).")
        sys.exit(0)


if __name__ == "__main__":
    main()
