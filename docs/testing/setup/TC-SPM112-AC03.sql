-- TC-SPM112-AC03 (SPM-112): Windows that only touch do not conflict
-- Automated in e2e/spm112.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM112-AC03
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
