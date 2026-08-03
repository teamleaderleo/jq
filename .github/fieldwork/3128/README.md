# jq #3128 destructuring-path experiment

State: `CONTROLLED SOURCE EXPERIMENT — NO UPSTREAM SUBMISSION`

Exact product base: `603db3f57741d217ba651e61086b550a72148b83`.

## Evidence leading to this candidate

A four-layout compiler matrix showed that the existing `SUBEXP` operations cannot express the required path semantics:

- the canonical layout rejects a matcher applied to a value that differs from the current path root;
- the closed PR #3384 layout fixes simple examples but breaks ordinary nested and array destructuring and still fails alternation;
- delaying `SUBEXP_END` until after the matcher erases every matcher path component;
- placing `POP` before that delayed `SUBEXP_END` corrupts the data stack and aborts.

`subexp_nest` intentionally suppresses both path integrity checks and path component recording. Destructuring needs a third behavior: bind against a separately produced value, record the matcher component, and keep `value_at_path` attached to the original input passed to the expression on the right of `as`.

## Experiment

The runner-local candidate introduces `INDEX_DESTRUCTURE` and emits it only from object and array destructuring matchers. At runtime it:

1. indexes the actual value being destructured for binding purposes;
2. skips the ordinary requirement that this value equal `value_at_path`;
3. records the matcher key/index in the path;
4. does not replace `value_at_path` with the bound value.

Ordinary `INDEX`, optional indexing, expression stack behavior, and product source outside the disposable runner remain unchanged.

## Gates

The controlled workflow verifies exact source blobs, applies the three-file experiment, builds jq, runs null and non-null object/array/nested/alternation/backtracking cases, checks ordinary bindings and `setpath`, requires the dedicated opcode in disassembly, runs Valgrind, and executes complete `make check`.

No result is claimed until the hosted run completes. No canonical issue comment, pull request, review, or other upstream contact is authorized or made.
