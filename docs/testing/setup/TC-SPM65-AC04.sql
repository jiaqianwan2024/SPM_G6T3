-- TC-SPM65-AC04 (SPM-65): Sort by wait and proposed date
-- Automated in e2e/spm65.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM65-AC04
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
