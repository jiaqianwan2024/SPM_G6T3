-- TC-SPM62-AC06 (SPM-62): Tight fit is a warning
-- Automated in e2e/spm62.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM62-AC06
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
