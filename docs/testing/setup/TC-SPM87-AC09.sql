-- TC-SPM87-AC09 (SPM-87): Reschedule written to the activity log
-- Automated in e2e/spm87.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM87-AC09
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
