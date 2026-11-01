-- TC-SPM61-AC03 (SPM-61): Confirmed booking, unavailability, or active hold excluded (with setup and turnaround)
-- Automated in e2e/spm61.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM61-AC03
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
