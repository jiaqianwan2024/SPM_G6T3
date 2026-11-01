-- TC-SPM82-AC07 (SPM-82): No minimum notice period
-- Automated in e2e/spm82.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM82-AC07
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
