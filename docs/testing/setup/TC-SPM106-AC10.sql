-- TC-SPM106-AC10 (SPM-106): Confirmed details stay confirmed while pending
-- Automated in e2e/spm106.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM106-AC10
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
