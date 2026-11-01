-- TC-SPM57-AC03 (SPM-57): Confirmed bookings in the next 7 days, with the setup time
-- Automated in e2e/spm57.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM57-AC03
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
