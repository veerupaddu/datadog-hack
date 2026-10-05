import os

# Tests must never push branches or open pull requests.
os.environ.setdefault("DEVPROD_ENABLE_PR", "0")
