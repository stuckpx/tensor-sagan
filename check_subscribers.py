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
    attr = d.get('attribution') or {}
    src = attr.get('utm_source') or ''
    if not src and attr.get('referrer'):
        # Show the referring host rather than the full URL.
        src = attr['referrer'].split('//')[-1].split('/')[0]
    entry = {
        'email': d.get('email', 'N/A'),
        'active': d.get('active', False),
        'subscribed': str(d.get('subscribed_at', 'N/A'))[:19],
        'source': src or ('direct' if attr else '—'),
        'country': attr.get('country', ''),
    }
    if entry['active']:
        active.append(entry)
    else:
        inactive.append(entry)

# Sort by subscribe date (newest first)
active.sort(key=lambda x: x['subscribed'], reverse=True)

print(f"\n🕌 Haramain Fridays — {len(active)} active subscriber(s)\n")
print(f"{'#':<4} {'Email':<38} {'Subscribed':<20} {'Source':<12} {'Cty'}")
print('-' * 86)
for i, s in enumerate(active, 1):
    print(f"{i:<4} {s['email']:<38} {s['subscribed']:<20} {s['source']:<12} {s['country']}")

# Channel rollup — the number that decides where effort goes next.
from collections import Counter
tally = Counter(s['source'] for s in active)
print(f"\n📊 By source: " + ", ".join(f"{k}={v}" for k, v in tally.most_common()))
print("   ('—' predates attribution tracking, added 2026-07-31)")

if inactive:
    print(f"\n⏸  {len(inactive)} inactive:")
    for s in inactive:
        print(f"     {s['email']}")

print()
