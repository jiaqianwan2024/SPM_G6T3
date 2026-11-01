-- TC-SPM70-AC05 (SPM-70): Rejecting releases holds
-- Automated in e2e/spm70.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM70-AC05
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
