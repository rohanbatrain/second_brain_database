#!/usr/bin/env bash
# Quick launcher for stopping all services
cd "$(dirname "$0")/scripts/startall" && ./stop_services.sh
