-- TC-SPM09-AC08 (SPM-9): Unavailability changes in activity log
-- Automated in e2e/spm09.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM09-AC08
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
