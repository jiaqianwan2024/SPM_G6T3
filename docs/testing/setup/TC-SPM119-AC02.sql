-- TC-SPM119-AC02 (SPM-119): The Lead can open any of those events
-- Automated in e2e/spm119.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM119-AC02
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
