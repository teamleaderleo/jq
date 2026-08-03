# jq #3128 destructuring-path experiment

State: `CONTROLLED SOURCE EXPERIMENT — NO UPSTREAM SUBMISSION`

Exact product base: `603db3f57741d217ba651e61086b550a72148b83`.

## Evidence leading to this candidate

A four-layout compiler matrix showed that existing `SUBEXP` placement cannot express the required path semantics:

- canonical code rejects a matcher applied to a value that differs from the current path root;
- closed PR #3384 fixes simple examples but breaks ordinary nested/array bindings and still fails alternation;
- delaying `SUBEXP_END` until after the matcher erases every matcher path component;
- placing `POP` before that delayed `SUBEXP_END` corrupts the data stack and aborts.

`subexp_nest` intentionally suppresses both path integrity checks and path component recording. A destructuring matcher needs a narrower exception: its input may come from a separate expression, but a successful matcher key/index and the resulting bound value must remain the current path state so later traversal through the bound variable continues to work.

## Experiment

The runner-local candidate introduces `INDEX_DESTRUCTURE` and emits it only from object and array destructuring matchers. At runtime it:

1. indexes the actual value being destructured;
2. skips only the ordinary requirement that this container equal the current `value_at_path`;
3. records the matcher key/index through the existing `path_append()` logic;
4. advances `value_at_path` to the bound result exactly as normal indexing does.

This preserves valid chains such as:

```jq
path(. as {$a} | $a.b)
```

while leaving the normal final-result integrity check in place. A non-null expression such as `path({a:1} as {$a} | .)` remains invalid because the final original input is not the value reached at path `.a`.

Ordinary `INDEX`, optional indexing, stack behavior, and product source outside the disposable runner remain unchanged.

## Gates

The controlled workflow verifies exact source blobs, applies the three-file experiment, builds jq, and runs:

- the exact null-valued issue forms;
- nested object and array matchers;
- alternation and backtracking;
- bound-variable traversal for dot and constant sources;
- expected-invalid non-null original-result controls;
- ordinary bindings and plain paths;
- a `setpath` consumer;
- dedicated-opcode disassembly;
- Valgrind discriminators;
- complete `make check` and ordinary fork workflows.

No result is claimed until the hosted run completes. No canonical issue comment, pull request, review, or other upstream contact is authorized or made.
