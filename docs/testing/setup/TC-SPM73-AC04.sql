-- TC-SPM73-AC04 (SPM-73): History stays readable
-- Automated in e2e/spm73.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM73-AC04
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
