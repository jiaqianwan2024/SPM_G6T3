-- TC-SPM47-AC01 (SPM-47): Overview shows only the organisation's requests, drafts and past records
-- Automated in e2e/spm47-api.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM47-AC01
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
