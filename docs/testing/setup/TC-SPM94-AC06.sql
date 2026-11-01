-- TC-SPM94-AC06 (SPM-94): Own notifications only, server enforced
-- Automated in e2e/spm94.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM94-AC06
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
