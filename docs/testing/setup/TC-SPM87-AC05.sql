-- TC-SPM87-AC05 (SPM-87): Old period released only after apply
-- Automated in e2e/spm87.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM87-AC05
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
