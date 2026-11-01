-- TC-SPM08-AC09 (SPM-8): Expired hold does not block and is not a confirmed booking
-- Automated in e2e/spm08.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM08-AC09
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
