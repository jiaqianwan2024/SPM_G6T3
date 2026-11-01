-- TC-SPM64-AC01 (SPM-64): Shared conflict rule
-- Automated in e2e/spm64.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM64-AC01
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
