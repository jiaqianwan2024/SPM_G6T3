-- TC-SPM77-AC03 (SPM-77): Coordinator notified of shortfall
-- Automated in e2e/spm77.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM77-AC03
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
