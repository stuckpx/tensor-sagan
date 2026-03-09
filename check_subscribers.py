#!/usr/bin/env python3
"""Quick CLI tool to check Haramain Fridays subscribers."""

import os
import firebase_admin
from firebase_admin import credentials, firestore

CRED_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'harmainfridays-firebase-adminsdk-fbsvc-c21f19e297.json')

cred = credentials.Certificate(CRED_PATH)
firebase_admin.initialize_app(cred)
db = firestore.client()

docs = db.collection('subscribers').stream()
active = []
inactive = []

for doc in docs:
    d = doc.to_dict()
    entry = {
        'email': d.get('email', 'N/A'),
        'active': d.get('active', False),
        'subscribed': str(d.get('subscribed_at', 'N/A'))[:19],
    }
    if entry['active']:
        active.append(entry)
    else:
        inactive.append(entry)

# Sort by subscribe date (newest first)
active.sort(key=lambda x: x['subscribed'], reverse=True)

print(f"\n🕌 Haramain Fridays — {len(active)} active subscriber(s)\n")
print(f"{'#':<4} {'Email':<40} {'Subscribed'}")
print('-' * 65)
for i, s in enumerate(active, 1):
    print(f"{i:<4} {s['email']:<40} {s['subscribed']}")

if inactive:
    print(f"\n⏸  {len(inactive)} inactive:")
    for s in inactive:
        print(f"     {s['email']}")

print()
