-- TC-SPM11-AC04 (SPM-11): Remaining places drop by one immediately
-- Automated in e2e/spm11.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM11-AC04
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
