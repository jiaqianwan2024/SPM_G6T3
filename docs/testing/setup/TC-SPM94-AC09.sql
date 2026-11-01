-- TC-SPM94-AC09 (SPM-94): Clear all empties the bell and badge, keeps history
-- Automated in e2e/spm94.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM94-AC09
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
