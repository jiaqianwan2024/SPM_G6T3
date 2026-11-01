-- TC-SPM95-AC06 (SPM-95): Ready, completed, cancelled, rejected produce none
-- Automated in e2e/spm95.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM95-AC06
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
