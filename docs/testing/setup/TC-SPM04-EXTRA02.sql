-- TC-SPM04-EXTRA02 (SPM-4): the status filter narrows the queue to one equipment state
-- Automated in e2e/spm04.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM04-EXTRA02
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
