-- TC-SPM90-AC07 (SPM-90): Settings changes written to the activity log
-- Automated in e2e/spm90.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM90-AC07
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
