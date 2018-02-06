"""

Count (W)ords from (S)econdary items across commits in a (G)it respository.

"""
# Based on https://gist.github.com/hjwp/7542608
# New functionality (c) 2018 Ben Zimmer. All rights reserved.

from __future__ import print_function

from datetime import datetime
import os
import re
import subprocess
import sys

import attr
from matplotlib import pyplot as plt


@attr.s(hash=True)
class Commit(object):
  hash = attr.ib()
  subject = attr.ib()
  date = attr.ib()


@attr.s(hash=True)
class WordCount(object):
  name = attr.ib()
  lines = attr.ib()
  words = attr.ib()


if hasattr(subprocess, "DEVNULL"):
    DEVNULL = subprocess.DEVNULL
else:
    DEVNULL = open(os.devnull,"w")


def git_log():
    commits = []
    log = subprocess.check_output(
        ["git", "log", "--format=%h|%s|%ai"], stderr=DEVNULL
    ).decode("utf8")
    for line in log.split("\n"):
        if line != "":
            hash, subject, datestring = line.split('|')
            date = datetime.strptime(datestring[:16], "%Y-%m-%d %H:%M")
            commits.append(Commit(hash, subject, date))
    return commits


def git_checkout(hash):
    subprocess.check_call(
        ["git", "checkout", hash],
        stderr=DEVNULL)


def parse_secondary_file(filename):
    """parse a secondary file into a list of item"""

    items = []

    with open(filename) as f:
        contents = f.read()
    lines = contents.split("\n")

    # 0 - before start of item
    # 1 - in header
    # 2 - in notes
    state = 0
    item = None

    for line in lines:
        if line.startswith("!"):
            if item != None:
                items.append(item)
            item = {}
            state = 1
        elif state == 1:
            if line.strip() == "":
                state = 2
            else:
                line_split = re.split(":\\s+", line)
                item[line_split[0]] = ": ".join(line_split[1:])
        elif state == 2:
            notes = item.get("notes", "")
            item["notes"] = notes + line + "\n"

    if item is not None and len(item) > 0:
        items.append(item)

    return items


def file_wordcounts(input_dir, ext):
    docs = [f for f in os.listdir(input_dir) if f.endswith(ext)]
    wordcounts = []
    for filename in docs:
        with open(os.path.join(input_dir, filename)) as f:
            contents = f.read()
        lines = contents.split("\n")
        length_words = sum([len(line.split()) for line in lines])
        wordcounts.append(WordCount(filename, len(lines), length_words))
    return wordcounts


def secondary_wordcounts(ids, input_dir, ext):
    docs = [f for f in os.listdir(input_dir) if f.endswith(ext)]
    wordcounts = []
    for filename in docs:
        items = parse_secondary_file(os.path.join(input_dir, filename))
        for item in items:
            if item.get("id") in ids or item.get("name") in ids:
                if item.get("notes") is not None:
                    lines = item["notes"].split("\n")
                    length_words = sum([len(line.split()) for line in lines])
                    wordcounts.append(WordCount(filename, len(lines), length_words))
    return wordcounts


def main(argv):
    """main program"""

    input_dir = "content"
    ids = argv[1:]
    # get_wordcounts = lambda: file_wordcounts(input_dir, ".sec")
    get_wordcounts = lambda: secondary_wordcounts(ids, input_dir, ".sec")

    commits = git_log()
    all_wordcounts = {}
    filenames = set()
    try:
        for commit in commits:
            print(commit.hash, commit.date, commit.subject)
            git_checkout(commit.hash)
            all_wordcounts[commit] = get_wordcounts()
            filenames.update(set(x.name for x in all_wordcounts[commit]))
        data = []
        with open("wordcounts.tsv", "w") as output_file:
            output_file.write("\t".join(["date", "subject", "hash", "lines", "words"]) + "\n")
            for commit, wordcounts in all_wordcounts.items():
                total_lines = sum([x.lines for x in wordcounts])
                total_words = sum([x.words for x in wordcounts])
                row = (commit.date, commit.subject, commit.hash, total_lines, total_words)
                data.append(row)
                output_file.write("\t".join([str(x) for x in row]) + "\n")
        data = sorted(data, key=lambda x: x[0])
        plt.plot([x[0] for x in data], [x[4] for x in data], marker="o")
        plt.title("Word Count - " + "; ".join([x.replace("*", "") for x in ids]))
        plt.xlabel("datetime")
        plt.ylabel("word count")
        fig = plt.gcf()
        fig.autofmt_xdate()
        fig.set_size_inches(8, 6)
        fig.savefig("wordcounts.png", dpi=100)
        # plt.show()

    finally:
        git_checkout("master")

if __name__ == "__main__":
    main(sys.argv)