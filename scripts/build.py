#!/usr/bin/env python3
"""Rebuild the complete static site from saved data, without fetching or translating."""
import argparse
from . import scrape


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="Preview directory; defaults to the repository")
    args = parser.parse_args(argv)
    scrape.write_site(scrape.load_log(), False, args.output)


if __name__ == "__main__":
    main()
