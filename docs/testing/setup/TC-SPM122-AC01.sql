-- TC-SPM122-AC01 (SPM-122): Every pair of confirmed bookings whose windows overlap under the venue's current times is listed
-- Automated in e2e/spm122.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM122-AC01
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
