"""Allow running as `python -m clippertv.scheduler`."""

import sys

from clippertv.scheduler.service import main

sys.exit(main())
