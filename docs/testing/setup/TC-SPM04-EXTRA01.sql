-- TC-SPM04-EXTRA01 (SPM-4): only technical support can read the queue
-- Automated in e2e/spm04.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM04-EXTRA01
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
