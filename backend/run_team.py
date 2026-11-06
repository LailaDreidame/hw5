"""Run the Campus Customs agent team from the command line.

From backend/:
    python run_team.py --ticket 102 "Work ticket 102."
"""

from agents.team import main

if __name__ == "__main__":
    main()
