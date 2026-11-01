-- TC-SPM58-AC04 (SPM-58): Upcoming supplied events soonest first
-- Automated in e2e/spm58.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM58-AC04
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
