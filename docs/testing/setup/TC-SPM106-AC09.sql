-- TC-SPM106-AC09 (SPM-106): Terminal events cannot raise a CR
-- Automated in e2e/spm106.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM106-AC09
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
