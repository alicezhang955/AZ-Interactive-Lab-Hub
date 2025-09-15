#!/bin/sh
'''exec' "/home/pi/Documents/GitHub/Interactive-Lab-Hub/Lab 2/.venv/bin/python3" "$0" "$@"
' '''
# -*- coding: utf-8 -*-
import re
import sys
from pyorbital.fetch_tles import run
if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw|\.exe)?$', '', sys.argv[0])
    sys.exit(run())
