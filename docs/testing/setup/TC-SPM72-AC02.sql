-- TC-SPM72-AC02 (SPM-72): Confirm unavailable while anything is outstanding, and the view names it
-- Automated in e2e/spm72.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM72-AC02
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
