-- TC-SPM56-AC04 (SPM-56): Confirmed events show venue, date, time
-- Automated in e2e/spm56.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM56-AC04
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
