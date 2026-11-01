-- TC-SPM04-AC05 (SPM-4): Status and date filters; terminal events excluded
-- Automated in e2e/spm04.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM04-AC05
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
