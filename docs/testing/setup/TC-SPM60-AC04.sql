-- TC-SPM60-AC04 (SPM-60): Add, edit, retire without deleting history
-- Automated in e2e/spm60.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM60-AC04
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
