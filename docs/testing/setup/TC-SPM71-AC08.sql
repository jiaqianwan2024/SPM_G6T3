-- TC-SPM71-AC08 (SPM-71): A changed start or end cannot be before today
-- Automated in e2e/spm71.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM71-AC08
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
