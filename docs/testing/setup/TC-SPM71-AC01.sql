-- TC-SPM71-AC01 (SPM-71): Quiet fields save without warning
-- Automated in e2e/spm71.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM71-AC01
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
