# Testing Guide

## Running Tests

```sh
# Run all tests with pytest
python3 -m pytest tests/ -v

# Run a specific test file
python3 -m pytest tests/test_sql_db.py -v

# Run a specific test function
python3 -m pytest tests/test_sql_db.py::test_hash_chain -v

# Run with coverage (optional)
python3 -m pytest tests/ --cov=tools --cov=scripts
```

## Test Summary

| Test | What it tests |
|------|---------------|
| test_sql_db.py | SQL hash chain, interaction storage |
| test_graph_db.py | Entity/relationship creation with proofs |
| test_verification.py | Cryptographic proof verification |
| test_db_utils.py | Retry/locking utilities |
| test_entity_retrieval.py | Column index correctness |
| test_deletion.py | Write protection (triggers prevent DELETE) |
| test_graph_traversal.py | Related entity queries, direction |
| test_workflow_hardening.py | Integration tests for sync workflow |
| test_timestamp_proof.py | OpenTimestamps proof handling |

## Known Issues on Windows

### test_tampering.py

This test intentionally bypasses write protection to show the vulnerability exists. It will FAIL if tampering is not detected - this is expected behavior showing the system needs database triggers.

Exit code 1 = tampering detection works correctly.

### test_store_query_integration.py

May fail with `sqlite3.OperationalError: unable to open database file` due to Windows temp directory permissions. This is a test harness issue, not the memory system.

### test_write_protection.py

May fail during cleanup with `PermissionError` because Windows still has the database file locked. The test assertions pass - only cleanup fails.

## Adding New Tests

1. Create `tests/test_yourfeature.py`
2. Use pytest conventions (`def test_*`, fixtures, etc.)
3. Use `tmp_path` fixture for temp directories (auto-cleanup)
4. Run with `python3 -m pytest tests/test_yourfeature.py -v`
