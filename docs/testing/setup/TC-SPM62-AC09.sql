-- TC-SPM62-AC09 (SPM-62): Shared suitability rule
-- Automated in e2e/spm62.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM62-AC09
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
