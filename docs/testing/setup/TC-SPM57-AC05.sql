-- TC-SPM57-AC05 (SPM-57): Lists obey the same access rules as Booking Requests (Venue Staff only)
-- Automated in e2e/spm57.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM57-AC05
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
