"""Entry point: python main.py crawl [urls...]"""

import sys

from webcrawler.cli import main

if __name__ == "__main__":
    sys.exit(main())
