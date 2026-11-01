-- TC-SPM93-AC08 (SPM-93): Messages name the event in plain language
-- Automated in e2e/spm93.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM93-AC08
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
