-- TC-SPM121-AC02 (SPM-121): The safety review starts only once every requested venue is approved and every equipment line is reserved or recorded as not required
-- Automated in e2e/spm121.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM121-AC02
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
