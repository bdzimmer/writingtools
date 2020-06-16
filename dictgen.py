"""

Generate custom dictionary files for various editors and word processors.

"""

# Copyright (c) 2020 Ben Zimmer. All rights reserved.

import os
import json
import sys


def main(argv):
    """main program"""

    if len(argv) < 2:
        config_filename = "dictgen.json"
    else:
        config_filename = argv[1]

    with open(config_filename, "r") as config_file:
        config = json.load(config_file)

    input_filename = config.get("input_filename")
    output_filename = config.get("output_filename")
    npp_dirname = config.get("npp_dirname")
    soffice_dirname = config.get("soffice_dirname")

    print("input file:          ", input_filename)
    print("output file:         ", output_filename)
    print("Notepad++ dict dir:  ", npp_dirname)
    print("LibreOffice dict dir:", soffice_dirname)

    if not os.path.exists(input_filename):
        print(f"input file '${input_filename}' not found")
        sys.exit()

    if npp_dirname is not None and not os.path.exists(npp_dirname):
        print(f"Notepad++ dict dir '{npp_dirname}' not found")
        sys.exit()

    if soffice_dirname is not None and not os.path.exists(soffice_dirname):
        print(f"LibreOffice dict dir '{npp_dirname}' not found")
        sys.exit()

    # read the source file
    with open(input_filename, "r") as input_file:
        lines = input_file.readlines()
    words = [x.rstrip() for x in lines]
    words = sorted(list(set(words)))

    # write sorted version
    lines = [x + "\n" for x in sorted(list(set(words)))]
    with open(output_filename, "w") as output_file:
        output_file.writelines(lines)

    # write Notepad++ version
    if npp_dirname is not None:
        # use parts of hyphenated words
        words_with_hyphens = [x for x in words if "-" in x]
        words_without_hyphens = [x for x in words if "-" not in x]
        word_parts = [y for x in words_with_hyphens for y in x.split("-")]
        lines = [x + "\n" for x in sorted(list(set(words_without_hyphens + word_parts)))]

        npp_filename = os.path.join(npp_dirname, "en_US.usr")
        with open(npp_filename, "w") as output_file:
            output_file.write(str(len(lines)) + "\n")
            output_file.writelines(lines)
        print(f"wrote '{npp_filename}'")

    # write LibreOffice version
    if soffice_dirname is not None:
        # use original set of words
        lines = [x + "\n" for x in sorted(list(set(words)))]

        soffice_filename = os.path.join(soffice_dirname, "standard.dic")
        with open(soffice_filename, "w") as output_file:
            output_file.write("OOoUserDict1\n")
            output_file.write("lang: <none>\n")
            output_file.write("type: positive\n")
            output_file.write("---\n")
            output_file.writelines(lines)
        print(f"wrote '{soffice_filename}'")


if __name__ == "__main__":
    main(sys.argv)
