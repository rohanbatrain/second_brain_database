#!/usr/bin/env python3
"""Inspect a user document in the local MongoDB for debugging.
Usage: .venv/bin/python scripts/inspect_user.py --username demo_user_b_c39ef6
"""
import argparse
import json
from pymongo import MongoClient

parser = argparse.ArgumentParser()
parser.add_argument('--username', required=True)
args = parser.parse_args()

client = MongoClient('mongodb://localhost:27017')
db = client['SecondBrainDatabase']
user = db.users.find_one({'username': args.username})
print(json.dumps(user, default=str, indent=2))
