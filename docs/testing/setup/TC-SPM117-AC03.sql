-- TC-SPM117-AC03 (SPM-117): The Lead sees unassigned requests in the review queue with name, organisation, date and time, attendance, and submission time
-- Automated in e2e/spm117.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM117-AC03
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
