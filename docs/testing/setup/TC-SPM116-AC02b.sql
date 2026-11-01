-- TC-SPM116-AC02b (SPM-116): An active hold reserves the venue until it expires or is released
-- Automated in e2e/spm116.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM116-AC02b
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
