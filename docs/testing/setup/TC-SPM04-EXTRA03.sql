-- TC-SPM04-EXTRA03 (SPM-4): an event needing re-verification is flagged on its row
-- Automated in e2e/spm04.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM04-EXTRA03
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
