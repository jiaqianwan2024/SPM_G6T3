-- TC-SPM83-AC02 (SPM-83): Discard confirmation names the event
-- Automated in e2e/spm83.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM83-AC02
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
