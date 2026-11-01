-- TC-SPM122-AC02 (SPM-122): Each clash names the venue, both events and the overlapping times
-- Automated in e2e/spm122.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM122-AC02
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
