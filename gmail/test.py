import time
import sys


def backspace(n):
    print((b'\x08' * n).decode()) # use \x08 char to go back
    # print('\r' * n, end='')                 # use '\r' to go back


for i in range(101):                        # for 0 to 100
    s = str(i) + '%'                        # string for output
    print(s)                        # just print and flush
    # sys.stdout.flush()                    # needed for flush when using \x08
    backspace(len(s))                       # back for n chars

    time.sleep(0.2)                         # sleep for 200ms
