# Write Protection & Security

The memory system implements multiple layers of write protection to ensure data integrity.

---

## Overview

The SQL database is **append-only** by design:
- Interactions can be added but not modified
- Hash chain ensures tamper detection
- Soft deletes instead of hard deletes
- Metadata can be updated (processed flags, etc.)

---

## Protection Mechanisms

### 1. Read-Only Connection (Application-Level)

**Class:** `SQLDatabaseReadOnly`

**Purpose:** Provide safe read-only access without risk of accidental writes.

**Usage:**
```python
from tools.sql_db_readonly import SQLDatabaseReadOnly

# Read-only connection
readonly_db = SQLDatabaseReadOnly('./memory/conversations.db')

# Read operations work
project = readonly_db.get_project_by_name('my-project')
interactions = readonly_db.get_all_interactions('my-project')

# Write operations are blocked
readonly_db.store_interaction(...)  # [ERROR] Raises PermissionError
readonly_db.create_project(...)     # [ERROR] Raises PermissionError
```

**Benefits:**
- Prevents accidental writes during queries
- Safe for concurrent read access
- Clear separation of read/write operations

---

### 2. Database Triggers (Database-Level)

**Purpose:** Enforce immutability at the database level (like stored procedures).

**Triggers:**

#### a) Prevent Hash Chain Modification

```sql
CREATE TRIGGER prevent_hash_chain_update
BEFORE UPDATE ON interactions
WHEN OLD.content_hash != NEW.content_hash
  OR OLD.previous_hash != NEW.previous_hash
  OR OLD.chain_index != NEW.chain_index
BEGIN
  SELECT RAISE(ABORT, 'Hash chain fields are immutable.');
END
```

**Protects:**
- `content_hash` - Cannot be changed
- `previous_hash` - Cannot be changed
- `chain_index` - Cannot be changed

---

#### b) Prevent Content Modification

```sql
CREATE TRIGGER prevent_content_update
BEFORE UPDATE ON interactions
WHEN OLD.user_message != NEW.user_message
  OR OLD.assistant_message != NEW.assistant_message
  OR OLD.timestamp != NEW.timestamp
BEGIN
  SELECT RAISE(ABORT, 'Conversation content is immutable.');
END
```

**Protects:**
- `user_message` - Cannot be changed
- `assistant_message` - Cannot be changed
- `timestamp` - Cannot be changed

---

#### c) Prevent Hard Deletes

```sql
CREATE TRIGGER prevent_hard_delete
BEFORE DELETE ON interactions
BEGIN
  SELECT RAISE(ABORT, 'Hard deletes not allowed. Use soft delete.');
END
```

**Enforces:** Soft delete pattern (set `deleted_at` timestamp)

---

#### d) Prevent Project Renaming

```sql
CREATE TRIGGER prevent_project_update
BEFORE UPDATE ON projects
WHEN OLD.name != NEW.name
BEGIN
  SELECT RAISE(ABORT, 'Project name is immutable.');
END
```

**Protects:** Project names cannot be changed

---

## What CAN Be Updated

### Allowed Updates

**Processing metadata:**
- `processed` - Mark as extracted
- `extracted_at` - Timestamp of extraction

**Optional metadata:**
- `session_id` - Session identifier
- `interaction_number` - Sequence number
- `response_time_ms` - Performance metrics
- `token_count` - Token usage
- `context_data` - Additional context

**Soft delete:**
- `deleted_at` - Soft delete timestamp

**Example:**
```python
conn = sqlite3.connect('./memory/conversations.db')
cursor = conn.cursor()

# [OK] Allowed: Update processing status
cursor.execute("""
    UPDATE interactions
    SET processed = TRUE, extracted_at = CURRENT_TIMESTAMP
    WHERE uuid = ?
""", (uuid,))

# [OK] Allowed: Soft delete
cursor.execute("""
    UPDATE interactions
    SET deleted_at = CURRENT_TIMESTAMP
    WHERE uuid = ?
""", (uuid,))

# [ERROR] Blocked: Modify content
cursor.execute("""
    UPDATE interactions
    SET user_message = 'Tampered'
    WHERE uuid = ?
""", (uuid,))  # Raises IntegrityError

conn.commit()
```

---

## Security Benefits

### 1. Tamper Resistance

**Multiple layers:**
1. **Application layer** - Read-only connection blocks writes
2. **Database layer** - Triggers prevent unauthorized updates
3. **Cryptographic layer** - Hash chain detects tampering

**Even if an attacker:**
- Gets direct database access
- Bypasses application code
- Tries to modify data directly

**They cannot:**
- Modify conversation content
- Alter hash chain
- Delete interactions (hard delete)
- Change timestamps

---

### 2. Audit Trail

**Immutable record:**
- Every interaction is permanent
- Soft deletes preserve history
- Hash chain proves integrity
- Extraction proofs trace to source

**Compliance:**
- GDPR: Right to erasure (soft delete)
- SOC 2: Audit trail requirements
- HIPAA: Data integrity requirements

---

### 3. Defense in Depth

**Layer 1:** Application code (SQLDatabase class)
- Controlled write operations
- Validation and sanitization

**Layer 2:** Read-only connection (SQLDatabaseReadOnly)
- Prevents accidental writes
- Safe for queries

**Layer 3:** Database triggers
- Enforces immutability
- Cannot be bypassed

**Layer 4:** Cryptographic proofs
- Detects tampering
- Independent verification

---

## Testing

**Test file:** `tests/test_write_protection.py`

**Tests:**
1. [OK] Read-only connection blocks writes
2. [OK] Triggers prevent hash chain modification
3. [OK] Triggers prevent content modification
4. [OK] Triggers prevent hard deletes
5. [OK] Soft delete still works
6. [OK] Allowed updates still work

**Run tests:**
```bash
python3 tests/test_write_protection.py
```

---

## Best Practices

### 1. Use Read-Only Connection for Queries

```python
# GOOD: Use read-only for queries
from tools.sql_db_readonly import SQLDatabaseReadOnly
readonly_db = SQLDatabaseReadOnly('./memory/conversations.db')
interactions = readonly_db.get_all_interactions('my-project')

# BAD: Use full database for queries
from tools.sql_db import SQLDatabase
db = SQLDatabase('./memory/conversations.db')  # Has write access!
interactions = db.get_all_interactions('my-project')
```

### 2. Use Soft Delete

```python
# GOOD: Soft delete
cursor.execute("""
    UPDATE interactions
    SET deleted_at = CURRENT_TIMESTAMP
    WHERE uuid = ?
""", (uuid,))

# BAD: Hard delete (will be blocked by trigger)
cursor.execute("""
    DELETE FROM interactions
    WHERE uuid = ?
""", (uuid,))  # [ERROR] Raises IntegrityError
```

### 3. Never Bypass Triggers

```python
# BAD: Don't try to disable triggers
cursor.execute("PRAGMA recursive_triggers = OFF")  # Don't do this!

# GOOD: Work with the triggers
# Use the allowed update operations
```

---

## Summary

**Write protection ensures:**
- [OK] Conversation content is immutable
- [OK] Hash chain cannot be tampered with
- [OK] Audit trail is preserved
- [OK] Accidental writes are prevented
- [OK] Compliance requirements are met

**Similar to stored procedures:**
- Triggers enforce business logic at database level
- Cannot be bypassed by application code
- Provides defense in depth

**The memory system is secure by design!** 

