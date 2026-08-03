#!/usr/bin/env python3
"""Compare jq #3128 candidate semantics with pinned gojq.

The comparison is observational except for process integrity. Differences are
retained as evidence; gojq is a useful independent implementation, not an
oracle that automatically defines jq behavior.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Case:
    name: str
    program: str
    input_text: str | None = None


@dataclass
class Observation:
    status: int
    stdout: str
    stderr: str
    json_values: list[object] | None


def run(binary: Path, case: Case) -> Observation:
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
    values: list[object] | None = []
    try:
        values = [json.loads(line) for line in process.stdout.splitlines() if line]
    except json.JSONDecodeError:
        values = None
    return Observation(process.returncode, process.stdout, process.stderr, values)


def main() -> None:
    jq = Path(sys.argv[1]).resolve()
    gojq = Path(sys.argv[2]).resolve()
    out = Path(sys.argv[3]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    cases = [
        Case("issue-constant-missing", "path({} as {$a} | .)"),
        Case("issue-dot-missing", "path(. as {$a} | .)"),
        Case("sibling-missing-body-dot", "path({} as {$a,$b} | .)"),
        Case("sibling-present-body-dot", "path({a:1,b:2} as {$a,$b} | .)"),
        Case("sibling-present-body-a", "path({a:1,b:2} as {$a,$b} | $a)"),
        Case("sibling-present-body-b", "path({a:1,b:2} as {$a,$b} | $b)"),
        Case("sibling-present-body-each", "path({a:1,b:2} as {$a,$b} | ($a,$b))"),
        Case("sibling-renamed-body-x", "path({a:1,b:2} as {a:$x,b:$y} | $x)"),
        Case("sibling-renamed-body-y", "path({a:1,b:2} as {a:$x,b:$y} | $y)"),
        Case("sibling-reversed-pattern", "path({a:1,b:2} as {$b,$a} | .)"),
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
            "path({} as {$a,$b} | .) as $p | {path:$p,result:setpath({};$p;42)}",
        ),
        Case(
            "setpath-sibling-present-b",
            "try (path({a:1,b:2} as {$a,$b} | $b) as $p | {path:$p,result:setpath({};$p;42)}) catch .",
        ),
    ]

    summary: list[dict[str, object]] = []
    for case in cases:
        jq_result = run(jq, case)
        gojq_result = run(gojq, case)
        case_dir = out / case.name
        case_dir.mkdir(parents=True, exist_ok=True)
        for implementation, result in (("jq", jq_result), ("gojq", gojq_result)):
            (case_dir / f"{implementation}.stdout").write_text(result.stdout)
            (case_dir / f"{implementation}.stderr").write_text(result.stderr)
            (case_dir / f"{implementation}.status").write_text(f"{result.status}\n")
        equivalent = (
            jq_result.status == gojq_result.status
            and jq_result.json_values == gojq_result.json_values
            and jq_result.stderr == gojq_result.stderr
        )
        summary.append(
            {
                "case": asdict(case),
                "jq": asdict(jq_result),
                "gojq": asdict(gojq_result),
                "equivalent": equivalent,
            }
        )
        print(
            f"{case.name}\tjq={jq_result.status}:{jq_result.json_values}"
            f"\tgojq={gojq_result.status}:{gojq_result.json_values}"
            f"\tequivalent={equivalent}"
        )

    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (out / "differences.tsv").write_text(
        "name\tjq_status\tgojq_status\tjq_json\tgojq_json\n"
        + "".join(
            f"{row['case']['name']}\t{row['jq']['status']}\t{row['gojq']['status']}\t"
            f"{json.dumps(row['jq']['json_values'], separators=(',', ':'))}\t"
            f"{json.dumps(row['gojq']['json_values'], separators=(',', ':'))}\n"
            for row in summary
            if not row["equivalent"]
        )
    )


if __name__ == "__main__":
    main()
