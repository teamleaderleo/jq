#!/usr/bin/env python3
"""Apply the bounded jq #3128 path-rebase experiment.

This script is execution-only. It changes exactly three source files in a
disposable checkout and refuses to run if the pinned source shapes drift.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root

    opcode = root / "src/opcode_list.h"
    replace_once(
        opcode,
        "OP(SUBEXP_BEGIN,  NONE,     1, 2)\n"
        "OP(SUBEXP_END,    NONE,     2, 2)\n",
        "OP(SUBEXP_BEGIN,  NONE,     1, 2)\n"
        "OP(SUBEXP_END,    NONE,     2, 2)\n"
        "OP(DESTRUCTURE_PATH_BEGIN, NONE, 1, 2)\n"
        "OP(DESTRUCTURE_PATH_END,   NONE, 1, 0)\n",
    )

    execute = root / "src/execute.c"
    replace_once(
        execute,
        "    case SUBEXP_END: {\n"
        "      assert(jq->subexp_nest > 0);\n"
        "      jq->subexp_nest--;\n"
        "      jv a = stack_pop(jq);\n"
        "      jv b = stack_pop(jq);\n"
        "      stack_push(jq, a);\n"
        "      stack_push(jq, b);\n"
        "      break;\n"
        "    }\n\n"
        "    case PUSHK_UNDER: {\n",
        "    case SUBEXP_END: {\n"
        "      assert(jq->subexp_nest > 0);\n"
        "      jq->subexp_nest--;\n"
        "      jv a = stack_pop(jq);\n"
        "      jv b = stack_pop(jq);\n"
        "      stack_push(jq, a);\n"
        "      stack_push(jq, b);\n"
        "      break;\n"
        "    }\n\n"
        "    case DESTRUCTURE_PATH_BEGIN: {\n"
        "      jv source = stack_pop(jq);\n"
        "      stack_push(jq, jq->value_at_path);\n"
        "      jq->value_at_path = jv_copy(source);\n"
        "      stack_push(jq, source);\n"
        "      break;\n"
        "    }\n\n"
        "    case DESTRUCTURE_PATH_END: {\n"
        "      jv_free(jq->value_at_path);\n"
        "      jq->value_at_path = stack_pop(jq);\n"
        "      break;\n"
        "    }\n\n"
        "    case PUSHK_UNDER: {\n",
    )

    compile_c = root / "src/compile.c"
    replace_once(
        compile_c,
        "  return BLOCK(top, gen_subexp(var), gen_op_simple(POP), "
        "bind_alternation_matchers(matchers, body));\n",
        "  return BLOCK(top,\n"
        "               gen_subexp(var),\n"
        "               gen_op_simple(POP),\n"
        "               gen_op_simple(DESTRUCTURE_PATH_BEGIN),\n"
        "               bind_alternation_matchers(\n"
        "                   matchers,\n"
        "                   BLOCK(gen_op_simple(DESTRUCTURE_PATH_END), body)));\n",
    )

    changed = [
        "src/compile.c",
        "src/execute.c",
        "src/opcode_list.h",
    ]
    print("\n".join(changed))


if __name__ == "__main__":
    main()
