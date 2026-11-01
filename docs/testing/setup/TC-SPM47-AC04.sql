-- TC-SPM47-AC04 (SPM-47): Own organisation's events still open to organisers; any event to staff
-- Automated in e2e/spm47-api.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM47-AC04
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
