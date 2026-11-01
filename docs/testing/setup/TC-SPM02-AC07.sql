-- TC-SPM02-AC07 (SPM-2): Re-check after reserve or release
-- Automated in e2e/spm02.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM02-AC07
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
