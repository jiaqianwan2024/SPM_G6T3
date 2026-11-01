-- TC-SPM64-AC02 (SPM-64): Occupied window adds setup and turnaround
-- Automated in e2e/spm64.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM64-AC02
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
