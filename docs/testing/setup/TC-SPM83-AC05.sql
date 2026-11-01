-- TC-SPM83-AC05 (SPM-83): Discard written to the activity log
-- Automated in e2e/spm83.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM83-AC05
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
