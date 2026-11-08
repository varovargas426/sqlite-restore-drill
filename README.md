# SQLite Restore Drill

Rehearse recovery of a ticket database. Create a consistent backup from a running SQLite application, restore into a disposable directory, and measure how much committed work the snapshot actually recovers.

## Reproduce the case

Requires Python 3.11+. All examples use synthetic data and run locally with the standard library. Run from the repository root.

```sh
python recovery.py demo
```

The case takes a backup after ticket 2, then commits ticket 3. Restoring the snapshot passes SQLite integrity and foreign-key checks but misses the required business watermark of 3. The verdict is behind_target with one missing sequence number. The demo exits successfully only if that expected outcome is reproduced.

## Design and limits

The online backup API captures committed pages, including WAL-backed changes. A transactional sequence ledger tracks ticket creation. The recovery check compares the ledger’s contiguous sequence and ticket count to an independently supplied minimum sequence. A matching count alone cannot detect malicious edits or prove authenticity. The workload model is append-only with IDs starting at one. `python recovery.py check BACKUP.sqlite --target 3` checks an existing closed snapshot of this schema and returns 0 for recovered, 1 for a failed drill, or 2 for invalid arguments. The checker copies the snapshot into a temporary directory before opening it; supply standalone snapshots created by the backup API.

## Verification

```sh
python -m unittest discover -s tests -v
```

Tests verify committed WAL data survives the backup, validate a lagging restore, detect ledger gaps, and reject corrupt bytes and orphaned records.
