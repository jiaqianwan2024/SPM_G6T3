-- TC-SPM72-AC01 (SPM-72): Confirm needs an approved venue booking for the event's date and time, and every equipment line reserved or recorded as not required
-- Automated in e2e/spm72.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM72-AC01
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
