-- TC-SPM121-AC01 (SPM-121): An approved venue booking and reserved equipment confirm the arrangements without moving the event to Confirmed or showing it to attendees
-- Automated in e2e/spm121.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM121-AC01
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
