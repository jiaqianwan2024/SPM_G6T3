-- TC-SPM76-AC02 (SPM-76): Only technical support can reserve or mark unavailable
-- Automated in e2e/spm76.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM76-AC02
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
