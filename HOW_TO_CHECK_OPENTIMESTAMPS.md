# How to Check OpenTimestamps Status (For Humans)

## Your Hash

```
a615b9c0627fbd94ea17dd7596dd9da3b9d23b8f590803dac7b500c20b355e65
```

Submitted at: 2026-03-09 16:13:03

---

## Method 1: Using Web Browser (Easiest)

### Check if hash is on calendar servers:

Visit these URLs in your browser:

1. **Alice Calendar:**
   ```
   https://alice.btc.calendar.opentimestamps.org/timestamp/a615b9c0627fbd94ea17dd7596dd9da3b9d23b8f590803dac7b500c20b355e65
   ```

2. **Bob Calendar:**
   ```
   https://bob.btc.calendar.opentimestamps.org/timestamp/a615b9c0627fbd94ea17dd7596dd9da3b9d23b8f590803dac7b500c20b355e65
   ```

3. **Finney Calendar:**
   ```
   https://finney.calendar.eternitywall.com/timestamp/a615b9c0627fbd94ea17dd7596dd9da3b9d23b8f590803dac7b500c20b355e65
   ```

**What you'll see:**
- **404 Not Found** = Hash not on this calendar yet (wait 10-60 minutes)
- **Binary data** = Hash is queued! (Download the .ots file)
- **Error** = Calendar server is down

---

## Method 2: Using curl (Command Line)

```powershell
# Check Alice calendar
curl https://alice.btc.calendar.opentimestamps.org/timestamp/a615b9c0627fbd94ea17dd7596dd9da3b9d23b8f590803dac7b500c20b355e65

# Check Bob calendar
curl https://bob.btc.calendar.opentimestamps.org/timestamp/a615b9c0627fbd94ea17dd7596dd9da3b9d23b8f590803dac7b500c20b355e65

# Check Finney calendar
curl https://finney.calendar.eternitywall.com/timestamp/a615b9c0627fbd94ea17dd7596dd9da3b9d23b8f590803dac7b500c20b355e65
```

---

## Method 3: Using Python Script

```powershell
python tmp/check_hash_on_calendar.py
```

This will check all 3 calendar servers and show the status.

---

## Method 4: Using OpenTimestamps CLI (Advanced)

If you have the `ots` command-line tool installed:

```sh
# Verify an .ots file
ots verify your_file.ots

# Upgrade an .ots file (get Bitcoin attestation)
ots upgrade your_file.ots
```

---

## Timeline

**What to expect:**

1. **0-10 minutes after submission:**
   - Hash is being processed by calendar servers
   - 404 Not Found is normal

2. **10-60 minutes after submission:**
   - Hash should appear on calendar servers
   - You can download the .ots file
   - Still no Bitcoin attestation (pending)

3. **1-24 hours after submission:**
   - Calendar servers batch submissions
   - Create Bitcoin transaction with Merkle tree
   - Transaction gets included in Bitcoin block
   - Bitcoin attestation becomes available!

4. **After Bitcoin confirmation:**
   - Hash is permanently anchored to Bitcoin blockchain
   - Can verify independently forever

---

## Current Status

**Submitted:** 2026-03-09 16:13:03 (a few minutes ago)

**Expected timeline:**
- Hash appears on calendars: ~16:23 - 17:13 (10-60 min from now)
- Bitcoin attestation: ~17:13 - 2026-03-10 16:13 (1-24 hours from now)

**Check again in 30 minutes!**

---

## Troubleshooting

**Q: Hash not found after 1 hour?**
- Calendar servers might be slow or down
- Try different calendar servers
- Check if submission actually succeeded

**Q: Hash found but no Bitcoin attestation after 24 hours?**
- Calendar servers might be batching less frequently
- Bitcoin network might be congested
- Wait another 24 hours

**Q: How do I know if it's anchored to Bitcoin?**
- The .ots file will contain a Bitcoin block header attestation
- You'll see a block height number
- You can verify on any Bitcoin block explorer

---

## For Developers

To check programmatically:

```python
from opentimestamps.calendar import RemoteCalendar

hash_hex = "a615b9c0627fbd94ea17dd7596dd9da3b9d23b8f590803dac7b500c20b355e65"
hash_bytes = bytes.fromhex(hash_hex)

calendar = RemoteCalendar('https://alice.btc.calendar.opentimestamps.org')
timestamp = calendar.get_timestamp(hash_bytes)

if timestamp:
    print("Hash is on calendar!")
    # Check for Bitcoin attestation
    from opentimestamps.core.notary import BitcoinBlockHeaderAttestation
    attestations = list(timestamp.all_attestations())
    bitcoin_atts = [a for a in attestations if isinstance(a, BitcoinBlockHeaderAttestation)]
    
    if bitcoin_atts:
        print(f"Bitcoin block: {bitcoin_atts[0].height}")
    else:
        print("Pending Bitcoin confirmation")
else:
    print("Hash not found yet")
```

