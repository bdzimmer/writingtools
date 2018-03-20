"""

Count (W)ords from (S)econdary items across commits in a (G)it respository.

"""
# Based on https://gist.github.com/hjwp/7542608
# New functionality (c) 2018 Ben Zimmer. All rights reserved.

from __future__ import print_function

import datetime
import os
import re
import subprocess
import sys

import attr
from matplotlib import pyplot as plt
import matplotlib.dates as mdates
import numpy as np


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
    DEVNULL = open(os.devnull, "w")


def git_log():
    commits = []
    log = subprocess.check_output(
        ["git", "log", "--format=%h|%s|%ai"], stderr=DEVNULL
    ).decode("utf8")
    for line in log.split("\n"):
        if line != "":
            hash, subject, datestring = line.split('|')
            date = datetime.datetime.strptime(datestring[:16], "%Y-%m-%d %H:%M")
            commits.append(Commit(hash, subject, date))
    return commits


def git_checkout(hash):
    subprocess.check_call(
        ["git", "checkout", hash],
        stderr=DEVNULL)


def parse_secondary_file(filename):
    """parse a secondary file into a list of items"""

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
        for commit, wordcounts in all_wordcounts.items():
            total_lines = sum([x.lines for x in wordcounts])
            total_words = sum([x.words for x in wordcounts])
            row = (commit.date, commit.subject, commit.hash, total_lines, total_words)
            data.append(row)
        data = sorted(data, key=lambda x: x[0])

        with open("wordcounts.tsv", "w") as output_file:
            output_file.write("\t".join(["date", "subject", "hash", "lines", "words"]) + "\n")
            for row in data:
                output_file.write("\t".join([str(x) for x in row]) + "\n")

        # plot total word count after each commit

        def round_date(x):
          return datetime.datetime(*x.timetuple()[:3]).date()

        def sunday_before(x):
            """given a date, get the Sunday before, rounded to midnight"""
            # https://stackoverflow.com/questions/18200530/get-the-last-sunday-and-saturdays-date-in-python
            weekday_idx = (x.weekday() + 1) % 7
            res = x - datetime.timedelta(weekday_idx)
            return round_date(res)

        date_first = data[0][0]
        date_last = max(x[0] for x in data)
        starting_wordcount = data[0][4]
        graph_start_date = sunday_before(date_first)
        graph_end_date = sunday_before(date_last + datetime.timedelta(7))
        days_count = (graph_end_date - graph_start_date).days

        title = "Word Count - " + "; ".join([x.replace("*", "") for x in ids])
        ticks = [
            round_date(graph_start_date + datetime.timedelta(7 * idx))
            for idx in range(days_count // 7 + 1)]

        plt.plot([x[0] for x in data], [x[4] for x in data], marker="o")
        plt.xticks(ticks)
        plt.title(title)
        plt.xlabel("datetime")
        plt.ylabel("word count")
        plt.grid(True)
        ax = plt.gca()
        ax.set_axisbelow(True)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        fig = plt.gcf()
        fig.autofmt_xdate()
        fig.set_size_inches(8, 6)
        fig.savefig("wordcounts.png", dpi=100)
        # plt.show()

        #### aggregate writing by week

        # group by sunday before
        wordcounts_with_sunday = [(sunday_before(x[0]), x[4]) for x in data]
        wordcounts_by_sunday = {}
        for sunday, wordcount in wordcounts_with_sunday:
            wordcounts = wordcounts_by_sunday.setdefault(sunday, [])
            wordcounts.append(wordcount)
        max_by_sunday = sorted([(k, max(v)) for k, v in wordcounts_by_sunday.items()], key=lambda x: x[0])

        diffs = np.diff([starting_wordcount] + [x[1] for x in max_by_sunday])
        sundays = [x[0] for x in max_by_sunday]

        plt.clf()
        plt.bar(range(len(diffs)), diffs, tick_label=sundays)
        plt.title(title)
        plt.xlabel("datetime")
        plt.ylabel("word count")
        plt.grid(True)
        ax = plt.gca()
        ax.set_axisbelow(True)
        fig = plt.gcf()
        fig.autofmt_xdate()
        fig.set_size_inches(8, 6)
        fig.savefig("weeks.png", dpi=100)

    finally:
        git_checkout("master")


if __name__ == "__main__":
    main(sys.argv)