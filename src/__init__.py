import sys
import os

# Directory this __init__.py itself lives in (src/), where BaseAdapter.py
# and Logger.py sit directly.
THIS_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, THIS_DIR)
sys.path.insert(0, os.path.join(THIS_DIR, "hpo"))
sys.path.insert(0, os.path.join(THIS_DIR, "sct"))

from BaseAdapter import BaseAdapter
from HPOAdapter import HPOAdapter
from SCTAdapter import SCTAdapter