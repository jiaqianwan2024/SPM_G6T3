-- TC-SPM79-AC06 (SPM-79): Internal users cannot see a draft
-- Automated in e2e/spm79.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM79-AC06
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
