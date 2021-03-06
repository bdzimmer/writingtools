"""

Count (W)ords from (S)econdary items across commits in a (G)it respository.

"""
# Copyright (c) 2018 Ben Zimmer. All rights reserved.
# Inspired by https://gist.github.com/hjwp/7542608

from __future__ import print_function

import datetime
import os
import pickle
import re
import subprocess
import string
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
    """run 'git log' and parse the output into commit objects"""
    commits = []
    log = subprocess.check_output(
        ["git", "log", "--format=%h|%s|%ai"], stderr=DEVNULL
    ).decode("utf8")
    for line in log.split("\n"):
        if line != "":
            commit_hash, subject, datestring = line.split('|')
            date = datetime.datetime.strptime(datestring[:16], "%Y-%m-%d %H:%M")
            commits.append(Commit(commit_hash, subject, date))
    return commits


def git_checkout(commit_hash):
    """run 'git checkout'"""
    subprocess.check_call(
        ["git", "checkout", commit_hash],
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
            if item is not None:
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

    for item in items:
        if item.get("id") is None and item.get("name") is not None:
            item_id = item.get("name")
            item_id = item_id.lower()
            for c in string.punctuation:
                item_id = item_id.replace(c, "")
            item_id = item_id.replace(" ", "_")
            item["id"] = item_id

    return items


def secondary_wordcounts(ids, input_dir, ext):
    """count words of secondary files by item id or name"""
    docs = [f for f in os.listdir(input_dir) if f.endswith(ext)]
    wordcounts = {x: WordCount(None, 0, 0) for x in ids}
    for filename in docs:
        items = parse_secondary_file(os.path.join(input_dir, filename))
        for item in items:
            for identifier in ids:
                if item.get("id") == identifier or item.get("name") == identifier:
                    if item.get("notes") is not None:
                        lines = item["notes"].split("\n")
                        length_words = sum([len(line.split()) for line in lines])
                        wordcounts[identifier] = WordCount(filename, len(lines), length_words)
    return wordcounts


def main(argv):
    """main program"""

    input_dir = "content"

    ids = argv[1:]

    # unique name based on set of ids
    config_name = ";".join(ids)
    cache_filename = config_name + "_wordcount.pkl"

    get_wordcounts = lambda: secondary_wordcounts(ids, input_dir, ".sec")

    if os.path.exists(cache_filename):
        with open(cache_filename, "rb") as cache_file:
            all_wordcounts = pickle.load(cache_file)
    else:
        all_wordcounts = {}

    commits = git_log()

    try:
        # update the master wordcounts cache
        for commit in commits:
            print(commit.hash, commit.date, commit.subject, end=" ")
            # update wordcounts (for all ids) if some are not present
            found = True
            for identifier in ids:
                if all_wordcounts.get(commit) is None or identifier not in all_wordcounts[commit]:
                    found = False
                    break
            if not found:
                print("*")
                git_checkout(commit.hash)
                commit_wordcounts = all_wordcounts.setdefault(commit, {})
                for identifier, wordcount in get_wordcounts().items():
                    commit_wordcounts[identifier] = wordcount
            else:
                print(".")

        # extract the data for the current set of ids
        data = []
        for commit, wordcounts in all_wordcounts.items():
            total_lines = sum([x.lines for x in wordcounts.values()])
            total_words = sum([x.words for x in wordcounts.values()])
            row = (commit.date, commit.subject, commit.hash, total_lines, total_words)
            data.append(row)
        data = sorted(data, key=lambda x: x[0])

        # keep everything between the first and last dates with
        # nonzero wordcount changes
        data_wordcounts = [x[4] for x in data]
        data_deltas = [x - y for x, y in zip(data_wordcounts, [0] + data_wordcounts[:-1])]
        nonzero_dates = [x[0] for x, y in zip(data, data_deltas) if y != 0]
        date_first = nonzero_dates[0]
        date_last = nonzero_dates[-1]
        data = [x for x in data if x[0] >= date_first and x[0] <= date_last]

        with open(config_name + "_wordcounts.tsv", "w") as output_file:
            output_file.write("\t".join(["date", "subject", "hash", "lines", "words"]) + "\n")
            for row in data:
                output_file.write("\t".join([str(x) for x in row]) + "\n")

        # save the cache
        with open(cache_filename, "wb") as cache_file:
            pickle.dump(all_wordcounts, cache_file)

        # -------- plot total word count after each commit --------

        def round_date(x):
            return datetime.datetime(*x.timetuple()[:3]).date()

        def startday_before(x):
            """given a date, get the start day before, rounded to midnight"""
            # https://stackoverflow.com/questions/18200530/get-the-last-sunday-and-saturdays-date-in-python
            # convert monday-sunday to sunday-saturday
            # sunday
            # weekday_idx = (x.weekday() + 1) % 7
            # monday
            weekday_idx = (x.weekday()) % 7
            res = x - datetime.timedelta(weekday_idx)
            return round_date(res)

        date_first = data[0][0]
        date_last = max(x[0] for x in data)

        graph_start_date = startday_before(date_first)
        graph_end_date = startday_before(date_last + datetime.timedelta(7))
        days_count = (graph_end_date - graph_start_date).days

        ids_string = "; ".join([x.replace("*", "") for x in ids])
        title = "Word Count - " + ids_string
        ticks = [
            round_date(graph_start_date + datetime.timedelta(7 * idx))
            for idx in range(days_count // 7 + 1)]

        plt.plot([x[0] for x in data], [x[4] for x in data], marker="o")
        plt.xticks(ticks, fontsize=8)
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
        fig.savefig(config_name + "_wordcounts.png", dpi=100)
        # plt.show()

        # -------- aggregate words written per week --------

        # starting_wordcount = data[0][4]
        starting_wordcount = 0

        # group by start day before
        wordcounts_with_startday = [(startday_before(x[0]), x[0], x[4]) for x in data]
        wordcounts_by_startday = {}
        for startday, day, wordcount in wordcounts_with_startday:
            wordcounts = wordcounts_by_startday.setdefault(startday, [])
            wordcounts.append((day, wordcount))
        last_by_startday = sorted([
            (k, sorted(v, key=lambda x: x[0])[-1][1])
            for k, v in wordcounts_by_startday.items()], key=lambda x: x[0])

        diffs = np.diff([starting_wordcount] + [x[1] for x in last_by_startday])
        startdays = [x[0] for x in last_by_startday]

        title = "Words Written per Week - " + ids_string
        plt.clf()
        plt.bar(range(len(diffs)), diffs, tick_label=startdays)
        plt.xticks(fontsize=8)
        plt.title(title)
        plt.xlabel("datetime")
        plt.ylabel("word count")
        plt.grid(True)
        ax = plt.gca()
        ax.set_axisbelow(True)
        fig = plt.gcf()
        fig.autofmt_xdate()
        fig.set_size_inches(8, 6)
        fig.savefig(config_name + "_weeks.png", dpi=100)

    finally:
        git_checkout("master")


if __name__ == "__main__":
    main(sys.argv)
