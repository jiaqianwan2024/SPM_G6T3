-- TC-SPM10-AC05 (SPM-10): A rejected request reserves nothing; its active hold is released
-- Automated in e2e/spm10.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM10-AC05
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
