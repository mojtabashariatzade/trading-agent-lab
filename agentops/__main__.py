"""Dedicated single-process deployment entry; delegates to the persistent supervisor."""
from .supervisor import main


if __name__ == "__main__":
    raise SystemExit(main())
