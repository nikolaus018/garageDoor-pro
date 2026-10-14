#!/bin/sh
# Builds and runs the host unit tests for the hardware-independent firmware modules.
set -e
cd "$(dirname "$0")"
cc -std=c11 -Wall -Wextra -Werror -O1 -fsanitize=address,undefined -I../main \
    test_main.c ../main/ubx.c ../main/geo.c ../main/trip.c ../main/nmea.c -lm -o /tmp/garagedoor_tests
/tmp/garagedoor_tests
