#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one match in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


root = Path(__file__).resolve().parents[3]

opcode_list = root / "src/opcode_list.h"
replace_once(
    opcode_list,
    "OP(INDEX, NONE,     2, 1)\nOP(INDEX_OPT, NONE,     2, 1)\n",
    "OP(INDEX, NONE,     2, 1)\n"
    "OP(INDEX_DESTRUCTURE, NONE, 2, 1)\n"
    "OP(INDEX_OPT, NONE,     2, 1)\n",
)

compile_c = root / "src/compile.c"

# Tag only the index operations owned by destructuring matcher construction.
# Dynamic object-key expressions retain their ordinary INDEX instructions.
replace_once(
    compile_c,
    "  return BLOCK(gen_op_simple(DUP), gen_subexp(gen_const(jv_number(index))),\n"
    "               gen_op_simple(INDEX), curr, left);\n",
    "  return BLOCK(gen_op_simple(DUP), gen_subexp(gen_const(jv_number(index))),\n"
    "               gen_op_simple(INDEX_DESTRUCTURE), curr, left);\n",
)
replace_once(
    compile_c,
    "  return BLOCK(gen_op_simple(DUP), gen_subexp(name), gen_op_simple(INDEX),\n"
    "               curr);\n",
    "  return BLOCK(gen_op_simple(DUP), gen_subexp(name),\n"
    "               gen_op_simple(INDEX_DESTRUCTURE), curr);\n",
)

# A jq path is linear. A complete matcher branch with one binding has one
# unambiguous matcher path. A branch with sibling bindings does not: every
# sibling indexes the same retained container, so accumulating their keys would
# manufacture a parent/child chain. Restore those matcher-owned instructions to
# canonical INDEX unless the complete branch has exactly one unbound binding.
replace_once(
    compile_c,
    '''static void block_get_unbound_vars(block b, jv *vars) {
  assert(vars != NULL);
  assert(jv_get_kind(*vars) == JV_KIND_OBJECT);
  for (inst* i = b.first; i; i = i->next) {
    if (i->subfn.first) {
      block_get_unbound_vars(i->subfn, vars);
      continue;
    }
    if ((i->op == STOREV || i->op == STOREVN) && i->bound_by == NULL) {
      *vars = jv_object_set(*vars, jv_string(i->symbol), jv_true());
    }
  }
}
''',
    '''static void block_get_unbound_vars(block b, jv *vars) {
  assert(vars != NULL);
  assert(jv_get_kind(*vars) == JV_KIND_OBJECT);
  for (inst* i = b.first; i; i = i->next) {
    if (i->subfn.first) {
      block_get_unbound_vars(i->subfn, vars);
      continue;
    }
    if ((i->op == STOREV || i->op == STOREVN) && i->bound_by == NULL) {
      *vars = jv_object_set(*vars, jv_string(i->symbol), jv_true());
    }
  }
}

static int count_unbound_matcher_bindings(inst *first) {
  int count = 0;

  for (inst *i = first; i; i = i->next) {
    if (i->subfn.first)
      count += count_unbound_matcher_bindings(i->subfn.first);
    if ((i->op == STOREV || i->op == STOREVN) && i->bound_by == NULL)
      count++;
  }

  return count;
}

static void restore_ambiguous_destructure_indexes(inst *first) {
  for (inst *i = first; i; i = i->next) {
    if (i->subfn.first)
      restore_ambiguous_destructure_indexes(i->subfn.first);
    if (i->op == INDEX_DESTRUCTURE)
      i->op = INDEX;
  }
}

static void scope_destructure_indexes(inst *first) {
  if (count_unbound_matcher_bindings(first) != 1)
    restore_ambiguous_destructure_indexes(first);
}
''',
)

replace_once(
    compile_c,
    '''block gen_destructure_alt(block matcher) {
  for (inst *i = matcher.first; i; i = i->next) {
''',
    '''block gen_destructure_alt(block matcher) {
  scope_destructure_indexes(matcher.first);
  for (inst *i = matcher.first; i; i = i->next) {
''',
)

replace_once(
    compile_c,
    '''block gen_destructure(block var, block matchers, block body) {
  // var bindings can be added after coding the program; leave the TOP first.
  block top = gen_noop();
''',
    '''block gen_destructure(block var, block matchers, block body) {
  // Alternative matchers were scoped before they were wrapped in DESTRUCTURE_ALT.
  // Scope only the final matcher segment here so sibling alternatives do not
  // affect one another's binding counts.
  inst *final_matcher = matchers.first;
  while (final_matcher && final_matcher->op == DESTRUCTURE_ALT)
    final_matcher = final_matcher->next;
  scope_destructure_indexes(final_matcher);

  // var bindings can be added after coding the program; leave the TOP first.
  block top = gen_noop();
''',
)

execute_c = root / "src/execute.c"
replace_once(
    execute_c,
    "    case INDEX:\n"
    "    case INDEX_OPT: {\n"
    "      jv t = stack_pop(jq);\n"
    "      jv k = stack_pop(jq);\n"
    "      // detect invalid path expression like path(reverse | .a)\n"
    "      if (!path_intact(jq, jv_copy(t))) {\n"
    "        char keybuf[30];\n"
    "        char objbuf[30];\n"
    "        jv msg = jv_string_fmt(\n"
    "            \"Invalid path expression near attempt to access element %s of %s\",\n"
    "            jv_dump_string_trunc(k, keybuf, sizeof(keybuf)),\n"
    "            jv_dump_string_trunc(t, objbuf, sizeof(objbuf)));\n"
    "        set_error(jq, jv_invalid_with_msg(msg));\n"
    "        goto do_backtrack;\n"
    "      }\n"
    "      jv v = jv_get(t, jv_copy(k));\n"
    "      if (jv_is_valid(v)) {\n"
    "        path_append(jq, k, jv_copy(v));\n"
    "        stack_push(jq, v);\n"
    "      } else {\n"
    "        jv_free(k);\n"
    "        if (opcode == INDEX)\n"
    "          set_error(jq, v);\n"
    "        else\n"
    "          jv_free(v);\n"
    "        goto do_backtrack;\n"
    "      }\n"
    "      break;\n"
    "    }\n",
    "    case INDEX:\n"
    "    case INDEX_DESTRUCTURE:\n"
    "    case INDEX_OPT: {\n"
    "      jv t = stack_pop(jq);\n"
    "      jv k = stack_pop(jq);\n"
    "      // A single-binding destructuring branch indexes a separately\n"
    "      // produced matcher value, but its one key/index and resulting value\n"
    "      // still form an unambiguous path for later bound traversal.\n"
    "      if (opcode != INDEX_DESTRUCTURE && !path_intact(jq, jv_copy(t))) {\n"
    "        char keybuf[30];\n"
    "        char objbuf[30];\n"
    "        jv msg = jv_string_fmt(\n"
    "            \"Invalid path expression near attempt to access element %s of %s\",\n"
    "            jv_dump_string_trunc(k, keybuf, sizeof(keybuf)),\n"
    "            jv_dump_string_trunc(t, objbuf, sizeof(objbuf)));\n"
    "        set_error(jq, jv_invalid_with_msg(msg));\n"
    "        goto do_backtrack;\n"
    "      }\n"
    "      jv v = jv_get(t, jv_copy(k));\n"
    "      if (jv_is_valid(v)) {\n"
    "        path_append(jq, k, jv_copy(v));\n"
    "        stack_push(jq, v);\n"
    "      } else {\n"
    "        jv_free(k);\n"
    "        if (opcode == INDEX || opcode == INDEX_DESTRUCTURE)\n"
    "          set_error(jq, v);\n"
    "        else\n"
    "          jv_free(v);\n"
    "        goto do_backtrack;\n"
    "      }\n"
    "      break;\n"
    "    }\n",
)
