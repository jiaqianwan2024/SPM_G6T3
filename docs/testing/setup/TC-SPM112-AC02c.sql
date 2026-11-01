-- TC-SPM112-AC02c (SPM-112): unavailability is judged on the same occupied window
-- Automated in e2e/spm112.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM112-AC02c
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
