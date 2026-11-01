-- TC-SPM77-AC05 (SPM-77): Accept shortfall or amend and resubmit
-- Automated in e2e/spm77.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM77-AC05
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
