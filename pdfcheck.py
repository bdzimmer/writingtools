"""

Check PDF files generated by secondary's typesetting feature.

"""

# Copyright (c) 2020 Ben Zimmer. All rights reserved.

import sys
from typing import List, Tuple, Optional

import PyPDF2 as pdf
from PyPDF2.utils import b_
from PyPDF2.pdf import ContentStream, PageObject


DEBUG = False

TEXT_POSITION_OPS = [  # page 310
    b_(x) for x in ["Td", "TD", "Tm", "T*"]]

TEXT_SHOW_OPS = [  # page 311
    b_(x) for x in ["TJ", "'", "\"", "TJ"]]

SPACING_EXPECTED = {-14.445, -14.446}
START_EXPECTED = {
    528.045,        # normal pages
    # 400.95        # chapter title pages
    402.143         # chapter title pages
}

FONT_WEIGHT_MAPPING = {
    "/F34": "regular",
    "/F32": "bold"
}


def main(argv):
    """main program"""

    input_filename = argv[1]

    # ~~~~ load input file ~~~~

    print("loading '" + input_filename + "'...", end="", flush=True)

    ops_by_page = []
    with open(input_filename, "rb") as input_file:
        pdf_reader = pdf.PdfFileReader(input_file)
        pages = [pdf_reader.getPage(idx) for idx in range(pdf_reader.numPages)]
        for idx, page in enumerate(pages):
            ops = extract_ops(page)
            ops_by_page.append(ops)

    print("done")
    print()

    print("page count:", len(pages))
    print()

    # ~~~~ check line spacing ~~~~

    # skip title page and following blank page

    for idx_page, ops in enumerate(ops_by_page):

        if idx_page < 2:
            continue

        if len(ops) == 0:
            continue

        if DEBUG:
            for idx_op, (operands, operator) in enumerate(ops):
                print(idx + 1, idx_op, operator, operands)

        # It appears that most pages only use these ops:
        # {b'TJ', b'Td', b'BT', b'ET', b'Tf'}
        # print(set([x[1] for x in ops]))

        y_start, y_lines = line_spacing_info(ops)

        # if we toss the first element of y_lines, these values
        # should be roughly identical
        # TODO: not sure if I should be filtering out 0.0s
        y_distinct = {x for x in y_lines[1:] if x != 0.0}

        y_unexpected = y_distinct.difference(SPACING_EXPECTED)
        y_start_unexpected = y_start not in START_EXPECTED

        if DEBUG or len(y_unexpected) > 1 or y_start_unexpected:
            print("page", idx_page + 1)
            print("y start:", y_start, "(unexpected)" if y_start_unexpected else "")
            print("distinct y spacing values:", y_distinct)
            print("unexpected y spacing values:", y_unexpected)
            print()


def extract_ops(page: PageObject) -> List[Tuple]:
    """extract all operators"""
    content = page.getContents()
    if not isinstance(content, ContentStream):
        content = ContentStream(content, page.pdf)
    return list(content.operations)


def line_spacing_info(ops: List[Tuple]) -> Tuple[float, List[float]]:
    """find line spacing info by page"""

    font_switches = [
        (idx, operands)
        for idx, (operands, operator) in enumerate(ops)
        if operator == b"Tf"]

    # (idx, weight, size)
    font_changes = [
        (idx, FONT_WEIGHT_MAPPING.get(str(operands[0])), operands[1])
        for idx, operands in font_switches]

    operators = [x[1] for x in ops]
    start_idx, end_idx = body_range(operators, font_changes)

    ops_before_body = ops[:start_idx]
    ops_body = ops[start_idx:end_idx]

    y_start = sum([
        float(x[0][1])
        for x in ops_before_body
        if x[1] == b"Td"
    ])

    y_lines = [
        float(x[0][1])
        for x in ops_body
        if x[1] == b"Td"
    ]

    return y_start, y_lines


def body_range(
        operators: List[str],
        font_changes: List[Tuple]) -> Tuple[Optional[int], Optional[int]]:

    """given some assumptions about how headers and footers are formatted,
    find the operations describing the body text of of a page"""

    # font_changes: (idx, weight, size)

    thresh = 20.0

    if font_changes[0][2] > thresh:
        # if the first font is big, this is a chapter heading page
        # we want everything after the next font change

        # find the first Td after this point
        if len(font_changes) < 2:
            start_idx = None
        else:
            start_idx = font_changes[1][0]

        # And last three operations (for the page number) can be discarded.
        end_idx = len(operators) - 3

    elif font_changes[0][1] == "regular":
        # otherwise, we are looking for a (regular bold regular) pattern
        if len(font_changes) < 3:
            start_idx = None
        else:
            start_idx = font_changes[2][0] + 1

        # discard the final operation
        end_idx = len(operators) - 1

    elif font_changes[0][1] == "bold":
        # or (bold regular) pattern
        if len(font_changes) < 2:
            start_idx = None
        else:
            start_idx = font_changes[1][0] + 1 + 2  # (to skip over page number)

        # discard the final operation
        end_idx = len(operators) - 1

    else:
        start_idx = None
        end_idx = None

    if start_idx is not None and start_idx < len(operators):
        start_idx = operators[start_idx:].index(b"Td") + start_idx

    if end_idx is not None and end_idx > len(operators):
        end_idx = None

    return start_idx, end_idx


if __name__ == "__main__":
    main(sys.argv)
