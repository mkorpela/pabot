import cProfile
import pstats
from pabot.pabot import main
import os
import sys
import tempfile

profile_results = tempfile.mktemp(suffix=".out", prefix="pybot-profile", dir=".")
cProfile.run("main(sys.argv[1:])", profile_results)
stats = pstats.Stats(profile_results)
stats.sort_stats("cumulative").print_stats(50)
os.remove(profile_results)
