-- TC-SPM72-AC06 (SPM-72): A registration-enabled event is visible to attendees once confirmed and its period opens
-- Automated in e2e/spm72.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM72-AC06
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
