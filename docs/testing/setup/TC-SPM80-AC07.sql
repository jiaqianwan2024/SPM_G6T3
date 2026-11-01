-- TC-SPM80-AC07 (SPM-80): Coordinator sees requirements unchanged
-- Automated in e2e/spm80.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM80-AC07
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
