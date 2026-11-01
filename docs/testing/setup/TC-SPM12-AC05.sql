-- TC-SPM12-AC05 (SPM-12): Place released immediately
-- Automated in e2e/spm12.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM12-AC05
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
