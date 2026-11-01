-- TC-SPM60-AC07 (SPM-60): Only venue staff can write
-- Automated in e2e/spm60.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM60-AC07
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
