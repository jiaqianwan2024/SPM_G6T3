-- TC-SPM86-AC10 (SPM-86): All re-verified restores presentation
-- Automated in e2e/spm86.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM86-AC10
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
