import os

# Tests price with the bundled price books, never a refreshed copy on this machine.
os.environ["CLARCHY_PRICES_DIR"] = ""
