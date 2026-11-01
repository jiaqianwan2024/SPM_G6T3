-- TC-SPM73-AC06 (SPM-73): Attendees cannot register or withdraw
-- Automated in e2e/spm73.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM73-AC06
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
