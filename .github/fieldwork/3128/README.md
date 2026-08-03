# jq #3128 single-binding destructuring-path experiment

State: `CONTROLLED SCOPED SOURCE EXPERIMENT — NO UPSTREAM SUBMISSION`

Exact product base: `603db3f57741d217ba651e61086b550a72148b83`.

## Evidence leading to this candidate

A four-layout compiler matrix proved that existing `SUBEXP` placement cannot express the required path semantics:

- canonical code rejects a matcher applied to a value that differs from the current path root;
- closed PR #3384 repairs simple examples but breaks ordinary nested/array bindings and alternatives;
- delaying `SUBEXP_END` until after the matcher erases every matcher path component;
- placing `POP` before the delayed end corrupts the data stack and aborts.

A first dedicated `INDEX_DESTRUCTURE` experiment then passed the reported single-binding cases, Valgrind, complete `make check`, and ordinary repository workflows. A separate multi-binding review exposed its over-broad compiler scope.

Sibling matchers each index the same retained container. Letting every matcher index advance one linear jq path manufactured artificial chains such as:

```text
["a","b"]
["x","a","b"]
[1,0]
```

The apparent path depended on matcher order and which bound value the body returned. That candidate is held and must not be promoted as written.

## Scoped experiment

Matcher construction still tags only its own generated index operations as `INDEX_DESTRUCTURE`; ordinary indexes inside dynamic key expressions are not tagged.

Before a complete matcher branch is bound to its body, the compiler counts unbound `STOREV`/`STOREVN` operations in that branch:

- exactly one binding: retain `INDEX_DESTRUCTURE` for the branch;
- zero or multiple bindings: restore every matcher-owned special index to canonical `INDEX`.

Alternative branches are scoped independently before being wrapped in `DESTRUCTURE_ALT`. The final alternative is scoped separately, so sibling alternatives do not affect one another's count.

At runtime the retained special opcode:

1. indexes the actual separately produced matcher value;
2. skips only the ordinary requirement that this container equal current `value_at_path`;
3. records the one unambiguous matcher key/index through existing `path_append()`;
4. advances `value_at_path` to the bound result for later bound-variable traversal;
5. leaves the normal final-result integrity check in place.

This keeps nested single-binding paths such as `{"x": [$a]}` expressible while refusing to invent a contract for `{$a,$b}`.

## Gates

The controlled workflow first builds exact canonical jq and records status, stdout, and stderr for 24 multi-binding programs, including:

- sibling object and array bindings;
- renamed and reversed patterns;
- nested siblings;
- source-path expressions;
- alternatives;
- source and body backtracking;
- `reduce` and `foreach`;
- correctly formed `setpath` consumers.

It then applies the three-file scoped patch and requires:

- the original single-binding semantic probe to pass;
- every multi-binding observation to remain byte-identical to canonical jq;
- single-binding disassembly to contain `INDEX_DESTRUCTURE`;
- sibling disassembly to contain no `INDEX_DESTRUCTURE`;
- Valgrind controls for both scopes;
- complete `make check`;
- exact product and carrier file fences.

No result is claimed until the hosted run completes. No canonical issue comment, pull request, review, reaction, email, or other upstream contact is authorized or made.
