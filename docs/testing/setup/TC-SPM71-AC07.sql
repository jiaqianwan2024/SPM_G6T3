-- TC-SPM71-AC07 (SPM-71): Terminal events cannot be edited
-- Automated in e2e/spm71.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM71-AC07
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
