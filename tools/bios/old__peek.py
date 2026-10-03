#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
d = open(sys.argv[1], 'rb').read()
for a in sys.argv[2:]:
    o = int(a, 0)
    print('--- 0x%X ---' % o)
    print(' '.join('%02X' % b for b in d[o:o+64]))
