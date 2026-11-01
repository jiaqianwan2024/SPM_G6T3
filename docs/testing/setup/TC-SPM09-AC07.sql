-- TC-SPM09-AC07 (SPM-9): Cancel block frees the slot
-- Automated in e2e/spm09.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM09-AC07
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
