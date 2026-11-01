-- TC-SPM90-AC02 (SPM-90): Close after open and not after event start
-- Automated in e2e/spm90.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM90-AC02
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
