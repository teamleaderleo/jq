#!/usr/bin/env bash
set -euo pipefail

jq_bin=${1:?jq binary required}
out=${2:?output directory required}
mkdir -p "$out/cases" "$out/observations" "$out/disassembly"

run_required() {
    local name=$1 input=$2 filter=$3 expected=$4
    local status=0
    printf '%s\n' "$input" | "$jq_bin" -c "$filter" \
        >"$out/cases/$name.stdout" 2>"$out/cases/$name.stderr" || status=$?
    printf '%d\n' "$status" >"$out/cases/$name.status"
    printf '%s' "$expected" >"$out/cases/$name.expected"

    local verdict=pass
    if [[ $status -ne 0 ]] || [[ -s "$out/cases/$name.stderr" ]] || \
       ! cmp -s "$out/cases/$name.expected" "$out/cases/$name.stdout"; then
        verdict=fail
    fi
    printf '%s\t%d\t%s\n' "$name" "$status" "$verdict" >>"$out/results.tsv"
}

run_observation() {
    local name=$1 input=$2 filter=$3
    local status=0
    printf '%s\n' "$input" | "$jq_bin" -c "$filter" \
        >"$out/observations/$name.stdout" 2>"$out/observations/$name.stderr" || status=$?
    printf '%d\n' "$status" >"$out/observations/$name.status"
    printf '%s\t%d\n' "$name" "$status" >>"$out/observations.tsv"
}

# Explicit issue contract and source/body separation.
run_required issue-constant-object null \
    'path({} as {$a} | .)' $'["a"]\n'
run_required issue-dot-object null \
    'path(. as {$a} | .)' $'["a"]\n'
run_required source-differs-from-input '{"body":2}' \
    'path({a:1} as {$a} | .)' $'["a"]\n'
run_required matcher-plus-body-path '{"body":2}' \
    'path({a:1} as {$a} | .body)' $'["a","body"]\n'
run_required source-path-is-not-traversal '{"src":{"a":1},"body":2}' \
    'path(.src as {$a} | .body)' $'["a","body"]\n'

# Nested, array, and alternative matchers.
run_required nested-object null \
    'path({b:{a:1}} as {b:{$a}} | .)' $'["b","a"]\n'
run_required array null \
    'path([1] as [$a] | .)' $'[0]\n'
run_required array-object null \
    'path([{a:1}] as [{$a}] | .)' $'[0,"a"]\n'
run_required alternation-object null \
    'path({a:1} as {$a} ?// [$a] | .)' $'["a"]\n'
run_required alternation-array null \
    'path([1] as {$a} ?// [$a] | .)' $'[0]\n'
run_required alternation-scalar null \
    'path(1 as {$a} ?// [$a] ?// $a | .)' $'[]\n'

# Backtracking must restore both path length and path authority.
run_required source-backtracking '{"body":2}' \
    'path(({}, {a:1}) as {$a} | .)' $'["a"]\n["a"]\n'
run_required alternative-backtracking null \
    'path(({a:1}, [2], 3) as {$a} ?// [$a] ?// $a | .)' $'["a"]\n[0]\n[]\n'
run_required body-backtracking '{"body":2,"other":3}' \
    'path({a:1} as {$a} | (.body, .other))' $'["a","body"]\n["a","other"]\n'

# Ordinary destructuring and ordinary paths must remain unchanged.
run_required binding-object null \
    '{} as {$a} | $a' $'null\n'
run_required binding-nested null \
    '{b:{a:1}} as {b:{$a}} | $a' $'1\n'
run_required binding-array null \
    '[1] as [$a] | $a' $'1\n'
run_required plain-path-object '{"a":1}' \
    'path(.a)' $'["a"]\n'
run_required plain-path-nested '{"b":{"a":1}}' \
    'path(.b.a)' $'["b","a"]\n'
run_required plain-path-array '[1]' \
    'path(.[0])' $'[0]\n'

# Assignment consequences are retained for review before they become a source contract.
run_observation assign-constant-root null \
    '({} as {$a} | .) = 1'
run_observation assign-matcher-and-body '{"body":2}' \
    '({a:1} as {$a} | .body) = 9'
run_observation update-matcher-and-body '{"a":{"body":10},"body":2}' \
    '({a:1} as {$a} | .body) |= . + 1'
run_observation assign-source-path-excluded '{"src":{"a":1},"body":2}' \
    '(.src as {$a} | .body) = 9'

for item in \
    'issue-constant-object|path({} as {$a} | .)' \
    'source-path-is-not-traversal|path(.src as {$a} | .body)' \
    'alternation-object|path({a:1} as {$a} ?// [$a] | .)'
do
    name=${item%%|*}
    filter=${item#*|}
    printf '%s\n' '{"src":{"a":1},"body":2}' | \
        "$jq_bin" --debug-dump-disasm -c "$filter" \
        >"$out/disassembly/$name.stdout" 2>"$out/disassembly/$name.stderr" || true
done

sha256sum "$jq_bin" >"$out/jq.sha256"
"$jq_bin" --version >"$out/jq-version.txt"

if grep -q $'\tfail$' "$out/results.tsv"; then
    exit 1
fi
