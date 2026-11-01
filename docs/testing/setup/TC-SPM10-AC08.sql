-- TC-SPM10-AC08 (SPM-10): A pending request without a hold stays queued until approved or rejected
-- Automated in e2e/spm10.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM10-AC08
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
