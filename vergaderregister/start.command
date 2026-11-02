#!/bin/bash
# Dubbelklik om het Vergaderregister te starten.
cd "$(dirname "$0")"
if [ ! -d "data/📆 Vergaderingen" ]; then python3 seed.py; fi
( sleep 1.5; open "http://127.0.0.1:8765" ) &
python3 server.py
