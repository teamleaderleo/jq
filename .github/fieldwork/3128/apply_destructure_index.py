#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one match in {path}, found {count}")
    path.write_text(text.replace(old, new, 1))


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

execute_c = root / "src/execute.c"
replace_once(
    execute_c,
    "static void path_append(jq_state* jq, jv component, jv value_at_path) {\n"
    "  if (jq->subexp_nest == 0 && jv_get_kind(jq->path) == JV_KIND_ARRAY) {\n"
    "    int n1 = jv_array_length(jv_copy(jq->path));\n"
    "    jq->path = jv_array_append(jq->path, component);\n"
    "    int n2 = jv_array_length(jv_copy(jq->path));\n"
    "    assert(n2 == n1 + 1);\n"
    "    jv_free(jq->value_at_path);\n"
    "    jq->value_at_path = value_at_path;\n"
    "  } else {\n"
    "    jv_free(component);\n"
    "    jv_free(value_at_path);\n"
    "  }\n"
    "}\n",
    "static void path_append(jq_state* jq, jv component, jv value_at_path) {\n"
    "  if (jq->subexp_nest == 0 && jv_get_kind(jq->path) == JV_KIND_ARRAY) {\n"
    "    int n1 = jv_array_length(jv_copy(jq->path));\n"
    "    jq->path = jv_array_append(jq->path, component);\n"
    "    int n2 = jv_array_length(jv_copy(jq->path));\n"
    "    assert(n2 == n1 + 1);\n"
    "    jv_free(jq->value_at_path);\n"
    "    jq->value_at_path = value_at_path;\n"
    "  } else {\n"
    "    jv_free(component);\n"
    "    jv_free(value_at_path);\n"
    "  }\n"
    "}\n"
    "\n"
    "/* Destructuring matchers describe a path while binding against a value\n"
    " * produced by another expression. Record their components without\n"
    " * replacing value_at_path: the expression to the right of `as` still\n"
    " * receives the original input. */\n"
    "static void path_append_destructure(jq_state* jq, jv component) {\n"
    "  if (jq->subexp_nest == 0 && jv_get_kind(jq->path) == JV_KIND_ARRAY) {\n"
    "    int n1 = jv_array_length(jv_copy(jq->path));\n"
    "    jq->path = jv_array_append(jq->path, component);\n"
    "    int n2 = jv_array_length(jv_copy(jq->path));\n"
    "    assert(n2 == n1 + 1);\n"
    "  } else\n"
    "    jv_free(component);\n"
    "}\n",
)
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
    "      // Ordinary indexing must continue from the value reached by the\n"
    "      // current path. A destructuring matcher indexes a separate binding\n"
    "      // value, so it contributes only its component.\n"
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
    "        if (opcode == INDEX_DESTRUCTURE)\n"
    "          path_append_destructure(jq, k);\n"
    "        else\n"
    "          path_append(jq, k, jv_copy(v));\n"
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
