-- TC-SPM12-AC06 (SPM-12): Attendee confirmation on screen; no notification to the attendee (SPM-93 AC5)
-- Automated in e2e/spm12.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM12-AC06
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
