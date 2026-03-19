"""
Quick script to check OpenTimestamps status for the latest submission.

Run with: python check_ots_status.py
"""
import sys
sys.path.insert(0, '.')

from opentimestamps.calendar import RemoteCalendar
from opentimestamps.core.notary import BitcoinBlockHeaderAttestation

# The hash we just submitted (with CORRECT pool servers)
HASH_HEX = "152c72907979bf46cf0b28e3c9a4791566b834c02e6717576f2f6054ed4ccf48"
SUBMITTED_AT = "2026-03-09 19:15:00"

print("="*80)
print("OpenTimestamps Status Check")
print("="*80)
print(f"\nHash: {HASH_HEX}")
print(f"Submitted: {SUBMITTED_AT}")
print("\nChecking calendar servers...")
print("="*80)

hash_bytes = bytes.fromhex(HASH_HEX)

calendars = [
    ('Alice', 'https://alice.btc.calendar.opentimestamps.org'),
    ('Bob', 'https://bob.btc.calendar.opentimestamps.org'),
    ('Finney', 'https://finney.calendar.eternitywall.com')
]

found_count = 0
bitcoin_count = 0

for name, url in calendars:
    print(f"\n{name} ({url})")
    calendar = RemoteCalendar(url)
    
    try:
        timestamp = calendar.get_timestamp(hash_bytes)
        
        if timestamp:
            found_count += 1
            print(f"  [FOUND] Hash is on this calendar!")
            
            attestations = list(timestamp.all_attestations())
            bitcoin_atts = [a for a in attestations if isinstance(a, BitcoinBlockHeaderAttestation)]
            
            if bitcoin_atts:
                bitcoin_count += 1
                print(f"  [SUCCESS] Bitcoin attestation found!")
                for att in bitcoin_atts:
                    height = att.height if hasattr(att, 'height') else 'unknown'
                    print(f"    Block height: {height}")
            else:
                print(f"  [PENDING] No Bitcoin attestation yet")
        else:
            print(f"  [NOT FOUND] Calendar returned None")
            
    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg or "Not found" in error_msg:
            print(f"  [NOT FOUND] 404 - Hash not on this calendar")
        else:
            print(f"  [ERROR] {e}")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"Calendars checked: {len(calendars)}")
print(f"Hash found on: {found_count}/{len(calendars)} calendars")
print(f"Bitcoin attestations: {bitcoin_count}/{len(calendars)} calendars")

if bitcoin_count > 0:
    print("\n[SUCCESS] Hash is anchored to Bitcoin blockchain!")
elif found_count > 0:
    print("\n[PENDING] Hash is queued, waiting for Bitcoin confirmation")
    print("Check again in 1-24 hours")
else:
    print("\n[WAITING] Hash not on calendars yet")
    print("This is normal for fresh submissions (< 10 minutes old)")
    print("Check again in 10-60 minutes")

print("\nTo check again, run: python check_ots_status.py")

