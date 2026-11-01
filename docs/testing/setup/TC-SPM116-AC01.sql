-- TC-SPM116-AC01 (SPM-116): Venue Staff hold a pending request until a future time no later than the event's start
-- Automated in e2e/spm116.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM116-AC01
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
