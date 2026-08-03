#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Case:
    name: str
    program: str
    expected: list[object]
    input_text: str | None = None


jq = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=True)

cases = [
    Case("issue-constant-object", "path({} as {$a} | .)", [["a"]]),
    Case("issue-dot-object", "path(. as {$a} | .)", [["a"]]),
    Case("constant-object-nonnull", "path({a: 1} as {$a} | .)", [["a"]], '{"root":true}\n'),
    Case("dot-object-nonnull", "path(. as {$a} | .)", [["a"]], '{"a":1}\n'),
    Case("nested-constant-object", "path({b:{}} as {b:{$a}} | .)", [["b", "a"]]),
    Case("constant-array", "path([] as [$a] | .)", [[0]]),
    Case("constant-array-object", "path([{}] as [{$a}] | .)", [[0, "a"]]),
    Case("alternation-object", "path({} as {$a} ?// [$a] | .)", [["a"]]),
    Case("alternation-array", "path([] as {$a} ?// [$a] | .)", [[0]]),
    Case("alternation-scalar", "path(1 as {$a} ?// [$a] ?// $a | .)", [[]]),
    Case("backtracking-object", "path(({}, {}) as {$a} | .)", [["a"], ["a"]]),
    Case("binding-object", "{a:1} as {$a} | $a", [1]),
    Case("binding-nested", "{b:{a:1}} as {b:{$a}} | $a", [1]),
    Case("binding-array", "[1] as [$a] | $a", [1]),
    Case("plain-path-object", "path(.a)", [["a"]], '{"a":1}\n'),
    Case("plain-path-nested", "path(.b.a)", [["b", "a"]], '{"b":{"a":1}}\n'),
    Case("plain-path-array", "path(.[0])", [[0]], '[1]\n'),
    Case(
        "setpath-from-destructure",
        "path({} as {$a} | .) as $p | setpath($p; 42)",
        [{"old": 0, "a": 42}],
        '{"old":0}\n',
    ),
]

summary: list[dict[str, object]] = []
failed = False
for case in cases:
    command = [str(jq), "-c"]
    if case.input_text is None:
        command.append("-n")
    command.append(case.program)
    proc = subprocess.run(
        command,
        input=case.input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    (out / f"{case.name}.stdout").write_text(proc.stdout)
    (out / f"{case.name}.stderr").write_text(proc.stderr)
    actual: list[object] = []
    parse_error: str | None = None
    if proc.returncode == 0:
        try:
            actual = [json.loads(line) for line in proc.stdout.splitlines() if line]
        except json.JSONDecodeError as exc:
            parse_error = str(exc)
    ok = proc.returncode == 0 and parse_error is None and actual == case.expected
    failed |= not ok
    summary.append(
        {
            "name": case.name,
            "status": proc.returncode,
            "expected": case.expected,
            "actual": actual,
            "parse_error": parse_error,
            "ok": ok,
        }
    )

(out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
for row in summary:
    print(f"{row['name']}\tstatus={row['status']}\tok={row['ok']}\tactual={row['actual']}")
raise SystemExit(1 if failed else 0)
