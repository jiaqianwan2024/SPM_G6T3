-- TC-SPM57-AC02 (SPM-57): Bookings flagged for re-verification, with what changed
-- Automated in e2e/spm57.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM57-AC02
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
