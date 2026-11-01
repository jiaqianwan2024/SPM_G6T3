-- TC-SPM116-AC06 (SPM-116): Rejecting a request releases its hold
-- Automated in e2e/spm116.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM116-AC06
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
