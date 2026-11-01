-- TC-SPM10-AC07 (SPM-10): A tentative hold expires at its expiry time, frees the venue, is not a confirmed booking
-- Automated in e2e/spm10.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM10-AC07
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
