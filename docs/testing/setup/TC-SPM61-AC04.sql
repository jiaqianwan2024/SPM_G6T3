-- TC-SPM61-AC04 (SPM-61): Expired hold does not exclude
-- Automated in e2e/spm61.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM61-AC04
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
