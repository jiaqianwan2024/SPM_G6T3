-- TC-SPM05-AC10 (SPM-5): A new or changed due date cannot be before today (SGT)
-- Automated in e2e/spm05.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM05-AC10
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
