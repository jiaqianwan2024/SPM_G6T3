-- TC-SPM120-AC05 (SPM-120): Reject records reason, no preparation, not cancelled, both notified, resubmit
-- Automated in e2e/spm120.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM120-AC05
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
