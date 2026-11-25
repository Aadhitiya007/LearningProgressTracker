"""Backward-compatible entrypoint delegating to cli.py and core modules."""

from cli import main

if __name__ == "__main__":
    main()
