#!/usr/bin/env python3
"""Record and compare canonical jq multi-binding path behavior.

The single-binding experiment must fix the reported unambiguous cases without
inventing semantics for sibling bindings. This script records exact canonical
status/stdout/stderr, then requires the candidate to remain byte-identical for
that ambiguous surface.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Case:
    name: str
    program: str
    input_text: str | None = None


CASES = [
    Case("sibling-missing-body-dot", "path({} as {$a,$b} | .)"),
    Case("sibling-present-body-dot", "path({a:1,b:2} as {$a,$b} | .)"),
    Case("sibling-present-body-a", "path({a:1,b:2} as {$a,$b} | $a)"),
    Case("sibling-present-body-b", "path({a:1,b:2} as {$a,$b} | $b)"),
    Case("sibling-present-body-each", "path({a:1,b:2} as {$a,$b} | ($a,$b))"),
    Case("sibling-renamed-body-x", "path({a:1,b:2} as {a:$x,b:$y} | $x)"),
    Case("sibling-renamed-body-y", "path({a:1,b:2} as {a:$x,b:$y} | $y)"),
    Case("sibling-reversed-pattern", "path({a:1,b:2} as {$b,$a} | .)"),
    Case("repeated-binding-sites", "path({a:1,b:2} as {a:$x,b:$x} | .)"),
    Case(
        "dynamic-key-local-binding",
        'path({"key":"a","a":null} as {(.key as $k | $k):$a} | .)',
    ),
    Case("nested-siblings-body-a", "path({x:{a:1,b:2}} as {x:{$a,$b}} | $a)"),
    Case("nested-siblings-body-b", "path({x:{a:1,b:2}} as {x:{$a,$b}} | $b)"),
    Case("array-siblings-body-a", "path([10,20] as [$a,$b] | $a)"),
    Case("array-siblings-body-b", "path([10,20] as [$a,$b] | $b)"),
    Case("array-siblings-body-each", "path([10,20] as [$a,$b] | ($a,$b))"),
    Case(
        "source-path-siblings-body-a",
        "path(.src as {$a,$b} | $a)",
        '{"src":{"a":1,"b":2}}\n',
    ),
    Case(
        "source-path-siblings-body-b",
        "path(.src as {$a,$b} | $b)",
        '{"src":{"a":1,"b":2}}\n',
    ),
    Case(
        "bound-traversal-second-sibling",
        "path({a:{x:1},b:{y:2}} as {$a,$b} | $b.y)",
    ),
    Case(
        "alternation-sibling-object",
        "path({a:1,b:2} as {$a,$b} ?// [$a,$b] | $b)",
    ),
    Case(
        "alternation-sibling-array",
        "path([10,20] as {$a,$b} ?// [$a,$b] | $b)",
    ),
    Case(
        "source-backtracking-siblings",
        "path(({}, {a:1,b:2}) as {$a,$b} | .)",
    ),
    Case(
        "body-backtracking-siblings",
        "path({a:1,b:2} as {$a,$b} | ($a,$b))",
    ),
    Case(
        "reduce-object-destructure",
        "path(reduce [{a:1,b:2}][] as {$a,$b} (null; $b))",
    ),
    Case(
        "foreach-object-destructure",
        "path(foreach [{a:1,b:2}][] as {$a,$b} (null; $b; .))",
    ),
    Case(
        "setpath-sibling-missing",
        "path({} as {$a,$b} | .) as $p | {path:$p,result:setpath($p;42)}",
    ),
    Case(
        "setpath-sibling-present-b",
        "try (path({a:1,b:2} as {$a,$b} | $b) as $p | {path:$p,result:setpath($p;42)}) catch .",
    ),
]


def execute(binary: Path, case: Case) -> dict[str, object]:
    command = [str(binary), "-c"]
    if case.input_text is None:
        command.append("-n")
    command.append(case.program)
    process = subprocess.run(
        command,
        input=case.input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "status": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def record(binary: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    observations = []
    for case in CASES:
        result = execute(binary, case)
        observations.append({"case": asdict(case), "result": result})
        case_dir = output / case.name
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "stdout").write_text(str(result["stdout"]), encoding="utf-8")
        (case_dir / "stderr").write_text(str(result["stderr"]), encoding="utf-8")
        (case_dir / "status").write_text(f"{result['status']}\n", encoding="utf-8")
    (output / "observations.json").write_text(
        json.dumps(observations, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def compare(binary: Path, baseline: Path, output: Path) -> None:
    expected_rows = json.loads((baseline / "observations.json").read_text(encoding="utf-8"))
    expected = {row["case"]["name"]: row for row in expected_rows}
    output.mkdir(parents=True, exist_ok=True)
    differences = []
    summary = []

    for case in CASES:
        actual = execute(binary, case)
        wanted = expected[case.name]["result"]
        equal = actual == wanted
        summary.append(
            {
                "case": asdict(case),
                "baseline": wanted,
                "candidate": actual,
                "equal": equal,
            }
        )
        print(
            f"{case.name}\tbaseline={wanted['status']}\t"
            f"candidate={actual['status']}\tequal={equal}"
        )
        if not equal:
            differences.append(case.name)

    (output / "comparison.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "differences.txt").write_text(
        "".join(f"{name}\n" for name in differences),
        encoding="utf-8",
    )
    if differences:
        raise SystemExit(f"candidate changed canonical multi-binding behavior: {differences}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("record", "compare"))
    parser.add_argument("binary", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()

    if args.mode == "record":
        record(args.binary.resolve(), args.output.resolve())
    else:
        if args.baseline is None:
            parser.error("--baseline is required in compare mode")
        compare(
            args.binary.resolve(),
            args.baseline.resolve(),
            args.output.resolve(),
        )


if __name__ == "__main__":
    main()
