#!/bin/bash
# Get latest code
cd /opt/node_apps/built-docs && CURRENT="$(git symbolic-ref --short HEAD)" && git fetch && git reset --hard origin/$CURRENT
