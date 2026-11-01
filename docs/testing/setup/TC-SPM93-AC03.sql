-- TC-SPM93-AC03 (SPM-93): Recipients from event relationships, not role alone
-- Automated in e2e/spm93.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM93-AC03
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
