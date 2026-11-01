-- TC-SPM119-AC03 (SPM-119): An Event Coordinator does not get the view and manages only their own events
-- Automated in e2e/spm119.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM119-AC03
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
