"""Check that the Python examples cover every Agent parameter and every
public remy export -- the central promise of
`docs/superpowers/specs/2026-09-09-examples-full-parameter-coverage-design.md`.

Usage: python3 scripts/check_coverage.py
Exits 0 with no gaps, 1 if any gap is found, 2 if it cannot even run the
check (no `remy` importable, no python/.venv found).

This script replaced an ad hoc check written by hand, promoted to the
repository after a code review found the original had a blind spot big
enough to produce a false positive (see "What this script cannot see"
below).

## What it checks

1. Every constructor parameter of `remy.Agent` is either:
   - named literally in some example, e.g. `Agent(model=...)`, or
   - carried by `python/examples/config.py`'s shared `config` dict and
     reached via `Agent(**config, ...)` in some example. Which keys that
     dict carries is read from config.py's own source with `ast`, not
     hard-coded here and not assumed by regex -- so if `options()` or
     `with_task()` ever starts or stops supplying a key, this check picks
     that up on its own next run.
2. Every name in `remy.__all__` (minus `__version__`) is named in EXECUTABLE
   CODE somewhere in `python/examples/*.py` -- imported, used in an
   `isinstance` check, or otherwise appearing as a real `ast.Name` or
   import `ast.alias`, as opposed to merely being spelled out in a comment
   or a string literal.

   A name that appears ONLY in a comment or a string is reported separately
   (see "exports mentioned only in a comment or string" in the output) and
   is NOT treated as covered -- unless it is listed in
   `KNOWN_UNEXERCISED_EXPORTS` below, each entry naming a real, considered
   reason the export cannot be exercised without contorting an example or
   this repository's test harness (`scripts/smoke.py`).

## What this script CANNOT see (its blind spots)

- A parameter or export reached through some indirection this script does
  not know to unpack. It understands exactly one indirection --
  config.py's dict, found via `**config` or `**{**config, ...}` -- because
  that is the one real case this repository has. A second dict assembled
  ad hoc inside an example, a name imported under an alias
  (`import remy as sdk` then `sdk.Model`), or a name reached only via
  `getattr`/`globals()`, would all be invisible to it: a genuinely covered
  parameter could be reported as a gap, or vice versa.
- Whether a covered name is exercised meaningfully, beyond appearing as a
  real name in the AST. `from remy import Tool, Run, RunResult, RunEvent,
  Usage, Session` followed by an unused import would still count as "named
  in executable code" here -- presence in the AST is necessary, not
  sufficient. Review passes upgraded exports from a bare mention (a comment,
  or an import nothing then used) into an `isinstance` check that would
  actually fail if the type changed. Read what a reported gap's fix actually
  does, don't just make the name appear.
- TypeScript. This inspects the installed Python `remy` package and
  `python/examples/*.py` only. Whether `typescript/examples/*.ts` covers the
  same surface is a separate question this script does not answer.

A name this script reports is worth reading, not blindly trusted as "real"
or dismissed as "checker artifact" -- and it should never be made to
disappear by teaching the checker a new blind spot on purpose. Fix the
example the gap belongs to; only fix this script when the gap is provably
a limitation of the check itself, and say so in the commit that does it.
`KNOWN_UNEXERCISED_EXPORTS` is the one sanctioned exception to that rule --
each entry is a deliberate, documented decision not to exercise a name, not
a way to quietly launder an oversight.
"""
import ast
import inspect
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES_DIR = ROOT / "python" / "examples"
CONFIG_PY = EXAMPLES_DIR / "config.py"

CONFIG_SPLAT_RE = re.compile(r"\*\*(?:\{\*\*)?config\b")

#: Exports this script has confirmed are named only in a comment or string in
#: every example, together with the reason no example calls or references
#: them in real code. Adding a name here is a considered decision, not a
#: shortcut -- see the module docstring.
KNOWN_UNEXERCISED_EXPORTS = {
    "run": (
        "run() is the SYNCHRONOUS one-shot entry point. It raises "
        "RuntimeError('run() cannot nest an event loop; use await arun()') "
        "when called from inside a running event loop, and every example's "
        "main() runs inside one -- scripts/smoke.py drives both bindings by "
        "awaiting main(config). Calling run() from there would either fail "
        "or require the smoke harness to invoke examples differently just "
        "for this one name, which is not worth contorting it for. Its async "
        "twin arun() is exercised for real in one_shot.py."
    ),
}


def _ensure_remy_importable():
    """Re-exec under python/.venv's interpreter, unless already running there.

    `python3 scripts/check_coverage.py` is meant to run with the system
    interpreter (like compileall in this repo's other gates), but the `remy`
    this check needs to inspect is the one installed in python/.venv -- the
    same split scripts/smoke.py resolves by pointing at that venv's python
    explicitly rather than assuming an activated shell.

    This deliberately does not just try `import remy` and treat success as
    good enough: a stray `remy` reachable on the system interpreter's own
    path (an unrelated sibling checkout on PYTHONPATH, say) can import
    without error yet be missing the very names this script inspects, which
    is a confusing way to fail. Comparing `sys.executable` against the venv's
    own interpreter path is unambiguous.
    """
    venv_python = ROOT / "python" / ".venv" / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    if pathlib.Path(sys.executable).resolve() == venv_python.resolve():
        return
    if not venv_python.exists():
        try:
            import remy  # noqa: F401
            return
        except ImportError:
            pass
        print(
            "error: could not import 'remy', and no venv found at "
            f"{venv_python}. Set up python/.venv first (see python/README.md).",
            file=sys.stderr,
        )
        sys.exit(2)
    os.execv(str(venv_python), [str(venv_python), __file__, *sys.argv[1:]])


def config_supplied_keys():
    """Dict keys that config.py's options()/with_task() put into `config`.

    Read via `ast` from config.py's own two `return {...}` statements,
    rather than by calling options() (which needs real DEMO_* environment
    variables and, for with_task(), a live HTTP call to open a usage task
    against the gateway) or by regex (which cannot tell a dict key from a
    keyword argument). Only string-literal Dict keys are collected; the
    `**config` spread inside with_task()'s own return is not a new key, it's
    the carry-through of options()'s keys -- which this same walk also
    visits, since both functions are inspected.
    """
    tree = ast.parse(CONFIG_PY.read_text())
    keys = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in ("options", "with_task"):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Dict):
                    for key_node in sub.value.keys:
                        if isinstance(key_node, ast.Constant) and isinstance(
                            key_node.value, str
                        ):
                            keys.add(key_node.value)
    return keys


def example_sources():
    return {p: p.read_text() for p in sorted(EXAMPLES_DIR.glob("*.py"))}


def named_in_code(sources):
    """Identifiers that appear as real names in an example's AST.

    Covers `from remy import X` (and `import remy as X`) aliases and every
    `ast.Name` (a bare reference like `isinstance(x, Tool)` or `Tool(...)`)
    -- as opposed to a name that only ever shows up inside a docstring, a
    comment, or an unrelated string literal, which `ast.parse` never turns
    into either of these nodes in the first place.

    Deliberately does NOT also collect `ast.Attribute` access (`x.run(...)`,
    `event.run`). That would reintroduce exactly the false positive this
    script exists to catch: `run` is a top-level `remy` export (the
    synchronous one-shot entry point) AND the method name every `Agent` and
    `Session` uses to start a turn, so counting `.run(` as evidence would
    call `run` "covered" on the strength of `agent.run(...)` calls that have
    nothing to do with the export. A name reached only via an attribute
    (`remy.Tool` after `import remy`) is out of scope for the same reason
    this script never claimed to follow `getattr`/`globals()` -- see "What
    this script CANNOT see" above.
    """
    names = set()
    for path, src in sources.items():
        tree = ast.parse(src, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    names.add(alias.asname or alias.name)
    return names


def main():
    _ensure_remy_importable()
    import remy
    from remy import Agent

    sources = example_sources()
    all_source = "\n".join(sources.values())

    params = list(inspect.signature(Agent.__init__).parameters)[1:]
    named_directly = {
        p for p in params if re.search(rf"\b{re.escape(p)}\s*=", all_source)
    }

    config_keys = config_supplied_keys()
    config_is_splatted = any(CONFIG_SPLAT_RE.search(src) for src in sources.values())
    covered_via_config = (config_keys & set(params)) if config_is_splatted else set()

    missing_params = [
        p for p in params if p not in named_directly and p not in covered_via_config
    ]

    exports = sorted(set(remy.__all__) - {"__version__"})
    # The old, looser signal: does this name appear ANYWHERE in the source --
    # comments and string literals included? Kept only to separate "mentioned
    # nowhere at all" from "mentioned, but only in a comment or string".
    named_anywhere = set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", all_source))
    in_code = named_in_code(sources)

    comment_or_string_only = sorted(
        e for e in exports if e in named_anywhere and e not in in_code
    )
    unaccounted_for = [
        e for e in exports if e not in in_code and e not in KNOWN_UNEXERCISED_EXPORTS
    ]
    stale_exceptions = sorted(
        e for e in KNOWN_UNEXERCISED_EXPORTS if e in in_code
    )

    print("params named directly (`param=`):", sorted(named_directly))
    print(
        "params covered via config.py's shared dict (**config):",
        sorted(covered_via_config) or "none",
    )
    print("params not set in any example:", missing_params or "none")
    print(
        "exports mentioned only in a comment or string (not exercised):",
        comment_or_string_only or "none",
    )
    print(
        "exports excluded as known, documented gaps (see KNOWN_UNEXERCISED_EXPORTS):",
        sorted(KNOWN_UNEXERCISED_EXPORTS) or "none",
    )
    if stale_exceptions:
        print(
            "note: these KNOWN_UNEXERCISED_EXPORTS entries are now named in "
            "executable code -- the exception (and the claim it documents) "
            "can be removed:",
            stale_exceptions,
        )
    print("exports not accounted for at all (a real gap):", unaccounted_for or "none")

    return 1 if (missing_params or unaccounted_for) else 0


if __name__ == "__main__":
    sys.exit(main())
