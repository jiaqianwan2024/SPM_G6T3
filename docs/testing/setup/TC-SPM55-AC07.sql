-- TC-SPM55-AC07 (SPM-55): Empty states say there is nothing to do
-- Automated in e2e/spm55.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM55-AC07
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
