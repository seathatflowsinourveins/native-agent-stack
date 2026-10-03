#!/usr/bin/env python3
"""Retired historical WSL retrieval fixture; offline audit only."""
import argparse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['source', 'qmd'], required=True)
    parser.add_argument('--run-dir')
    for name in ['source', 'rg', 'ast-grep', 'node', 'package-prefix']:
        parser.add_argument('--'+name)
    parser.parse_args()
    parser.exit(1, 'WSL retrieval fixture retired: source/QMD replay is disabled. '
                'Run audit.py for offline historical consistency checks; '
                'see README.md for the separate current QMD recipe and unresolved advisory.\n')


if __name__ == '__main__':
    main()
