-- TC-SPM46-AC03 (SPM-46): Reassignment swaps permissions
-- Automated in e2e/spm46-api.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM46-AC03
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
