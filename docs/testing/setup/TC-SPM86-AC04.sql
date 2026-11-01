-- TC-SPM86-AC04 (SPM-86): Booking re-checked, not silently moved
-- Automated in e2e/spm86.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM86-AC04
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
