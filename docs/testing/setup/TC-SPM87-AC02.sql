-- TC-SPM87-AC02 (SPM-87): Preview venue and equipment at the new period
-- Automated in e2e/spm87.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM87-AC02
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
