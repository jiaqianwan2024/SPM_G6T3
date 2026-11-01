-- TC-SPM92-AC07 (SPM-92): Only own registrations; no other attendee identity
-- Automated in e2e/spm92.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM92-AC07
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
